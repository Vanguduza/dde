"""DDE-067 canvas mutations — token-bound HTML/manifest edits, no Gateway."""

from __future__ import annotations

import pytest

from engine.core.errors import DdeError
from engine.studio.canvas import (
    apply_insert,
    apply_move,
    apply_remove,
    apply_set_animation,
    apply_update,
    apply_upsert_step,
)
from engine.studio.tokens_catalog import assert_token_value, color_aliases


STARTER = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8" /></head>
<body></body></html>
"""


def test_color_aliases_are_css_vars_not_hex() -> None:
    aliases = color_aliases()
    assert "--accent-primary" in aliases
    assert "--text-primary" in aliases
    assert all(item.startswith("--") for item in aliases)
    assert not any(item.startswith("#") for item in aliases)


def test_assert_token_value_refuses_hex_and_px() -> None:
    with pytest.raises(DdeError) as captured:
        assert_token_value("color", "#1177bb")
    assert captured.value.error_code == "POLICY_DENIED"
    with pytest.raises(DdeError):
        assert_token_value("spacing", "12px")
    with pytest.raises(DdeError):
        assert_token_value("duration", "120ms")
    assert_token_value("color", "--accent-primary")
    assert_token_value("spacing", "space3")
    assert_token_value("duration", "motion-duration-base")


def test_insert_update_move_remove_round_trip() -> None:
    html, first = apply_insert(
        STARTER,
        kind="button",
        anchor_parent="root",
        position_index=0,
        label="Save",
    )
    assert f'data-dde-el="{first}"' in html
    html = apply_update(
        html, element_id=first, property_name="color", value="--accent-primary"
    )
    assert "var(--accent-primary)" in html
    html, second = apply_insert(
        html,
        kind="text",
        anchor_parent="root",
        position_index=1,
        label="Hint",
    )
    html = apply_move(
        html,
        element_id=second,
        new_anchor_parent="root",
        new_position_index=0,
    )
    html = apply_remove(html, element_id=first)
    assert first not in html
    assert second in html


def test_update_refuses_freehand_literal() -> None:
    html, element_id = apply_insert(
        STARTER,
        kind="button",
        anchor_parent="root",
        position_index=0,
        label="Go",
    )
    with pytest.raises(DdeError) as captured:
        apply_update(html, element_id=element_id, property_name="color", value="#fff")
    assert captured.value.error_code == "POLICY_DENIED"


def test_set_animation_and_upsert_step() -> None:
    manifest: dict[str, object] = {
        "version": 1,
        "flows": [
            {
                "id": "checkout",
                "entry": "cart.ready.html",
                "steps": [
                    {
                        "from": "cart.ready.html",
                        "on": "[data-dde-el=pay]",
                        "to": "pay.ready.html",
                    }
                ],
            }
        ],
    }
    apply_set_animation(
        manifest,
        flow_id="checkout",
        step_index=0,
        animation={
            "durationToken": "motion-duration-fast",
            "easingToken": "motion-easing-arrival",
            "reducedMotionVariant": True,
        },
    )
    steps = manifest["flows"][0]["steps"]  # type: ignore[index]
    assert steps[0]["animation"]["durationToken"] == "motion-duration-fast"
    apply_upsert_step(
        manifest,
        flow_id="checkout",
        step_index=1,
        from_file="pay.ready.html",
        on="[data-dde-el=done]",
        to_file="done.ready.html",
    )
    assert len(steps) == 2
    with pytest.raises(DdeError):
        apply_set_animation(
            manifest,
            flow_id="checkout",
            step_index=0,
            animation={
                "durationToken": "120ms",
                "easingToken": "ease-out",
            },
        )
