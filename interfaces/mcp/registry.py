"""Chapter 15.6 MCP tool declarations.

Every DDE MCP tool declares: stable name, semantic version, JSON Schema
2020-12 input/output, required principal scopes, mutation classification,
idempotency requirement, target-resource rules, audit event type, error
codes, and sync/async execution. Tool discovery never constitutes
authorization — CapabilityLease / Gateway scope checks remain the
execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MutationClass = Literal["none", "controlled", "high"]
ExecutionMode = Literal["sync", "async"]


@dataclass(frozen=True)
class McpToolDeclaration:
    """One Chapter 15.6 tool row — declaration only, not a handler."""

    name: str
    version: str
    description: str
    tool_class: str
    input_schema: dict[str, object]
    output_schema: dict[str, object]
    required_scopes: tuple[str, ...]
    mutation: MutationClass
    idempotency_required: bool
    target_resource: str
    audit_event_type: str
    error_codes: tuple[str, ...]
    execution: ExecutionMode
    #: True only when a production handler dispatches through the Gateway
    #: (or an explicitly named Gateway read). Discovery still lists tools
    #: that are not yet gateway-backed; calling them fails closed.
    gateway_backed: bool


def _object_schema(
    *,
    required: list[str],
    properties: dict[str, object],
) -> dict[str, object]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


_UUID = {"type": "string", "format": "uuid"}
_STRING = {"type": "string", "minLength": 1}


#: Chapter 15.6 tool table — names and mutation classes are normative.
TOOL_DECLARATIONS: tuple[McpToolDeclaration, ...] = (
    McpToolDeclaration(
        name="dde_get_mission",
        version="1.0.0",
        description="Read a mission by id (Chapter 15.4 GET /v1/missions/{id}).",
        tool_class="Read",
        input_schema=_object_schema(
            required=["mission_id"],
            properties={"mission_id": _UUID},
        ),
        output_schema=_object_schema(
            required=["mission"],
            properties={"mission": {"type": "object"}},
        ),
        required_scopes=("mission.read",),
        mutation="none",
        idempotency_required=False,
        target_resource="mission",
        audit_event_type="McpToolRead",
        error_codes=("FORBIDDEN", "TENANT_SCOPE_VIOLATION", "SESSION_EXPIRED"),
        execution="sync",
        gateway_backed=True,
    ),
    McpToolDeclaration(
        name="dde_get_task",
        version="1.0.0",
        description="Read a task by id.",
        tool_class="Read",
        input_schema=_object_schema(
            required=["task_id"],
            properties={"task_id": _UUID},
        ),
        output_schema=_object_schema(
            required=["task"],
            properties={"task": {"type": "object"}},
        ),
        required_scopes=("mission.read",),
        mutation="none",
        idempotency_required=False,
        target_resource="task",
        audit_event_type="McpToolRead",
        error_codes=("FORBIDDEN", "TENANT_SCOPE_VIOLATION", "SESSION_EXPIRED"),
        execution="sync",
        gateway_backed=True,
    ),
    McpToolDeclaration(
        name="dde_get_evidence",
        version="1.0.0",
        description="Read evidence by id.",
        tool_class="Read",
        input_schema=_object_schema(
            required=["evidence_id"],
            properties={"evidence_id": _UUID},
        ),
        output_schema=_object_schema(
            required=["evidence"],
            properties={"evidence": {"type": "object"}},
        ),
        required_scopes=("evidence.read",),
        mutation="none",
        idempotency_required=False,
        target_resource="evidence",
        audit_event_type="McpToolRead",
        error_codes=("FORBIDDEN", "TENANT_SCOPE_VIOLATION", "SESSION_EXPIRED"),
        execution="sync",
        gateway_backed=False,
    ),
    McpToolDeclaration(
        name="dde_get_graph",
        version="1.0.0",
        description="Read a TaskGraph by id.",
        tool_class="Read",
        input_schema=_object_schema(
            required=["graph_id"],
            properties={"graph_id": _UUID},
        ),
        output_schema=_object_schema(
            required=["graph"],
            properties={"graph": {"type": "object"}},
        ),
        required_scopes=("mission.read",),
        mutation="none",
        idempotency_required=False,
        target_resource="task_graph",
        audit_event_type="McpToolRead",
        error_codes=("FORBIDDEN", "TENANT_SCOPE_VIOLATION", "SESSION_EXPIRED"),
        execution="sync",
        gateway_backed=True,
    ),
    McpToolDeclaration(
        name="dde_compile_context",
        version="1.0.0",
        description="Compile a ContextPackage for a task.",
        tool_class="Context",
        input_schema=_object_schema(
            required=["task_id", "idempotency_key"],
            properties={"task_id": _UUID, "idempotency_key": _STRING},
        ),
        output_schema=_object_schema(
            required=["command_id", "status"],
            properties={
                "command_id": _UUID,
                "status": _STRING,
            },
        ),
        required_scopes=("context.compile",),
        mutation="controlled",
        idempotency_required=True,
        target_resource="task",
        audit_event_type="McpToolMutationAccepted",
        error_codes=("FORBIDDEN", "SESSION_EXPIRED", "CONTEXT_BUDGET_EXCEEDED"),
        execution="async",
        gateway_backed=False,
    ),
    McpToolDeclaration(
        name="dde_request_context",
        version="1.0.0",
        description="JIT context expansion request for a task.",
        tool_class="Context",
        input_schema=_object_schema(
            required=["task_id", "idempotency_key", "request"],
            properties={
                "task_id": _UUID,
                "idempotency_key": _STRING,
                "request": {"type": "object"},
            },
        ),
        output_schema=_object_schema(
            required=["command_id", "status"],
            properties={"command_id": _UUID, "status": _STRING},
        ),
        required_scopes=("context.expand",),
        mutation="controlled",
        idempotency_required=True,
        target_resource="task",
        audit_event_type="McpToolMutationAccepted",
        error_codes=("FORBIDDEN", "SESSION_EXPIRED", "POLICY_DENIED"),
        execution="async",
        gateway_backed=False,
    ),
    McpToolDeclaration(
        name="dde_propose_amendment",
        version="1.0.0",
        description="Propose a TaskGraph amendment.",
        tool_class="Planning",
        input_schema=_object_schema(
            required=["graph_id", "idempotency_key", "rationale"],
            properties={
                "graph_id": _UUID,
                "idempotency_key": _STRING,
                "rationale": _STRING,
            },
        ),
        output_schema=_object_schema(
            required=["command_id", "status"],
            properties={"command_id": _UUID, "status": _STRING},
        ),
        required_scopes=("plan.amend",),
        mutation="controlled",
        idempotency_required=True,
        target_resource="task_graph",
        audit_event_type="McpToolMutationAccepted",
        error_codes=("FORBIDDEN", "SESSION_EXPIRED", "GRAPH_INVALID"),
        execution="sync",
        gateway_backed=False,
    ),
    McpToolDeclaration(
        name="dde_evaluate_route",
        version="1.0.0",
        description="Evaluate a route for a task.",
        tool_class="Planning",
        input_schema=_object_schema(
            required=["task_id", "idempotency_key"],
            properties={"task_id": _UUID, "idempotency_key": _STRING},
        ),
        output_schema=_object_schema(
            required=["command_id", "status"],
            properties={"command_id": _UUID, "status": _STRING},
        ),
        required_scopes=("route.evaluate",),
        mutation="controlled",
        idempotency_required=True,
        target_resource="task",
        audit_event_type="McpToolMutationAccepted",
        error_codes=("FORBIDDEN", "SESSION_EXPIRED", "NO_ELIGIBLE_WORKER"),
        execution="sync",
        gateway_backed=False,
    ),
    McpToolDeclaration(
        name="dde_create_execution_plan",
        version="1.0.0",
        description="Create and validate an ExecutionPlan.",
        tool_class="Planning",
        input_schema=_object_schema(
            required=["task_id", "route_decision_id", "idempotency_key"],
            properties={
                "task_id": _UUID,
                "route_decision_id": _UUID,
                "idempotency_key": _STRING,
            },
        ),
        output_schema=_object_schema(
            required=["command_id", "status"],
            properties={"command_id": _UUID, "status": _STRING},
        ),
        required_scopes=("execution.plan",),
        mutation="controlled",
        idempotency_required=True,
        target_resource="task",
        audit_event_type="McpToolMutationAccepted",
        error_codes=("FORBIDDEN", "SESSION_EXPIRED", "POLICY_DENIED"),
        execution="sync",
        gateway_backed=False,
    ),
    McpToolDeclaration(
        name="dde_start_task",
        version="1.0.0",
        description="Start execution for a task (WorkerRun).",
        tool_class="Execution",
        input_schema=_object_schema(
            required=["task_id", "execution_plan_id", "idempotency_key"],
            properties={
                "task_id": _UUID,
                "execution_plan_id": _UUID,
                "idempotency_key": _STRING,
            },
        ),
        output_schema=_object_schema(
            required=["command_id", "status"],
            properties={"command_id": _UUID, "status": _STRING},
        ),
        required_scopes=("worker.execute",),
        mutation="high",
        idempotency_required=True,
        target_resource="task",
        audit_event_type="McpToolMutationAccepted",
        error_codes=("FORBIDDEN", "SESSION_EXPIRED", "CAPABILITY_LEASE_EXPIRED"),
        execution="async",
        gateway_backed=False,
    ),
    McpToolDeclaration(
        name="dde_request_capability",
        version="1.0.0",
        description="Request a CapabilityLease for a worker run.",
        tool_class="Execution",
        input_schema=_object_schema(
            required=["worker_run_id", "capability_id", "idempotency_key"],
            properties={
                "worker_run_id": _UUID,
                "capability_id": _STRING,
                "idempotency_key": _STRING,
            },
        ),
        output_schema=_object_schema(
            required=["command_id", "status"],
            properties={"command_id": _UUID, "status": _STRING},
        ),
        required_scopes=("capability.request",),
        mutation="high",
        idempotency_required=True,
        target_resource="worker_run",
        audit_event_type="McpToolMutationAccepted",
        error_codes=("FORBIDDEN", "SESSION_EXPIRED", "POLICY_DENIED"),
        execution="sync",
        gateway_backed=False,
    ),
    McpToolDeclaration(
        name="dde_start_verification",
        version="1.0.0",
        description="Start a VerificationRun for a completed WorkerRun.",
        tool_class="Verification",
        input_schema=_object_schema(
            required=["worker_run_id", "idempotency_key"],
            properties={"worker_run_id": _UUID, "idempotency_key": _STRING},
        ),
        output_schema=_object_schema(
            required=["command_id", "status"],
            properties={"command_id": _UUID, "status": _STRING},
        ),
        required_scopes=("verification.run",),
        mutation="controlled",
        idempotency_required=True,
        target_resource="worker_run",
        audit_event_type="McpToolMutationAccepted",
        error_codes=("FORBIDDEN", "SESSION_EXPIRED", "VERIFICATION_FAILED"),
        execution="async",
        gateway_backed=False,
    ),
    McpToolDeclaration(
        name="dde_get_verification",
        version="1.0.0",
        description="Read a VerificationRun by id.",
        tool_class="Verification",
        input_schema=_object_schema(
            required=["verification_run_id"],
            properties={"verification_run_id": _UUID},
        ),
        output_schema=_object_schema(
            required=["verification_run"],
            properties={"verification_run": {"type": "object"}},
        ),
        required_scopes=("verification.read",),
        mutation="none",
        idempotency_required=False,
        target_resource="verification_run",
        audit_event_type="McpToolRead",
        error_codes=("FORBIDDEN", "TENANT_SCOPE_VIOLATION", "SESSION_EXPIRED"),
        execution="sync",
        gateway_backed=False,
    ),
    McpToolDeclaration(
        name="dde_request_approval",
        version="1.0.0",
        description="Request a governance approval.",
        tool_class="Governance",
        input_schema=_object_schema(
            required=["project_id", "idempotency_key", "kind", "summary"],
            properties={
                "project_id": _UUID,
                "idempotency_key": _STRING,
                "kind": _STRING,
                "summary": _STRING,
            },
        ),
        output_schema=_object_schema(
            required=["command_id", "status"],
            properties={"command_id": _UUID, "status": _STRING},
        ),
        required_scopes=("approval.request",),
        mutation="high",
        idempotency_required=True,
        target_resource="project",
        audit_event_type="McpToolMutationAccepted",
        error_codes=("FORBIDDEN", "SESSION_EXPIRED", "POLICY_DENIED"),
        execution="async",
        gateway_backed=False,
    ),
    McpToolDeclaration(
        name="dde_record_decision",
        version="1.0.0",
        description="Record a human approval decision.",
        tool_class="Governance",
        input_schema=_object_schema(
            required=["project_id", "idempotency_key", "approval_ids", "decision"],
            properties={
                "project_id": _UUID,
                "idempotency_key": _STRING,
                "approval_ids": {"type": "array", "items": _UUID, "minItems": 1},
                "decision": {"type": "string", "enum": ["approved", "rejected"]},
            },
        ),
        output_schema=_object_schema(
            required=["command_id", "status"],
            properties={"command_id": _UUID, "status": _STRING},
        ),
        required_scopes=("approval.decide",),
        mutation="high",
        idempotency_required=True,
        target_resource="project",
        audit_event_type="McpToolMutationAccepted",
        error_codes=("FORBIDDEN", "SESSION_EXPIRED", "POLICY_DENIED"),
        execution="async",
        gateway_backed=False,
    ),
    McpToolDeclaration(
        name="dde_pause_task",
        version="1.0.0",
        description="Pause a task.",
        tool_class="Control",
        input_schema=_object_schema(
            required=["task_id", "idempotency_key"],
            properties={"task_id": _UUID, "idempotency_key": _STRING},
        ),
        output_schema=_object_schema(
            required=["command_id", "status"],
            properties={"command_id": _UUID, "status": _STRING},
        ),
        required_scopes=("mission.control",),
        mutation="high",
        idempotency_required=True,
        target_resource="task",
        audit_event_type="McpToolMutationAccepted",
        error_codes=("FORBIDDEN", "SESSION_EXPIRED", "RESOURCE_LOCKED"),
        execution="async",
        gateway_backed=False,
    ),
    McpToolDeclaration(
        name="dde_resume_task",
        version="1.0.0",
        description="Resume a paused task.",
        tool_class="Control",
        input_schema=_object_schema(
            required=["task_id", "idempotency_key"],
            properties={"task_id": _UUID, "idempotency_key": _STRING},
        ),
        output_schema=_object_schema(
            required=["command_id", "status"],
            properties={"command_id": _UUID, "status": _STRING},
        ),
        required_scopes=("mission.control",),
        mutation="high",
        idempotency_required=True,
        target_resource="task",
        audit_event_type="McpToolMutationAccepted",
        error_codes=("FORBIDDEN", "SESSION_EXPIRED", "RESOURCE_LOCKED"),
        execution="async",
        gateway_backed=False,
    ),
    McpToolDeclaration(
        name="dde_cancel_task",
        version="1.0.0",
        description="Cancel a task.",
        tool_class="Control",
        input_schema=_object_schema(
            required=["task_id", "idempotency_key"],
            properties={"task_id": _UUID, "idempotency_key": _STRING},
        ),
        output_schema=_object_schema(
            required=["command_id", "status"],
            properties={"command_id": _UUID, "status": _STRING},
        ),
        required_scopes=("mission.control",),
        mutation="high",
        idempotency_required=True,
        target_resource="task",
        audit_event_type="McpToolMutationAccepted",
        error_codes=("FORBIDDEN", "SESSION_EXPIRED", "RESOURCE_LOCKED"),
        execution="async",
        gateway_backed=False,
    ),
)


FABRIC_TOOL_DECLARATIONS: tuple[McpToolDeclaration, ...] = (
    McpToolDeclaration(
        name="dde_get_ai_fabric",
        version="1.0.0",
        description="Read DDE AI Conversation Fabric state for a mission/conversation.",
        tool_class="AI Fabric",
        input_schema=_object_schema(
            required=["mission_id"],
            properties={
                "mission_id": _UUID,
                "conversation_id": {"anyOf": [_UUID, {"type": "null"}]},
            },
        ),
        output_schema=_object_schema(
            required=["fabric"], properties={"fabric": {"type": "object"}}
        ),
        required_scopes=("mission.read",),
        mutation="none",
        idempotency_required=False,
        target_resource="mission",
        audit_event_type="McpToolRead",
        error_codes=("FORBIDDEN", "TENANT_SCOPE_VIOLATION", "SESSION_EXPIRED"),
        execution="sync",
        gateway_backed=True,
    ),
    McpToolDeclaration(
        name="dde_send_frontend_chat",
        version="1.0.0",
        description="Send a governed DDE Frontend Chat turn.",
        tool_class="AI Fabric",
        input_schema=_object_schema(
            required=["mission_id", "conversation_id", "text", "idempotency_key"],
            properties={
                "mission_id": _UUID,
                "conversation_id": _UUID,
                "text": _STRING,
                "attachment_ids": {"type": "array", "items": _UUID},
                "approval_id": {"anyOf": [_UUID, {"type": "null"}]},
                "idempotency_key": _STRING,
            },
        ),
        output_schema=_object_schema(
            required=["command_id", "status"],
            properties={
                "command_id": _UUID,
                "status": _STRING,
                "payload": {"type": "object"},
            },
        ),
        required_scopes=("mission.control",),
        mutation="controlled",
        idempotency_required=True,
        target_resource="mission",
        audit_event_type="McpToolMutationAccepted",
        error_codes=(
            "FORBIDDEN",
            "SESSION_EXPIRED",
            "PROVIDER_UNAVAILABLE",
            "APPROVAL_REQUIRED",
        ),
        execution="async",
        gateway_backed=True,
    ),
    McpToolDeclaration(
        name="dde_memory_recall",
        version="1.0.0",
        description=(
            "Recall approved shared DDE memory for a conversation under a bounded "
            "token budget. Providers receive excerpts, never R2/database credentials."
        ),
        tool_class="AI Memory",
        input_schema=_object_schema(
            required=["mission_id", "conversation_id", "query"],
            properties={
                "mission_id": _UUID,
                "conversation_id": _UUID,
                "query": _STRING,
                "budget_tokens": {"type": "integer", "minimum": 128, "maximum": 16000},
            },
        ),
        output_schema=_object_schema(
            required=["memory", "estimated_tokens", "budget_tokens"],
            properties={
                "memory": {"type": "array", "items": {"type": "object"}},
                "estimated_tokens": {"type": "integer"},
                "budget_tokens": {"type": "integer"},
            },
        ),
        required_scopes=("mission.read",),
        mutation="none",
        idempotency_required=False,
        target_resource="conversation",
        audit_event_type="McpToolRead",
        error_codes=("FORBIDDEN", "TENANT_SCOPE_VIOLATION", "SESSION_EXPIRED"),
        execution="sync",
        gateway_backed=True,
    ),
    McpToolDeclaration(
        name="dde_memory_propose",
        version="1.0.0",
        description=(
            "Propose advisory shared DDE memory from a provider. The proposal enters "
            "CANDIDATE state and cannot self-promote to authoritative memory."
        ),
        tool_class="AI Memory",
        input_schema=_object_schema(
            required=[
                "mission_id",
                "conversation_id",
                "content",
                "idempotency_key",
            ],
            properties={
                "mission_id": _UUID,
                "conversation_id": _UUID,
                "content": _STRING,
                "scope_kind": {"type": "string", "enum": ["CONVERSATION", "MISSION"]},
                "source_refs": {"type": "array", "items": _STRING},
                "provider_profile_id": {"anyOf": [_STRING, {"type": "null"}]},
                "idempotency_key": _STRING,
            },
        ),
        output_schema=_object_schema(
            required=["command_id", "status"],
            properties={
                "command_id": _UUID,
                "status": _STRING,
                "payload": {"type": "object"},
            },
        ),
        required_scopes=("mission.control",),
        mutation="controlled",
        idempotency_required=True,
        target_resource="conversation",
        audit_event_type="McpToolMutationAccepted",
        error_codes=("FORBIDDEN", "SESSION_EXPIRED", "POLICY_DENIED"),
        execution="async",
        gateway_backed=True,
    ),
    McpToolDeclaration(
        name="dde_fabric_command",
        version="1.0.0",
        description="Submit an explicitly registered AI Conversation Fabric command.",
        tool_class="AI Fabric",
        input_schema=_object_schema(
            required=["mission_id", "command_type", "parameters", "idempotency_key"],
            properties={
                "mission_id": _UUID,
                "command_type": _STRING,
                "parameters": {"type": "object"},
                "idempotency_key": _STRING,
            },
        ),
        output_schema=_object_schema(
            required=["command_id", "status"],
            properties={
                "command_id": _UUID,
                "status": _STRING,
                "payload": {"type": "object"},
            },
        ),
        required_scopes=("mission.control",),
        mutation="controlled",
        idempotency_required=True,
        target_resource="mission",
        audit_event_type="McpToolMutationAccepted",
        error_codes=("FORBIDDEN", "SESSION_EXPIRED", "POLICY_DENIED"),
        execution="async",
        gateway_backed=True,
    ),
)
FABRIC_TOOL_NAMES: frozenset[str] = frozenset(
    tool.name for tool in FABRIC_TOOL_DECLARATIONS
)
TOOL_DECLARATIONS = (*TOOL_DECLARATIONS, *FABRIC_TOOL_DECLARATIONS)


TOOL_BY_NAME: dict[str, McpToolDeclaration] = {
    tool.name: tool for tool in TOOL_DECLARATIONS
}


#: Normative Chapter 15.6 tool names — the contract suite pins this set.
CHAPTER_15_6_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "dde_get_mission",
        "dde_get_task",
        "dde_get_evidence",
        "dde_get_graph",
        "dde_compile_context",
        "dde_request_context",
        "dde_propose_amendment",
        "dde_evaluate_route",
        "dde_create_execution_plan",
        "dde_start_task",
        "dde_request_capability",
        "dde_start_verification",
        "dde_get_verification",
        "dde_request_approval",
        "dde_record_decision",
        "dde_pause_task",
        "dde_resume_task",
        "dde_cancel_task",
    }
)
