"""Chapter 19.1's "Environment" fixtures: workspace escape, symlink escape.

`Workspace.read(path)`/`write(path)` (Chapter 7.5) resolve their target
against the workspace root and reject anything that would land outside it —
including via a symlink, since `Path.resolve()` follows symlink targets
before the containment check runs. This is the one filesystem-policy
guarantee a plain OS process genuinely can enforce (Chapter 7.2's other T2
guarantees — egress proxy, seccomp, non-privileged user — need
container/microVM isolation this backend does not have)."""

from __future__ import annotations

from pathlib import Path

from engine.core.errors import DdeError


def resolve_within_workspace(root: Path, relative_path: str) -> Path:
    if Path(relative_path).is_absolute():
        raise DdeError(
            "POLICY_DENIED",
            "Workspace paths must be relative",
            details={"path": relative_path},
        )
    resolved_root = root.resolve()
    candidate = (resolved_root / relative_path).resolve()
    if not candidate.is_relative_to(resolved_root):
        raise DdeError(
            "POLICY_DENIED",
            "Path escapes the workspace root",
            details={"path": relative_path},
        )
    return candidate
