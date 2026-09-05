"""DDE-069 Frontend Studio read transport is present and mission scoped."""

from __future__ import annotations

from engine.gateway.api import router

EXPECTED = {
    "/v1/missions/{mission_id}/frontend/snapshot",
    "/v1/missions/{mission_id}/frontend/chat",
    "/v1/missions/{mission_id}/frontend/previews/{preview_session_id}",
    "/v1/missions/{mission_id}/frontend/inspector/{candidate_id}",
}


def test_frontend_read_routes_are_registered_on_the_gateway() -> None:
    paths = {route.path for route in router.routes}
    assert EXPECTED <= paths


def test_frontend_reads_are_get_only() -> None:
    by_path = {route.path: route for route in router.routes if route.path in EXPECTED}
    assert set(by_path) == EXPECTED
    for route in by_path.values():
        assert route.methods == {"GET"}
