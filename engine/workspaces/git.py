"""Real `git` subprocess operations backing Chapter 7.5's Workspace
interface. No git library dependency: this repository's own `git` binary,
invoked via `subprocess` — AGENTS.md's dependency policy explicitly allows
this ("git via subprocess calls are all fine — no new PyPI packages for
process/container orchestration").
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class GitCommandError(RuntimeError):
    """A real `git` invocation failed. Callers persist this as a `FAILED`
    row (Chapter 19.1's negative-test requirement) rather than letting it
    propagate as an unhandled exception."""

    def __init__(self, args: list[str], returncode: int, stderr: str) -> None:
        super().__init__(
            f"git {' '.join(args)} failed ({returncode}): {stderr.strip()}"
        )
        self.returncode = returncode
        self.stderr = stderr


def _git_executable() -> str:
    git = shutil.which("git")
    if git is None:
        raise GitCommandError(["--version"], -1, "git executable not found on PATH")
    return git


def _run(args: list[str], *, cwd: Path, timeout_seconds: float = 30.0) -> str:
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
    if completed.returncode != 0:
        raise GitCommandError(args, completed.returncode, completed.stderr)
    return completed.stdout.strip()


def rev_parse(repo_root: Path, revision: str) -> str:
    """Resolve `revision` to a full commit SHA. Raises `GitCommandError` for
    an unknown ref — this is the real check behind the "bad workspace ref"
    negative fixture, not a fabricated validation."""
    return _run(["rev-parse", "--verify", f"{revision}^{{commit}}"], cwd=repo_root)


def worktree_add(repo_root: Path, target: Path, revision: str) -> None:
    """Create a real, detached git worktree at `target`, checked out to
    `revision` (Chapter 7.5: "Normally a Git worktree bound to one
    environment and one task"). Chapter 7.5 says worktrees normally branch
    "from the mission integration branch" (Ch.10.2) — that branch does not
    exist yet (Ch.10/DDE-013 is out of this mission's scope), so this
    mission worktrees directly from `revision` against this repository, the
    only real corpus Stage 1 has (`engine.context.repo`)."""
    _run(["worktree", "add", "--detach", str(target), revision], cwd=repo_root)


def worktree_remove(repo_root: Path, target: Path) -> None:
    _run(["worktree", "remove", "--force", str(target)], cwd=repo_root)


def worktree_prune(repo_root: Path) -> None:
    _run(["worktree", "prune"], cwd=repo_root)


def rev_parse_head(worktree_path: Path) -> str:
    return _run(["rev-parse", "HEAD"], cwd=worktree_path)


def status_porcelain(worktree_path: Path) -> str:
    return _run(["status", "--porcelain"], cwd=worktree_path)
