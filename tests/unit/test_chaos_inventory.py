"""Chaos catalog: every DDE-061 scenario is named, and named files exist."""

from __future__ import annotations

from pathlib import Path

from tests.support.chaos_inventory import (
    CHAOS_SCENARIO_NAMES,
    SCENARIOS,
    assert_chaos_inventory_complete,
)

ROOT = Path(__file__).resolve().parents[2]
CATALOG_MD = ROOT / "evals" / "chaos" / "catalog.md"


def test_chaos_catalog_covers_every_scenario_and_named_files_exist() -> None:
    assert_chaos_inventory_complete()
    assert tuple(item.scenario for item in SCENARIOS) == CHAOS_SCENARIO_NAMES
    assert CATALOG_MD.is_file()
    catalog = CATALOG_MD.read_text(encoding="utf-8")
    for item in SCENARIOS:
        assert item.scenario in catalog, item.scenario
        for relative in item.named_tests:
            assert (ROOT / relative).is_file(), relative
        assert item.production_call_sites
