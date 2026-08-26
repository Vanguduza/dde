"""Real `git` subprocess operations backing Chapter 10's merge queue --
branch/ref plumbing, real rebase-based textual-conflict detection, and
fast-forward advancement.

No git library dependency: this repository's own `git` binary, invoked via
`subprocess`, exactly matching `engine.workspaces.git`'s established
convention (AGENTS.md: "git via subprocess calls are all fine"). Kept as a
separate module rather than importing `engine.workspaces.git` because that
module's own docstring scopes it to the detached-worktree operations Chapter
7.5 needs; branch/ref/rebase plumbing is Chapter 10's concern and belongs to
its own owning module.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

_COMMIT_AUTHOR_NAME = "DDE Integration Manager"
_COMMIT_AUTHOR_EMAIL = "integration@dde.local"


class GitCommandError(RuntimeError):
    """A real `git` invocation failed. Callers persist this as a real
    `CONFLICT`/`REJECTED` row (Chapter 19.1's negative-test requirement)
    rather than letting it propagate as an unhandled exception."""

    def __init__(self, args: list[str], returncode: int, stderr: str) -> None:
        super().__init__(
            f"git {' '.join(args)} failed ({returncode}): {stderr.strip()}"
        )
        self.returncode = returncode
        self.stderr = stderr


@dataclass(frozen=True)
class RebaseResult:
    """Chapter 10.4 step 2's real outcome: either a clean rebase onto the
    mission head (`ok=True`, `revision` is the new, real commit) or a real
    textual conflict (`ok=False`) -- the rebase is aborted immediately in
    the latter case so the worktree is left clean, never mid-conflict."""

    ok: bool
    revision: str | None
    stderr: str


def _git_executable() -> str:
    git = shutil.which("git")
    if git is None:
        raise GitCommandError(["--version"], -1, "git executable not found on PATH")
    return git


def _run(
    args: list[str], *, cwd: Path, timeout_seconds: float = 30.0, check: bool = True
) -> subprocess.CompletedProcess[str]:
    git = _git_executable()
    try:
        completed = subprocess.run(  # noqa: S603
            [git, *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitCommandError(args, -1, f"timed out after {timeout_seconds}s") from exc
    if check and completed.returncode != 0:
        raise GitCommandError(args, completed.returncode, completed.stderr)
    return completed


def rev_parse(repo_root: Path, revision: str) -> str:
    return _run(
        ["rev-parse", "--verify", f"{revision}^{{commit}}"], cwd=repo_root
    ).stdout.strip()


def branch_exists(repo_root: Path, branch: str) -> bool:
    result = _run(
        ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=repo_root,
        check=False,
    )
    return result.returncode == 0


def create_branch(repo_root: Path, branch: str, revision: str) -> None:
    _run(["branch", branch, revision], cwd=repo_root)


def update_ref(repo_root: Path, ref_name: str, revision: str) -> None:
    """Move `refs/heads/<ref_name>` to `revision` without a checkout --
    Chapter 10.4 step 6's fast-forward, and the same mechanism used to
    stand up the ephemeral integration candidate ref in step 4."""
    _run(["update-ref", f"refs/heads/{ref_name}", revision], cwd=repo_root)


def delete_branch(repo_root: Path, branch: str) -> None:
    """Best-effort, idempotent cleanup -- a branch that was never created
    or was already removed is not an error."""
    _run(["branch", "-D", branch], cwd=repo_root, check=False)


def status_porcelain(worktree_path: Path) -> str:
    return _run(["status", "--porcelain"], cwd=worktree_path).stdout


def commit_all(worktree_path: Path, message: str) -> str:
    """Chapter 10.1's "Integration is a DDE operation": turns a workspace's
    real, still-uncommitted diff (Chapter 8's scripted worker writes files
    but never commits -- see `engine.workers.scripted_adapter`) into a real
    commit, authored by the integration manager, never the worker. A
    worktree with nothing to commit is not an error: it returns its
    current, unchanged `HEAD`."""
    if not status_porcelain(worktree_path).strip():
        return rev_parse(worktree_path, "HEAD")
    _run(["add", "-A"], cwd=worktree_path)
    _run(
        [
            "-c",
            f"user.name={_COMMIT_AUTHOR_NAME}",
            "-c",
            f"user.email={_COMMIT_AUTHOR_EMAIL}",
            "commit",
            "-m",
            message,
        ],
        cwd=worktree_path,
    )
    return rev_parse(worktree_path, "HEAD")


def rebase_onto(worktree_path: Path, onto_revision: str) -> RebaseResult:
    """Rebase the worktree's current (detached) `HEAD` onto
    `onto_revision` -- Chapter 10.4 step 2's real textual-conflict
    detection. Runs directly against the detached worktree `git worktree
    add --detach` already left checked out (`engine.workspaces.service`);
    no separate checkout of a named branch is needed or attempted here."""
    result = _run(["rebase", onto_revision], cwd=worktree_path, check=False)
    if result.returncode == 0:
        return RebaseResult(
            ok=True, revision=rev_parse(worktree_path, "HEAD"), stderr=""
        )
    _run(["rebase", "--abort"], cwd=worktree_path, check=False)
    return RebaseResult(ok=False, revision=None, stderr=result.stderr)


def diff_name_only(
    repo_root: Path, base_revision: str, target_revision: str
) -> list[str]:
    result = _run(
        ["diff", "--name-only", base_revision, target_revision], cwd=repo_root
    )
    return [line for line in result.stdout.splitlines() if line]


def diff_name_only_filter(
    repo_root: Path, base_revision: str, target_revision: str, diff_filter: str
) -> list[str]:
    """`git diff --diff-filter` -- used to distinguish newly added paths
    (licence-header gate) from modified ones."""
    result = _run(
        [
            "diff",
            "--name-only",
            f"--diff-filter={diff_filter}",
            base_revision,
            target_revision,
        ],
        cwd=repo_root,
    )
    return [line for line in result.stdout.splitlines() if line]


def diff_unified(repo_root: Path, base_revision: str, target_revision: str) -> str:
    """Unified diff of the real commits Chapter 10.4 step 3 evaluates.

    `--text` forces a line-oriented diff so secret/SAST scanners never miss
    an added payload because git classified the blob as binary (empty
    ``Binary files differ`` hunk with no ``+`` lines).
    """
    return _run(
        ["diff", "--text", base_revision, target_revision], cwd=repo_root
    ).stdout


def show_blob(repo_root: Path, revision: str, path: str) -> str | None:
    """File content at `revision:path`, or `None` if that path does not
    exist at that revision (deleted, or never present)."""
    result = _run(["show", f"{revision}:{path}"], cwd=repo_root, check=False)
    if result.returncode != 0:
        return None
    return result.stdout


def ls_tree_names(repo_root: Path, revision: str) -> list[str]:
    result = _run(["ls-tree", "-r", "--name-only", revision], cwd=repo_root)
    return [line for line in result.stdout.splitlines() if line]
