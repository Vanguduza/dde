"""Pinned OpenAI ChatGPT/Codex plugin catalogue for Production VEKL discovery.

This module records a narrow, DDE-owned metadata snapshot of high-value engineering
plugins observed in OpenAI's public ``openai/plugins`` repository.  It does not copy
upstream skill instructions, install plugins, authorize ChatGPT/Codex, grant egress,
or qualify executable components.  Each seed materializes only as a
``PACKAGE_METADATA``/``DISCOVERY_ONLY`` VEKL candidate so the normal Source
Intelligence, licence, component-decomposition, capability and execution-qualification
pipeline still governs any later use.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.core.hashing import canonical_json, sha256_hex
from engine.vekl.models import VEKLResourceSpec

CATALOG_ID = "dde.openai-chatgpt-codex-plugin-catalog"
CATALOG_SNAPSHOT_DATE = "2026-09-08"
OPENAI_PLUGINS_REPOSITORY = "https://github.com/openai/plugins"
OPENAI_PLUGINS_COMMIT = "1e285826e604f66f7208f7ac4dba0fe8341d1f57"
OPENAI_PLUGIN_HELP = (
    "https://help.openai.com/en/articles/20001256-plugins-in-chatgpt-and-codex"
)


@dataclass(frozen=True)
class OpenAIPluginSeed:
    """Non-executable metadata for one exact upstream plugin bundle."""

    name: str
    version: str
    upstream_license: str
    skill_ids: tuple[str, ...]
    has_app: bool = False
    has_mcp: bool = False
    additional_component_surfaces: tuple[str, ...] = ()

    @property
    def component_surfaces(self) -> tuple[str, ...]:
        surfaces = ["SKILL"]
        if self.has_app:
            surfaces.append("APP")
        if self.has_mcp:
            surfaces.append("MCP_SERVER")
        surfaces.extend(self.additional_component_surfaces)
        return tuple(dict.fromkeys(surfaces))

    @property
    def manifest_path(self) -> str:
        return f"plugins/{self.name}/.codex-plugin/plugin.json"

    @property
    def content_hash(self) -> str:
        return sha256_hex(
            canonical_json(
                {
                    "catalog_id": CATALOG_ID,
                    "snapshot_date": CATALOG_SNAPSHOT_DATE,
                    "repository": OPENAI_PLUGINS_REPOSITORY,
                    "commit": OPENAI_PLUGINS_COMMIT,
                    "name": self.name,
                    "version": self.version,
                    "license": self.upstream_license,
                    "skill_ids": list(self.skill_ids),
                    "has_app": self.has_app,
                    "has_mcp": self.has_mcp,
                    "component_surfaces": list(self.component_surfaces),
                }
            )
        )

    def to_resource_spec(self) -> VEKLResourceSpec:
        """Return a DDE-authored discovery candidate with zero runtime authority."""

        surfaces = ",".join(self.component_surfaces)
        body = (
            f"OpenAI plugin {self.name} {self.version}; "
            f"{len(self.skill_ids)} skill(s); surfaces={surfaces}."
        )
        return VEKLResourceSpec(
            resource_kind="PACKAGE_METADATA",
            title=f"OpenAI plugin catalogue: {self.name}",
            publisher="DDE",
            source_uri=None,
            revision=f"{OPENAI_PLUGINS_COMMIT}:{self.version}",
            content_hash=self.content_hash,
            source_trust="S7_DISCOVERY_ONLY",
            reuse_class="SOURCE_REFERENCE_ONLY",
            activation_modes=["DISCOVERY_ONLY"],
            license_ids=["DDE_PROJECT"],
            provenance={
                "source": CATALOG_ID,
                "hash_verified": True,
                "offline_pin_available": True,
                "upstream_publisher": "OpenAI",
                "upstream_repository": OPENAI_PLUGINS_REPOSITORY,
                "upstream_commit": OPENAI_PLUGINS_COMMIT,
                "upstream_manifest_path": self.manifest_path,
                "upstream_plugin_version": self.version,
                "upstream_license": self.upstream_license,
                "skill_ids": list(self.skill_ids),
                "skill_paths": [
                    f"plugins/{self.name}/skills/{skill_id}/SKILL.md"
                    for skill_id in self.skill_ids
                ],
                "has_app": self.has_app,
                "has_mcp": self.has_mcp,
                "component_surfaces": list(self.component_surfaces),
                "observed_at": CATALOG_SNAPSHOT_DATE,
                "official_plugin_help": OPENAI_PLUGIN_HELP,
                "authority": "DISCOVERY_METADATA_ONLY",
                "caveats": [
                    "metadata seed is not upstream skill content",
                    "plugin installation is not execution qualification",
                    "apps/MCP/tools require independent component qualification",
                    "Project Truth and DDE policy always win",
                ],
            },
            required_capabilities=[],
            filesystem_scopes=[],
            network_scopes=[],
            secret_scopes=[],
            sandbox_requirements={},
            side_effect_class="PURE_READ",
            required_verifiers=[],
            stack_constraints={},
            truth_constraints={},
            freshness={"stale": False, "snapshot": CATALOG_SNAPSHOT_DATE},
            budget={"tokens": max(1, len(body) // 4)},
            content_excerpt=body,
        )


OPENAI_ENGINEERING_PLUGIN_SEEDS: dict[str, OpenAIPluginSeed] = {
    "build-ios-apps": OpenAIPluginSeed(
        name="build-ios-apps",
        version="0.1.2",
        upstream_license="MIT",
        has_mcp=True,
        additional_component_surfaces=("AGENT", "SCRIPT"),
        skill_ids=(
            "ios-app-intents",
            "ios-debugger-agent",
            "ios-ettrace-performance",
            "ios-memgraph-leaks",
            "ios-simulator-browser",
            "swiftui-liquid-glass",
            "swiftui-performance-audit",
            "swiftui-ui-patterns",
            "swiftui-view-refactor",
        ),
    ),
    "build-macos-apps": OpenAIPluginSeed(
        name="build-macos-apps",
        version="0.1.4",
        upstream_license="MIT",
        additional_component_surfaces=("AGENT", "COMMAND"),
        skill_ids=(
            "appkit-interop",
            "build-run-debug",
            "liquid-glass",
            "packaging-notarization",
            "signing-entitlements",
            "swiftpm-macos",
            "swiftui-patterns",
            "telemetry",
            "test-triage",
            "view-refactor",
            "window-management",
        ),
    ),
    "build-web-apps": OpenAIPluginSeed(
        name="build-web-apps",
        version="0.1.2",
        upstream_license="MIT",
        additional_component_surfaces=("AGENT",),
        skill_ids=(
            "frontend-app-builder",
            "frontend-testing-debugging",
            "react-best-practices",
            "shadcn-best-practices",
            "stripe-best-practices",
            "supabase-best-practices",
        ),
    ),
    "build-web-data-visualization": OpenAIPluginSeed(
        name="build-web-data-visualization",
        version="0.1.21",
        upstream_license="MIT",
        additional_component_surfaces=("AGENT",),
        skill_ids=(
            "accessibility-and-inclusive-visualization",
            "canvas2d-data-visualization",
            "d3-data-visualization",
            "dashboards-and-real-time-visualization",
            "data-visualization",
            "gantt-chart-visualization",
            "geospatial-and-cartographic-visualization",
            "grammar-of-graphics-and-declarative-visualization",
            "node-link-and-diagram-layout",
            "react-and-nextjs-data-visualization",
            "reports-pdfs-and-slide-automation",
            "scrollytelling-and-parallax-data-visualization",
            "statistical-and-uncertainty-visualization",
            "testing-data-visualizations",
            "threejs-data-visualization",
            "typescript-data-visualization-engineering",
            "uml-and-software-architecture-visualization",
            "visualization-strategy-and-critique",
        ),
    ),
    "openai-developers": OpenAIPluginSeed(
        name="openai-developers",
        version="1.2.3",
        upstream_license="Proprietary",
        has_app=True,
        has_mcp=True,
        additional_component_surfaces=("AGENT", "SCRIPT"),
        skill_ids=(
            "agents-sdk",
            "build-chatgpt-app",
            "chatgpt-app-submission",
            "openai-api-troubleshooting",
            "openai-platform-api-key",
        ),
    ),
    "product-design": OpenAIPluginSeed(
        name="product-design",
        version="0.1.52",
        upstream_license="Proprietary",
        additional_component_surfaces=("AGENT", "SCRIPT"),
        skill_ids=(
            "audit",
            "design-qa",
            "get-context",
            "ideate",
            "image-to-code",
            "index",
            "research",
            "share",
            "url-to-code",
            "user-context",
        ),
    ),
    "codex-security": OpenAIPluginSeed(
        name="codex-security",
        version="0.1.22",
        upstream_license="Proprietary",
        has_app=True,
        has_mcp=True,
        additional_component_surfaces=("AGENT", "SCRIPT"),
        skill_ids=(
            "attack-path-analysis",
            "deep-security-scan",
            "define-security-policy",
            "finding-discovery",
            "fix-finding",
            "propose-security-hardening",
            "security-diff-scan",
            "security-scan",
            "threat-model",
            "track-findings",
            "triage-finding",
            "validation",
            "verify-fix",
            "vulnerability-writeup",
        ),
    ),
    "test-android-apps": OpenAIPluginSeed(
        name="test-android-apps",
        version="0.1.2",
        upstream_license="MIT",
        additional_component_surfaces=("AGENT", "SCRIPT"),
        skill_ids=("android-emulator-qa", "android-performance"),
    ),
    "plugin-eval": OpenAIPluginSeed(
        name="plugin-eval",
        version="0.1.2",
        upstream_license="MIT",
        additional_component_surfaces=("AGENT", "SCRIPT"),
        skill_ids=(
            "evaluate-plugin",
            "evaluate-skill",
            "improve-skill",
            "metric-pack-designer",
            "plugin-eval",
        ),
    ),
    "data-analytics": OpenAIPluginSeed(
        name="data-analytics",
        version="0.2.8",
        upstream_license="Proprietary",
        has_app=True,
        has_mcp=True,
        additional_component_surfaces=("AGENT", "SCRIPT"),
        skill_ids=(
            "analyze-data-quality",
            "build-dashboard",
            "build-report",
            "report-to-google-doc",
            "report-to-google-slides",
            "report-to-pdf",
            "create-data-context",
            "design-kpis",
            "gather-business-context",
            "index",
            "jupyter-notebooks",
            "kpi-reporting",
            "market-sizing",
            "metric-diagnostics",
            "product-business-analysis",
            "publish-artifact-to-sites",
            "validate-data",
            "visualize-data",
        ),
    ),
}


def openai_plugin_catalog_specs(
    names: tuple[str, ...] | None = None,
) -> list[VEKLResourceSpec]:
    """Return deterministic metadata-only candidates for selected catalogue entries."""

    selected = tuple(OPENAI_ENGINEERING_PLUGIN_SEEDS) if names is None else names
    unknown = sorted(set(selected) - set(OPENAI_ENGINEERING_PLUGIN_SEEDS))
    if unknown:
        raise ValueError(f"unknown OpenAI plugin seed(s): {', '.join(unknown)}")
    return [
        OPENAI_ENGINEERING_PLUGIN_SEEDS[name].to_resource_spec() for name in selected
    ]
