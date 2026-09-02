"""Broker-internal authenticated JSON HTTP execution.

This is the network counterpart to static-secret capture.  Callers provide a
provider id, HTTPS URL and secret-free request body.  The raw provider secret
is resolved and attached to the Authorization header entirely inside
`engine.capabilities.broker`; it is never returned to an adapter, Gateway,
Studio, event payload, log, or idempotency record.

The caller must construct this service with an explicit hostname allowlist.
Redirects are disabled so an allowed origin cannot bounce a credential to a
different host.  This seam intentionally uses the Python standard library;
provider-specific request/response syntax belongs in `adapters/**`.
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.capabilities.broker.capture import StaticSecretCaptureService
from engine.core.errors import DdeError

DEFAULT_HTTP_TIMEOUT_SECONDS = 45.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class BrokeredJsonResponse:
    status_code: int
    body: dict[str, object]
    duration_ms: int


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        del req, fp, code, msg, headers, newurl
        return None


class BrokeredJsonHttpService:
    """Authenticated HTTPS POST with broker-confined secret material."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        allowed_hosts: frozenset[str],
        captures: StaticSecretCaptureService | None = None,
        timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
    ) -> None:
        if not allowed_hosts:
            raise ValueError("allowed_hosts must not be empty")
        self._captures = captures or StaticSecretCaptureService(engine)
        self._allowed_hosts = frozenset(host.lower() for host in allowed_hosts)
        self._timeout_seconds = timeout_seconds

    async def post_json(
        self,
        *,
        tenant_id,
        project_id,
        provider_id: str,
        url: str,
        body: dict[str, object],
        headers: dict[str, str] | None = None,
    ) -> BrokeredJsonResponse:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or host not in self._allowed_hosts:
            raise DdeError(
                "POLICY_DENIED",
                "brokered HTTP destination is outside the HTTPS host allowlist",
                retryable=False,
                details={"scheme": parsed.scheme, "host": host},
            )
        if parsed.username or parsed.password:
            raise DdeError(
                "POLICY_DENIED",
                "brokered HTTP URL must not contain userinfo",
                retryable=False,
            )
        secret = await self._captures.resolve_secret(
            tenant_id=tenant_id,
            project_id=project_id,
            provider_id=provider_id,
        )
        if secret is None:
            raise DdeError(
                "POLICY_DENIED",
                "no active provider credential is captured for brokered HTTP",
                retryable=False,
                details={"provider_id": provider_id},
            )
        safe_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if headers:
            for key, value in headers.items():
                if key.lower() == "authorization":
                    raise DdeError(
                        "POLICY_DENIED",
                        "callers may not provide an Authorization header",
                        retryable=False,
                    )
                safe_headers[key] = value

        # Secret material enters the request only here and is never included
        # in any returned object or DDE error detail.
        safe_headers["Authorization"] = f"Bearer {secret}"
        encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
        return await asyncio.to_thread(
            self._post_sync,
            url,
            encoded,
            safe_headers,
        )

    def _post_sync(
        self,
        url: str,
        encoded: bytes,
        headers: dict[str, str],
    ) -> BrokeredJsonResponse:
        started = time.monotonic()
        request = urllib.request.Request(
            url=url,
            data=encoded,
            headers=headers,
            method="POST",
        )
        opener = urllib.request.build_opener(_NoRedirect())
        try:
            with opener.open(request, timeout=self._timeout_seconds) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                status = int(response.status)
        except urllib.error.HTTPError as exc:
            raw = exc.read(MAX_RESPONSE_BYTES + 1)
            status = int(exc.code)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise DdeError(
                "PROVIDER_UNAVAILABLE",
                "brokered provider request failed",
                retryable=True,
                details={"error_type": type(exc).__name__},
            ) from exc

        elapsed = int((time.monotonic() - started) * 1000)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise DdeError(
                "POLICY_DENIED",
                "brokered provider response exceeded the size ceiling",
                retryable=False,
                details={"max_response_bytes": MAX_RESPONSE_BYTES},
            )
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DdeError(
                "PROVIDER_UNAVAILABLE",
                "brokered provider returned invalid JSON",
                retryable=True,
                details={"status_code": status},
            ) from exc
        if not isinstance(parsed, dict):
            raise DdeError(
                "PROVIDER_UNAVAILABLE",
                "brokered provider response must be a JSON object",
                retryable=True,
                details={"status_code": status},
            )
        return BrokeredJsonResponse(
            status_code=status,
            body=parsed,
            duration_ms=elapsed,
        )
