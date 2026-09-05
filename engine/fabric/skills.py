"""Versioned AI skill candidate/evaluation/certification authority."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.contracts.ai_skill import AiSkill
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.fabric.repository import FabricRepository
from engine.fabric.tables import ai_skills


def skill_manifest_hash(
    *,
    instructions: str,
    capabilities: list[str],
    toolsets: list[str],
    source_ref: str | None,
) -> str:
    payload = {
        "instructions": instructions,
        "capabilities": sorted(capabilities),
        "toolsets": sorted(toolsets),
        "source_ref": source_ref,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class SkillService:
    def __init__(self, engine: AsyncEngine) -> None:
        self.repo = FabricRepository(engine)

    async def propose(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        slug: str,
        version: str,
        title: str,
        description: str,
        instructions: str,
        source_kind: str,
        source_ref: str | None,
        provenance_refs: list[str],
        license: str | None,
        required_capability_ids: list[str],
        toolset_ids: list[str],
        parent_skill_id: UUID | None = None,
    ) -> AiSkill:
        if not all(item.strip() for item in (slug, version, title, instructions)):
            raise DdeError(
                "VALIDATION_FAILED",
                "skill slug/version/title/instructions are required",
            )
        now = datetime.now(UTC)
        values: dict[str, object] = {
            "skill_id": uuid7(),
            "tenant_id": tenant_id,
            "project_id": project_id,
            "slug": slug.strip(),
            "version": version.strip(),
            "title": title.strip(),
            "description": description.strip(),
            "instructions": instructions,
            "source_kind": source_kind,
            "source_ref": source_ref,
            "provenance_refs": provenance_refs,
            "license": license,
            "manifest_hash": skill_manifest_hash(
                instructions=instructions,
                capabilities=required_capability_ids,
                toolsets=toolset_ids,
                source_ref=source_ref,
            ),
            "required_capability_ids": sorted(set(required_capability_ids)),
            "toolset_ids": sorted(set(toolset_ids)),
            "status": "CANDIDATE",
            "evaluation_refs": [],
            "certified_by": None,
            "certified_at": None,
            "parent_skill_id": parent_skill_id,
            "lock_version": 1,
            "created_at": now,
            "updated_at": now,
        }
        AiSkill.model_validate(values)
        return await self.repo.insert_model(
            table=ai_skills,
            model=AiSkill,
            tenant_id=tenant_id,
            project_id=project_id,
            values=values,
        )

    async def begin_evaluation(
        self, *, tenant_id: UUID, project_id: UUID, skill_id: UUID, lock_version: int
    ) -> AiSkill:
        current = await self.get(
            tenant_id=tenant_id, project_id=project_id, skill_id=skill_id
        )
        if current.status != "CANDIDATE":
            raise DdeError("VERSION_CONFLICT", "only candidate skills enter evaluation")
        return await self.repo.update_locked(
            table=ai_skills,
            model=AiSkill,
            id_column="skill_id",
            object_id=skill_id,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            values={"status": "EVALUATING", "updated_at": datetime.now(UTC)},
        )

    async def certify(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        skill_id: UUID,
        principal_id: UUID,
        evaluation_refs: list[str],
        lock_version: int,
    ) -> AiSkill:
        current = await self.get(
            tenant_id=tenant_id, project_id=project_id, skill_id=skill_id
        )
        if current.status != "EVALUATING":
            raise DdeError(
                "VERSION_CONFLICT", "skill must be evaluated before certification"
            )
        if not evaluation_refs:
            raise DdeError(
                "EVIDENCE_MISSING", "skill certification requires evaluation evidence"
            )
        now = datetime.now(UTC)
        return await self.repo.update_locked(
            table=ai_skills,
            model=AiSkill,
            id_column="skill_id",
            object_id=skill_id,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            values={
                "status": "CERTIFIED",
                "evaluation_refs": evaluation_refs,
                "certified_by": principal_id,
                "certified_at": now,
                "updated_at": now,
            },
        )

    async def reject(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        skill_id: UUID,
        evaluation_refs: list[str],
        lock_version: int,
    ) -> AiSkill:
        current = await self.get(
            tenant_id=tenant_id, project_id=project_id, skill_id=skill_id
        )
        if current.status not in {"CANDIDATE", "EVALUATING"}:
            raise DdeError(
                "VERSION_CONFLICT", "skill cannot be rejected from current state"
            )
        return await self.repo.update_locked(
            table=ai_skills,
            model=AiSkill,
            id_column="skill_id",
            object_id=skill_id,
            tenant_id=tenant_id,
            project_id=project_id,
            lock_version=lock_version,
            values={
                "status": "REJECTED",
                "evaluation_refs": evaluation_refs,
                "updated_at": datetime.now(UTC),
            },
        )

    async def get(
        self, *, tenant_id: UUID, project_id: UUID, skill_id: UUID
    ) -> AiSkill:
        return await self.repo.get_model(
            table=ai_skills,
            model=AiSkill,
            id_column="skill_id",
            object_id=skill_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )

    async def list_skills(
        self, *, tenant_id: UUID, project_id: UUID, status: str | None = None
    ) -> tuple[AiSkill, ...]:
        return await self.repo.list_models(
            table=ai_skills,
            model=AiSkill,
            tenant_id=tenant_id,
            project_id=project_id,
            filters={"status": status} if status else None,
            order_by=(ai_skills.c.slug.asc(), ai_skills.c.version.desc()),
        )
