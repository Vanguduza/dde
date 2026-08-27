"""EDR-0015 donor-search egress allowlist (host + path, in-repo, hash-pinned)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from engine.core.errors import DdeError
from engine.core.hashing import sha256_hex

ALLOWLIST_PATH = (
    Path(__file__).resolve().parents[2]
    / "schemas"
    / "design"
    / "donor_search_allowlist.json"
)


@lru_cache(maxsize=1)
def load_allowlist() -> dict[str, object]:
    payload = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("donor search allowlist must be a JSON object")
    return payload


def allowlist_hash() -> str:
    return sha256_hex(ALLOWLIST_PATH.read_bytes())


def assert_uri_admitted(uri: str) -> None:
    parsed = urlparse(uri)
    host = (parsed.hostname or "").lower()
    path = parsed.path or "/"
    catalog = load_allowlist()
    rejected_raw = catalog["rejected_hosts"]
    if not isinstance(rejected_raw, list):
        raise TypeError("rejected_hosts must be a JSON array")
    rejected = {str(item).lower() for item in rejected_raw}
    if host in rejected:
        raise DdeError(
            "POLICY_DENIED",
            "donor-search host is REJECTED marketplace",
            retryable=False,
            details={"host": host, "uri": uri},
        )
    hosts_raw = catalog["hosts"]
    if not isinstance(hosts_raw, list):
        raise TypeError("hosts must be a JSON array")
    for entry in hosts_raw:
        if not isinstance(entry, dict):
            continue
        if str(entry["host"]).lower() != host:
            continue
        prefixes = [str(item) for item in entry["path_prefixes"]]
        if any(path.startswith(prefix) for prefix in prefixes):
            return
        raise DdeError(
            "POLICY_DENIED",
            "donor-search path is outside the EDR-0015 allowlist",
            retryable=False,
            details={"host": host, "path": path},
        )
    raise DdeError(
        "POLICY_DENIED",
        "donor-search host is not on the EDR-0015 allowlist",
        retryable=False,
        details={"host": host, "uri": uri},
    )
