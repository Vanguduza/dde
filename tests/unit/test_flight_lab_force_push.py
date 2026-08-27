"""Flight Lab force-push attempt (Ch.10.7 / 10.9 / Ch.19.1 Integration).

Uses a throwaway git repo -- never the DDE checkout's `main`. The
production mutation is `engine.integration.git.update_ref`, which
`IntegrationQueueService.integrate` uses for mission branches.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from engine.integration.git import (
    ForcePushRefusedError,
    create_branch,
    is_protected_ref,
    rev_parse,
    update_ref,
)

_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "DDE Flight Lab",
    "GIT_AUTHOR_EMAIL": "flight-lab@dde.local",
    "GIT_COMMITTER_NAME": "DDE Flight Lab",
    "GIT_COMMITTER_EMAIL": "flight-lab@dde.local",
}


def _git(repo: Path, *args: str) -> str:
    git = shutil.which("git")
    assert git is not None
    env = os.environ.copy()
    env.update(_COMMIT_ENV)
    cmd = [git]
    if args and args[0] == "commit":
        cmd.extend(
            [
                "-c",
                "user.name=DDE Flight Lab",
                "-c",
                "user.email=flight-lab@dde.local",
            ]
        )
    cmd.extend(args)
    completed = subprocess.run(  # noqa: S603
        cmd,
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return completed.stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "protected-refs"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "commit", "--allow-empty", "-m", "init")
    return repo


def _orphan_commit(repo: Path) -> str:
    _git(repo, "checkout", "--orphan", "orphan-lab")
    _git(repo, "commit", "--allow-empty", "-m", "unrelated")
    sha = rev_parse(repo, "HEAD")
    _git(repo, "checkout", "main")
    return sha


def test_main_and_mission_refs_are_protected() -> None:
    assert is_protected_ref("main") is True
    assert is_protected_ref("mission/abc") is True
    assert is_protected_ref("task/abc-a") is False
    assert is_protected_ref("candidate/abc") is False


def test_force_push_of_main_is_refused(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    unrelated = _orphan_commit(repo)
    with pytest.raises(ForcePushRefusedError) as refused:
        update_ref(repo, "main", unrelated)
    assert refused.value.ref_name == "main"
    assert "force-push" in str(refused.value)


def test_force_push_of_mission_branch_is_refused(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    create_branch(repo, "mission/lab", rev_parse(repo, "main"))
    unrelated = _orphan_commit(repo)
    with pytest.raises(ForcePushRefusedError) as refused:
        update_ref(repo, "mission/lab", unrelated)
    assert refused.value.ref_name == "mission/lab"


def test_fast_forward_of_protected_ref_is_allowed(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _git(repo, "commit", "--allow-empty", "-m", "second")
    child = rev_parse(repo, "HEAD")
    _git(repo, "reset", "--soft", "HEAD~1")
    # main is now at the first commit; child is a descendant.
    update_ref(repo, "main", child)
    assert rev_parse(repo, "main") == child


def test_task_branch_may_still_rewind_after_rebase(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    create_branch(repo, "task/lab-a", rev_parse(repo, "main"))
    unrelated = _orphan_commit(repo)
    update_ref(repo, "task/lab-a", unrelated)
    assert rev_parse(repo, "task/lab-a") == unrelated
