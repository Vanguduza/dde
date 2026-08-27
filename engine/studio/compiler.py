"""DDE-065 generation-prompt compiler — production call site.

`compile_generation_prompt` is the only function that may mint a compiled
UI generation prompt. It is deterministic, offline, and stdlib string
assembly over durable inputs. It never calls a network or model, never
loads third-party design skills, and never mints a TaskGraph (DDE-040
registry remains the decomposition path).
"""

from __future__ import annotations

from typing import Any

from engine.core.hashing import sha256_hex
from engine.studio.art_direction import validate_art_direction
from engine.studio.catalog import (
    COPY_FORBIDDEN_PHRASES,
    COPY_RULES,
    LAYOUT_PATTERN_IDS,
    LAYOUT_PATTERNS,
    NEVER_ITEMS,
    PLAYBOOK_VERSION,
)
from engine.studio.errors import CompileRefusedError
from engine.studio.models import CompileRequest, GenerationPrompt
from engine.studio.preview import render_preview_catalog
from engine.studio.tokens_pin import TokenSheet, resolve_tokens_pin


def compile_generation_prompt(request: CompileRequest) -> GenerationPrompt:
    """Fail-closed compile. Production mutation: this return value is the
    versioned generation-prompt artifact (content-addressed). Persistence
    through Gateway is DDE-067; this function is the chapter-gate site
    that either produces the artifact or refuses."""
    if request.playbook_version != PLAYBOOK_VERSION:
        raise CompileRefusedError(
            "unknown playbook version pin",
            missing_artifact="playbook",
            details={"pinned_version": request.playbook_version},
        )
    sheet = resolve_tokens_pin(
        version=request.tokens_version,
        content_hash=request.tokens_hash,
    )
    if request.art_direction is None:
        raise CompileRefusedError(
            "art-direction record is absent",
            missing_artifact="art_direction",
        )
    art = validate_art_direction(
        request.art_direction,
        semantic_role_names=sheet.semantic_role_names,
        motion_identity_ids=sheet.motion_identity_ids,
    )
    approved = tuple(
        sorted(
            (item for item in request.requirements if item.status == "approved"),
            key=lambda row: row.slug,
        )
    )
    if not approved:
        raise CompileRefusedError(
            "PRD has no approved Requirements",
            missing_artifact="approved_requirements",
        )
    features = tuple(sorted(request.features, key=lambda row: row.feature_id))
    _validate_features(features)
    prompt_body = _assemble_prompt(request, art, sheet, approved, features)
    preview_html = render_preview_catalog(art, sheet)
    provenance = {
        "prd_id": request.prd_id,
        "prd_version": request.prd_version,
        "requirement_ids": [item.requirement_id for item in approved],
        "requirement_slugs": [item.slug for item in approved],
        "feature_ids": [item.feature_id for item in features],
        "art_direction_id": str(art["record_id"]),
        "art_direction_version": str(art["version"]),
        "playbook_version": request.playbook_version,
        "tokens_version": sheet.version,
        "tokens_hash": sheet.content_hash,
        "font_pairing_id": str(art["type_pairing"]["pairing_id"]),
        "layout_patterns": sorted({item.layout_pattern for item in features}),
    }
    return GenerationPrompt(
        prd_id=request.prd_id,
        prd_version=request.prd_version,
        playbook_version=request.playbook_version,
        tokens_version=sheet.version,
        tokens_hash=sheet.content_hash,
        art_direction_id=str(art["record_id"]),
        art_direction_version=str(art["version"]),
        prompt_body=prompt_body,
        content_hash=sha256_hex(prompt_body),
        preview_html=preview_html,
        provenance=provenance,
    )


def _validate_features(features: tuple[Any, ...]) -> None:
    if not features:
        raise CompileRefusedError(
            "PRD has no feature surfaces",
            missing_artifact="features",
        )
    for feature in features:
        if feature.layout_pattern not in LAYOUT_PATTERN_IDS:
            raise CompileRefusedError(
                "feature references an undeclared layout pattern",
                missing_artifact="layout_pattern",
                details={
                    "feature_id": feature.feature_id,
                    "layout_pattern": feature.layout_pattern,
                },
            )


def _assemble_prompt(
    request: CompileRequest,
    art: dict[str, Any],
    sheet: TokenSheet,
    approved: tuple[Any, ...],
    features: tuple[Any, ...],
) -> str:
    pairing = art["type_pairing"]
    dials = art["dials"]
    roles = art["palette_roles"]
    semantic_names = "\n".join(
        f"- color.semantic.{name}" for name in sorted(sheet.semantic_role_names)
    )
    nevers = "\n".join(f"- {item['id']}: {item['statement']}" for item in NEVER_ITEMS)
    copy_phrases = "\n".join(f"- {phrase}" for phrase in COPY_FORBIDDEN_PHRASES)
    copy_rules = "\n".join(f"- {rule}" for rule in COPY_RULES)
    patterns = "\n".join(
        f"- {item['id']}: {item['description']}" for item in LAYOUT_PATTERNS
    )
    requirement_lines = "\n".join(
        f"- {item.slug} ({item.requirement_id}): {item.statement}" for item in approved
    )
    feature_lines = "\n".join(
        f"- {item.feature_id}: {item.title} — {item.purpose} "
        f"[layout_pattern={item.layout_pattern}; "
        f"states={','.join(item.states)}]"
        for item in features
    )
    role_lines = "\n".join(
        f"- {name}: token semantic {alias}" for name, alias in sorted(roles.items())
    )
    dos = "\n".join(f"- {item}" for item in art["dos_donts"]["dos"])
    donts = "\n".join(f"- {item}" for item in art["dos_donts"]["donts"])
    stylings = "\n".join(
        f"- {entry['component']}: states {', '.join(entry['states'])}"
        for entry in art["component_stylings"]
    )
    return "\n".join(
        [
            "# Generation prompt",
            "",
            "## Provenance",
            f"prd_id: {request.prd_id}",
            f"prd_version: {request.prd_version}",
            f"playbook_version: {request.playbook_version}",
            f"tokens_version: {sheet.version}",
            f"tokens_hash: {sheet.content_hash}",
            f"art_direction_id: {art['record_id']}",
            f"art_direction_version: {art['version']}",
            "Provenance chain: PRD → requirements → features → this prompt.",
            "Donors → screen is DDE-066/067; do not invent donor rows here.",
            "",
            "## Design Read",
            str(art["design_read"]),
            "",
            "## Dials",
            f"DESIGN_VARIANCE: {dials['DESIGN_VARIANCE']}",
            f"MOTION_INTENSITY: {dials['MOTION_INTENSITY']}",
            f"VISUAL_DENSITY: {dials['VISUAL_DENSITY']}",
            "",
            "## Art direction",
            f"theme_atmosphere: {art['theme_atmosphere']}",
            f"typography_hierarchy: {art['typography_hierarchy']}",
            f"layout_idiom: {art['layout_idiom']}",
            f"layout_principles: {art['layout_principles']}",
            f"depth_elevation: {art['depth_elevation']}",
            f"responsive_behavior: {art['responsive_behavior']}",
            f"agent_prompt_guide: {art['agent_prompt_guide']}",
            f"motion_identity preset: {art['motion_identity']}",
            "Springs/bounce/overshoot remain banned (playbook §5.2); "
            "preset spring pin is none.",
            "Type pairing:",
            f"- pairing_id: {pairing['pairing_id']}",
            f"- display: {pairing['display']}",
            f"- body: {pairing['body']}",
            "Palette roles (token semantic aliases only; never raw hex):",
            role_lines,
            "Component stylings with states:",
            stylings,
            "Dos:",
            dos,
            "Donts:",
            donts,
            "",
            "## Token sheet (exclusive visual values)",
            "Use only token names from the pinned schemas/design/tokens.json "
            "sheet. Off-token literals are forbidden. Do not invent hex, px, "
            "ms, or cubic-bezier values. Do not instruct off-token values.",
            "Allowed color.semantic names:",
            semantic_names,
            "",
            "## Nevers (playbook §1.1)",
            nevers,
            "",
            "## Copy law (FORBIDDEN_HELPER superset)",
            "Forbidden phrases:",
            copy_phrases,
            "Rules:",
            copy_rules,
            "",
            "## Declared layout patterns",
            "Every surface must use exactly one of:",
            patterns,
            "",
            "## Requirements (approved)",
            requirement_lines,
            "",
            "## Features",
            feature_lines,
            "",
            "## Compiler constraints",
            "- Do not mint TaskGraphs; decomposition uses DDE-040 "
            "submit_draft → validate_draft → promote_draft.",
            "- Do not make a network or model call to produce UI.",
            "- Do not load third-party design skills.",
            "",
        ]
    )
