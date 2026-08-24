"""Prompt-injection screen for donor content (Chapter 14.5 invariant 6).

Findings are hypotheses only (authority rank 10). They never elevate
leases or promote source_class. Full screening depth remains iterative;
this stub catches common instruction-override phrases so ingest is never
"screened = empty by omission."
"""

from __future__ import annotations

_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous",
    "disregard previous",
    "you are now",
    "system prompt",
    "jailbreak",
    "do not follow your system",
)


def screen_donor_text(text: str) -> list[str]:
    lowered = text.lower()
    findings: list[str] = []
    for pattern in _PATTERNS:
        if pattern in lowered:
            findings.append(f"injection_phrase:{pattern}")
    return findings
