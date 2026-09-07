"""Import-boundary tests beyond DDE-001 layout checks.

Extended by DDE-004 to cover `audit_events` alongside the three Project
Truth tables, and by DDE-006 (later corrected — see below) to cover the
Stage 1 mission-spine tables: each durable table name below may only appear
as a string literal inside its owning module's directory (Chapter 3.8's
"one authoritative owner per mutable state").

Chapter 3.8 lists `TaskGraph`'s owner module as `planning` and `Task`'s as
`missions`. DDE-006 initially consolidated `missions`/`task_graphs`/`tasks`/
`task_graph_edges` under `engine.missions` as a flagged, intentional
divergence; this corrects that split so `task_graphs`/`task_graph_edges` map
to `engine.planning` (`engine/planning/tables.py`,
`engine/planning/repository.py`) and `missions`/`tasks` map to
`engine.missions` (`engine/missions/tables.py`,
`engine/missions/repository.py`), matching the blueprint exactly.

DDE-008 adds `context_packages`, owned by `engine.context` (Chapter 3.8:
ContextPackage's owner module is `context`).

DDE-009 adds `route_decisions`, owned by `engine.routing` (Chapter 3.8:
RouteDecision's owner module is `routing`).

DDE-010 adds `execution_plans`, `execution_environments` and `workspaces`,
owned respectively by `engine.execution`, `engine.environments` and
`engine.workspaces` (Chapter 3.8's ownership matrix).

DDE-011 adds `task_attempts` (owned by `engine.missions` per Chapter 3.8,
via the new, additive `engine/missions/attempts.py` — see that module's
docstring for why it lives there rather than in a new module) and
`worker_runs`/`worker_events` (owned by `engine.workers`, Chapter 3.8).

DDE-012 adds `acceptance_oracles`, `verification_runs` and `evidence`, all
owned by `engine.verification` (Chapter 3.6's repository layout: "oracle,
runners, product envs"; Chapter 3.8's matrix lists `VerificationRun` and
`Evidence` under the same owner).

DDE-013 adds `write_scope_leases` and `integration_proposals`, owned by
`engine.integration` (Chapter 3.6's repository layout: "merge queue + write
scopes"; Chapter 3.8's matrix gives `WriteScopeLease` its own explicit
`integration` row).

DDE-016 adds `capabilities`, owned by `engine.capabilities` (Chapter 3.6's
repository layout: "registry, leases, proxy, broker"). Unlike every table
above, `capabilities` is a Chapter 3.2 global registry with no `tenant_id`/
`project_id` columns of its own.

DDE-017 adds `capability_leases`, also owned by `engine.capabilities`
(same Chapter 3.6 repository-layout line -- "registry, leases, proxy,
broker" -- and Chapter 3.8's matrix gives `CapabilityLease` its own
`engine.capabilities` row, "Lease manager"), tenant/project-scoped unlike
its sibling `capabilities` table.

DDE-019 adds `credential_handles`, owned by the `broker` subpackage of
`engine.capabilities` (`engine/capabilities/broker/`) -- AGENTS.md's literal
boundary rule ("Nothing except `engine/capabilities/broker/**` reads secret
material") and Chapter 3.8's matrix give "Credential handle" its own row,
distinct from `CapabilityLease`'s: owner module `capabilities/broker`,
created by "Credential Broker". `owner in path.parts` matches this exactly,
since `broker` is a real subdirectory, not merely a table-owner label.

DDE-020 adds `external_effects`, owned by `engine.recovery` (Chapter 3.6's
repository layout: "checkpoints, effects, replay"; Chapter 3.8's matrix
gives `ExternalEffect` its own row: owner module `recovery`, created by
"Capability adapter"). The actual insert/transition calls are made from
`engine.workers.scripted_adapter`/`engine.workspaces.service` (the real
capability-adapter call sites), but the table name `"external_effects"`
itself is only ever a string literal inside `engine/recovery/`, mirroring
`credential_handles`' identical split between writer module and calling
module.

DDE-021 adds `diff_gate_reports` and `dependency_admissions`, owned by
`engine.integration` (Chapter 9.7: gates are "blocking verification steps
rather than registry entries"; Chapter 10.4 step 3 runs them on the merge
queue). Table-name literals live in `engine/integration/tables.py` and
`engine/integration/repository.py`.

DDE-023 adds `checkpoints`, owned by `engine.recovery` (Chapter 3.6:
"checkpoints, effects, replay"). Table-name literals live in
`engine/recovery/tables.py` and `engine/recovery/checkpoint_repository.py`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TABLE_OWNERS = {
    "product_constitution_versions": "truth",
    "requirements": "truth",
    "edrs": "truth",
    "audit_events": "audit",
    "missions": "missions",
    "tasks": "missions",
    "task_graphs": "planning",
    "task_graph_edges": "planning",
    "context_packages": "context",
    "route_decisions": "routing",
    "execution_plans": "execution",
    "execution_environments": "environments",
    "workspaces": "workspaces",
    "task_attempts": "missions",
    "worker_runs": "workers",
    "worker_events": "workers",
    "acceptance_oracles": "verification",
    "verification_runs": "verification",
    "evidence": "verification",
    "write_scope_leases": "integration",
    "integration_proposals": "integration",
    "capabilities": "capabilities",
    "capability_leases": "capabilities",
    "credential_handles": "broker",
    "external_effects": "recovery",
    "diff_gate_reports": "integration",
    "dependency_admissions": "integration",
    "checkpoints": "recovery",
    "mission_oracle_evaluations": "verification",
}


_SQL_WRITE = re.compile(
    r"\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)
_WRITE_CALLS = frozenset({"insert", "update", "delete"})


def _imported_table_aliases(tree: ast.Module) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if not node.module.endswith(".tables"):
            continue
        for imported in node.names:
            if imported.name in TABLE_OWNERS:
                aliases[imported.asname or imported.name] = imported.name
    return aliases


def _table_name(expr: ast.expr, aliases: dict[str, str]) -> str | None:
    if isinstance(expr, ast.Name):
        if expr.id in aliases:
            return aliases[expr.id]
        if expr.id in TABLE_OWNERS:
            return expr.id
    return None


def _call_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def test_only_the_owning_module_writes_its_tables() -> None:
    offenders: list[str] = []
    for path in (ROOT / "engine").rglob("*.py"):
        if "contracts" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliases = _imported_table_aliases(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call_name = _call_name(node.func)
            table: str | None = None
            if call_name in _WRITE_CALLS:
                if isinstance(node.func, ast.Attribute):
                    table = _table_name(node.func.value, aliases)
                elif node.args:
                    table = _table_name(node.args[0], aliases)
            if table is not None:
                owner = TABLE_OWNERS[table]
                if owner not in path.parts:
                    offenders.append(f"{path}:{table}:{call_name}")

            if call_name != "text" or not node.args:
                continue
            sql = node.args[0]
            if not isinstance(sql, ast.Constant) or not isinstance(sql.value, str):
                continue
            for match in _SQL_WRITE.finditer(sql.value):
                table = match.group(1).lower()
                owner = TABLE_OWNERS.get(table)
                if owner is not None and owner not in path.parts:
                    offenders.append(f"{path}:{table}:sql")
    assert offenders == []
