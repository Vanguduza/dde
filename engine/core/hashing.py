"""Canonical hashes used by immutable definitions and the audit chain."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def sha256_hex(payload: str | bytes) -> str:
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
