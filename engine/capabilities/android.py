"""Chapter 9 Android/APK analysis capability contract (DDE-048).

Static APK analysis is an in-process evaluator (stdlib `zipfile`, same
discipline as DDE-045's no-vendor-binary rule). Dynamic modes — ADB,
instrumentation, on-device execution — fail closed: this protocol grants no
device authority (Chapter 7.2 containment; donor isolation is EDR-0017).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AndroidScanSpec:
    """One workspace Android artifact scan.

    `mode` is `static` (executable) or `dynamic`/`adb`/`instrumentation`
    (fail closed). `root` is the workspace filesystem path already bound
    by DDE; the first `*.apk` found at the root is the scan target.
    """

    root: str
    mode: str = "static"


@dataclass(frozen=True)
class AndroidScanResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    passed: bool


class AndroidCapability(Protocol):
    """T1-brokered APK analysis. Callers must hold an active
    `capability.android_analysis` lease before invoking `scan`."""

    async def scan(self, spec: AndroidScanSpec) -> AndroidScanResult: ...
