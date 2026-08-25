"""In-process static APK analysis for capability.android_analysis (DDE-048).

Chapter 9.6 discipline: no vendor Android tooling (JADX/Apktool/MobSF/ADB)
is invoked. The APK is a ZIP; the analyzer reads the binary manifest's
string pool for permission declarations, inspects entry names and asset
content with the same secret classes as Chapter 9.7, and reports structure
(native ABIs, DEX presence, signing block). Dynamic analysis — ADB,
instrumentation, on-device execution — refuses rather than invent a device
attack surface (EDR-0017 owns donor/isolation profiles).
"""

from __future__ import annotations

import io
import json
import re
import time
import zipfile
from pathlib import Path

from engine.capabilities.android import AndroidScanResult, AndroidScanSpec
from engine.core.errors import DdeError
from engine.integration.gates import _AWS_KEY, _GITHUB_PAT, _PRIVATE_KEY

_EXECUTABLE_MODES = frozenset({"static"})

#: Runtime-granted permissions that map to user data or money. Declared but
#: not in this set is informational; any hit here is blocking.
_DANGEROUS_PERMISSIONS = frozenset(
    {
        "android.permission.READ_CONTACTS",
        "android.permission.WRITE_CONTACTS",
        "android.permission.CAMERA",
        "android.permission.RECORD_AUDIO",
        "android.permission.ACCESS_FINE_LOCATION",
        "android.permission.ACCESS_COARSE_LOCATION",
        "android.permission.READ_SMS",
        "android.permission.SEND_SMS",
        "android.permission.RECEIVE_SMS",
        "android.permission.READ_CALL_LOG",
        "android.permission.WRITE_CALL_LOG",
        "android.permission.CALL_PHONE",
        "android.permission.READ_PHONE_STATE",
        "android.permission.RECORD_VIDEO",
        "android.permission.BODY_SENSORS",
    }
)

_SECRET_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aws_access_key", _AWS_KEY),
    ("github_pat", _GITHUB_PAT),
    ("private_key_pem", _PRIVATE_KEY),
)

_MAX_ENTRY_BYTES = 1_000_000


class InProcessAndroidAnalyzer:
    async def scan(self, spec: AndroidScanSpec) -> AndroidScanResult:
        return _scan_sync(spec)


def _scan_sync(spec: AndroidScanSpec) -> AndroidScanResult:
    started = time.monotonic()
    if spec.mode not in _EXECUTABLE_MODES:
        raise DdeError(
            "POLICY_DENIED",
            f"capability.android_analysis mode={spec.mode!r} is not "
            "executable (dynamic/ADB/instrumentation are deferred to "
            "EDR-0017; no device attack surface)",
            details={"mode": spec.mode},
        )
    root = Path(spec.root)
    if not root.is_dir():
        raise DdeError(
            "POLICY_DENIED",
            "android scan root is not a workspace directory",
            details={"root": spec.root},
        )
    apk_path = _find_apk(root)
    if apk_path is None:
        raise DdeError(
            "VALIDATION_FAILED",
            "android scan requires an .apk file in the workspace",
            details={"root": spec.root},
        )

    apk = _ApkFacts.from_bytes(apk_path.read_bytes())
    blocking: list[str] = []
    dangerous = sorted(
        name for name in apk.permissions if name in _DANGEROUS_PERMISSIONS
    )
    blocking.extend(f"dangerous_permission:{name.split('.')[-1]}" for name in dangerous)
    if apk.secret_hits:
        blocking.append("secret_material_in_asset")

    passed = not blocking
    payload = {
        "mode": spec.mode,
        "apk": {
            "path": str(apk_path.relative_to(root)).replace("\\", "/"),
            "permissions": sorted(apk.permissions),
            "dangerous_permissions": dangerous,
            "native_abi": sorted(apk.native_abis),
            "has_dex": apk.has_dex,
            "signed_v1": apk.signed_v1,
            "entry_count": apk.entry_count,
        },
        "secret_detection": {
            "passed": not apk.secret_hits,
            "hits": apk.secret_hits[:50],
        },
        "blocking": blocking,
        "passed": passed,
    }
    elapsed = int((time.monotonic() - started) * 1000)
    return AndroidScanResult(
        exit_code=0 if passed else 1,
        stdout=json.dumps(payload, sort_keys=True),
        stderr="" if passed else "android scan reported blocking findings",
        duration_ms=elapsed,
        timed_out=False,
        passed=passed,
    )


def _find_apk(root: Path) -> Path | None:
    candidates = sorted(path for path in root.rglob("*.apk") if path.is_file())
    return candidates[0] if candidates else None


class _ApkFacts:
    def __init__(self) -> None:
        self.permissions: set[str] = set()
        self.native_abis: set[str] = set()
        self.has_dex = False
        self.signed_v1 = False
        self.entry_count = 0
        self.secret_hits: list[str] = []

    @classmethod
    def from_bytes(cls, raw: bytes) -> _ApkFacts:
        try:
            archive = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile as exc:
            raise DdeError(
                "VALIDATION_FAILED",
                "the selected .apk is not a readable ZIP archive",
                details={},
            ) from exc
        facts = cls()
        with archive:
            facts.entry_count = len(archive.namelist())
            for info in archive.infolist():
                name = info.filename.replace("\\", "/")
                if name.endswith("AndroidManifest.xml"):
                    facts._absorb_strings(archive.read(info))
                if name.startswith("lib/") and "/lib" in name:
                    parts = name.split("/")
                    if len(parts) >= 3:
                        facts.native_abis.add(parts[1])
                if name.startswith(("classes",)) and name.endswith(".dex"):
                    facts.has_dex = True
                if name.startswith("META-INF/") and name.endswith(
                    (".SF", ".RSA", ".DSA")
                ):
                    facts.signed_v1 = True
                if name.startswith("assets/") and info.file_size <= _MAX_ENTRY_BYTES:
                    facts._scan_entry(name, archive.read(info))
        return facts

    def _absorb_strings(self, blob: bytes) -> None:
        """AXML stores its strings UTF-16-LE in one pool; permission names
        survive as readable substrings without parsing the XML tree."""
        text = blob.decode("utf-16-le", errors="replace")
        for match in re.finditer(r"android\.permission\.[A-Z_]+", text):
            self.permissions.add(match.group(0))

    def _scan_entry(self, name: str, blob: bytes) -> None:
        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError:
            text = blob.decode("latin-1")
        for label, pattern in _SECRET_RULES:
            if pattern.search(text):
                self.secret_hits.append(f"{name}:{label}")
