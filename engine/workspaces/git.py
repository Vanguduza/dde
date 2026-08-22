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


def diff_name_only(worktree_path: Path, base_revision: str) -> list[str]:
    """Every path that differs between `base_revision` and the worktree's
    current state -- committed *and* uncommitted (no second ref: `git
    diff --name-only <base>` diffs against the working tree directly).
    Chapter 5.11's "did it edit outside the supplied scope?" deterministic
    rule (`engine.attribution.rules`) needs the real set of touched paths,
    not merely the last commit's."""
    output = _run(["diff", "--name-only", base_revision], cwd=worktree_path)
    return [line for line in output.splitlines() if line.strip()]


#: Every ref namespace scrubbed from a verification workspace. `refs/HEAD`
#: and per-worktree namespaces (`refs/bisect`, `refs/worktree`,
#: `refs/stash`) are excluded by the `for-each-refs` pattern set below;
#: other-worktree branches under `refs/worktree/**` are DDE's own
#: bookkeeping for concurrent workspaces and must never be touched.
SCRUBBED_REF_PATTERNS = (
    "refs/heads/",
    "refs/tags/",
    "refs/remotes/",
)

GC_TIMEOUT_SECONDS = 120.0


def _common_git_dir(worktree_path: Path) -> Path:
    """The shared `.git` directory backing `worktree_path` (the worktree
    itself carries only a `.git` *file* pointing at it)."""
    output = _run(
        ["rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=worktree_path,
    )
    return Path(output)


def list_refs(git_dir: Path, patterns: tuple[str, ...] | None = None) -> dict[str, str]:
    """Every loose and packed ref in `git_dir` matching `patterns`
    (`--all`'s full surface when `None`), as `{refname: commit_sha}`.
    Reads the real `refs/` tree plus `packed-refs`; no `git` call needed."""
    resolved: dict[str, str] = {}

    def _resolve(name: str) -> str | None:
        direct = git_dir / name
        try:
            value = direct.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if value.startswith("ref:"):
            return _resolve(value.split(":", 1)[1].strip())
        return value or None

    refs_dir = git_dir / "refs"
    if refs_dir.is_dir():
        for path in sorted(refs_dir.rglob("*")):
            if not path.is_file():
                continue
            name = path.relative_to(git_dir).as_posix()
            sha = _resolve(name)
            if sha is not None:
                resolved[name] = sha
    packed = git_dir / "packed-refs"
    try:
        lines = packed.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("^"):
            continue
        sha, _, name = stripped.partition(" ")
        if sha and name:
            resolved.setdefault(name.strip(), sha)
    if patterns is None:
        return resolved
    return {
        name: sha
        for name, sha in resolved.items()
        if any(name.startswith(pattern) for pattern in patterns)
    }


def delete_ref(git_dir: Path, refname: str) -> None:
    """Delete one ref through real git (`update-ref -d`), so packed and
    loose copies both go and the deletion itself is journaled where a
    reflog exists."""
    _run(["update-ref", "-d", refname], cwd=git_dir)


def expire_reflogs(worktree_path: Path) -> None:
    """Expire every reflog entry now, including unreachable ones."""
    _run(
        ["reflog", "expire", "--expire=now", "--expire-unreachable=now", "--all"],
        cwd=worktree_path,
    )


def gc_prune_now(worktree_path: Path) -> None:
    """Drop every object unreachable from any remaining ref immediately
    (`gc --prune=now`). The aggressive variant was measured as unnecessary
    here: correctness comes from reachability, not repacking quality, and
    aggressive costs minutes instead of seconds on large repos."""
    _run(["gc", "--prune=now"], cwd=worktree_path, timeout_seconds=GC_TIMEOUT_SECONDS)


def scrub_future_state(worktree_path: Path, keep_revision: str) -> list[str]:
    """Strip every name a generator or verifier could resolve to
    solution-bearing history, leaving only `keep_revision` itself.

    Three real mutations, in dependency order:

    1. ``reflog expire`` -- after this, no entry reachable only through
       "where was I recently" survives, including the detached-HEAD log of
       this worktree.
    2. Ref deletion -- every branch/tag/remote-tracking ref resolving away
       from `keep_revision` is deleted through real `git update-ref -d`.
       Refs pointing at the kept commit survive by construction; nothing
       outside `refs/heads|tags|remotes` is touched (other workspaces'
       bookkeeping lives elsewhere).
    3. ``gc --prune=now`` -- drops every now-unreachable object from the
       object store, so solution-bearing history is genuinely gone rather
       than merely unreferenced.

    Returns the sorted names of the refs actually deleted, for callers
    that journal or assert on the scrub. The caller runs this against the
    *worktree* directory; git resolves the shared repository through the
    worktree's `.git` file, so all three commands act on the one real
    object store.
    """
    head_sha = rev_parse_head(worktree_path)
    keep = (
        keep_revision
        if len(keep_revision) == 40
        else rev_parse(worktree_path, keep_revision)
    )
    if keep != head_sha:
        raise GitCommandError(
            ["scrub-future-state"], -1, "keep_revision is not the checked-out HEAD"
        )
    expire_reflogs(worktree_path)
    git_dir = _common_git_dir(worktree_path)
    deleted: list[str] = []
    for refname, sha in sorted(list_refs(git_dir, SCRUBBED_REF_PATTERNS).items()):
        if sha == keep:
            continue
        delete_ref(git_dir, refname)
        deleted.append(refname)
    gc_prune_now(worktree_path)
    return deleted
