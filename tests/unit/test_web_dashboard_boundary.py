"""DDE-052 web dashboard: package boundary + honesty pins (no Core)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = ROOT / "interfaces" / "dashboard"
STATIC = DASHBOARD / "static"

# Paths the browser client may call — keep in sync with gateway.js.
ALLOWED_PATH_MARKERS = (
    "/v1/sessions",
    "/v1/commands",
    "/v1/missions/",
    "/v1/mission-control/",
)


def test_dashboard_package_exists_with_operator_shell() -> None:
    assert (DASHBOARD / "README.md").is_file()
    for name in ("index.html", "app.js", "gateway.js", "styles.css"):
        assert (STATIC / name).is_file(), name


def test_dashboard_never_imports_engine_or_sql() -> None:
    banned = re.compile(
        r"(from\s+engine\.|import\s+engine\b|sqlalchemy|asyncpg|CREATE TABLE)",
        re.IGNORECASE,
    )
    offenders: list[str] = []
    for path in DASHBOARD.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".py", ".js", ".ts", ".html", ".md", ".css"}:
            continue
        text = path.read_text(encoding="utf-8")
        if banned.search(text):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_gateway_js_only_documents_existing_endpoints() -> None:
    source = (STATIC / "gateway.js").read_text(encoding="utf-8")
    assert "ALLOWED_PATHS" in source
    # No invented list endpoints.
    assert "/v1/missions`" not in source
    assert '"/v1/missions"' not in source or "/v1/missions/{id}" in source
    assert "events" not in source.lower() or "last_event_at" in source
    for marker in ALLOWED_PATH_MARKERS:
        assert marker in source, marker


def test_app_js_does_not_fabricate_fleet_or_mission_lists() -> None:
    source = (STATIC / "app.js").read_text(encoding="utf-8")
    lowered = source.lower()
    assert "fabricat" not in lowered
    assert "fake mission" not in lowered
    assert "sample mission" not in lowered
    # Control commands must use real idempotency helpers.
    assert "idempotencyKey" in source or "idempotency_key" in source
