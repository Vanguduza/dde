"""Resolve and hash the pinned design-token sheet."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from engine.core.hashing import sha256_hex
from engine.studio.errors import CompileRefusedError

TOKENS_SCHEMA = (
    Path(__file__).resolve().parents[2] / "schemas" / "design" / "tokens.json"
)


@dataclass(frozen=True)
class TokenSheet:
    version: int
    content_hash: str
    semantic_role_names: frozenset[str]
    palette_literals: frozenset[str]
    motion_identity_ids: frozenset[str]
    raw: dict[str, Any]


def tokens_file_hash() -> str:
    return sha256_hex(TOKENS_SCHEMA.read_bytes())


@lru_cache(maxsize=1)
def load_token_sheet() -> TokenSheet:
    payload = json.loads(TOKENS_SCHEMA.read_text(encoding="utf-8"))
    properties = payload["properties"]
    version = int(properties["version"]["const"])
    semantic = properties["color"]["properties"]["semantic"]["properties"]
    palette = properties["color"]["properties"]["palette"]["properties"]
    identity = (
        properties["motion"]["properties"].get("identity", {}).get("properties", {})
    )
    literals = {str(item["const"]) for item in palette.values()}
    return TokenSheet(
        version=version,
        content_hash=tokens_file_hash(),
        semantic_role_names=frozenset(semantic),
        palette_literals=frozenset(literals),
        motion_identity_ids=frozenset(identity),
        raw=payload,
    )


def resolve_tokens_pin(*, version: int, content_hash: str) -> TokenSheet:
    sheet = load_token_sheet()
    if version != sheet.version or content_hash != sheet.content_hash:
        raise CompileRefusedError(
            "tokens pin does not resolve against schemas/design/tokens.json",
            missing_artifact="tokens",
            details={
                "pinned_version": version,
                "pinned_hash": content_hash,
                "resolved_version": sheet.version,
                "resolved_hash": sheet.content_hash,
            },
        )
    return sheet
