#!/usr/bin/env python3
"""Repository branch, changelog, and fixed-bug governance for DDE.

Project Truth remains authoritative. This module governs how temporary Git
branches are allowed to carry candidate work into the sole integration branch,
`main`, and makes changelog/bug-fix history mechanically reviewable.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from collections.abc import Iterable
from typing import Any, cast

ROOT = pathlib.Path(__file__).resolve().parents[1]
CANONICAL_STATE = ROOT / "PROJECT_CANONICAL_STATE.json"
CHANGELOG = ROOT / "CHANGELOG.md"
BUG_LEDGER = ROOT / "docs/project-state/BUG_FIX_LEDGER.jsonl"
BUG_VIEW = ROOT / "docs/project-state/BUG_FIX_LEDGER.md"
BRANCH_POLICY = ROOT / "BRANCH_MANAGEMENT.md"
DEFAULT_BRANCH = "main"
ALLOWED_SIDE_PREFIXES = (
    "feat/",
    "fix/",
    "work/",
    "docs/",
    "ci/",
    "test/",
    "chore/",
    "refactor/",
    "security/",
    "hotfix/",
)
FORBIDDEN_AUTHORITY_TERMS = ("canonical", "source-of-truth", "mainline")
MATERIAL_ROOTS = (
    "engine/",
    "adapters/",
    "interfaces/",
    "schemas/",
    "migrations/",
    "infra/",
    "packaging/",
)
CHANGELOG_SUBJECT = re.compile(
    r"^(?:feat|fix|hotfix|perf|refactor|security|revert)(?:\([^)]*\))?!?:",
    re.IGNORECASE,
)
FIX_SUBJECT = re.compile(r"^(?:fix|hotfix)(?:\([^)]*\))?!?:", re.IGNORECASE)
BUG_ID = re.compile(r"^DDE-BUG-(\d{4})$")
_git = shutil.which("git")
if _git is None:
    raise RuntimeError("git executable is required by repository governance")
GIT: str = _git


def git_text(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- local Git argv only
        [GIT, *args], cwd=ROOT, check=check, capture_output=True, text=True
    )


def output(*args: str) -> str:
    return git_text(*args).stdout.strip()


def fail(errors: Iterable[str]) -> int:
    rows = list(errors)
    if not rows:
        return 0
    for row in rows:
        print(f"BLOCKED: {row}", file=sys.stderr)
    return 50


def validate_branch_name(name: str) -> list[str]:
    if name == DEFAULT_BRANCH:
        return []
    errors: list[str] = []
    if not any(name.startswith(prefix) for prefix in ALLOWED_SIDE_PREFIXES):
        errors.append(
            f"side branch {name!r} must use an approved temporary prefix: "
            + ", ".join(ALLOWED_SIDE_PREFIXES)
        )
    lowered = name.lower()
    for term in FORBIDDEN_AUTHORITY_TERMS:
        if term in lowered:
            errors.append(
                f"side branch {name!r} may not imply authority with term {term!r}"
            )
    if name.endswith("/") or ".." in name or "//" in name:
        errors.append(f"side branch {name!r} has an invalid lifecycle name")
    return errors


def parse_bug_entries(text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"bug ledger line {line_no} is invalid JSON: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise ValueError(f"bug ledger line {line_no} must be a JSON object")
        entries.append(cast(dict[str, Any], value))
    return entries


def validate_bug_entries(entries: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version",
        "bug_id",
        "status",
        "fixed_at_utc",
        "severity",
        "title",
        "symptom",
        "root_cause",
        "resolution",
        "affected_scope",
        "regression_tests",
        "evidence_refs",
        "fixed_by_commit",
        "fix_subject",
    }
    seen: set[str] = set()
    numbers: list[int] = []
    for index, entry in enumerate(entries, start=1):
        missing = sorted(required - entry.keys())
        if missing:
            errors.append(
                f"bug ledger entry {index} missing fields: {', '.join(missing)}"
            )
        bug_id = str(entry.get("bug_id", ""))
        match = BUG_ID.fullmatch(bug_id)
        if match is None:
            errors.append(f"bug ledger entry {index} has invalid bug_id {bug_id!r}")
        else:
            numbers.append(int(match.group(1)))
        if bug_id in seen:
            errors.append(f"bug ledger has duplicate bug_id {bug_id}")
        seen.add(bug_id)
        if entry.get("schema_version") != 1:
            errors.append(f"{bug_id or index}: schema_version must be 1")
        if entry.get("status") != "FIXED":
            errors.append(f"{bug_id or index}: status must be FIXED")
        if entry.get("severity") not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            errors.append(f"{bug_id or index}: invalid severity")
        for field in ("affected_scope", "regression_tests", "evidence_refs"):
            value = entry.get(field)
            if not isinstance(value, list) or not value:
                errors.append(f"{bug_id or index}: {field} must be a non-empty list")
        for field in ("title", "symptom", "root_cause", "resolution", "fix_subject"):
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{bug_id or index}: {field} must be non-empty text")
    if numbers and numbers != list(range(1, len(numbers) + 1)):
        errors.append("bug IDs must be contiguous and append-only from DDE-BUG-0001")
    return errors


def render_bug_ledger(entries: list[dict[str, Any]]) -> str:
    lines = [
        "# DDE Fixed-Bug Ledger",
        "",
        "> Generated from `BUG_FIX_LEDGER.jsonl`. Do not edit this file directly.",
        "> The JSONL ledger is append-only; corrections are new entries, "
        "never history rewrites.",
        "",
        "| Bug | Fixed | Severity | Summary | Fix commit |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in entries:
        title = str(entry["title"]).replace("|", "\\|")
        lines.append(
            f"| `{entry['bug_id']}` | {str(entry['fixed_at_utc'])[:10]} | "
            f"{entry['severity']} | {title} | `{entry['fixed_by_commit']}` |"
        )
    for entry in entries:
        lines.extend(
            [
                "",
                f"## {entry['bug_id']} — {entry['title']}",
                "",
                f"**Symptom:** {entry['symptom']}",
                "",
                f"**Root cause:** {entry['root_cause']}",
                "",
                f"**Resolution:** {entry['resolution']}",
                "",
                "**Affected scope:** "
                + ", ".join(f"`{x}`" for x in entry["affected_scope"]),
                "",
                "**Regression proof:** "
                + ", ".join(f"`{x}`" for x in entry["regression_tests"]),
                "",
                "**Evidence:** " + ", ".join(f"`{x}`" for x in entry["evidence_refs"]),
                "",
                f"**Fix:** `{entry['fixed_by_commit']}` — {entry['fix_subject']}",
            ]
        )
    return "\n".join(lines) + "\n"


def read_git_file(revision: str, path: pathlib.Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    result = git_text("show", f"{revision}:{rel}", check=False)
    return result.stdout if result.returncode == 0 else ""


def commit_subjects(base: str, head: str) -> list[tuple[str, str]]:
    raw = output("log", "--format=%H%x00%s", f"{base}..{head}")
    rows: list[tuple[str, str]] = []
    for line in raw.splitlines():
        if "\x00" not in line:
            continue
        sha, subject = line.split("\x00", 1)
        rows.append((sha, subject))
    return rows


def changed_files(base: str, head: str) -> list[str]:
    return [
        row
        for row in output(
            "diff", "--name-only", "--no-renames", base, head
        ).splitlines()
        if row
    ]


def material_change(files: Iterable[str], subjects: Iterable[str]) -> bool:
    file_list = list(files)
    if any(path.startswith(MATERIAL_ROOTS) for path in file_list):
        return True
    return any(CHANGELOG_SUBJECT.match(subject) for subject in subjects)


def verify_bug_append_only(base: str, head: str) -> list[str]:
    old = read_git_file(base, BUG_LEDGER)
    new = read_git_file(head, BUG_LEDGER)
    if old and not new.startswith(old):
        return [
            "BUG_FIX_LEDGER.jsonl is append-only; existing entries were changed "
            "or removed"
        ]
    return []


def validate_static(*, revision: str | None = None) -> list[str]:
    errors: list[str] = []
    if revision is None:
        state_text = CANONICAL_STATE.read_text() if CANONICAL_STATE.exists() else ""
        bug_text = BUG_LEDGER.read_text() if BUG_LEDGER.exists() else ""
        view_text = BUG_VIEW.read_text() if BUG_VIEW.exists() else ""
        changelog_exists = CHANGELOG.exists()
        branch_policy_exists = BRANCH_POLICY.exists()
    else:
        state_text = read_git_file(revision, CANONICAL_STATE)
        bug_text = read_git_file(revision, BUG_LEDGER)
        view_text = read_git_file(revision, BUG_VIEW)
        changelog_exists = bool(read_git_file(revision, CHANGELOG))
        branch_policy_exists = bool(read_git_file(revision, BRANCH_POLICY))
    try:
        state = json.loads(state_text)
    except json.JSONDecodeError:
        return ["PROJECT_CANONICAL_STATE.json is missing or invalid"]
    policy = state.get("policy", {})
    required_policy = {
        "only_main_is_persistent_branch": True,
        "side_branches_are_non_authoritative": True,
        "side_branches_must_target_main": True,
        "merged_side_branches_auto_delete": True,
        "material_changes_require_changelog": True,
        "bug_fixes_require_bug_ledger": True,
    }
    for key, expected in required_policy.items():
        if policy.get(key) is not expected:
            errors.append(f"canonical-state policy {key} must be {expected}")
    canonical = state.get("canonical_state", {})
    if canonical.get("canonical_integration_branch") != DEFAULT_BRANCH:
        errors.append("canonical integration branch must remain main")
    if not changelog_exists:
        errors.append("CHANGELOG.md is required")
    if not branch_policy_exists:
        errors.append("BRANCH_MANAGEMENT.md is required")
    try:
        entries = parse_bug_entries(bug_text)
    except ValueError as exc:
        errors.append(str(exc))
        entries = []
    errors.extend(validate_bug_entries(entries))
    if entries and view_text != render_bug_ledger(entries):
        errors.append("BUG_FIX_LEDGER.md drifted from append-only JSONL source")
    return errors


def verify_range(base: str, head: str) -> list[str]:
    errors = validate_static(revision=head)
    files = changed_files(base, head)
    commits = commit_subjects(base, head)
    subjects = [subject for _sha, subject in commits]
    if material_change(files, subjects) and "CHANGELOG.md" not in files:
        errors.append(
            "material change must update CHANGELOG.md in the same PR/change range"
        )
    fix_commits = [
        (sha, subject) for sha, subject in commits if FIX_SUBJECT.match(subject)
    ]
    if fix_commits and "docs/project-state/BUG_FIX_LEDGER.jsonl" not in files:
        errors.append("fix/hotfix change must append BUG_FIX_LEDGER.jsonl")
    if "docs/project-state/BUG_FIX_LEDGER.jsonl" in files:
        errors.extend(verify_bug_append_only(base, head))
        old = read_git_file(base, BUG_LEDGER)
        new = read_git_file(head, BUG_LEDGER)
        added_text = new[len(old) :] if new.startswith(old) else ""
        try:
            added_entries = parse_bug_entries(added_text)
        except ValueError as exc:
            errors.append(str(exc))
            added_entries = []
        if fix_commits and not added_entries:
            errors.append("fix/hotfix change must append at least one fixed-bug entry")
    return errors


def staged_files() -> list[str]:
    return [
        row
        for row in output(
            "diff", "--cached", "--name-only", "--no-renames"
        ).splitlines()
        if row
    ]


def verify_staged(message: str) -> list[str]:
    errors = validate_static()
    files = staged_files()
    if material_change(files, [message]) and "CHANGELOG.md" not in files:
        errors.append("material staged change requires CHANGELOG.md")
    if (
        FIX_SUBJECT.match(message)
        and "docs/project-state/BUG_FIX_LEDGER.jsonl" not in files
    ):
        errors.append(
            "fix/hotfix commit requires an appended BUG_FIX_LEDGER.jsonl entry"
        )
    if "docs/project-state/BUG_FIX_LEDGER.jsonl" in files:
        old = read_git_file("HEAD", BUG_LEDGER)
        new = BUG_LEDGER.read_text()
        if old and not new.startswith(old):
            errors.append("BUG_FIX_LEDGER.jsonl is append-only")
    branch = output("rev-parse", "--abbrev-ref", "HEAD")
    if branch == DEFAULT_BRANCH:
        errors.append(
            "direct substantive commits on main are forbidden; use a temporary "
            "branch + PR"
        )
    else:
        errors.extend(validate_branch_name(branch))
    return errors


def event_range() -> tuple[str, str] | None:
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path or not pathlib.Path(event_path).exists():
        return None
    event = json.loads(pathlib.Path(event_path).read_text())
    if os.getenv("GITHUB_EVENT_NAME") == "pull_request":
        return str(event["pull_request"]["base"]["sha"]), str(
            event["pull_request"]["head"]["sha"]
        )
    if os.getenv("GITHUB_EVENT_NAME") == "push":
        before = str(event.get("before", ""))
        after = str(event.get("after", ""))
        if before and before != "0" * 40:
            return before, after
        merge_base = output("merge-base", f"origin/{DEFAULT_BRANCH}", after)
        return merge_base, after
    return None


def verify_event() -> int:
    errors: list[str] = []
    event_name = os.getenv("GITHUB_EVENT_NAME", "")
    ref_name = (
        os.getenv("GITHUB_HEAD_REF") or os.getenv("GITHUB_REF_NAME") or DEFAULT_BRANCH
    )
    ref_type = os.getenv("GITHUB_REF_TYPE", "branch")
    if event_name == "pull_request":
        base_ref = os.getenv("GITHUB_BASE_REF", "")
        if base_ref != DEFAULT_BRANCH:
            errors.append(
                f"all side-work PRs must target {DEFAULT_BRANCH}, not {base_ref!r}"
            )
        errors.extend(validate_branch_name(ref_name))
    elif ref_type != "tag" and ref_name != DEFAULT_BRANCH:
        errors.extend(validate_branch_name(ref_name))
    range_pair = event_range()
    if range_pair is None:
        errors.extend(validate_static())
    else:
        errors.extend(verify_range(*range_pair))
    return fail(errors)


def github_json(url: str, token: str) -> Any:
    if not url.startswith("https://api.github.com/"):
        raise ValueError("repository governance only permits the GitHub HTTPS API")
    request = urllib.request.Request(  # noqa: S310 -- URL is pinned above
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "dde-repository-governance",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 -- fixed GitHub API origin
        return json.load(response)


def audit_remote() -> int:
    repository = os.getenv("GITHUB_REPOSITORY", "Vanguduza/dde")
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        return fail(["GITHUB_TOKEN is required for remote branch audit"])
    quoted = urllib.parse.quote(repository, safe="/")
    branches = github_json(
        f"https://api.github.com/repos/{quoted}/branches?per_page=100", token
    )
    pulls = github_json(
        f"https://api.github.com/repos/{quoted}/pulls?state=open&base={DEFAULT_BRANCH}&per_page=100",
        token,
    )
    open_heads = {
        str(pr["head"]["ref"])
        for pr in pulls
        if pr.get("head", {}).get("repo", {}).get("full_name") == repository
    }
    errors: list[str] = []
    active: list[str] = []
    for row in branches:
        name = str(row["name"])
        if name == DEFAULT_BRANCH:
            continue
        errors.extend(validate_branch_name(name))
        if name not in open_heads:
            errors.append(
                f"orphan side branch {name!r} has no open PR to main; reconcile "
                "then merge/delete it"
            )
        else:
            active.append(name)
    for pr in pulls:
        head_repo = pr.get("head", {}).get("repo", {}).get("full_name")
        if head_repo == repository:
            errors.extend(validate_branch_name(str(pr["head"]["ref"])))
    if not errors:
        print(
            f"Repository branch audit green: main + {len(active)} active PR branch(es)"
        )
        for name in sorted(active):
            print(f"ACTIVE_NON_AUTHORITATIVE: {name}")
    return fail(errors)


def render_command(check: bool) -> int:
    try:
        entries = parse_bug_entries(BUG_LEDGER.read_text())
    except (OSError, ValueError) as exc:
        return fail([str(exc)])
    errors = validate_bug_entries(entries)
    if errors:
        return fail(errors)
    rendered = render_bug_ledger(entries)
    if check:
        current = BUG_VIEW.read_text() if BUG_VIEW.exists() else ""
        return fail([] if current == rendered else ["BUG_FIX_LEDGER.md is out of date"])
    BUG_VIEW.write_text(rendered)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify-event")
    sub.add_parser("verify-static")
    sub.add_parser("audit-remote")
    staged = sub.add_parser("verify-staged")
    staged.add_argument("--message", required=True)
    render = sub.add_parser("render-bug-ledger")
    render.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.cmd == "verify-event":
        return verify_event()
    if args.cmd == "verify-static":
        return fail(validate_static())
    if args.cmd == "audit-remote":
        return audit_remote()
    if args.cmd == "verify-staged":
        return fail(verify_staged(args.message))
    return render_command(args.check)


if __name__ == "__main__":
    raise SystemExit(main())
