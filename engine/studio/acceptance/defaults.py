"""DDE-069 default acceptance-oracle bindings for generated screens.

This module closes the one thing DDE-068 deliberately left open. DDE-068
built the visual-verification capability *and* its enforcement: an
`AcceptanceOracle` carrying a `silhouette` / `visual_critique` /
`visual_diff` binding is machine-gated at promotion, proven against real
PostgreSQL. What did not exist was anything that *authors* such a binding
by default, which left the guarantee conditional -- "a bound check
refuses" rather than "every generated screen is checked".

`build_screen_specs` is what makes the binding exist, and
`assert_mandatory_bindings` is what stops an authoring path quietly
omitting it. The policy itself lives in
`schemas/design/screen_acceptance_defaults.json` so it is versioned and
inspectable rather than buried in constants.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final
from uuid import UUID

from engine.context.repo import repo_root
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.verification.checks import CheckSpec

POLICY_RELATIVE: Final = "schemas/design/screen_acceptance_defaults.json"

#: Profiles a screen may be bound under. A caller naming anything else is
#: refused rather than silently defaulted, because a silent default is
#: how a screen ends up under a weaker bar than intended.
GENERATED_SCREEN: Final = "generated_screen"
IMPORTED_SCREEN: Final = "imported_screen"


@dataclass(frozen=True)
class AcceptanceProfile:
    name: str
    mandatory_kinds: tuple[str, ...]
    optional_kinds: tuple[str, ...]


@dataclass(frozen=True)
class AcceptanceDefaults:
    policy_version: int
    profiles: dict[str, AcceptanceProfile]

    def profile(self, name: str) -> AcceptanceProfile:
        try:
            return self.profiles[name]
        except KeyError as exc:
            raise DdeError(
                "VALIDATION_FAILED",
                "unknown screen acceptance profile",
                retryable=False,
                details={"profile": name, "known": sorted(self.profiles)},
            ) from exc


@lru_cache(maxsize=1)
def load_defaults(root: Path | None = None) -> AcceptanceDefaults:
    base = root or repo_root()
    path = base / POLICY_RELATIVE
    if not path.is_file():
        raise DdeError(
            "CONTEXT_INCOMPLETE",
            "screen acceptance defaults policy is missing; a generated "
            "screen cannot be bound to verification without it",
            retryable=False,
            details={"path": POLICY_RELATIVE},
        )
    document = json.loads(path.read_text(encoding="utf-8"))
    profiles = {
        name: AcceptanceProfile(
            name=name,
            mandatory_kinds=tuple(entry["mandatory_kinds"]),
            optional_kinds=tuple(entry.get("optional_kinds") or ()),
        )
        for name, entry in document["profiles"].items()
    }
    if not profiles:
        raise DdeError(
            "CONTEXT_INCOMPLETE",
            "screen acceptance defaults declare no profiles",
            retryable=False,
        )
    return AcceptanceDefaults(
        policy_version=int(document["policy_version"]),
        profiles=profiles,
    )


def build_screen_specs(
    *,
    screen_ref: str,
    preview_url: str,
    profile: str = GENERATED_SCREEN,
    expect_text: str | None = None,
    visual_diff_spec_path: str | None = None,
    root: Path | None = None,
) -> tuple[CheckSpec, ...]:
    """Return the default DDE-068 bindings for one generated screen.

    `visual_diff` is emitted only when a spec path is supplied: binding it
    without an approved golden would fail closed on every run for the
    wrong reason, which trains people to ignore the gate.
    """
    if not preview_url:
        raise DdeError(
            "VALIDATION_FAILED",
            "a screen cannot be bound to visual verification without a "
            "renderable preview URL",
            retryable=False,
            details={"screen_ref": screen_ref},
        )
    resolved = load_defaults(root).profile(profile)
    render_command = [preview_url]
    if expect_text:
        render_command.append(expect_text)

    specs: list[CheckSpec] = []
    for kind in resolved.mandatory_kinds:
        if kind == "visual_diff":
            continue
        specs.append(
            CheckSpec(
                outcome_id=uuid7(),
                statement=_statement(kind, screen_ref),
                kind=kind,
                ref=f"{screen_ref}:{kind}",
                command=list(render_command),
            )
        )
    if visual_diff_spec_path and "visual_diff" in (
        resolved.mandatory_kinds + resolved.optional_kinds
    ):
        specs.append(
            CheckSpec(
                outcome_id=uuid7(),
                statement=_statement("visual_diff", screen_ref),
                kind="visual_diff",
                ref=f"{screen_ref}:visual_diff",
                command=[visual_diff_spec_path],
            )
        )
    return tuple(specs)


def assert_mandatory_bindings(
    specs: tuple[CheckSpec, ...] | list[CheckSpec],
    *,
    screen_ref: str,
    profile: str = GENERATED_SCREEN,
    root: Path | None = None,
) -> None:
    """Refuse an oracle for a screen that is missing a mandatory binding.

    This is the fail-closed half. Without it an authoring path could
    assemble its own spec list, omit `visual_critique`, and produce a
    screen that promotes on code validity alone -- exactly the state
    DDE-068 was built to end.
    """
    resolved = load_defaults(root).profile(profile)
    present = {spec.kind for spec in specs}
    missing = [kind for kind in resolved.mandatory_kinds if kind not in present]
    if missing:
        raise DdeError(
            "POLICY_DENIED",
            "a generated screen may not be accepted without its mandatory "
            "visual-verification bindings",
            retryable=False,
            details={
                "screen_ref": screen_ref,
                "profile": profile,
                "missing_kinds": missing,
                "policy": POLICY_RELATIVE,
            },
        )


def mandatory_kinds(
    profile: str = GENERATED_SCREEN, *, root: Path | None = None
) -> tuple[str, ...]:
    return load_defaults(root).profile(profile).mandatory_kinds


def _statement(kind: str, screen_ref: str) -> str:
    if kind == "silhouette":
        return (
            f"{screen_ref} does not near-match a generic layout template "
            "(DDE-068 deterministic silhouette gate)"
        )
    if kind == "visual_critique":
        return (
            f"{screen_ref} scores at or above the rubric threshold on every "
            "dimension (DDE-068 multimodal critique)"
        )
    if kind == "visual_diff":
        return f"{screen_ref} matches its approved golden image"
    return f"{screen_ref} satisfies its {kind} binding"


def outcome_ids(specs: tuple[CheckSpec, ...]) -> tuple[UUID, ...]:
    return tuple(spec.outcome_id for spec in specs)
