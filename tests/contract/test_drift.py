"""Generated contracts must match schemas/."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from engine.contracts.healthz import Healthz
from scripts.generate_contracts import check, render

ROOT = Path(__file__).resolve().parents[2]


def test_generated_code_does_not_drift() -> None:
    assert check(render()) == 0


def test_schemas_are_json_schema_2020_12() -> None:
    files = list((ROOT / "schemas" / "objects").glob("*.json"))
    files.extend((ROOT / "schemas" / "events").glob("*.json"))
    files.extend((ROOT / "schemas" / "api").glob("*.json"))
    assert files
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_healthz_contract_rejects_unknown_fields() -> None:
    Healthz.model_validate({"status": "ok"})
    try:
        Healthz.model_validate({"status": "ok", "extra": True})
    except ValidationError:
        return
    raise AssertionError("unknown fields must be rejected")
