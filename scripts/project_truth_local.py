#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
from collections.abc import Sequence
from typing import cast

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs/project-state/CHANGE_LEDGER.jsonl"
CURRENT = ROOT / "docs/project-state/CURRENT_STATE.json"
EXCLUDES = (
    ":(exclude)docs/project-state/CHANGE_LEDGER.jsonl",
    ":(exclude)docs/project-state/CURRENT_STATE.json",
)
_git = shutil.which("git")
if _git is None:
    raise RuntimeError("git executable is required by the Project Truth local guard")
GIT: str = _git


def git_text(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- arguments are local Git operations only
        [GIT, *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def git_bytes(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(  # noqa: S603 -- arguments are local Git operations only
        [GIT, *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
    )


def output(*args: str) -> str:
    return git_text(*args).stdout.strip()


def parent(commit: str) -> str | None:
    result = git_text("rev-parse", f"{commit}^1", check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def staged_files() -> list[str]:
    result = git_text(
        "diff", "--cached", "--name-only", "--no-renames", "--", ".", *EXCLUDES
    )
    return [line for line in result.stdout.splitlines() if line]


def staged_digest() -> str:
    diff = git_bytes(
        "diff",
        "--cached",
        "--binary",
        "--no-ext-diff",
        "--no-renames",
        "--",
        ".",
        *EXCLUDES,
    ).stdout
    return hashlib.sha256(diff).hexdigest()


def commit_files(commit: str) -> list[str]:
    ancestor = parent(commit)
    args: Sequence[str]
    if ancestor is None:
        args = ("show", "--pretty=", "--name-only", commit, "--", ".", *EXCLUDES)
    else:
        args = (
            "diff",
            "--name-only",
            "--no-renames",
            ancestor,
            commit,
            "--",
            ".",
            *EXCLUDES,
        )
    return [line for line in git_text(*args).stdout.splitlines() if line]


def commit_digest(commit: str) -> str:
    ancestor = parent(commit)
    args: Sequence[str]
    if ancestor is None:
        args = (
            "show",
            "--binary",
            "--format=",
            "--no-ext-diff",
            commit,
            "--",
            ".",
            *EXCLUDES,
        )
    else:
        args = (
            "diff",
            "--binary",
            "--no-ext-diff",
            "--no-renames",
            ancestor,
            commit,
            "--",
            ".",
            *EXCLUDES,
        )
    return hashlib.sha256(git_bytes(*args).stdout).hexdigest()


def parse_rows(text: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in text.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(cast(dict[str, object], value))
    return rows


def current_rows() -> list[dict[str, object]]:
    return parse_rows(LEDGER.read_text()) if LEDGER.exists() else []


def commit_parents(commit: str) -> list[str]:
    fields = output("rev-list", "--parents", "-n", "1", commit).split()
    return fields[1:]


def commit_tree(commit: str) -> str:
    return output("show", "-s", "--format=%T", commit)


def is_project_state_only(files: list[str]) -> bool:
    return bool(files) and all(path.startswith("docs/project-state/") for path in files)


def is_pure_merge_carrier(commit: str) -> bool:
    parents = commit_parents(commit)
    if len(parents) < 2:
        return False
    tree = commit_tree(commit)
    return any(commit_tree(parent_sha) == tree for parent_sha in parents)


def recorded_in_current_ledger(
    *,
    rows: list[dict[str, object]],
    commit: str,
    source_parent: str | None,
    digest: str,
    files: list[str],
) -> bool:
    for row in rows:
        if row.get("commit_sha") == commit and row.get("diff_sha256") == digest:
            return True
        if (
            row.get("source_parent") == source_parent
            and row.get("diff_sha256") == digest
            and sorted(cast(list[str], row.get("changed_files", []))) == sorted(files)
        ):
            return True
    return False


def record() -> int:
    files = staged_files()
    if not files:
        return 0
    digest = staged_digest()
    source_parent = output("rev-parse", "HEAD")
    rows = parse_rows(LEDGER.read_text()) if LEDGER.exists() else []
    is_duplicate = bool(
        rows
        and rows[-1].get("source_parent") == source_parent
        and rows[-1].get("diff_sha256") == digest
    )
    if not is_duplicate:
        entry: dict[str, object] = {
            "schema_version": 1,
            "kind": "precommit-staged-diff",
            "recorded_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "branch": output("rev-parse", "--abbrev-ref", "HEAD"),
            "source_parent": source_parent,
            "changed_files": files,
            "diff_sha256": digest,
            "actor": os.getenv("USER") or os.getenv("USERNAME") or "unknown",
        }
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a") as handle:
            handle.write(
                json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n"
            )
        CURRENT.write_text(
            json.dumps(
                {"schema_version": 1, "state": "PENDING_COMMIT", **entry},
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    git_text(
        "add",
        "docs/project-state/CHANGE_LEDGER.jsonl",
        "docs/project-state/CURRENT_STATE.json",
    )
    return 0


def install_commit() -> str | None:
    result = git_text(
        "log",
        "--reverse",
        "--format=%H",
        "--diff-filter=A",
        "--",
        "scripts/project_truth_local.py",
        check=False,
    )
    commits = [line for line in result.stdout.splitlines() if line]
    return commits[0] if commits else None


def verify() -> int:
    baseline = install_commit()
    if baseline is None:
        print("BLOCKED: Project Truth local guard baseline missing", file=sys.stderr)
        return 40
    rows = current_rows()
    bad: list[str] = []
    commits = [
        line
        for line in output("rev-list", "--reverse", f"{baseline}..HEAD").splitlines()
        if line
    ]
    for commit in commits:
        files = commit_files(commit)
        if not files or is_project_state_only(files) or is_pure_merge_carrier(commit):
            continue
        source_parent = parent(commit)
        digest = commit_digest(commit)
        if not recorded_in_current_ledger(
            rows=rows,
            commit=commit,
            source_parent=source_parent,
            digest=digest,
            files=files,
        ):
            bad.append(commit)
    if bad:
        print(
            "BLOCKED: unlogged post-guard commits: " + ", ".join(bad),
            file=sys.stderr,
        )
        return 41
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["record", "verify"])
    args = parser.parse_args()
    return record() if args.cmd == "record" else verify()


if __name__ == "__main__":
    raise SystemExit(main())
