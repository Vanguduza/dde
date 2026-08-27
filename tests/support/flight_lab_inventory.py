"""Machine-readable Chapter 19.1 Flight Lab inventory (DDE-060).

This is a catalog of existing production-backed fixtures, not a claim
that every row is a newly written Flight Lab scenario. Gaps are named
with an owner (open EDR or later mission). The S7 golden-mission
scenarios live in `tests/unit/test_flight_lab_golden_mission.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

CH19_SUITE_NAMES: tuple[str, ...] = (
    "Schema/contract",
    "API",
    "MCP",
    "Planning",
    "Context",
    "Routing",
    "Worker protocol",
    "Environment",
    "Integration",
    "Verification",
    "Recovery",
    "Side effects",
    "Security",
    "Governance",
    "Learning",
)


@dataclass(frozen=True)
class SuiteInventory:
    suite: str
    named_tests: tuple[str, ...]
    production_call_sites: tuple[str, ...]
    deferred: str | None = None


SUITES: tuple[SuiteInventory, ...] = (
    SuiteInventory(
        suite="Schema/contract",
        named_tests=(
            "tests/contract/test_schema_objects.py",
            "tests/contract/test_drift.py",
        ),
        production_call_sites=("schemas/objects/* plus generated engine.contracts",),
    ),
    SuiteInventory(
        suite="API",
        named_tests=(
            "tests/unit/test_gateway_api.py",
            "tests/unit/test_gateway_sessions.py",
            "tests/unit/test_client_parity_fixture.py",
        ),
        production_call_sites=("engine.gateway.commands.GatewayCommandService.accept",),
        deferred="Stale ETag / oversized payload / pagination: Gateway gaps",
    ),
    SuiteInventory(
        suite="MCP",
        named_tests=(
            "tests/contract/test_mcp_tool_declarations.py",
            "tests/unit/test_mcp_server.py",
        ),
        production_call_sites=(
            "interfaces.mcp.server.McpStdioServer",
            "engine.capabilities.lease_service.require_active",
        ),
    ),
    SuiteInventory(
        suite="Planning",
        named_tests=(
            "tests/unit/test_planning.py",
            "tests/unit/test_planning_postgres.py",
            "tests/recovery/test_replan_recovery.py",
        ),
        production_call_sites=(
            "engine.planning.validate.validate_graph",
            "engine.missions.service.MissionService.create_task_graph",
        ),
    ),
    SuiteInventory(
        suite="Context",
        named_tests=(
            "tests/unit/test_context_postgres.py",
            "tests/unit/test_context_assembly.py",
            "tests/unit/test_context_activation_postgres.py",
        ),
        production_call_sites=("engine.context.service.ContextService.compile",),
        deferred="EDR-0002 semantic default-off; EDR-0003 replay gates 2/4",
    ),
    SuiteInventory(
        suite="Routing",
        named_tests=(
            "tests/unit/test_routing_postgres.py",
            "tests/unit/test_routing_rules.py",
            "tests/unit/test_flight_lab_golden_mission.py",
            "tests/unit/test_simulation_scenarios.py",
        ),
        production_call_sites=(
            "engine.routing.service.RouterService.route",
            "engine.routing.rules.evaluate",
        ),
        deferred=(
            "Ch.6.10 pick-flip / distribution-shift harness is not a "
            "Ch.19.1 named fixture; exploration is structurally "
            "unreachable (selection_source never exploration)"
        ),
    ),
    SuiteInventory(
        suite="Worker protocol",
        named_tests=(
            "tests/unit/test_workers_postgres.py",
            "tests/recovery/test_workers_recovery.py",
            "tests/unit/test_kill_flag_process_sweep.py",
        ),
        production_call_sites=("engine.workers.service.WorkerManagerService",),
    ),
    SuiteInventory(
        suite="Environment",
        named_tests=(
            "tests/unit/test_workspaces_postgres.py",
            "tests/unit/test_flight_lab_golden_mission.py",
            "tests/unit/test_environments_postgres.py",
            "tests/unit/test_local_process_containment.py",
            "tests/unit/test_chaos_suite.py",
        ),
        production_call_sites=(
            "engine.workspaces.paths.resolve_within_workspace",
            "engine.workspaces.service.WorkspaceService.read/write",
            "engine.environments.service.ExecutionEnvironmentService.replace",
            "engine.workers.service.WorkerManagerService.resume_run",
        ),
        deferred=None,
    ),
    SuiteInventory(
        suite="Integration",
        named_tests=(
            "tests/unit/test_integration_queue_postgres.py",
            "tests/unit/test_flight_lab_force_push.py",
            "tests/unit/test_flight_lab_golden_mission.py",
        ),
        production_call_sites=(
            "engine.integration.service.IntegrationQueueService.integrate",
            "engine.integration.git.update_ref",
        ),
        deferred="Semantic-conflict repair insert; revert-as-task",
    ),
    SuiteInventory(
        suite="Verification",
        named_tests=(
            "tests/unit/test_verification_postgres.py",
            "tests/unit/test_cli_mission_trace_postgres.py",
            "tests/unit/test_flaky_quarantine.py",
            "tests/unit/test_mission_oracle_postgres.py",
        ),
        production_call_sites=("engine.verification.runner",),
        deferred="EDR-0007 mission-oracle wrong-product partial scope",
    ),
    SuiteInventory(
        suite="Recovery",
        named_tests=(
            "tests/recovery/test_cli_mission_trace_recovery.py",
            "tests/recovery/test_execution_recovery.py",
            "tests/recovery/test_events_recovery.py",
            "tests/unit/test_recovery_matrix.py",
        ),
        production_call_sites=("engine.recovery.service.ExternalEffectService",),
        deferred="EDR-0027 WS/SSE replay; full Core process-crash",
    ),
    SuiteInventory(
        suite="Side effects",
        named_tests=(
            "tests/unit/test_external_effects_postgres.py",
            "tests/recovery/test_external_effects_recovery.py",
        ),
        production_call_sites=(
            "engine.recovery.service.ExternalEffectService",
            "engine.integration.service.IntegrationQueueService.submit",
        ),
    ),
    SuiteInventory(
        suite="Security",
        named_tests=(
            "tests/unit/test_local_process_containment.py",
            "tests/unit/test_multi_tenant_isolation.py",
            "tests/unit/test_rls_enforcement.py",
            "tests/unit/test_flight_lab_golden_mission.py",
        ),
        production_call_sites=(
            "engine.environments.backends.local_process.LocalProcessBackend.run",
            "engine.workspaces.service.WorkspaceService.read",
        ),
        deferred="Donor prompt-injection / planted vuln dep",
    ),
    SuiteInventory(
        suite="Governance",
        named_tests=(
            "tests/unit/test_governance_approvals.py",
            "tests/unit/test_governance.py",
            "tests/recovery/test_governance_approvals_recovery.py",
        ),
        production_call_sites=("engine.governance.service.ApprovalService",),
    ),
    SuiteInventory(
        suite="Learning",
        named_tests=(
            "tests/unit/test_learning_eligibility_rules.py",
            "tests/unit/test_learning_activation_gates.py",
            "tests/unit/test_learning_canary_postgres.py",
            "tests/unit/test_flight_lab_golden_mission.py",
            "tests/unit/test_context_activation_postgres.py",
        ),
        production_call_sites=(
            "engine.learning.activation_service.LearningActivationService.rollback",
            "engine.context.activation_service.ContextActivationService.rollback",
        ),
        deferred="EDR-0005 RouteDecision.predicted_success remains null",
    ),
)


def assert_inventory_complete() -> None:
    names = tuple(item.suite for item in SUITES)
    if names != CH19_SUITE_NAMES:
        missing = set(CH19_SUITE_NAMES) - set(names)
        extra = set(names) - set(CH19_SUITE_NAMES)
        raise AssertionError(f"inventory drift missing={missing} extra={extra}")
