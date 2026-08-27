"""Named certified fixture suites for Chapter 16.5 non-latency SLOs.

These suites already exist. DDE-063 does not copy them. The inventory is
the production catalog that names which fixtures gate each SLO.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SLO_FIXTURE_SUITES: dict[str, tuple[str, ...]] = {
    "mission_state_reconstruction": (
        "tests/recovery/test_missions_recovery.py",
        "tests/recovery/test_checkpoints_recovery.py",
    ),
    "duplicate_side_effect_prevention": (
        "tests/recovery/test_external_effects_recovery.py",
        "tests/unit/test_external_effects_postgres.py",
    ),
    "lease_fail_closed": (
        "tests/unit/test_capability_lease_enforcement.py",
        "tests/unit/test_capability_leases_postgres.py",
    ),
    "worker_replacement_without_mission_loss": ("tests/unit/test_chaos_suite.py",),
    "checkpoint_recovery": (
        "tests/recovery/test_checkpoints_recovery.py",
        "tests/unit/test_checkpoints_postgres.py",
    ),
    "post_integration_verification": (
        "tests/unit/test_integration_queue_postgres.py",
        "tests/recovery/test_diff_gates_recovery.py",
    ),
    "gateway_reconnect": (
        "tests/unit/test_android_gateway_reconnect.py",
        "tests/unit/test_gateway_sessions.py",
    ),
}


def missing_fixture_files() -> list[str]:
    missing: list[str] = []
    for paths in SLO_FIXTURE_SUITES.values():
        for relative in paths:
            if not (ROOT / relative).is_file():
                missing.append(relative)
    return missing
