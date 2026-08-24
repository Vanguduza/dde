"""DDE-045 security capability (in-process SAST)."""

from adapters.security.adapter import SecurityWorkerAdapter
from adapters.security.sast import InProcessSecurityScanner

__all__ = ["SecurityWorkerAdapter", "InProcessSecurityScanner"]
