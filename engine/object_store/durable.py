"""Scoped durable object storage with local and Cloudflare R2 backends.

The backend never owns authorization: every key is derived from tenant/project
scope and content hash before byte IO. R2 uses its S3-compatible SigV4 API;
credentials are read from process environment only and are never persisted in
DDE records or exposed to provider harnesses.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import quote, urlparse
from uuid import UUID

import httpx

from engine.core.errors import DdeError

OBJECT_BACKEND_ENV = "DDE_OBJECT_BACKEND"
R2_ACCOUNT_ENV = "DDE_R2_ACCOUNT_ID"
R2_BUCKET_ENV = "DDE_R2_BUCKET"
R2_ACCESS_ENV = "DDE_R2_ACCESS_KEY"
R2_SECRET_ENV = "DDE_R2_SECRET_KEY"  # noqa: S105 - env var name, not a secret
R2_ENDPOINT_ENV = "DDE_R2_ENDPOINT"
R2_REGION_ENV = "DDE_R2_REGION"
DEFAULT_OBJECT_ROOT = Path.home() / ".dde" / "objects"


def scoped_content_key(
    *, namespace: str, tenant_id: UUID, project_id: UUID, content_hash: str
) -> str:
    clean = namespace.strip("/")
    if not clean or "/" in clean or ".." in clean:
        raise DdeError("VALIDATION_FAILED", "invalid object-store namespace")
    if len(content_hash) != 64 or any(
        c not in "0123456789abcdef" for c in content_hash
    ):
        raise DdeError("VALIDATION_FAILED", "content hash must be lowercase SHA-256")
    return f"{clean}/{tenant_id}/{project_id}/{content_hash}"


def verify_scoped_key(
    *, namespace: str, tenant_id: UUID, project_id: UUID, key: str
) -> None:
    expected = f"{namespace.strip('/')}/{tenant_id}/{project_id}/"
    if not key.startswith(expected):
        raise DdeError(
            "TENANT_SCOPE_VIOLATION",
            "object key is outside the authorized project scope",
            retryable=False,
            details={"key": key, "expected_prefix": expected},
        )


class ScopedObjectStore(Protocol):
    @property
    def backend_name(self) -> str: ...

    def put(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        content_hash: str,
        content: bytes,
    ) -> str: ...

    def read(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        key: str,
        max_bytes: int | None = None,
    ) -> bytes: ...


@dataclass
class LocalScopedObjectStore:
    namespace: str
    root: Path = DEFAULT_OBJECT_ROOT
    backend_name: str = "LOCAL"

    def _path(self, *, tenant_id: UUID, project_id: UUID, key: str) -> Path:
        verify_scoped_key(
            namespace=self.namespace,
            tenant_id=tenant_id,
            project_id=project_id,
            key=key,
        )
        root = self.root.expanduser().resolve()
        target = (root / Path(*key.split("/"))).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise DdeError(
                "TENANT_SCOPE_VIOLATION",
                "object path escaped managed storage",
                retryable=False,
            ) from exc
        return target

    def put(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        content_hash: str,
        content: bytes,
    ) -> str:
        actual = hashlib.sha256(content).hexdigest()
        if actual != content_hash:
            raise DdeError("VERSION_CONFLICT", "object bytes do not match content hash")
        key = scoped_content_key(
            namespace=self.namespace,
            tenant_id=tenant_id,
            project_id=project_id,
            content_hash=content_hash,
        )
        target = self._path(tenant_id=tenant_id, project_id=project_id, key=key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() != content:
                raise DdeError("VERSION_CONFLICT", "content-addressed object collision")
            return key
        fd, temporary = tempfile.mkstemp(prefix="dde-object-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return key

    def read(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        key: str,
        max_bytes: int | None = None,
    ) -> bytes:
        target = self._path(tenant_id=tenant_id, project_id=project_id, key=key)
        if not target.is_file():
            raise DdeError("CONTEXT_INCOMPLETE", "durable object is missing")
        size = target.stat().st_size
        if max_bytes is not None and size > max_bytes:
            raise DdeError(
                "RESOURCE_EXHAUSTION",
                "durable object exceeds requested read bound",
                details={"size_bytes": size, "max_bytes": max_bytes},
            )
        return target.read_bytes()


@dataclass(frozen=True)
class R2Config:
    account_id: str
    bucket: str
    access_key: str
    secret_key: str
    endpoint: str
    region: str = "auto"

    @classmethod
    def from_env(cls) -> R2Config | None:
        account = os.environ.get(R2_ACCOUNT_ENV, "").strip()
        bucket = os.environ.get(R2_BUCKET_ENV, "").strip()
        access = os.environ.get(R2_ACCESS_ENV, "").strip()
        secret = os.environ.get(R2_SECRET_ENV, "").strip()
        if not all((account, bucket, access, secret)):
            return None
        endpoint = os.environ.get(
            R2_ENDPOINT_ENV, f"https://{account}.r2.cloudflarestorage.com"
        ).rstrip("/")
        return cls(
            account_id=account,
            bucket=bucket,
            access_key=access,
            secret_key=secret,
            endpoint=endpoint,
            region=os.environ.get(R2_REGION_ENV, "auto").strip() or "auto",
        )


@dataclass
class R2ScopedObjectStore:
    namespace: str
    config: R2Config
    timeout_seconds: float = 30.0
    transport: httpx.BaseTransport | None = None
    backend_name: str = "R2"

    def _url(self, key: str) -> str:
        encoded = quote(f"/{self.config.bucket}/{key}", safe="/-_.~")
        return f"{self.config.endpoint}{encoded}"

    @staticmethod
    def _signing_key(secret: str, date: str, region: str) -> bytes:
        k_date = hmac.new(
            ("AWS4" + secret).encode(), date.encode(), hashlib.sha256
        ).digest()
        k_region = hmac.new(k_date, region.encode(), hashlib.sha256).digest()
        k_service = hmac.new(k_region, b"s3", hashlib.sha256).digest()
        return hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()

    def _headers(self, *, method: str, url: str, payload_hash: str) -> dict[str, str]:
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date = now.strftime("%Y%m%d")
        parsed = urlparse(url)
        host = parsed.netloc
        canonical_headers = (
            f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
        )
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = "\n".join(
            [
                method,
                parsed.path or "/",
                parsed.query,
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )
        scope = f"{date}/{self.config.region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                scope,
                hashlib.sha256(canonical_request.encode()).hexdigest(),
            ]
        )
        signature = hmac.new(
            self._signing_key(self.config.secret_key, date, self.config.region),
            string_to_sign.encode(),
            hashlib.sha256,
        ).hexdigest()
        return {
            "Host": host,
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
            "Authorization": (
                "AWS4-HMAC-SHA256 "
                f"Credential={self.config.access_key}/{scope}, "
                f"SignedHeaders={signed_headers}, Signature={signature}"
            ),
        }

    def _request(
        self, method: str, *, key: str, content: bytes = b""
    ) -> httpx.Response:
        url = self._url(key)
        payload_hash = hashlib.sha256(content).hexdigest()
        headers = self._headers(method=method, url=url, payload_hash=payload_hash)
        try:
            with httpx.Client(
                timeout=self.timeout_seconds, transport=self.transport
            ) as client:
                response = client.request(method, url, headers=headers, content=content)
        except httpx.HTTPError as exc:
            raise DdeError(
                "STORAGE_UNAVAILABLE",
                "R2 object storage request failed",
                retryable=True,
                details={"backend": "R2", "error_type": type(exc).__name__},
            ) from exc
        if response.status_code >= 400:
            raise DdeError(
                "STORAGE_UNAVAILABLE",
                "R2 object storage rejected the request",
                retryable=response.status_code >= 500,
                details={"backend": "R2", "status_code": response.status_code},
            )
        return response

    def put(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        content_hash: str,
        content: bytes,
    ) -> str:
        actual = hashlib.sha256(content).hexdigest()
        if actual != content_hash:
            raise DdeError("VERSION_CONFLICT", "object bytes do not match content hash")
        key = scoped_content_key(
            namespace=self.namespace,
            tenant_id=tenant_id,
            project_id=project_id,
            content_hash=content_hash,
        )
        verify_scoped_key(
            namespace=self.namespace,
            tenant_id=tenant_id,
            project_id=project_id,
            key=key,
        )
        self._request("PUT", key=key, content=content)
        return key

    def read(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        key: str,
        max_bytes: int | None = None,
    ) -> bytes:
        verify_scoped_key(
            namespace=self.namespace,
            tenant_id=tenant_id,
            project_id=project_id,
            key=key,
        )
        content = self._request("GET", key=key).content
        if max_bytes is not None and len(content) > max_bytes:
            raise DdeError(
                "RESOURCE_EXHAUSTION",
                "R2 object exceeds requested read bound",
                details={"size_bytes": len(content), "max_bytes": max_bytes},
            )
        return content


def scoped_object_store_from_env(
    *, namespace: str, local_root: Path | None = None
) -> ScopedObjectStore:
    mode = os.environ.get(OBJECT_BACKEND_ENV, "auto").strip().lower() or "auto"
    r2 = R2Config.from_env()
    if mode not in {"auto", "local", "r2"}:
        raise DdeError("VALIDATION_FAILED", f"unknown object backend '{mode}'")
    if mode == "r2":
        if r2 is None:
            raise DdeError(
                "STORAGE_UNAVAILABLE",
                "R2 storage is required but its scoped credentials are not configured",
                retryable=False,
            )
        return R2ScopedObjectStore(namespace=namespace, config=r2)
    if mode == "auto" and r2 is not None:
        return R2ScopedObjectStore(namespace=namespace, config=r2)
    return LocalScopedObjectStore(
        namespace=namespace, root=local_root or DEFAULT_OBJECT_ROOT
    )
