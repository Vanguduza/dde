"""Pinned OpenAI ChatGPT/Codex plugin-catalog VEKL tests."""

from __future__ import annotations

import pytest

from engine.vekl.openai_catalog import (
    CATALOG_ID,
    OPENAI_ENGINEERING_PLUGIN_SEEDS,
    OPENAI_PLUGINS_COMMIT,
    openai_plugin_catalog_specs,
)


def test_openai_catalog_is_exact_pinned_discovery_metadata_only() -> None:
    specs = openai_plugin_catalog_specs()
    assert len(specs) == len(OPENAI_ENGINEERING_PLUGIN_SEEDS) == 10
    total_skills = sum(
        len(seed.skill_ids) for seed in OPENAI_ENGINEERING_PLUGIN_SEEDS.values()
    )
    assert total_skills == 98
    assert len({spec.content_hash for spec in specs}) == len(specs)

    for spec in specs:
        assert spec.resource_kind == "PACKAGE_METADATA"
        assert spec.publisher == "DDE"
        assert spec.source_uri is None
        assert spec.source_trust == "S7_DISCOVERY_ONLY"
        assert spec.reuse_class == "SOURCE_REFERENCE_ONLY"
        assert spec.activation_modes == ["DISCOVERY_ONLY"]
        assert spec.required_capabilities == []
        assert spec.filesystem_scopes == []
        assert spec.network_scopes == []
        assert spec.secret_scopes == []
        assert spec.side_effect_class == "PURE_READ"
        assert spec.provenance["source"] == CATALOG_ID
        assert spec.provenance["upstream_commit"] == OPENAI_PLUGINS_COMMIT
        assert spec.provenance["authority"] == "DISCOVERY_METADATA_ONLY"


def test_openai_catalog_contains_high_value_application_engineering_families() -> None:
    ios = OPENAI_ENGINEERING_PLUGIN_SEEDS["build-ios-apps"]
    web = OPENAI_ENGINEERING_PLUGIN_SEEDS["build-web-apps"]
    android = OPENAI_ENGINEERING_PLUGIN_SEEDS["test-android-apps"]
    design = OPENAI_ENGINEERING_PLUGIN_SEEDS["product-design"]
    developers = OPENAI_ENGINEERING_PLUGIN_SEEDS["openai-developers"]
    security = OPENAI_ENGINEERING_PLUGIN_SEEDS["codex-security"]

    assert "swiftui-ui-patterns" in ios.skill_ids
    assert "ios-simulator-browser" in ios.skill_ids
    assert "frontend-testing-debugging" in web.skill_ids
    assert "android-emulator-qa" in android.skill_ids
    assert "image-to-code" in design.skill_ids
    assert "design-qa" in design.skill_ids
    assert "build-chatgpt-app" in developers.skill_ids
    assert developers.has_mcp and developers.has_app
    assert "security-scan" in security.skill_ids
    assert security.has_mcp and security.has_app


def test_openai_catalog_records_bundle_component_surfaces() -> None:
    expected_counts = {
        "SKILL": 10,
        "APP": 3,
        "MCP_SERVER": 4,
        "AGENT": 10,
        "SCRIPT": 7,
        "COMMAND": 1,
    }
    observed = {surface: 0 for surface in expected_counts}
    for seed in OPENAI_ENGINEERING_PLUGIN_SEEDS.values():
        for surface in seed.component_surfaces:
            observed[surface] = observed.get(surface, 0) + 1

    assert observed == expected_counts
    macos = OPENAI_ENGINEERING_PLUGIN_SEEDS["build-macos-apps"]
    assert macos.component_surfaces == ("SKILL", "AGENT", "COMMAND")
    ios = OPENAI_ENGINEERING_PLUGIN_SEEDS["build-ios-apps"]
    assert ios.component_surfaces == ("SKILL", "MCP_SERVER", "AGENT", "SCRIPT")

    for spec in openai_plugin_catalog_specs():
        surfaces = spec.provenance["component_surfaces"]
        assert isinstance(surfaces, list)
        assert "SKILL" in surfaces
        assert spec.activation_modes == ["DISCOVERY_ONLY"]
        assert spec.required_capabilities == []
        assert spec.network_scopes == []
        assert spec.secret_scopes == []


def test_personal_appcreator_claim_is_not_misclassified_as_openai_first_party() -> None:
    all_skill_ids = {
        skill_id.lower()
        for seed in OPENAI_ENGINEERING_PLUGIN_SEEDS.values()
        for skill_id in seed.skill_ids
    }
    assert "appcreator" not in all_skill_ids
    assert "app-creator" not in all_skill_ids


def test_openai_catalog_selection_is_deterministic_and_rejects_unknown_names() -> None:
    names = ("build-ios-apps", "build-web-apps")
    first = openai_plugin_catalog_specs(names)
    second = openai_plugin_catalog_specs(names)
    assert [item.content_hash for item in first] == [
        item.content_hash for item in second
    ]
    assert [item.title for item in first] == [
        "OpenAI plugin catalogue: build-ios-apps",
        "OpenAI plugin catalogue: build-web-apps",
    ]
    with pytest.raises(ValueError, match="unknown OpenAI plugin"):
        openai_plugin_catalog_specs(("not-a-real-plugin",))
