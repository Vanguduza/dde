"""Feature DNA stub extraction (DDE-046).

Deterministic stub body hashed as dna_hash. Deeper extraction and taint
into tasks/diffs are DDE-047.
"""

from __future__ import annotations

import json
from typing import Any

from engine.core.hashing import sha256_hex


def build_feature_dna_stub(
    *,
    source_uri: str,
    content_hash: str,
    media_kind: str,
    source_class: str,
    injection_findings: list[str],
) -> tuple[str, dict[str, Any], str]:
    """Return (title, body, dna_hash)."""
    title = f"Donor stub: {source_uri}"
    if len(title) > 200:
        title = title[:197] + "..."
    body: dict[str, Any] = {
        "kind": "feature_dna_stub",
        "source_uri": source_uri,
        "content_hash": content_hash,
        "media_kind": media_kind,
        "source_class": source_class,
        "injection_findings": list(injection_findings),
        "extraction": "stub",
        "deferred": "DDE-047",
    }
    dna_hash = sha256_hex(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return title, body, dna_hash
