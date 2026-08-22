"""Auto-mark unit tests that require live backing services (PostgreSQL/Redis).

`just test-unit` runs this directory with `-m "not integration"` so the pure
suite passes on any host -- including Windows -- without the devcontainer's
services. Marking is derived here, once, instead of sprinkling decorators
across ~40 files: a test is `integration` when its module is one of the
`*_postgres.py` service-backed suites, imports the shared database helpers,
or talks to Redis directly. New suites matching either shape are picked up
automatically; a genuinely pure test is never deselected.
"""

from __future__ import annotations

import pytest

_SOURCE_HINTS = ("from tests.support.db import", "import redis")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    source_cache: dict[object, str] = {}
    for item in items:
        if item.path.name.endswith("_postgres.py"):
            item.add_marker(pytest.mark.integration)
            continue
        if item.path not in source_cache:
            source_cache[item.path] = item.path.read_text(encoding="utf-8")
        if any(hint in source_cache[item.path] for hint in _SOURCE_HINTS):
            item.add_marker(pytest.mark.integration)
