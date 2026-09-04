"""DDE-069 — every generated screen is bound to DDE-068 by default.

This is the carry-over DDE-068 recorded and deliberately left open. That
mission proved a *bound* visual check is machine-gated at promotion; what
did not exist was anything that authors the binding. Without it the
guarantee reads "a bound check refuses" instead of "every generated
screen is checked", and the difference is a screen that promotes on code
validity alone.

These tests are pure -- the policy and spec construction need no
database. The persisted half is
`test_screen_acceptance_binding_postgres.py`.
"""

from __future__ import annotations

import json

import pytest

from engine.context.repo import repo_root
from engine.core.errors import DdeError
from engine.core.ids import uuid7
from engine.studio.acceptance.defaults import (
    GENERATED_SCREEN,
    IMPORTED_SCREEN,
    POLICY_RELATIVE,
    assert_mandatory_bindings,
    build_screen_specs,
    load_defaults,
    mandatory_kinds,
)
from engine.verification.checks import CheckSpec


def test_policy_is_versioned_and_inspectable_in_the_repository() -> None:
    """FRONTEND_STUDIO_REV3 section 42: defaults are versioned and
    inspectable, not buried in frontend constants."""
    document = json.loads((repo_root() / POLICY_RELATIVE).read_text(encoding="utf-8"))
    assert document["policy_version"] >= 1
    for name in (GENERATED_SCREEN, IMPORTED_SCREEN):
        profile = document["profiles"][name]
        assert profile["mandatory_kinds"], name
        # Each mandatory kind states why it is mandatory, so raising the
        # bar later is an argued change rather than an edit.
        for kind in profile["mandatory_kinds"]:
            assert profile["rationale"][kind]


def test_the_dde068_visual_kinds_are_mandatory_for_a_generated_screen() -> None:
    kinds = mandatory_kinds(GENERATED_SCREEN)
    assert "silhouette" in kinds
    assert "visual_critique" in kinds


def test_an_imported_screen_is_held_to_the_same_visual_bar() -> None:
    """Provenance is not evidence of quality; an adopted template is the
    likeliest source of a generic-layout near-match."""
    assert set(mandatory_kinds(IMPORTED_SCREEN)) >= {
        "silhouette",
        "visual_critique",
    }


def test_default_specs_render_the_screen_and_carry_stable_refs() -> None:
    specs = build_screen_specs(
        screen_ref="screens/checkout",
        preview_url="file:///tmp/checkout.html",
        expect_text="Order summary",
    )
    by_kind = {spec.kind: spec for spec in specs}
    assert set(by_kind) == {"silhouette", "visual_critique"}
    for kind, spec in by_kind.items():
        assert spec.ref == f"screens/checkout:{kind}"
        assert spec.command[0] == "file:///tmp/checkout.html"
        assert spec.command[1] == "Order summary"
        assert spec.statement.strip()
        assert spec.is_negative_case is False


def test_visual_diff_is_only_bound_when_a_golden_spec_exists() -> None:
    """Binding a diff with no golden would fail closed on every run for
    the wrong reason, which teaches people to ignore the gate."""
    without = build_screen_specs(screen_ref="screens/a", preview_url="file:///a.html")
    assert "visual_diff" not in {spec.kind for spec in without}

    with_golden = build_screen_specs(
        screen_ref="screens/a",
        preview_url="file:///a.html",
        visual_diff_spec_path="visual/checkout.json",
    )
    diff = next(spec for spec in with_golden if spec.kind == "visual_diff")
    assert diff.command == ["visual/checkout.json"]


def test_a_screen_without_a_preview_url_cannot_be_bound() -> None:
    with pytest.raises(DdeError) as excinfo:
        build_screen_specs(screen_ref="screens/a", preview_url="")
    assert excinfo.value.error_code == "VALIDATION_FAILED"


def test_an_unknown_profile_is_refused_rather_than_defaulted() -> None:
    """A silent default is how a screen ends up under a weaker bar than
    whoever wrote the caller intended."""
    with pytest.raises(DdeError) as excinfo:
        build_screen_specs(
            screen_ref="screens/a",
            preview_url="file:///a.html",
            profile="whatever",
        )
    assert excinfo.value.error_code == "VALIDATION_FAILED"
    assert "known" in excinfo.value.details


def _functional_spec() -> CheckSpec:
    return CheckSpec(
        outcome_id=uuid7(),
        statement="unit tests pass",
        kind="test",
        ref="screens/a:test",
        command=["pytest", "-q"],
    )


def test_assembling_your_own_specs_cannot_drop_a_mandatory_binding() -> None:
    """The fail-closed half. An authoring path that builds its own list
    and omits visual_critique must be refused, not accommodated."""
    with pytest.raises(DdeError) as excinfo:
        assert_mandatory_bindings([_functional_spec()], screen_ref="screens/a")
    assert excinfo.value.error_code == "POLICY_DENIED"
    assert set(excinfo.value.details["missing_kinds"]) == {
        "silhouette",
        "visual_critique",
    }

    partial = [
        _functional_spec(),
        *[
            spec
            for spec in build_screen_specs(
                screen_ref="screens/a", preview_url="file:///a.html"
            )
            if spec.kind == "silhouette"
        ],
    ]
    with pytest.raises(DdeError) as excinfo:
        assert_mandatory_bindings(partial, screen_ref="screens/a")
    assert excinfo.value.details["missing_kinds"] == ["visual_critique"]


def test_extra_functional_specs_satisfy_the_assertion_alongside_defaults() -> None:
    merged = (
        _functional_spec(),
        *build_screen_specs(screen_ref="screens/a", preview_url="file:///a.html"),
    )
    assert_mandatory_bindings(merged, screen_ref="screens/a")


def test_a_missing_policy_file_fails_closed(tmp_path) -> None:
    load_defaults.cache_clear()
    try:
        with pytest.raises(DdeError) as excinfo:
            load_defaults(tmp_path)
        assert excinfo.value.error_code == "CONTEXT_INCOMPLETE"
    finally:
        load_defaults.cache_clear()
