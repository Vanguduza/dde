"""Prototype HTML + flows.json mutations (DDE-067).

Every edit is a structured artifact mutation. Raw DOM patches are not a
code path. Token-bound properties refuse freehand literals via
`assert_token_value` before any write.
"""

from __future__ import annotations

import json
import re
from html import escape
from typing import Any

from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.tokens_catalog import (
    BASE_KINDS,
    STYLE_PROPERTIES,
    assert_token_value,
    css_var_for,
)

SCREEN_FILE_RE = re.compile(r"^[A-Za-z0-9._-]+\.html$")
ELEMENT_RE = re.compile(
    r'<div\s+([^>]*\bdata-dde-el="([^"]+)"[^>]*)>(.*?)</div>',
    re.DOTALL,
)
ATTR_RE = re.compile(r'([\w:-]+)="([^"]*)"')
DURATION_ENUM = frozenset(
    {"motion-duration-fast", "motion-duration-base", "motion-duration-slow"}
)
EASING_ENUM = frozenset(
    {
        "motion-easing-arrival",
        "motion-easing-state",
        "motion-easing-linear",
    }
)


def screen_relative_path(screen_file: str) -> str:
    if not SCREEN_FILE_RE.match(screen_file):
        raise DdeError(
            "POLICY_DENIED",
            "screen_file must be a prototypes/screens HTML filename",
            retryable=False,
            details={"screen_file": screen_file},
        )
    return f"prototypes/screens/{screen_file}"


def _attrs(blob: str) -> dict[str, str]:
    return {name: value for name, value in ATTR_RE.findall(blob)}


def _render(attrs: dict[str, str], inner: str) -> str:
    ordered = " ".join(f'{key}="{escape(value, quote=True)}"' for key, value in attrs.items())
    return f"<div {ordered}>{inner}</div>"


def list_elements(html: str) -> tuple[tuple[str, dict[str, str], str], ...]:
    found: list[tuple[str, dict[str, str], str]] = []
    for match in ELEMENT_RE.finditer(html):
        element_id = match.group(2)
        found.append((element_id, _attrs(match.group(1)), match.group(3)))
    return tuple(found)


def _replace_all(html: str, elements: list[tuple[str, dict[str, str], str]]) -> str:
    stripped = ELEMENT_RE.sub("", html)
    rendered = "".join(_render(attrs, inner) for _eid, attrs, inner in elements)
    if "</body>" in stripped:
        return stripped.replace("</body>", f"{rendered}</body>", 1)
    return stripped + rendered


def apply_insert(
    html: str,
    *,
    kind: str,
    anchor_parent: str,
    position_index: int,
    label: str,
    element_id: str | None = None,
) -> tuple[str, str]:
    if kind not in BASE_KINDS:
        raise DdeError(
            "POLICY_DENIED",
            "unknown base component kind",
            retryable=False,
            details={"kind": kind, "allowed": sorted(BASE_KINDS)},
        )
    if position_index < 0:
        raise DdeError(
            "POLICY_DENIED",
            "position_index must be >= 0",
            retryable=False,
            details={"position_index": position_index},
        )
    new_id = element_id or f"el-{uuid7().hex[:12]}"
    attrs = {
        "data-dde-el": new_id,
        "data-dde-kind": kind,
        "data-dde-parent": anchor_parent,
        "data-dde-color": "--text-primary",
        "style": "color: var(--text-primary)",
    }
    elements = list(list_elements(html))
    siblings = [
        index
        for index, (_eid, item_attrs, _inner) in enumerate(elements)
        if item_attrs.get("data-dde-parent", "") == anchor_parent
    ]
    insert_at = len(elements)
    if siblings:
        clamped = min(position_index, len(siblings))
        insert_at = siblings[clamped] if clamped < len(siblings) else siblings[-1] + 1
    elif position_index == 0:
        insert_at = len(elements)
    elements.insert(insert_at, (new_id, attrs, escape(label)))
    return _replace_all(html, elements), new_id


def apply_update(html: str, *, element_id: str, property_name: str, value: str) -> str:
    assert_token_value(property_name, value)
    elements = list(list_elements(html))
    found = False
    updated: list[tuple[str, dict[str, str], str]] = []
    for eid, attrs, inner in elements:
        if eid != element_id:
            updated.append((eid, attrs, inner))
            continue
        found = True
        next_attrs = dict(attrs)
        next_inner = inner
        if property_name == "label":
            next_inner = escape(value)
        elif property_name == "variant":
            next_attrs["data-dde-variant"] = value
        elif property_name in STYLE_PROPERTIES:
            css_name = css_var_for(property_name, value)
            next_attrs[f"data-dde-{property_name.replace('_', '-')}"] = value
            next_attrs["style"] = _merge_style(next_attrs.get("style", ""), property_name, css_name)
        updated.append((eid, next_attrs, next_inner))
    if not found:
        raise DdeError(
            "POLICY_DENIED",
            "unknown element_id",
            retryable=False,
            details={"element_id": element_id},
        )
    return _replace_all(html, updated)


def _merge_style(existing: str, property_name: str, css_var: str) -> str:
    css_prop = {
        "color": "color",
        "spacing": "padding",
        "radius": "border-radius",
        "shadow": "box-shadow",
        "type": "font-size",
        "duration": "transition-duration",
        "easing": "transition-timing-function",
        "z_index": "z-index",
    }[property_name]
    parts = [item.strip() for item in existing.split(";") if item.strip()]
    kept = [item for item in parts if not item.startswith(f"{css_prop}:")]
    kept.append(f"{css_prop}: var({css_var})")
    return "; ".join(kept)


def apply_remove(html: str, *, element_id: str) -> str:
    elements = list(list_elements(html))
    kept = [(eid, attrs, inner) for eid, attrs, inner in elements if eid != element_id]
    if len(kept) == len(elements):
        raise DdeError(
            "POLICY_DENIED",
            "unknown element_id",
            retryable=False,
            details={"element_id": element_id},
        )
    return _replace_all(html, kept)


def apply_move(
    html: str,
    *,
    element_id: str,
    new_anchor_parent: str,
    new_position_index: int,
) -> str:
    if new_position_index < 0:
        raise DdeError(
            "POLICY_DENIED",
            "new_position_index must be >= 0",
            retryable=False,
            details={"new_position_index": new_position_index},
        )
    elements = list(list_elements(html))
    moving: tuple[str, dict[str, str], str] | None = None
    rest: list[tuple[str, dict[str, str], str]] = []
    for item in elements:
        if item[0] == element_id:
            moving = item
        else:
            rest.append(item)
    if moving is None:
        raise DdeError(
            "POLICY_DENIED",
            "unknown element_id",
            retryable=False,
            details={"element_id": element_id},
        )
    attrs = dict(moving[1])
    attrs["data-dde-parent"] = new_anchor_parent
    moved = (moving[0], attrs, moving[2])
    siblings = [
        index
        for index, (_eid, item_attrs, _inner) in enumerate(rest)
        if item_attrs.get("data-dde-parent", "") == new_anchor_parent
    ]
    insert_at = len(rest)
    if siblings:
        clamped = min(new_position_index, len(siblings))
        insert_at = siblings[clamped] if clamped < len(siblings) else siblings[-1] + 1
    rest.insert(insert_at, moved)
    return _replace_all(html, rest)


def apply_set_animation(
    manifest: dict[str, Any],
    *,
    flow_id: str,
    step_index: int,
    animation: dict[str, Any],
) -> dict[str, Any]:
    _validate_animation(animation)
    flows = manifest.get("flows")
    if not isinstance(flows, list):
        raise DdeError(
            "POLICY_DENIED",
            "flows.json has no flows array",
            retryable=False,
        )
    for flow in flows:
        if not isinstance(flow, dict) or flow.get("id") != flow_id:
            continue
        steps = flow.get("steps")
        if not isinstance(steps, list) or step_index < 0 or step_index >= len(steps):
            raise DdeError(
                "POLICY_DENIED",
                "flow step_index is out of range",
                retryable=False,
                details={"flow_id": flow_id, "step_index": step_index},
            )
        step = steps[step_index]
        if not isinstance(step, dict):
            raise DdeError(
                "POLICY_DENIED",
                "flow step is not an object",
                retryable=False,
            )
        step["animation"] = dict(animation)
        return manifest
    raise DdeError(
        "POLICY_DENIED",
        "unknown flow_id",
        retryable=False,
        details={"flow_id": flow_id},
    )


def apply_upsert_step(
    manifest: dict[str, Any],
    *,
    flow_id: str,
    step_index: int,
    from_file: str,
    on: str,
    to_file: str,
    animation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if animation is not None:
        _validate_animation(animation)
    if not SCREEN_FILE_RE.match(from_file) or not SCREEN_FILE_RE.match(to_file):
        raise DdeError(
            "POLICY_DENIED",
            "flow step from/to must be screen filenames",
            retryable=False,
        )
    if not on.strip():
        raise DdeError(
            "POLICY_DENIED",
            "flow step trigger 'on' must be non-empty",
            retryable=False,
        )
    flows = manifest.get("flows")
    if not isinstance(flows, list):
        raise DdeError(
            "POLICY_DENIED",
            "flows.json has no flows array",
            retryable=False,
        )
    step: dict[str, Any] = {"from": from_file, "on": on, "to": to_file}
    if animation is not None:
        step["animation"] = dict(animation)
    for flow in flows:
        if not isinstance(flow, dict) or flow.get("id") != flow_id:
            continue
        steps = flow.setdefault("steps", [])
        if not isinstance(steps, list):
            raise DdeError(
                "POLICY_DENIED",
                "flow steps must be an array",
                retryable=False,
            )
        if step_index < 0 or step_index > len(steps):
            raise DdeError(
                "POLICY_DENIED",
                "flow step_index is out of range",
                retryable=False,
                details={"flow_id": flow_id, "step_index": step_index},
            )
        if step_index == len(steps):
            steps.append(step)
        else:
            steps[step_index] = step
        return manifest
    raise DdeError(
        "POLICY_DENIED",
        "unknown flow_id",
        retryable=False,
        details={"flow_id": flow_id},
    )


def parse_manifest(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DdeError(
            "POLICY_DENIED",
            "flows.json is not valid JSON",
            retryable=False,
        ) from exc
    if not isinstance(payload, dict):
        raise DdeError(
            "POLICY_DENIED",
            "flows.json must be an object",
            retryable=False,
        )
    return payload


def dump_manifest(manifest: dict[str, Any]) -> bytes:
    return json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")


def _validate_animation(animation: dict[str, Any]) -> None:
    duration = animation.get("durationToken")
    easing = animation.get("easingToken")
    if duration not in DURATION_ENUM or easing not in EASING_ENUM:
        raise DdeError(
            "POLICY_DENIED",
            "animation tokens must be sheet enums, never literals",
            retryable=False,
            details={
                "durationToken": duration,
                "easingToken": easing,
            },
        )
    extra = set(animation) - {
        "durationToken",
        "easingToken",
        "reducedMotionVariant",
        "boundedLoopMs",
    }
    if extra:
        raise DdeError(
            "POLICY_DENIED",
            "animation field is not in the AnimationRef schema",
            retryable=False,
            details={"unknown_fields": sorted(extra)},
        )
    if "reducedMotionVariant" in animation and not isinstance(
        animation["reducedMotionVariant"], bool
    ):
        raise DdeError(
            "POLICY_DENIED",
            "reducedMotionVariant must be a boolean",
            retryable=False,
        )
    if "boundedLoopMs" in animation:
        bound = animation["boundedLoopMs"]
        if not isinstance(bound, int) or isinstance(bound, bool) or bound <= 0 or bound > 2000:
            raise DdeError(
                "POLICY_DENIED",
                "boundedLoopMs must be an integer 1..2000",
                retryable=False,
            )
