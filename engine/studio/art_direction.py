"""Fail-closed validation of the art-direction record."""

from __future__ import annotations

from typing import Any, NoReturn

from engine.studio.catalog import font_pairings_catalog
from engine.studio.errors import CompileRefusedError

_REQUIRED = (
    "record_id",
    "product_id",
    "version",
    "design_read",
    "dials",
    "type_pairing",
    "palette_roles",
    "theme_atmosphere",
    "typography_hierarchy",
    "component_stylings",
    "layout_idiom",
    "layout_principles",
    "depth_elevation",
    "dos_donts",
    "responsive_behavior",
    "agent_prompt_guide",
    "motion_identity",
)
_DIALS = ("DESIGN_VARIANCE", "MOTION_INTENSITY", "VISUAL_DENSITY")
_ROLES = (
    "canvas",
    "surface",
    "ink",
    "accent",
    "semantic_ok",
    "semantic_warn",
    "semantic_err",
)


def _refuse(message: str) -> NoReturn:
    raise CompileRefusedError(message, missing_artifact="art_direction")


def validate_art_direction(
    record: dict[str, Any],
    *,
    semantic_role_names: frozenset[str],
    motion_identity_ids: frozenset[str] | None = None,
) -> dict[str, Any]:
    for key in _REQUIRED:
        if key not in record:
            _refuse(f"art-direction record missing field {key}")
    design_read = record["design_read"]
    if not isinstance(design_read, str) or not design_read.strip():
        _refuse("art-direction Design Read is empty")
    dials = record["dials"]
    if not isinstance(dials, dict):
        _refuse("art-direction dials must be an object")
    for name in _DIALS:
        value = dials.get(name)
        if isinstance(value, bool) or not isinstance(value, int):
            _refuse(f"art-direction dial {name} is unset")
        if value < 1 or value > 10:
            _refuse(f"art-direction dial {name} is out of range")
    _validate_type_pairing(record["type_pairing"])
    roles = record["palette_roles"]
    if not isinstance(roles, dict):
        _refuse("art-direction palette_roles must be an object")
    for role in _ROLES:
        alias = roles.get(role)
        if not isinstance(alias, str) or not alias:
            _refuse(f"art-direction palette role {role} is unset")
        if alias not in semantic_role_names:
            _refuse(f"art-direction palette role {role} is not a token semantic alias")
    stylings = record["component_stylings"]
    if not isinstance(stylings, list) or not stylings:
        _refuse("art-direction component stylings with states are required")
    for entry in stylings:
        if not isinstance(entry, dict):
            _refuse("art-direction component styling is malformed")
        states = entry.get("states")
        if not isinstance(states, list) or not states:
            _refuse("art-direction component stylings require interactive states")
    dos_donts = record["dos_donts"]
    if not isinstance(dos_donts, dict):
        _refuse("art-direction dos/donts are required")
    if not dos_donts.get("dos") or not dos_donts.get("donts"):
        _refuse("art-direction dos/donts are required")
    motion = record["motion_identity"]
    allowed_motion = motion_identity_ids or frozenset(
        {"restrained", "measured", "expressive"}
    )
    if motion not in allowed_motion:
        _refuse("art-direction motion identity is not a token preset")
    for text_key in (
        "theme_atmosphere",
        "typography_hierarchy",
        "layout_idiom",
        "layout_principles",
        "depth_elevation",
        "responsive_behavior",
        "agent_prompt_guide",
    ):
        value = record[text_key]
        if not isinstance(value, str) or not value.strip():
            _refuse(f"art-direction {text_key} is empty")
    return record


def _validate_type_pairing(pairing: object) -> None:
    if not isinstance(pairing, dict):
        _refuse("art-direction type pairing is missing")
    pairing_id = pairing.get("pairing_id")
    display = pairing.get("display")
    body = pairing.get("body")
    if not isinstance(pairing_id, str) or not pairing_id:
        _refuse("art-direction type pairing is missing")
    corpus = font_pairings_catalog()
    match = next(
        (
            row
            for row in corpus["pairings"]
            if row["id"] == pairing_id
            and row["display"] == display
            and row["body"] == body
        ),
        None,
    )
    if match is None:
        _refuse("art-direction type pairing is not in the font corpus")
    if match.get("requires_explicit_inter_display") and not pairing.get(
        "explicit_inter_display"
    ):
        _refuse("Inter as display requires explicit_inter_display")
