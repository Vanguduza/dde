"""DDE-069 M2 — the golden visual authority is pinned, or it fails closed.

AD-035 makes a user-approved 1672x941 mockup the canonical DDE visual
baseline. These tests exist so that the *difference* between "Project
Truth describes an image" and "the repository can read that image" stays
visible and machine-checked, rather than being papered over by prose.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from engine.context.repo import repo_root
from engine.core.errors import DdeError
from engine.studio.golden_visual import (
    GoldenArtifactState,
    get_artifact,
    load_manifest,
    require_pixel_reference,
)

PRIMARY = "frontend-studio-shell"


def test_manifest_pins_the_ad035_frontend_studio_baseline() -> None:
    artifacts = load_manifest(repo_root())
    primary = [item for item in artifacts if item.is_primary_desktop_baseline]
    assert len(primary) == 1, "exactly one primary desktop visual baseline"
    shell = primary[0]
    assert shell.artifact_id == PRIMARY
    # The approved viewport is Project Truth, not a preference.
    assert (shell.expected_width_px, shell.expected_height_px) == (1672, 941)
    assert shell.approved_on == "2026-09-03"
    assert "AD-035" in shell.authority


def test_absent_artifact_is_reported_as_missing_not_as_conformance() -> None:
    """The honest state today. This test is expected to change to PINNED
    the moment the owner commits the approved image and records its hash;
    it must never be changed to make an absent artifact look present."""
    shell = get_artifact(repo_root(), PRIMARY)
    if shell.state is GoldenArtifactState.PINNED:
        pytest.skip("artifact has since been supplied; covered by the pinned test")
    assert shell.state is GoldenArtifactState.ARTIFACT_MISSING
    assert shell.pixel_reference_available is False
    assert shell.observed_sha256 is None


def test_pixel_reference_claim_fails_closed_while_unpinned() -> None:
    shell = get_artifact(repo_root(), PRIMARY)
    if shell.pixel_reference_available:
        assert require_pixel_reference(repo_root(), PRIMARY).state is (
            GoldenArtifactState.PINNED
        )
        return
    with pytest.raises(DdeError) as excinfo:
        require_pixel_reference(repo_root(), PRIMARY)
    assert excinfo.value.error_code == "CONTEXT_INCOMPLETE"
    # The refusal must name where the structural fallback lives, so a
    # caller is pointed at the honest claim rather than left stuck.
    assert excinfo.value.details["structural_specification"]


def test_unknown_artifact_id_is_refused() -> None:
    with pytest.raises(DdeError) as excinfo:
        get_artifact(repo_root(), "not-a-real-artifact")
    assert excinfo.value.error_code == "CONTEXT_INCOMPLETE"


def test_a_supplied_artifact_is_detected_and_hash_checked(tmp_path) -> None:
    """Prove the mechanism actually pins, rather than only ever reporting
    absence: build a manifest over a real PNG and sweep every state."""
    png = _png_bytes(1672, 941)
    (tmp_path / "docs" / "truth" / "golden").mkdir(parents=True)
    artifact_path = tmp_path / "docs" / "truth" / "golden" / "shell.png"
    artifact_path.write_bytes(png)
    digest = hashlib.sha256(png).hexdigest()

    def write_manifest(sha: str | None, width: int = 1672) -> None:
        (
            tmp_path / "docs" / "truth" / "golden" / "GOLDEN_VISUAL_MANIFEST.json"
        ).write_text(
            json.dumps(
                {
                    "manifest_version": 1,
                    "artifacts": [
                        {
                            "id": PRIMARY,
                            "title": "t",
                            "authority": "AD-035",
                            "approved_on": "2026-09-03",
                            "revision": 1,
                            "is_primary_desktop_baseline": True,
                            "expected_path": "docs/truth/golden/shell.png",
                            "expected_width_px": width,
                            "expected_height_px": 941,
                            "content_sha256": sha,
                            "state_note": "",
                            "structural_specification": "spec",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    write_manifest(digest)
    assert get_artifact(tmp_path, PRIMARY).state is GoldenArtifactState.PINNED
    assert require_pixel_reference(tmp_path, PRIMARY).observed_sha256 == digest

    write_manifest(None)
    assert get_artifact(tmp_path, PRIMARY).state is (
        GoldenArtifactState.HASH_UNRECORDED
    )

    write_manifest("0" * 64)
    assert get_artifact(tmp_path, PRIMARY).state is GoldenArtifactState.HASH_MISMATCH

    write_manifest(digest, width=1440)
    assert get_artifact(tmp_path, PRIMARY).state is (
        GoldenArtifactState.DIMENSION_MISMATCH
    )

    artifact_path.write_bytes(b"not a png at all")
    write_manifest(digest)
    assert get_artifact(tmp_path, PRIMARY).state is GoldenArtifactState.UNREADABLE

    artifact_path.unlink()
    assert get_artifact(tmp_path, PRIMARY).state is (
        GoldenArtifactState.ARTIFACT_MISSING
    )


def _png_bytes(width: int, height: int) -> bytes:
    """Minimal valid PNG: signature + IHDR + IDAT + IEND."""
    import struct
    import zlib

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
