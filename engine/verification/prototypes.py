"""Prototype-manifest verification (frontend/UX playbook §5.3, guardrail 16).

A mission chartered to touch user-visible surfaces must deliver
`prototypes/flows.json` plus the screens it declares. This module gives
`VerificationRunnerService.run` a mechanical check over those artifacts --
same shape as the self-grading guardrails (`engine.verification.guardrails`):
cheap, deterministic findings recorded on every `Evidence` row this run
writes under `independence_flags["prototype_manifest_findings"]`, with a
violation demoting a fully-passing outcome set to PARTIAL so a missing or
broken manifest can never be certified as an independent PASS.

Deliberately NOT harness-gaming territory: a stale or unparsable manifest is
ordinary failed verification (`VERIFICATION_FAILURE` on the TaskAttempt),
unlike test-scope violations which classify SCOPE_VIOLATION -- Chapter 12.3's
matrix already governs both through their existing rows; no new row invented.

**Honest limits.** Byte-stable `index.html` regeneration (playbook §5.3)
needs a shipped gallery generator; until one lands, index staleness is not
checked here and remains a review-skill concern (`component-gallery`).
Animation-token conformance inside screen HTML is enforced repo-side by
`scripts/design_lints.py`, not duplicated per-workspace.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

PROTOTYPE_DIRNAME = "prototypes"
MANIFEST_NAME = "flows.json"
SCREENS_SUBDIR = "screens"

FLAG_KEY = "prototype_manifest_findings"
VIOLATION_FLAG_KEY = "prototype_manifest_violation"

_SCREEN_FILE = re.compile(r"^[A-Za-z0-9._-]+\.html$")
_FLOW_ID = re.compile(r"^[a-z][a-z0-9-]*$")


@dataclass(frozen=True)
class PrototypeFinding:
    kind: str
    detail: str
    path: str = ""
    violation: bool = True


@dataclass(frozen=True)
class PrototypeAssessment:
    findings: tuple[PrototypeFinding, ...]

    @property
    def violations(self) -> tuple[PrototypeFinding, ...]:
        return tuple(item for item in self.findings if item.violation)

    def as_flags(self) -> dict[str, object]:
        return {
            FLAG_KEY: [
                {
                    "kind": item.kind,
                    "path": item.path,
                    "detail": item.detail,
                    "violation": item.violation,
                }
                for item in self.findings
            ],
            VIOLATION_FLAG_KEY: bool(self.violations),
        }


def _clean_assessment() -> PrototypeAssessment:
    return PrototypeAssessment(
        findings=(
            PrototypeFinding(
                kind="no_prototypes",
                detail="workspace declares no prototypes directory",
                violation=False,
            ),
        )
    )


def assess_prototype_dir(root: Path) -> PrototypeAssessment:
    """Real reads against one workspace's prototypes/ directory. Absent
    directory is informational -- only missions that SHIP prototypes are
    judged; a directory that exists must be internally consistent."""
    base = root / PROTOTYPE_DIRNAME
    if not base.is_dir():
        return _clean_assessment()

    findings: list[PrototypeFinding] = []
    manifest_path = base / MANIFEST_NAME
    screens = base / SCREENS_SUBDIR
    screen_files: set[str] = set()
    if screens.is_dir():
        screen_files = {
            item.name
            for item in screens.iterdir()
            if item.is_file() and _SCREEN_FILE.match(item.name)
        }
    else:
        findings.append(
            PrototypeFinding(
                kind="missing_screens_dir",
                detail=f"{PROTOTYPE_DIRNAME}/{SCREENS_SUBDIR}/ does not exist",
            )
        )

    if not manifest_path.is_file():
        findings.append(
            PrototypeFinding(
                kind="missing_manifest",
                detail=f"{PROTOTYPE_DIRNAME}/{MANIFEST_NAME} does not exist",
            )
        )
        return PrototypeAssessment(findings=tuple(findings))

    try:
        parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        findings.append(
            PrototypeFinding(
                kind="manifest_unparsable",
                detail=f"{MANIFEST_NAME} is not valid UTF-8 JSON",
                path=MANIFEST_NAME,
            )
        )
        return PrototypeAssessment(findings=tuple(findings))

    if not isinstance(parsed, dict):
        findings.append(
            PrototypeFinding(
                kind="manifest_unparsable",
                detail=f"{MANIFEST_NAME} must be a JSON object",
                path=MANIFEST_NAME,
            )
        )
        return PrototypeAssessment(findings=tuple(findings))

    version = parsed.get("version")
    if version != 1:
        findings.append(
            PrototypeFinding(
                kind="unsupported_version",
                detail=f"version must be 1, got {version!r}",
                path=MANIFEST_NAME,
            )
        )

    flows = parsed.get("flows")
    if not isinstance(flows, list) or not flows:
        findings.append(
            PrototypeFinding(
                kind="no_flows",
                detail="flows must be a non-empty array",
                path=MANIFEST_NAME,
            )
        )
        return PrototypeAssessment(findings=tuple(findings))

    declared_screens = parsed.get("screens")
    if isinstance(declared_screens, list):
        for entry in declared_screens:
            if not isinstance(entry, dict):
                continue
            name = entry.get("file")
            if isinstance(name, str) and name not in screen_files:
                findings.append(
                    PrototypeFinding(
                        kind="declared_screen_missing",
                        detail="declared screen file absent from screens/",
                        path=f"{SCREENS_SUBDIR}/{name}",
                    )
                )
        declared_names = {
            entry.get("file") for entry in declared_screens if isinstance(entry, dict)
        }
        for extra in sorted(screen_files - declared_names):
            findings.append(
                PrototypeFinding(
                    kind="undeclared_screen_file",
                    detail="screen on disk not declared in manifest screens[]",
                    path=f"{SCREENS_SUBDIR}/{extra}",
                )
            )

    for flow in flows:
        if not isinstance(flow, dict):
            findings.append(
                PrototypeFinding(
                    kind="flow_invalid",
                    detail="flow entry must be an object",
                    path=MANIFEST_NAME,
                )
            )
            continue
        flow_id = flow.get("id")
        if not isinstance(flow_id, str) or not _FLOW_ID.match(flow_id):
            findings.append(
                PrototypeFinding(
                    kind="flow_id_invalid",
                    detail=f"flow id {flow_id!r} violates ^[a-z][a-z0-9-]*$",
                    path=MANIFEST_NAME,
                )
            )
        entry_screen = flow.get("entry")
        if not isinstance(entry_screen, str) or not _SCREEN_FILE.match(entry_screen):
            findings.append(
                PrototypeFinding(
                    kind="entry_invalid",
                    detail=f"entry {entry_screen!r} is not a screen filename",
                    path=MANIFEST_NAME,
                )
            )
        elif entry_screen not in screen_files:
            findings.append(
                PrototypeFinding(
                    kind="referenced_screen_missing",
                    detail="flow entry screen absent from screens/",
                    path=f"{SCREENS_SUBDIR}/{entry_screen}",
                )
            )
        steps = flow.get("steps")
        if not isinstance(steps, list) or not steps:
            findings.append(
                PrototypeFinding(
                    kind="steps_empty",
                    detail=f"flow {flow_id!r} has no steps",
                    path=MANIFEST_NAME,
                )
            )
            continue
        for step in steps:
            if not isinstance(step, dict):
                findings.append(
                    PrototypeFinding(
                        kind="step_invalid",
                        detail="step must be an object",
                        path=MANIFEST_NAME,
                    )
                )
                continue
            target = step.get("to")
            if (
                isinstance(target, str)
                and _SCREEN_FILE.match(target)
                and target not in screen_files
            ):
                findings.append(
                    PrototypeFinding(
                        kind="referenced_screen_missing",
                        detail="transition target absent from screens/",
                        path=f"{SCREENS_SUBDIR}/{target}",
                    )
                )

    return PrototypeAssessment(findings=tuple(findings))


def merge_prototype_flags(
    base: dict[str, object], assessment: PrototypeAssessment
) -> dict[str, object]:
    """Evidence independence-flags with prototype findings appended; never
    overwrites the runner/guardrail keys already present."""
    merged = dict(base)
    merged.update(assessment.as_flags())
    return merged
