"""Flight Lab inventory: every Ch.19.1 suite is named, and named files exist.

Does not claim those existing tests *are* the Flight Lab. S7 scenarios
are in `test_flight_lab_golden_mission.py` and `test_flight_lab_force_push.py`.
"""

from __future__ import annotations

from pathlib import Path

from tests.support.flight_lab_inventory import (
    CH19_SUITE_NAMES,
    SUITES,
    assert_inventory_complete,
)

ROOT = Path(__file__).resolve().parents[2]
INVENTORY_MD = ROOT / "evals" / "golden-mission" / "ch19-inventory.md"


def test_ch19_inventory_covers_every_suite_and_named_files_exist() -> None:
    assert_inventory_complete()
    assert tuple(item.suite for item in SUITES) == CH19_SUITE_NAMES
    assert INVENTORY_MD.is_file()
    catalog = INVENTORY_MD.read_text(encoding="utf-8")
    for item in SUITES:
        assert item.suite in catalog, item.suite
        for relative in item.named_tests:
            assert (ROOT / relative).is_file(), relative
        assert item.production_call_sites
