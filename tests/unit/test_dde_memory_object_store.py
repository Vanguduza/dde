from __future__ import annotations

import hashlib
from uuid import UUID

import httpx
import pytest

from engine.core.errors import DdeError
from engine.object_store.durable import (
    R2Config,
    R2ScopedObjectStore,
    scoped_content_key,
    scoped_object_store_from_env,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")
PROJECT = UUID("00000000-0000-0000-0000-000000000002")


def test_scoped_content_key_is_deterministic_and_project_jailed() -> None:
    digest = hashlib.sha256(b"memory").hexdigest()
    assert (
        scoped_content_key(
            namespace="memory",
            tenant_id=TENANT,
            project_id=PROJECT,
            content_hash=digest,
        )
        == f"memory/{TENANT}/{PROJECT}/{digest}"
    )
    with pytest.raises(DdeError) as exc:
        scoped_content_key(
            namespace="../memory",
            tenant_id=TENANT,
            project_id=PROJECT,
            content_hash=digest,
        )
    assert exc.value.error_code == "VALIDATION_FAILED"


def test_r2_backend_uses_sigv4_without_exposing_secret() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, content=b"shared-memory")
        return httpx.Response(200)

    config = R2Config(
        account_id="account",
        bucket="dde",
        access_key="access-id",
        secret_key="never-return-this-secret",  # noqa: S106 - sentinel test value
        endpoint="https://account.r2.cloudflarestorage.com",
    )
    store = R2ScopedObjectStore(
        namespace="memory", config=config, transport=httpx.MockTransport(handler)
    )
    payload = b"shared-memory"
    digest = hashlib.sha256(payload).hexdigest()
    key = store.put(
        tenant_id=TENANT, project_id=PROJECT, content_hash=digest, content=payload
    )
    assert store.read(tenant_id=TENANT, project_id=PROJECT, key=key) == payload
    assert len(requests) == 2
    auth = requests[0].headers["Authorization"]
    assert "Credential=access-id/" in auth
    assert "never-return-this-secret" not in auth
    assert requests[0].headers["x-amz-content-sha256"] == digest


def test_strict_r2_mode_fails_closed_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DDE_OBJECT_BACKEND", "r2")
    for name in (
        "DDE_R2_ACCOUNT_ID",
        "DDE_R2_BUCKET",
        "DDE_R2_ACCESS_KEY",
        "DDE_R2_SECRET_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(DdeError) as exc:
        scoped_object_store_from_env(namespace="memory")
    assert exc.value.error_code == "STORAGE_UNAVAILABLE"


def test_auto_mode_uses_local_content_addressed_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("DDE_OBJECT_BACKEND", "auto")
    for name in (
        "DDE_R2_ACCOUNT_ID",
        "DDE_R2_BUCKET",
        "DDE_R2_ACCESS_KEY",
        "DDE_R2_SECRET_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    store = scoped_object_store_from_env(namespace="memory", local_root=tmp_path)
    payload = b"local-shared-memory"
    digest = hashlib.sha256(payload).hexdigest()
    key = store.put(
        tenant_id=TENANT, project_id=PROJECT, content_hash=digest, content=payload
    )
    assert store.backend_name == "LOCAL"
    assert store.read(tenant_id=TENANT, project_id=PROJECT, key=key) == payload
