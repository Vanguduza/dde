"""`dde` console-script entry point -- DDE-015's general subcommand
framework, built by generalising DDE-014's single `mission trace`
`argparse` parser into `argparse` subparsers-of-subparsers: `mission
{create,status,trace}`, `task {list}`. Every subcommand here is real: it
performs a real `engine.*` service/repository call and produces real,
durable, independently re-readable side effects or output -- no stubbed
command, no fabricated result.

**Why stdlib `argparse`, still.** The mission brief is explicit, same as
DDE-014's: no new third-party CLI framework. `typer` remains an unused
`pyproject.toml` dependency; this module uses only `argparse`, generalised
to subparser groups rather than switched to a different framework.

**Why `--tenant-id` is required on every command.** Unchanged from
DDE-014: Stage 1 has no Gateway session/auth layer (`engine/gateway/app.py`
serves only `/healthz`/`/readyz`) that could supply a tenant scope
implicitly, and every `missions`-family table's row-level-security policy
is fail-closed on `current_setting('dde.tenant_id')`
(`schemas/sql/0001_stage1.sql`). Peeking at a row to discover its own
tenant before scoping the read/write would defeat that fail-closed
guarantee. `--project-id` is required only for `mission create` (a
project-scoped table needs it to know *which* project's mission this is,
and to check the project-unique slug constraint) and stays optional
everywhere else, exactly as DDE-014 established: once a mission row is
legitimately readable, its own `project_id` column serves every subsequent
call in that same command.

**What changed vs. DDE-014, and what did not.** `mission trace`'s parser
shape, its `build_mission_trace`/`independence_proofs`/
`render_mission_trace`/`require_complete_trace` call sequence, its exit
codes and its printed output are byte-for-byte unchanged -- see
`_cmd_mission_trace` below, which is DDE-014's original `main()` body
factored out verbatim into its own function so the existing `mission
trace` tests keep passing without modification. What changed is `main()`
itself: it now dispatches on `(object, action)` across four commands
    instead of hard-coding one.

**What changed vs. DDE-015, and what did not.** Every command now accepts
`--json`, which emits the same built structures as machine-readable JSON
(`contract.model_dump(mode="json")` shapes) instead of the text renderer.
Default behaviour is byte-for-byte unchanged: same renders, same exit codes,
same error mapping. `mission trace --json` prints before the Chapter 1
completeness check runs, so a caller can parse a trace and still observe
`MISSION_TRACE_INCOMPLETE`'s exit code.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from datetime import datetime
from uuid import UUID

from engine.core.errors import DdeError
from engine.gateway.settings import get_settings
from engine.truth.db import build_engine
from interfaces.cli.mission_create import create_mission, render_created_mission
from interfaces.cli.mission_status import build_mission_status, render_mission_status
from interfaces.cli.mission_trace import (
    EXIT_INCOMPLETE,
    EXIT_UNKNOWN_MISSION,
    MISSION_TRACE_INCOMPLETE,
    UNKNOWN_MISSION,
    build_mission_trace,
    independence_proofs,
    render_mission_trace,
    require_complete_trace,
)
from interfaces.cli.task_list import build_task_listing, render_task_listing

EXIT_OK = 0
EXIT_UNEXPECTED_ERROR = 1
EXIT_USAGE_ERROR = 2
#: A real, typed validation failure from an existing service call (e.g.
#: `MissionService.create_mission`'s "slug already used" `VERSION_CONFLICT`)
#: -- distinct from `EXIT_UNEXPECTED_ERROR`, which is reserved for a
#: `DdeError` code no command here otherwise recognises.
EXIT_VALIDATION_ERROR = 5


def _parse_uuid(value: str, *, flag: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{flag} must be a UUID: {value!r}") from exc


def _jsonify(value: object) -> object:
    """Recursive serializer for the CLI's built structures: engine contracts
    are Pydantic models (`model_dump(mode="json")`), CLI view objects are
    frozen dataclasses, everything else is JSON-native. One rule set for
    every command so `--json` output shapes stay predictable."""
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _jsonify(v) for k, v in asdict(value).items()}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (list, tuple, set)):
        return [_jsonify(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items()}
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    return value


def _add_tenant_project_database_args(
    parser: argparse.ArgumentParser, *, project_required: bool
) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the text rendering.",
    )
    parser.add_argument(
        "--tenant-id",
        required=True,
        type=str,
        help=(
            "Tenant UUID that owns this mission. Required: Stage 1 has no "
            "session/auth layer to derive it automatically, and no command "
            "here ever bypasses row-level security to guess it."
        ),
    )
    if project_required:
        parser.add_argument(
            "--project-id",
            required=True,
            type=str,
            help="Project UUID this mission belongs to.",
        )
    else:
        parser.add_argument(
            "--project-id",
            required=False,
            type=str,
            default=None,
            help="Project UUID. Optional: resolved from the mission row if omitted.",
        )
    parser.add_argument(
        "--database-url",
        required=False,
        type=str,
        default=None,
        help="Override DDE_DATABASE_URL for this invocation.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dde",
        description=(
            "DDE control-plane CLI -- a thin, real client over the "
            "engine services that already exist end to end as of Stage 1 "
            "(mission -> task graph -> ... -> evidence). No Gateway/HTTP "
            "hop, no fabricated results: every command performs a real "
            "service call."
        ),
    )
    subparsers = parser.add_subparsers(dest="object", required=True)

    mission = subparsers.add_parser("mission", help="Mission-scoped commands")
    mission_actions = mission.add_subparsers(dest="action", required=True)

    create = mission_actions.add_parser(
        "create",
        help="Persist a new Mission via engine.missions.MissionService",
    )
    _add_tenant_project_database_args(create, project_required=True)
    create.add_argument(
        "--slug",
        required=True,
        type=str,
        help="Project-unique, immutable mission slug",
    )
    create.add_argument(
        "--title", required=True, type=str, help="Human-readable mission title"
    )
    create.add_argument(
        "--intent", required=True, type=str, help="Free-text mission intent"
    )
    create.add_argument(
        "--success-definition",
        required=True,
        type=str,
        help="Free-text definition of mission success",
    )
    create.add_argument(
        "--scope",
        action="append",
        default=[],
        metavar="PATH",
        help="Repository path/module in this mission's scope. Repeatable.",
    )
    create.add_argument(
        "--requirement-ref",
        dest="requirement_refs",
        action="append",
        default=[],
        metavar="SLUG",
        help="Approved requirement slug this mission fulfils. Repeatable.",
    )
    create.add_argument(
        "--autonomy-ceiling",
        required=True,
        type=int,
        help="Maximum autonomy level (Chapter 13) any task in this mission may reach",
    )

    status = mission_actions.add_parser(
        "status",
        help=(
            "Print a mission's current status, task-status histogram and "
            "TaskGraph(s) -- a lighter-weight complement to `mission trace`"
        ),
    )
    status.add_argument("mission_id", type=str, help="Mission UUID to inspect")
    _add_tenant_project_database_args(status, project_required=False)

    trace = mission_actions.add_parser(
        "trace",
        help=(
            "Reconstruct and print a mission's full spine "
            "(Chapter 18.2's Stage 1 exit gate)"
        ),
    )
    trace.add_argument("mission_id", type=str, help="Mission UUID to trace")
    _add_tenant_project_database_args(trace, project_required=False)

    task = subparsers.add_parser("task", help="Task-scoped commands")
    task_actions = task.add_subparsers(dest="action", required=True)

    task_list_parser = task_actions.add_parser(
        "list", help="List every persisted Task for a mission"
    )
    task_list_parser.add_argument(
        "mission_id", type=str, help="Mission UUID whose tasks to list"
    )
    _add_tenant_project_database_args(task_list_parser, project_required=False)

    return parser


def _cmd_mission_create(args: argparse.Namespace) -> int:
    try:
        tenant_id = _parse_uuid(args.tenant_id, flag="--tenant-id")
        project_id = _parse_uuid(args.project_id, flag="--project-id")
    except argparse.ArgumentTypeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    try:
        return asyncio.run(
            _run_mission_create(
                tenant_id=tenant_id,
                project_id=project_id,
                slug=args.slug,
                title=args.title,
                intent=args.intent,
                success_definition=args.success_definition,
                scope=list(args.scope),
                requirement_refs=list(args.requirement_refs),
                autonomy_ceiling=args.autonomy_ceiling,
                database_url=args.database_url,
                as_json=args.json,
            )
        )
    except DdeError as exc:
        print(f"error[{exc.error_code}]: {exc.message}", file=sys.stderr)
        if exc.error_code == "VERSION_CONFLICT":
            return EXIT_VALIDATION_ERROR
        return EXIT_UNEXPECTED_ERROR


async def _run_mission_create(
    *,
    tenant_id: UUID,
    project_id: UUID,
    slug: str,
    title: str,
    intent: str,
    success_definition: str,
    scope: list[str],
    requirement_refs: list[str],
    autonomy_ceiling: int,
    database_url: str | None,
    as_json: bool,
) -> int:
    engine = build_engine(database_url or get_settings().database_url)
    try:
        mission = await create_mission(
            engine,
            tenant_id=tenant_id,
            project_id=project_id,
            slug=slug,
            title=title,
            intent=intent,
            success_definition=success_definition,
            scope=scope,
            requirement_refs=requirement_refs,
            autonomy_ceiling=autonomy_ceiling,
        )
    finally:
        await engine.dispose()
    if as_json:
        print(json.dumps(_jsonify(mission), indent=2))
    else:
        print(render_created_mission(mission))
    return EXIT_OK


def _cmd_mission_status(args: argparse.Namespace) -> int:
    try:
        mission_id = _parse_uuid(args.mission_id, flag="mission_id")
        tenant_id = _parse_uuid(args.tenant_id, flag="--tenant-id")
        project_id = (
            _parse_uuid(args.project_id, flag="--project-id")
            if args.project_id
            else None
        )
    except argparse.ArgumentTypeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    try:
        return asyncio.run(
            _run_mission_status(
                mission_id=mission_id,
                tenant_id=tenant_id,
                project_id=project_id,
                database_url=args.database_url,
                as_json=args.json,
            )
        )
    except DdeError as exc:
        print(f"error[{exc.error_code}]: {exc.message}", file=sys.stderr)
        if exc.error_code == UNKNOWN_MISSION:
            return EXIT_UNKNOWN_MISSION
        return EXIT_UNEXPECTED_ERROR


async def _run_mission_status(
    *,
    mission_id: UUID,
    tenant_id: UUID,
    project_id: UUID | None,
    database_url: str | None,
    as_json: bool,
) -> int:
    engine = build_engine(database_url or get_settings().database_url)
    try:
        status = await build_mission_status(
            engine, tenant_id=tenant_id, mission_id=mission_id, project_id=project_id
        )
    finally:
        await engine.dispose()
    if as_json:
        print(json.dumps(_jsonify(status), indent=2))
    else:
        print(render_mission_status(status))
    return EXIT_OK


def _cmd_mission_trace(args: argparse.Namespace) -> int:
    """DDE-014's original `main()` body, factored out unchanged: same UUID
    parsing, same `build_mission_trace`/`independence_proofs`/
    `render_mission_trace`/`require_complete_trace` sequence, same exit
    codes. Behaviour is not modified by this mission."""
    try:
        mission_id = _parse_uuid(args.mission_id, flag="mission_id")
        tenant_id = _parse_uuid(args.tenant_id, flag="--tenant-id")
        project_id = (
            _parse_uuid(args.project_id, flag="--project-id")
            if args.project_id
            else None
        )
    except argparse.ArgumentTypeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    try:
        return asyncio.run(
            _run_trace(
                mission_id=mission_id,
                tenant_id=tenant_id,
                project_id=project_id,
                database_url=args.database_url,
                as_json=args.json,
            )
        )
    except DdeError as exc:
        print(f"error[{exc.error_code}]: {exc.message}", file=sys.stderr)
        if exc.error_code == UNKNOWN_MISSION:
            return EXIT_UNKNOWN_MISSION
        if exc.error_code == MISSION_TRACE_INCOMPLETE:
            return EXIT_INCOMPLETE
        return EXIT_UNEXPECTED_ERROR


async def _run_trace(
    *,
    mission_id: UUID,
    tenant_id: UUID,
    project_id: UUID | None,
    database_url: str | None,
    as_json: bool,
) -> int:
    engine = build_engine(database_url or get_settings().database_url)
    try:
        trace = await build_mission_trace(
            engine, tenant_id=tenant_id, mission_id=mission_id, project_id=project_id
        )
    finally:
        await engine.dispose()

    proofs = independence_proofs(trace)
    if as_json:
        print(
            json.dumps(
                _jsonify({"trace": trace, "independence_proofs": proofs}), indent=2
            )
        )
    else:
        print(render_mission_trace(trace, proofs))
    require_complete_trace(trace, proofs)
    return 0


def _cmd_task_list(args: argparse.Namespace) -> int:
    try:
        mission_id = _parse_uuid(args.mission_id, flag="mission_id")
        tenant_id = _parse_uuid(args.tenant_id, flag="--tenant-id")
        project_id = (
            _parse_uuid(args.project_id, flag="--project-id")
            if args.project_id
            else None
        )
    except argparse.ArgumentTypeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    try:
        return asyncio.run(
            _run_task_list(
                mission_id=mission_id,
                tenant_id=tenant_id,
                project_id=project_id,
                database_url=args.database_url,
                as_json=args.json,
            )
        )
    except DdeError as exc:
        print(f"error[{exc.error_code}]: {exc.message}", file=sys.stderr)
        if exc.error_code == UNKNOWN_MISSION:
            return EXIT_UNKNOWN_MISSION
        return EXIT_UNEXPECTED_ERROR


async def _run_task_list(
    *,
    mission_id: UUID,
    tenant_id: UUID,
    project_id: UUID | None,
    database_url: str | None,
    as_json: bool,
) -> int:
    engine = build_engine(database_url or get_settings().database_url)
    try:
        listing = await build_task_listing(
            engine, tenant_id=tenant_id, mission_id=mission_id, project_id=project_id
        )
    finally:
        await engine.dispose()
    if as_json:
        print(json.dumps(_jsonify(listing), indent=2))
    else:
        print(render_task_listing(listing))
    return EXIT_OK


_DISPATCH: dict[tuple[str, str], Callable[[argparse.Namespace], int]] = {
    ("mission", "create"): _cmd_mission_create,
    ("mission", "status"): _cmd_mission_status,
    ("mission", "trace"): _cmd_mission_trace,
    ("task", "list"): _cmd_task_list,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = _DISPATCH.get((args.object, args.action))
    if handler is None:  # pragma: no cover -- every subparser group above
        # is `required=True`, so argparse itself rejects any `(object,
        # action)` pair not in `_DISPATCH` before `main` ever sees it.
        parser.print_usage(sys.stderr)
        return EXIT_USAGE_ERROR
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
