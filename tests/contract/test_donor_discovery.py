"""DDE-066 contract pins: allowlist, grouping schema, no engine httpx."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from engine.donor.grouping import (
    DiscoveryHit,
    FeatureCategory,
    group_discovery_hits,
    grouped_results_as_dict,
)

ROOT = Path(__file__).resolve().parents[2]
DONOR = ROOT / "engine" / "donor"
ADAPTER = ROOT / "adapters" / "donor"
SCHEMA = ROOT / "schemas" / "design" / "grouped_donor_results.schema.json"
ALLOWLIST = ROOT / "schemas" / "design" / "donor_search_allowlist.json"
BANNED_IMPORTS = frozenset(
    {"httpx", "requests", "aiohttp", "urllib3", "cursor_sdk", "anthropic"}
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_grouped_results_match_schema_required_shape() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    results = group_discovery_hits(
        prd_id="prd-1",
        features=(FeatureCategory(feature_id="feat-a", title="A"),),
        hits=(
            DiscoveryHit(
                source_uri="https://ui.shadcn.com/r/button",
                summary="MIT licensed shadcn button",
                feature_hints=("feat-a",),
            ),
        ),
    )
    payload = grouped_results_as_dict(results)
    for key in schema["required"]:
        assert key in payload
    hit = payload["groups"][0]["hits"][0]
    for key in schema["$defs"]["hit"]["required"]:
        assert key in hit
    assert hit["source_class"] != "UNKNOWN"


def test_allowlist_enumerates_edr_0015_hosts() -> None:
    catalog = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    hosts = {entry["host"] for entry in catalog["hosts"]}
    assert "api.github.com" in hosts
    assert "ui.shadcn.com" in hosts
    assert "registry.npmjs.org" in hosts
    assert "themeforest.net" in catalog["rejected_hosts"]


def test_engine_donor_does_not_import_http_clients() -> None:
    for path in DONOR.glob("*.py"):
        imported = _imported_modules(path)
        banned = imported & BANNED_IMPORTS
        assert not banned, f"{path} imports {banned}"


def test_http_adapter_is_the_httpx_site_and_ignores_environ() -> None:
    source = (ADAPTER / "http.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = _imported_modules(ADAPTER / "http.py")
    assert "httpx" in imported
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in {
            "environ",
            "getenv",
        }:
            raise AssertionError("donor HTTP adapter must not read process env")
    assert "os.environ" not in source
    assert "getenv" not in source


def test_no_taste_or_impeccable_skill_strings_in_donor_discovery() -> None:
    haystack = " ".join(path.read_text(encoding="utf-8") for path in DONOR.glob("*.py"))
    for needle in ("Impeccable", "vercel-labs/agent-skills", "taste-skill"):
        assert needle.lower() not in haystack.lower()
