"""Durable schedules and conditional future-work proposals for DDE Chat."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.ai_automation import AiAutomation
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.fabric.repository import FabricRepository
from engine.fabric.tables import ai_automations


@dataclass(frozen=True)
class AutomationProposal:
    automation_id: UUID
    action_kind: str
    action_payload: dict[str, object]
    idempotency_key: str


def _parse_int(value: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise DdeError("VALIDATION_FAILED", f"invalid schedule value: {value}") from exc
    if not minimum <= parsed <= maximum:
        raise DdeError(
            "VALIDATION_FAILED", f"schedule value {value} outside {minimum}..{maximum}"
        )
    return parsed


def _cron_values(field: str, minimum: int, maximum: int) -> frozenset[int]:
    values: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if part == "*":
            values.update(range(minimum, maximum + 1))
        elif part.startswith("*/"):
            step = _parse_int(part[2:], 1, maximum - minimum + 1)
            values.update(range(minimum, maximum + 1, step))
        else:
            values.add(_parse_int(part, minimum, maximum))
    if not values:
        raise DdeError("VALIDATION_FAILED", "empty cron field")
    return frozenset(values)


def parse_cron(expression: str) -> tuple[frozenset[int], ...]:
    parts = expression.split()
    if len(parts) != 5:
        raise DdeError("VALIDATION_FAILED", "cron expression must have five fields")
    return (
        _cron_values(parts[0], 0, 59),
        _cron_values(parts[1], 0, 23),
        _cron_values(parts[2], 1, 31),
        _cron_values(parts[3], 1, 12),
        _cron_values(parts[4], 0, 6),
    )


def _cron_weekday(value: datetime) -> int:
    # Python Monday=0; cron Sunday=0.
    return (value.weekday() + 1) % 7


def next_cron_at(expression: str, *, after: datetime, timezone: str) -> datetime:
    fields = parse_cron(expression)
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise DdeError("VALIDATION_FAILED", f"unknown timezone {timezone}") from exc
    local = after.astimezone(tz).replace(second=0, microsecond=0) + timedelta(minutes=1)
    # Bound search to 5 years. If an impossible date (e.g. February 31) was
    # requested, fail rather than spinning forever.
    for _ in range(5 * 366 * 24 * 60):
        minute, hour, day, month, weekday = fields
        if (
            local.minute in minute
            and local.hour in hour
            and local.day in day
            and local.month in month
            and _cron_weekday(local) in weekday
        ):
            return local.astimezone(UTC)
        local += timedelta(minutes=1)
    raise DdeError(
        "VALIDATION_FAILED", "cron expression has no occurrence within five years"
    )


def next_run_at(
    kind: str, expression: str, *, now: datetime, timezone: str
) -> datetime | None:
    if kind == "CONDITION":
        return None
    if kind == "ONCE":
        try:
            value = datetime.fromisoformat(expression.replace("Z", "+00:00"))
        except ValueError as exc:
            raise DdeError(
                "VALIDATION_FAILED", "ONCE schedule must be ISO-8601"
            ) from exc
        if value.tzinfo is None:
            try:
                value = value.replace(tzinfo=ZoneInfo(timezone))
            except ZoneInfoNotFoundError as exc:
                raise DdeError(
                    "VALIDATION_FAILED", f"unknown timezone {timezone}"
                ) from exc
        return value.astimezone(UTC)
    if kind == "INTERVAL":
        raw = expression.removeprefix("seconds:").strip()
        seconds = _parse_int(raw, 60, 31_536_000)
        return now.astimezone(UTC) + timedelta(seconds=seconds)
    if kind == "CRON":
        return next_cron_at(expression, after=now, timezone=timezone)
    raise DdeError("VALIDATION_FAILED", f"unknown schedule kind {kind}")


def condition_matches(condition: object, context: dict[str, object]) -> bool:
    """Evaluate a deliberately small deterministic condition language.

    Shapes: {"all":[...]}, {"any":[...]}, {"not":...}, or
    {"path":"verification.state","op":"eq|ne|gt|gte|lt|lte|in|exists","value":...}.
    """
    if not isinstance(condition, dict):
        return False
    if "all" in condition:
        rows = condition["all"]
        return isinstance(rows, list) and all(
            condition_matches(item, context) for item in rows
        )
    if "any" in condition:
        rows = condition["any"]
        return isinstance(rows, list) and any(
            condition_matches(item, context) for item in rows
        )
    if "not" in condition:
        return not condition_matches(condition["not"], context)
    path = condition.get("path")
    op = condition.get("op", "eq")
    if not isinstance(path, str):
        return False
    current: object = context
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            current = None
            break
        current = current[part]
    expected = condition.get("value")
    if op == "exists":
        return current is not None
    if op == "eq":
        return current == expected
    if op == "ne":
        return current != expected
    if op == "in":
        return isinstance(expected, list) and current in expected
    if op in {"gt", "gte", "lt", "lte"}:
        if not isinstance(current, (int, float)) or isinstance(current, bool):
            return False
        if not isinstance(expected, (int, float)) or isinstance(expected, bool):
            return False
        if op == "gt":
            return current > expected
        if op == "gte":
            return current >= expected
        if op == "lt":
            return current < expected
        return current <= expected
    return False


class AutomationService:
    def __init__(self, engine: AsyncEngine) -> None:
        self.repo = FabricRepository(engine)

    async def create(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        conversation_id: UUID,
        name: str,
        schedule_kind: str,
        schedule_expression: str,
        timezone: str,
        action_kind: str,
        action_payload: dict[str, object],
        mission_id: UUID | None = None,
        created_by: UUID | None = None,
        now: datetime | None = None,
    ) -> AiAutomation:
        if not name.strip():
            raise DdeError("VALIDATION_FAILED", "automation name is required")
        observed = now or datetime.now(UTC)
        next_at = next_run_at(
            schedule_kind, schedule_expression, now=observed, timezone=timezone
        )
        if (
            schedule_kind == "ONCE"
            and next_at is not None
            and next_at <= observed.astimezone(UTC)
        ):
            raise DdeError(
                "VALIDATION_FAILED", "one-time automation must be in the future"
            )
        values: dict[str, object] = {
            "automation_id": uuid7(),
            "tenant_id": tenant_id,
            "project_id": project_id,
            "conversation_id": conversation_id,
            "mission_id": mission_id,
            "name": name.strip(),
            "schedule_kind": schedule_kind,
            "schedule_expression": schedule_expression,
            "timezone": timezone,
            "action_kind": action_kind,
            "action_payload": action_payload,
            "state": "ACTIVE",
            "next_run_at": next_at,
            "last_run_at": None,
            "last_result_ref": None,
            "run_count": 0,
            "created_by": created_by,
            "lock_version": 1,
            "created_at": observed,
            "updated_at": observed,
        }
        AiAutomation.model_validate(values)
        return await self.repo.insert_model(
            table=ai_automations,
            model=AiAutomation,
            tenant_id=tenant_id,
            project_id=project_id,
            values=values,
        )

    async def due(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        now: datetime | None = None,
        condition_context: dict[str, object] | None = None,
    ) -> tuple[AutomationProposal, ...]:
        observed = (now or datetime.now(UTC)).astimezone(UTC)
        rows = await self.repo.list_models(
            table=ai_automations,
            model=AiAutomation,
            tenant_id=tenant_id,
            project_id=project_id,
            filters={"state": "ACTIVE"},
            order_by=(ai_automations.c.created_at.asc(),),
            limit=500,
        )
        proposals = []
        for row in rows:
            is_due = row.next_run_at is not None and row.next_run_at <= observed
            if row.schedule_kind == "CONDITION":
                is_due = condition_matches(
                    row.action_payload.get("condition"), condition_context or {}
                )
            if is_due:
                proposals.append(
                    AutomationProposal(
                        row.automation_id,
                        row.action_kind,
                        row.action_payload,
                        f"fabric:auto:{row.automation_id}:{row.run_count + 1}",
                    )
                )
        return tuple(proposals)

    async def record_result(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        automation_id: UUID,
        lock_version: int,
        result_ref: str,
        succeeded: bool,
        now: datetime | None = None,
    ) -> AiAutomation:
        row = await self.get(
            tenant_id=tenant_id, project_id=project_id, automation_id=automation_id
        )
        if row.state != "ACTIVE":
            raise DdeError("VERSION_CONFLICT", "automation is not active")
        observed = (now or datetime.now(UTC)).astimezone(UTC)
        state = "ACTIVE" if succeeded else "BLOCKED"
        next_at = None
        if succeeded:
            if row.schedule_kind == "ONCE":
                state = "COMPLETED"
            elif row.schedule_kind != "CONDITION":
                next_at = next_run_at(
                    row.schedule_kind,
                    row.schedule_expression,
                    now=observed,
                    timezone=row.timezone,
                )
        return await self.repo.update_locked(
            table=ai_automations,
            model=AiAutomation,
            id_column="automation_id",
            object_id=automation_id,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            values={
                "state": state,
                "next_run_at": next_at,
                "last_run_at": observed,
                "last_result_ref": result_ref,
                "run_count": row.run_count + 1,
                "updated_at": observed,
            },
        )

    async def set_state(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        automation_id: UUID,
        lock_version: int,
        state: str,
    ) -> AiAutomation:
        row = await self.get(
            tenant_id=tenant_id, project_id=project_id, automation_id=automation_id
        )
        legal = {
            "ACTIVE": {"PAUSED", "CANCELLED"},
            "PAUSED": {"ACTIVE", "CANCELLED"},
            "BLOCKED": {"ACTIVE", "CANCELLED"},
        }
        if state not in legal.get(row.state, set()):
            raise DdeError("VERSION_CONFLICT", "illegal automation state transition")
        next_at = row.next_run_at
        if state == "ACTIVE" and row.schedule_kind != "CONDITION":
            next_at = next_run_at(
                row.schedule_kind,
                row.schedule_expression,
                now=datetime.now(UTC),
                timezone=row.timezone,
            )
        return await self.repo.update_locked(
            table=ai_automations,
            model=AiAutomation,
            id_column="automation_id",
            object_id=automation_id,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            values={
                "state": state,
                "next_run_at": next_at,
                "updated_at": datetime.now(UTC),
            },
        )

    async def get(
        self, *, tenant_id: UUID, project_id: UUID, automation_id: UUID
    ) -> AiAutomation:
        return await self.repo.get_model(
            table=ai_automations,
            model=AiAutomation,
            id_column="automation_id",
            object_id=automation_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )

    async def list_for_conversation(
        self, *, tenant_id: UUID, project_id: UUID, conversation_id: UUID
    ) -> tuple[AiAutomation, ...]:
        return await self.repo.list_models(
            table=ai_automations,
            model=AiAutomation,
            tenant_id=tenant_id,
            project_id=project_id,
            filters={"conversation_id": conversation_id},
            order_by=(ai_automations.c.updated_at.desc(),),
        )
