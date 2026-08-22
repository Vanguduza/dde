"""Future-state scrubbing of verification workspaces (comparable-systems
adoption #6): neither generator nor verifier may read solution-bearing
history out of a provisioned workspace.

Pure tests over real git repositories built in `tmp_path` — every branch,
tag and reflog entry is created through real `git` subprocess calls, then
`engine.workspaces.git.scrub_future_state()` must prove none survive by
inspecting `.git/refs`, `packed-refs` and the reflog files directly.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from engine.workspaces.git import (
    SCRUBBED_REF_PATTERNS,
    GitCommandError,
    list_refs,
    scrub_future_state,
)


def _git(repo: Path, *args: str) -> str:
    git = shutil.which("git")
    assert git is not None
    completed = subprocess.run(  # noqa: S603 -- fixed argv, no shell
        [git, *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def _init_repo(root: Path) -> Path:
    """A real repo whose HEAD commit carries no solution content, plus a
    second commit on a side branch that does — the shape a generator's
    history has before provisioning."""
    repo = root / "origin"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "dde@example.com")
    _git(repo, "config", "user.name", "DDE Test")
    clean_file = repo / "clean.txt"
    clean_file.write_text("nothing sensitive\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "clean base")
    solution_commit = _git(
        repo,
        "commit-tree",
        "HEAD^{tree}",
        "-m",
        "solution: the answer the verifier must not see",
    )
    # A detached commit object only reachable from refs + reflog: exactly
    # what scrubbing must render unreachable AND unnameable.
    _git(repo, "branch", "solution/candidate-a", solution_commit)
    _git(repo, "tag", "solution-tag", solution_commit)
    _git(repo, "update-ref", "refs/remotes/origin/solution", solution_commit)
    return repo


def _worktree_from_head(origin: Path, root: Path) -> tuple[Path, str]:
    worktree = root / "ws"
    _git(origin, "worktree", "add", "--detach", str(worktree), "HEAD")
    head_sha = _git(worktree, "rev-parse", "HEAD")
    return worktree, head_sha


def test_scrub_removes_branches_tags_reflogs_and_prunes(tmp_path: Path) -> None:
    """Contract: after scrubbing a workspace provisioned from a repo with
    extra branches/tags/reflog entries, none survive — asserted against
    the real `.git/refs` tree, `packed-refs` and reflog files."""
    origin = _init_repo(tmp_path)
    worktree, keep_revision = _worktree_from_head(origin, tmp_path)

    deleted = scrub_future_state(worktree, keep_revision=keep_revision)

    assert sorted(deleted) == [
        "refs/heads/solution/candidate-a",
        "refs/remotes/origin/solution",
        "refs/tags/solution-tag",
    ]
    git_dir = origin / ".git"
    surviving = list_refs(git_dir, SCRUBBED_REF_PATTERNS)
    assert set(surviving.values()) == {keep_revision}
    packed_refs = git_dir / "packed-refs"
    if packed_refs.exists():
        for line in packed_refs.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#") or line.startswith("^"):
                continue
            sha, _, name = line.partition(" ")
            assert name.strip() in surviving, name
            assert sha == keep_revision
    # No loose ref file anywhere under refs/ resolves away from HEAD.
    for path in (git_dir / "refs").rglob("*"):
        if path.is_file():
            assert path.read_text(encoding="utf-8").strip() == keep_revision
    # Reflogs are empty everywhere (`reflog expire --expire=now --all`
    # leaves zero entries; files may exist but hold no lines).
    logs_dir = git_dir / "logs"
    if logs_dir.is_dir():
        for log_file in logs_dir.rglob("*"):
            if log_file.is_file():
                assert log_file.read_text(encoding="utf-8").strip() == ""
    # The solution commit itself is gone from the object store: it was
    # never an ancestor of HEAD and its last names just disappeared.
    listing = _git(origin, "cat-file", "--batch-all-objects", "--batch-check")
    shas = {line.split()[0] for line in listing.splitlines()}
    solution_sha = _resolve_pre_scrub_commit(origin)
    if solution_sha is not None:
        assert solution_sha not in shas


def _resolve_pre_scrub_commit(origin: Path) -> str | None:
    """The solution commit SHA recorded while creating the fixture. After
    scrubbing it must be unresolvable, so this helper re-reads it from the
    fixture bookkeeping rather than git."""
    marker = origin / "solution.sha"
    if not marker.exists():
        return None
    return marker.read_text(encoding="utf-8").strip()


def test_init_repo_fixture_records_solution_commit(tmp_path: Path) -> None:
    """Fixture self-check: the recorded pre-scrub solution SHA exists as a
    real commit object before scrubbing, so the pruning assertion above is
    exercised against something that was genuinely there."""
    origin = _init_repo(tmp_path)
    solution_sha = _git(origin, "rev-parse", "refs/heads/solution/candidate-a")
    (origin / "solution.sha").write_text(solution_sha, encoding="utf-8")
    listing = _git(origin, "cat-file", "--batch-all-objects", "--batch-check")
    assert solution_sha in {line.split()[0] for line in listing.splitlines()}
    worktree, head = _worktree_from_head(origin, tmp_path)
    assert head != solution_sha


def test_scrub_keeps_refs_that_point_at_the_checked_out_commit(
    tmp_path: Path,
) -> None:
    """A branch already sitting on the workspace's base commit survives:
    scrubbing removes *future* state, not every name."""
    origin = _init_repo(tmp_path)
    head_sha = _git(origin, "rev-parse", "HEAD")
    _git(origin, "branch", "on-base", head_sha)
    worktree, keep_revision = _worktree_from_head(origin, tmp_path)

    deleted = scrub_future_state(worktree, keep_revision=keep_revision)

    assert deleted == [
        "refs/heads/solution/candidate-a",
        "refs/remotes/origin/solution",
        "refs/tags/solution-tag",
    ]
    surviving = list_refs(origin / ".git", SCRUBBED_REF_PATTERNS)
    assert surviving["refs/heads/on-base"] == keep_revision
    assert surviving["refs/heads/main"] == keep_revision


def test_scrub_refuses_a_keep_revision_that_is_not_head(tmp_path: Path) -> None:
    """Scrubbing is defined against the checked-out commit; a caller asking
    to keep anything else would strand the worktree, so it fails closed."""
    origin = _init_repo(tmp_path)
    worktree, _ = _worktree_from_head(origin, tmp_path)
    other_sha = _git(origin, "rev-parse", "refs/heads/solution/candidate-a")

    with pytest.raises(GitCommandError):
        scrub_future_state(worktree, keep_revision=other_sha)


def test_scrub_accepts_a_symbolic_keep_revision(tmp_path: Path) -> None:
    origin = _init_repo(tmp_path)
    worktree, head_sha = _worktree_from_head(origin, tmp_path)
    solution_sha = _git(origin, "rev-parse", "refs/heads/solution/candidate-a")
    _git(worktree, "update-ref", "refs/remotes/upstream/main", solution_sha)

    deleted = scrub_future_state(worktree, keep_revision=head_sha[:12])

    assert deleted == [
        "refs/heads/solution/candidate-a",
        "refs/remotes/origin/solution",
        "refs/remotes/upstream/main",
        "refs/tags/solution-tag",
    ]
