"""In-process SAST for capability.security (DDE-045).

Chapter 9.6: no new vendor SAST binary. Reuses the control-plane rules in
`engine.integration.gates.scan_workspace` (same secret/static classes as
Chapter 9.7). DAST and agentic modes refuse rather than invent a live
attack plane.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from engine.capabilities.security import SecurityScanResult, SecurityScanSpec
from engine.core.errors import DdeError
from engine.integration.gates import scan_workspace

_EXECUTABLE_MODES = frozenset({"sast"})


class InProcessSecurityScanner:
    async def scan(self, spec: SecurityScanSpec) -> SecurityScanResult:
        return _scan_sync(spec)


def _scan_sync(spec: SecurityScanSpec) -> SecurityScanResult:
    started = time.monotonic()
    if spec.mode not in _EXECUTABLE_MODES:
        raise DdeError(
            "POLICY_DENIED",
            f"capability.security mode={spec.mode!r} is not executable "
            "(DAST/agentic security worker are deferred; no live attack "
            "plane)",
            details={"mode": spec.mode},
        )
    if not os.path.isdir(spec.root):
        raise DdeError(
            "POLICY_DENIED",
            "security scan root is not a workspace directory",
            details={"root": spec.root},
        )
    secret, static = scan_workspace(Path(spec.root))
    passed = secret.passed and static.passed
    payload = {
        "mode": spec.mode,
        "secret_detection": {
            "passed": secret.passed,
            "summary": secret.summary,
            "details": secret.details,
        },
        "static_analysis": {
            "passed": static.passed,
            "summary": static.summary,
            "details": static.details,
        },
    }
    elapsed = int((time.monotonic() - started) * 1000)
    return SecurityScanResult(
        exit_code=0 if passed else 1,
        stdout=json.dumps(payload, sort_keys=True),
        stderr="" if passed else "security scan reported blocking findings",
        duration_ms=elapsed,
        timed_out=False,
        passed=passed,
    )
