from datetime import UTC, datetime
from uuid import uuid4

from engine.contracts.pxg_node import PxgNode
from engine.studio.pxg.service import PxgGraph
from engine.studio.verification_requests import derive_verification_binding


def _screen(*, complete: bool = True) -> PxgNode:
    now = datetime.now(UTC)
    task_id = uuid4()
    return PxgNode(
        node_id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        pxg_key="screens/checkout",
        node_kind="screen",
        title="Checkout",
        parent_key=None,
        pxg_revision=4,
        source_refs=[],
        attributes=(
            {
                "bound_verification_kinds": ["visual_critique", "silhouette"],
                "acceptance_oracle_version": "oracle-v4",
            }
            if complete
            else {"bound_verification_kinds": ["silhouette"]}
        ),
        provenance={"authored_by_task_id": str(task_id)} if complete else {},
        lock_version=1,
        created_at=now,
        updated_at=now,
    )


def test_complete_screen_binding_schedules_existing_dde068_kinds() -> None:
    binding = derive_verification_binding(
        PxgGraph(revision=4, nodes=(_screen(),), edges=()),
        "screens/checkout",
    )
    assert binding.state == "PENDING"
    assert binding.required_kinds == ("silhouette", "visual_critique")
    assert binding.task_id is not None
    assert binding.acceptance_oracle_version == "oracle-v4"
    assert binding.reason is None


def test_missing_acceptance_binding_is_blocked_not_assumed() -> None:
    binding = derive_verification_binding(
        PxgGraph(revision=4, nodes=(_screen(complete=False),), edges=()),
        "screens/checkout",
    )
    assert binding.state == "BLOCKED"
    assert "authored_by_task_id" in (binding.reason or "")
    assert "acceptance_oracle_version" in (binding.reason or "")


def test_missing_candidate_screen_is_blocked() -> None:
    binding = derive_verification_binding(
        PxgGraph(revision=4, nodes=(), edges=()),
        "screens/checkout",
    )
    assert binding.state == "BLOCKED"
    assert binding.required_kinds == ()
    assert "absent" in (binding.reason or "")
