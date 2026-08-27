"""Typed refusals for the DDE-065 generation-prompt compiler.

Unresolved compiler inputs are Chapter 15.5 CONTEXT family
(`CONTEXT_INCOMPLETE`): nothing is compiled, and the refusal names the
missing artifact. This path never creates a WorkerRun, so the recovery
matrix's context-recompile row is not a caller.
"""

from __future__ import annotations

from engine.core.errors import DdeError


class CompileRefusedError(DdeError):
    """Fail-closed compile: a required visual or PRD input did not resolve."""

    def __init__(
        self,
        message: str,
        *,
        missing_artifact: str,
        details: dict[str, object] | None = None,
    ) -> None:
        merged: dict[str, object] = {"missing_artifact": missing_artifact}
        if details:
            merged.update(details)
        super().__init__(
            "CONTEXT_INCOMPLETE",
            message,
            retryable=False,
            details=merged,
        )
