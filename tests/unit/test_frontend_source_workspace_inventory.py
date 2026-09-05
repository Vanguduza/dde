from datetime import UTC, datetime
from uuid import uuid4

from engine.contracts.workspace import Workspace
from engine.studio.reads import Availability, build_source_workspace_inventory


def _workspace(
    *,
    status: str = "READY",
    revision: str | None = "a" * 40,
    purpose: str | None = None,
) -> Workspace:
    now = datetime.now(UTC)
    policy = {"purpose": purpose} if purpose else {}
    return Workspace(
        workspace_id=uuid4(), tenant_id=uuid4(), project_id=uuid4(), mission_id=uuid4(),
        task_id=None, execution_environment_id=None, base_revision="0" * 40,
        current_revision=revision, workspace_path="/tmp/workspace", policy=policy,
        status=status, lock_version=1, created_at=now, updated_at=now,
    )


def test_source_workspace_inventory_is_empty_without_ready_durable_source() -> None:
    result = build_source_workspace_inventory([
        _workspace(status="PROVISIONING"),
        _workspace(revision=None),
        _workspace(purpose="frontend_candidate_preview"),
    ])
    assert result.selection_state == "EMPTY"
    assert result.availability is Availability.EMPTY
    assert result.auto_selected_workspace_id is None
    assert result.options == ()


def test_source_workspace_inventory_auto_selects_only_unique_source() -> None:
    source = _workspace(purpose="worker_source")
    result = build_source_workspace_inventory([source])
    assert result.selection_state == "UNIQUE"
    assert result.auto_selected_workspace_id == str(source.workspace_id)
    assert [item.workspace_id for item in result.options] == [str(source.workspace_id)]


def test_source_workspace_inventory_requires_explicit_choice_when_ambiguous() -> None:
    first = _workspace(purpose="worker_source")
    second = _workspace(purpose="worker_source")
    result = build_source_workspace_inventory([first, second])
    assert result.selection_state == "AMBIGUOUS"
    assert result.auto_selected_workspace_id is None
    assert len(result.options) == 2
    assert "explicit selection" in (result.reason or "")
