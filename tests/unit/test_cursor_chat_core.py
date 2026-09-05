from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.core.command_identity import logical_command_hash
from engine.core.errors import DdeError
from engine.studio.chat.models import CLAUDE_CODE_PROFILE, FrontendChatModelCatalog
from engine.studio.chat.plans import FrontendChatPlanService
from engine.studio.chat.storage import ChatObjectStore, storage_key_for_chat_object
from engine.workspaces import git

TENANT = UUID("00000000-0000-0000-0000-000000000001")
PROJECT = UUID("00000000-0000-0000-0000-000000000002")
MISSION = UUID("00000000-0000-0000-0000-000000000003")


def test_logical_command_hash_is_order_stable_and_payload_sensitive() -> None:
    first = logical_command_hash(
        command_type="frontend.mutation.apply",
        target_type="mission",
        target_id=MISSION,
        parameters={"b": 2, "a": {"y": 2, "x": 1}},
        protocol_version="1",
    )
    reordered = logical_command_hash(
        command_type="frontend.mutation.apply",
        target_type="mission",
        target_id=MISSION,
        parameters={"a": {"x": 1, "y": 2}, "b": 2},
        protocol_version="1",
    )
    changed = logical_command_hash(
        command_type="frontend.mutation.apply",
        target_type="mission",
        target_id=MISSION,
        parameters={"a": {"x": 1, "y": 3}, "b": 2},
        protocol_version="1",
    )
    assert first == reordered
    assert first != changed


def test_chat_object_store_is_content_addressed_and_project_jailed(
    tmp_path: Path,
) -> None:
    store = ChatObjectStore(root=tmp_path)
    payload = b"cursor-class-chat"
    digest = hashlib.sha256(payload).hexdigest()
    key = store.put(
        tenant_id=TENANT, project_id=PROJECT, content_hash=digest, content=payload
    )
    assert key == storage_key_for_chat_object(
        tenant_id=TENANT, project_id=PROJECT, content_hash=digest
    )
    assert store.read(tenant_id=TENANT, project_id=PROJECT, key=key) == payload
    assert (
        store.put(
            tenant_id=TENANT, project_id=PROJECT, content_hash=digest, content=payload
        )
        == key
    )

    other_project = UUID("00000000-0000-0000-0000-000000000099")
    with pytest.raises(DdeError, match="outside the authorized project scope") as exc:
        store.read(tenant_id=TENANT, project_id=other_project, key=key)
    assert exc.value.error_code == "TENANT_SCOPE_VIOLATION"

    with pytest.raises(DdeError) as oversized:
        store.read(
            tenant_id=TENANT, project_id=PROJECT, key=key, max_bytes=len(payload) - 1
        )
    assert oversized.value.error_code == "ATTACHMENT_TOO_LARGE"


def test_chat_object_store_rejects_hash_collision(tmp_path: Path) -> None:
    store = ChatObjectStore(root=tmp_path)
    key_hash = "f" * 64
    store.put(
        tenant_id=TENANT, project_id=PROJECT, content_hash=key_hash, content=b"one"
    )
    with pytest.raises(DdeError) as exc:
        store.put(
            tenant_id=TENANT, project_id=PROJECT, content_hash=key_hash, content=b"two"
        )
    assert exc.value.error_code == "VERSION_CONFLICT"


def test_model_catalog_never_upgrades_cli_presence_into_unapproved_availability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "engine.studio.chat.models.shutil.which", lambda _: "/usr/bin/claude"
    )
    catalog = FrontendChatModelCatalog()
    claude = next(
        item for item in catalog.options() if item.option_id == CLAUDE_CODE_PROFILE
    )
    assert claude.status == "APPROVAL_REQUIRED"
    assert claude.requires_approval is True
    assert "fresh human approval" in claude.reason

    with pytest.raises(DdeError) as exc:
        catalog.require_known("model:not-admitted")
    assert exc.value.error_code == "VALIDATION_FAILED"


def _plan_service() -> FrontendChatPlanService:
    return FrontendChatPlanService(cast(AsyncEngine, object()))


def test_plan_parser_admits_only_mission_control_commands() -> None:
    service = _plan_service()
    steps = service._parse_steps(  # noqa: SLF001 - contract-level pure parser test
        [
            {
                "title": "Set spacing",
                "command_type": "frontend.mutation.apply",
                "parameters": {"candidate_id": "candidate"},
            }
        ],
        mission_id=MISSION,
    )
    assert len(steps) == 1
    assert steps[0].target_type == "mission"
    assert steps[0].target_id == MISSION

    with pytest.raises(DdeError) as exc:
        service._parse_steps(  # noqa: SLF001
            [
                {
                    "title": "raw command",
                    "command_type": "worker.invoke",
                    "parameters": {},
                }
            ],
            mission_id=MISSION,
        )
    assert exc.value.error_code == "COMMAND_NOT_ALLOWED"


def test_plan_parser_rejects_dependency_cycles() -> None:
    service = _plan_service()
    first = UUID("00000000-0000-0000-0000-000000000011")
    second = UUID("00000000-0000-0000-0000-000000000012")
    with pytest.raises(DdeError, match="cycle"):
        service._parse_steps(  # noqa: SLF001
            [
                {
                    "step_id": str(first),
                    "command_type": "frontend.mutation.apply",
                    "depends_on": [str(second)],
                },
                {
                    "step_id": str(second),
                    "command_type": "frontend.mutation.apply",
                    "depends_on": [str(first)],
                },
            ],
            mission_id=MISSION,
        )


def _run_git(repo: Path, *args: str) -> str:
    executable = shutil.which("git")
    assert executable is not None
    completed = subprocess.run(  # noqa: S603 - fixed test executable + literals
        [executable, *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


def test_workspace_git_diff_patch_and_restore_are_real(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "dde@example.invalid")
    _run_git(repo, "config", "user.name", "DDE Test")
    source = repo / "screen.txt"
    source.write_text("space2\n", encoding="utf-8")
    _run_git(repo, "add", "screen.txt")
    _run_git(repo, "commit", "-m", "base")
    base = _run_git(repo, "rev-parse", "HEAD")

    source.write_text("space4\n", encoding="utf-8")
    (repo / "new.txt").write_text("new\n", encoding="utf-8")
    assert git.changed_paths(repo) == ["new.txt", "screen.txt"]
    assert "space4" in git.unified_diff(repo, base, "screen.txt")
    assert "new" in git.unified_diff(repo, base, "new.txt")

    git.restore_path(repo, base, "screen.txt")
    git.restore_path(repo, base, "new.txt")
    assert git.changed_paths(repo) == []

    patch = """--- a/screen.txt\n+++ b/screen.txt\n@@ -1 +1 @@\n-space2\n+space6\n"""
    git.apply_patch(repo, patch)
    assert source.read_text(encoding="utf-8") == "space6\n"
    git.restore_path(repo, base, "screen.txt")
    assert source.read_text(encoding="utf-8") == "space2\n"
