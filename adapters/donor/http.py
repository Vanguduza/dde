"""Allowlisted donor-search GET (EDR-0015).

Credentials are caller-supplied from a broker mint — this adapter never
reads process environment secrets. Redirects are refused so a 3xx cannot
walk off the host allowlist.
"""

from __future__ import annotations

import httpx

from engine.donor.allowlist import assert_uri_admitted

_TIMEOUT = httpx.Timeout(20.0)


def fetch_uri(uri: str, authorization: str | None = None) -> str:
    assert_uri_admitted(uri)
    headers = {"Accept": "application/vnd.github+json, application/json"}
    if authorization:
        headers["Authorization"] = f"Bearer {authorization}"
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=False) as client:
            response = client.get(uri, headers=headers)
            response.raise_for_status()
            return response.text
    except httpx.TimeoutException as exc:
        raise TimeoutError(str(exc)) from exc
