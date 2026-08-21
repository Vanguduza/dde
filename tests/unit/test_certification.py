"""Chapter 8.5 certification policy (pure, no I/O)."""

from __future__ import annotations

from engine.workers.certification import (
    SMOKE_FIXTURE_IDS,
    SMOKE_MAX_USD,
    ProfileIdentity,
    profile_hash,
    selectable,
)


def test_profile_hash_changes_when_any_tuple_part_changes() -> None:
    base = ProfileIdentity(
        model_version="m1",
        harness_version="h1",
        toolset_manifest="t1",
        image_digest="d1",
    )
    changed = ProfileIdentity(
        model_version="m2",
        harness_version="h1",
        toolset_manifest="t1",
        image_digest="d1",
    )
    assert profile_hash(base) != profile_hash(changed)
    assert profile_hash(base) == profile_hash(
        ProfileIdentity(
            model_version="m1",
            harness_version="h1",
            toolset_manifest="t1",
            image_digest="d1",
        )
    )


def test_stale_is_selectable_only_in_development() -> None:
    assert selectable("CERTIFIED", environment_class="production") is True
    assert selectable("STALE", environment_class="development") is True
    assert selectable("STALE", environment_class="production") is False
    assert selectable("STALE", environment_class="staging") is False
    assert selectable("STALE", environment_class="security") is False
    assert selectable("ABSENT", environment_class="development") is False


def test_smoke_tier_names_twelve_fixtures_and_a_usd_ceiling() -> None:
    assert len(SMOKE_FIXTURE_IDS) == 12
    assert "tool_call_correctness" in SMOKE_FIXTURE_IDS
    assert "cost_reporting_accuracy" in SMOKE_FIXTURE_IDS
    assert SMOKE_MAX_USD == 5.0
