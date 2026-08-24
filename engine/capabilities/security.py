"""Chapter 9 security-scanning capability contract — no vendor SAST/DAST SDK.

In-process evaluators live in `engine.integration.gates.scan_workspace`.
Live DAST and an agentic security worker fail closed (DDE-045 deferral):
this protocol does not grant network attack authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SecurityScanSpec:
    """One workspace security scan.

    `mode` is `sast` (executable), `dast`, or `agentic` (fail closed).
    `root` is the workspace filesystem path already bound by DDE.
    """

    root: str
    mode: str = "sast"


@dataclass(frozen=True)
class SecurityScanResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    passed: bool


class SecurityCapability(Protocol):
    """T1-brokered security scan. Callers must hold an active
    `capability.security` lease before invoking `scan`."""

    async def scan(self, spec: SecurityScanSpec) -> SecurityScanResult: ...
