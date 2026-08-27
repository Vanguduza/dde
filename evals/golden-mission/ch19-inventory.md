# Chapter 19.1 Flight Lab inventory (DDE-060)

Machine-readable SSOT: `tests/support/flight_lab_inventory.py`.
This file is the human catalog. Named tests are **existing** fixtures
unless marked as DDE-060 Flight Lab. Do not treat a unit test as the
Flight Lab unless this mission's S7 scenario files are listed.

Golden mission identity: `MISSION-ERP-000421` — Implement supplier
credit limits (`REQ-AP-019`). Executable spine is the Stage-1
verification-terminated graph, not a manufactured seven-node ERP
product. S7 scenarios: worker outage (`RouterService.route`) and
policy rollback (`LearningActivationService.rollback`).

| Suite | Named tests | Production call sites | Deferred |
|---|---|---|---|
| Schema/contract | `tests/contract/test_schema_objects.py`, `tests/contract/test_drift.py` | generated `engine.contracts` | |
| API | `tests/unit/test_gateway_api.py`, `tests/unit/test_gateway_sessions.py`, `tests/unit/test_client_parity_fixture.py` | `GatewayCommandService.accept` | Stale ETag / oversized payload / pagination |
| MCP | `tests/contract/test_mcp_tool_declarations.py`, `tests/unit/test_mcp_server.py` | `McpStdioServer`, `require_active` | |
| Planning | `tests/unit/test_planning.py`, `tests/unit/test_planning_postgres.py`, `tests/recovery/test_replan_recovery.py` | `validate_graph`, `MissionService.create_task_graph` | |
| Context | `tests/unit/test_context_postgres.py`, `tests/unit/test_context_assembly.py`, `tests/unit/test_context_activation_postgres.py` | `ContextService.compile` | EDR-0002, EDR-0003 |
| Routing | `tests/unit/test_routing_postgres.py`, `tests/unit/test_routing_rules.py`, `tests/unit/test_flight_lab_golden_mission.py`, `tests/unit/test_simulation_scenarios.py` | `RouterService.route` | Ch.6.10 pick-flip / distribution-shift harness; exploration structurally unreachable |
| Worker protocol | `tests/unit/test_workers_postgres.py`, `tests/recovery/test_workers_recovery.py`, `tests/unit/test_kill_flag_process_sweep.py` | `WorkerManagerService` | |
| Environment | `tests/unit/test_workspaces_postgres.py`, `tests/unit/test_flight_lab_golden_mission.py`, `tests/unit/test_environments_postgres.py`, `tests/unit/test_local_process_containment.py`, `tests/unit/test_chaos_suite.py` | `WorkspaceService.read/write`, `ExecutionEnvironmentService.replace`, `WorkerManagerService.resume_run` | |
| Integration | `tests/unit/test_integration_queue_postgres.py`, `tests/unit/test_flight_lab_force_push.py`, `tests/unit/test_flight_lab_golden_mission.py` | `IntegrationQueueService.integrate`, `git.update_ref` | Semantic-conflict repair insert; revert-as-task |
| Verification | `tests/unit/test_verification_postgres.py`, `tests/unit/test_cli_mission_trace_postgres.py`, `tests/unit/test_flaky_quarantine.py`, `tests/unit/test_mission_oracle_postgres.py` | `engine.verification.runner` | EDR-0007 |
| Recovery | `tests/recovery/test_cli_mission_trace_recovery.py`, `tests/recovery/test_execution_recovery.py`, `tests/recovery/test_events_recovery.py`, `tests/unit/test_recovery_matrix.py` | `ExternalEffectService` | EDR-0027; full Core process-crash |
| Side effects | `tests/unit/test_external_effects_postgres.py`, `tests/recovery/test_external_effects_recovery.py` | `ExternalEffectService`, `IntegrationQueueService.submit` | |
| Security | `tests/unit/test_local_process_containment.py`, `tests/unit/test_multi_tenant_isolation.py`, `tests/unit/test_rls_enforcement.py`, `tests/unit/test_flight_lab_golden_mission.py` | `LocalProcessBackend.run`, `WorkspaceService.read` | Donor prompt-injection / planted vuln dep |
| Governance | `tests/unit/test_governance_approvals.py`, `tests/unit/test_governance.py`, `tests/recovery/test_governance_approvals_recovery.py` | `ApprovalService` | |
| Learning | `tests/unit/test_learning_eligibility_rules.py`, `tests/unit/test_learning_activation_gates.py`, `tests/unit/test_learning_canary_postgres.py`, `tests/unit/test_flight_lab_golden_mission.py`, `tests/unit/test_context_activation_postgres.py` | `LearningActivationService.rollback` / `attempt_advance`, `ContextActivationService.rollback` | EDR-0005 |

Chaos (`evals/chaos/catalog.md`) is the DDE-061 suite. Full Core OS process-crash remains EDR-0027.
