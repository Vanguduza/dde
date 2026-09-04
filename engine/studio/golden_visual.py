"""Golden visual authority — the pinned artifacts DDE accepts against.

`docs/truth/ARCHITECTURE_DECISIONS.md` AD-035 makes a user-approved
1672x941 Frontend Studio mockup the canonical visual baseline. Prose
describing an image is not the image: a claim of pixel-reference
conformance is only honest when the referenced pixels are actually
readable from the repository. This module is the fail-closed boundary
between the two claims.

Two conformance claims exist and must never be collapsed:

`STRUCTURAL`
    the implementation matches the normative measurements written into
    `FRONTEND_STUDIO_REV3.md` Part I (bar heights, panel widths, gutters,
    padding, gaps, token values). These are checkable without the image.

`PIXEL_REFERENCE`
    the rendered implementation matches the approved image itself. This
    requires the artifact; `pixel_reference_available` is the only thing
    that may authorise the claim.
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from engine.core.errors import DdeError

MANIFEST_RELATIVE: Final = "docs/truth/golden/GOLDEN_VISUAL_MANIFEST.json"
_PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"


class GoldenArtifactState(StrEnum):
    """Why a pinned artifact can or cannot be used as a pixel reference."""

    PINNED = "PINNED"
    """File present, dimensions and content hash both match the manifest."""

    ARTIFACT_MISSING = "ARTIFACT_MISSING"
    """Manifest names the artifact; no file exists at `expected_path`."""

    HASH_UNRECORDED = "HASH_UNRECORDED"
    """File present but the manifest records no `content_sha256` to pin it
    to, so the file could be swapped without any check noticing."""

    HASH_MISMATCH = "HASH_MISMATCH"
    """File present and hashed, but it is not the approved artifact."""

    DIMENSION_MISMATCH = "DIMENSION_MISMATCH"
    """File present but not at the approved viewport."""

    UNREADABLE = "UNREADABLE"
    """File present but not a PNG this reader can measure."""


@dataclass(frozen=True)
class GoldenArtifact:
    """One pinned visual-authority artifact and its verified state."""

    artifact_id: str
    title: str
    authority: str
    approved_on: str
    revision: int
    is_primary_desktop_baseline: bool
    expected_path: str
    expected_width_px: int
    expected_height_px: int
    declared_sha256: str | None
    observed_sha256: str | None
    observed_width_px: int | None
    observed_height_px: int | None
    state: GoldenArtifactState
    state_note: str
    structural_specification: str

    @property
    def pixel_reference_available(self) -> bool:
        """Whether a PIXEL_REFERENCE conformance claim is permitted."""
        return self.state is GoldenArtifactState.PINNED


def _png_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24 or not data.startswith(_PNG_SIGNATURE):
        return None
    if data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)


def _int(entry: dict[str, object], key: str) -> int:
    value = entry.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise DdeError(
            "VALIDATION_FAILED",
            f"golden manifest field {key} must be an integer",
            retryable=False,
            details={"artifact_id": str(entry.get("id"))},
        )
    return value


def _resolve(entry: dict[str, object], root: Path) -> GoldenArtifact:
    expected_path = str(entry["expected_path"])
    declared = entry.get("content_sha256")
    declared_sha256 = str(declared) if isinstance(declared, str) else None
    expected_width = _int(entry, "expected_width_px")
    expected_height = _int(entry, "expected_height_px")

    path = root / expected_path
    observed_sha256: str | None = None
    observed_width: int | None = None
    observed_height: int | None = None

    if not path.is_file():
        state = GoldenArtifactState.ARTIFACT_MISSING
    else:
        data = path.read_bytes()
        observed_sha256 = hashlib.sha256(data).hexdigest()
        dimensions = _png_dimensions(data)
        if dimensions is None:
            state = GoldenArtifactState.UNREADABLE
        else:
            observed_width, observed_height = dimensions
            if (observed_width, observed_height) != (expected_width, expected_height):
                state = GoldenArtifactState.DIMENSION_MISMATCH
            elif declared_sha256 is None:
                state = GoldenArtifactState.HASH_UNRECORDED
            elif declared_sha256 != observed_sha256:
                state = GoldenArtifactState.HASH_MISMATCH
            else:
                state = GoldenArtifactState.PINNED

    return GoldenArtifact(
        artifact_id=str(entry["id"]),
        title=str(entry["title"]),
        authority=str(entry["authority"]),
        approved_on=str(entry["approved_on"]),
        revision=_int(entry, "revision"),
        is_primary_desktop_baseline=bool(entry["is_primary_desktop_baseline"]),
        expected_path=expected_path,
        expected_width_px=expected_width,
        expected_height_px=expected_height,
        declared_sha256=declared_sha256,
        observed_sha256=observed_sha256,
        observed_width_px=observed_width,
        observed_height_px=observed_height,
        state=state,
        state_note=str(entry.get("state_note", "")),
        structural_specification=str(entry["structural_specification"]),
    )


def load_manifest(root: Path) -> tuple[GoldenArtifact, ...]:
    """Read the manifest and resolve every entry against the filesystem."""
    manifest_path = root / MANIFEST_RELATIVE
    if not manifest_path.is_file():
        raise DdeError(
            "CONTEXT_INCOMPLETE",
            "golden visual manifest is missing",
            retryable=False,
            details={"path": MANIFEST_RELATIVE},
        )
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = document.get("artifacts")
    if not isinstance(entries, list) or not entries:
        raise DdeError(
            "CONTEXT_INCOMPLETE",
            "golden visual manifest declares no artifacts",
            retryable=False,
            details={"path": MANIFEST_RELATIVE},
        )
    return tuple(_resolve(entry, root) for entry in entries)


def get_artifact(root: Path, artifact_id: str) -> GoldenArtifact:
    for artifact in load_manifest(root):
        if artifact.artifact_id == artifact_id:
            return artifact
    raise DdeError(
        "CONTEXT_INCOMPLETE",
        "unknown golden artifact id",
        retryable=False,
        details={"artifact_id": artifact_id},
    )


def require_pixel_reference(root: Path, artifact_id: str) -> GoldenArtifact:
    """Fail closed unless a PIXEL_REFERENCE claim is actually supportable.

    Callers that intend to compare rendered pixels against the approved
    image must go through here, so an absent artifact can never be
    silently downgraded into a pass.
    """
    artifact = get_artifact(root, artifact_id)
    if not artifact.pixel_reference_available:
        raise DdeError(
            "CONTEXT_INCOMPLETE",
            "golden artifact is not pinned; pixel-reference conformance "
            "cannot be claimed",
            retryable=False,
            details={
                "artifact_id": artifact.artifact_id,
                "state": artifact.state.value,
                "expected_path": artifact.expected_path,
                "structural_specification": artifact.structural_specification,
            },
        )
    return artifact
