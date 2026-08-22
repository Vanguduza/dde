"""Pure unit tests for the CLI `--json` surface (no PostgreSQL required).

Covers the shared recursive serializer (`_jsonify`) and that every
subcommand accepts `--json`. Rendering paths themselves are exercised by
the existing per-command unit suites; end-to-end output shapes are proven
by the postgres-backed subprocess suites.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from interfaces.cli.__main__ import _jsonify, build_parser


@dataclass(frozen=True)
class _Inner:
    when: datetime
    ref: object  # pydantic model stand-in exposing model_dump


class _FakeContract:
    def __init__(self) -> None:
        self.value = 7

    def model_dump(self, *, mode: str) -> dict[str, int]:
        assert mode == "json"
        return {"value": self.value}


def test_jsonify_contracts_dataclasses_uuids_datetimes() -> None:
    payload = {
        "id": uuid4(),
        "created": datetime(2026, 1, 1, tzinfo=UTC),
        "items": (_FakeContract(), _FakeContract()),
        "nested": {"inner": _Inner(when=datetime(2026, 2, 2, tzinfo=UTC), ref=uuid4())},
    }
    result = _jsonify(payload)
    # Must be round-trippable JSON with no opaque objects left.
    text = json.dumps(result)
    reparsed = json.loads(text)
    assert len(reparsed["items"]) == 2
    assert reparsed["items"][0]["value"] == 7
    assert reparsed["nested"]["inner"]["ref"] == result["nested"]["inner"]["ref"]
    assert isinstance(result["id"], str)


def test_jsonify_passthrough_scalars() -> None:
    assert _jsonify(None) is None
    assert _jsonify(3) == 3
    assert _jsonify("x") == "x"


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        ("mission create", "--json"),
        ("mission status", "--json"),
        ("mission trace", "--json"),
        ("task list", "--json"),
    ],
)
def test_every_subcommand_accepts_json(argv: str, expected: str) -> None:
    parser = build_parser()
    # Parse just enough: missing required args would fail, so probe help-free
    # by parsing with placeholder values where needed.
    if argv == "mission create":
        args = parser.parse_args(
            [
                *argv.split(),
                expected,
                "--tenant-id",
                "00000000-0000-0000-0000-000000000000",
                "--project-id",
                "00000000-0000-0000-0000-000000000000",
                "--slug",
                "s",
                "--title",
                "t",
                "--intent",
                "i",
                "--success-definition",
                "d",
                "--autonomy-ceiling",
                "1",
            ]
        )
    elif argv == "mission status" or argv == "mission trace":
        args = parser.parse_args(
            [
                *argv.split(),
                expected,
                "00000000-0000-0000-0000-000000000000",
                "--tenant-id",
                "00000000-0000-0000-0000-000000000000",
            ]
        )
    else:
        args = parser.parse_args(
            [
                *argv.split(),
                expected,
                "00000000-0000-0000-0000-000000000000",
                "--tenant-id",
                "00000000-0000-0000-0000-000000000000",
            ]
        )
    assert args.json is True
