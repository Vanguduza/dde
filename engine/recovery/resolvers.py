"""Production reconciliation resolvers for journaled Stage 1 operations
(Chapter 12.4: idempotency key / external reference / read-after-write /
provider-specific method).

These are the real checks `ExternalEffectService.reconcile_journaled`
dispatches to -- not test-supplied lambdas. What "verified presence" and
"verified absence" mean:

`run_local_process` (`target_system=local_process`)
    Method: `workspace_artifact_stat`.
    Evidence: `external_reference` is the workspace-relative artifact the
    command was expected to write; `target_resource` is the workspace root.
    Verified presence: that path exists inside the workspace jail.
    Verified absence: that path does not exist.
    Undeterminable: no evidence path was journaled, or the path escapes
    the workspace (the resolver never guesses from argv/stdout).

`capability.git_operations` mutation (`target_system=git`,
`operation=update-ref`)
    Method: `git_ref_stat`.
    Evidence: `target_resource` is the full ref name (`refs/heads/...`).
    Verified presence: `git show-ref --verify` succeeds for that ref.
    Verified absence: the ref does not exist.
    Undeterminable: git is not on PATH.

`WorkspaceService.snapshot` (`operation=git_snapshot`) is a read, journaled
only as optional extra audit -- it is not a Chapter 12.4 mutation proof and
has no production mutation resolver.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from engine.core.errors import DdeError
from engine.recovery.outcomes import ReconciliationOutcome
from engine.workspaces.paths import resolve_within_workspace


def resolve_local_process_artifact(
    *, workspace_root: Path, expected_artifact: str | None
) -> ReconciliationOutcome:
    if expected_artifact is None or expected_artifact.strip() == "":
        return ReconciliationOutcome(
            verified=False,
            present=False,
            detail=(
                "no expected workspace artifact was journaled for this "
                "run_local_process effect -- cannot determine presence "
                "or absence from the command string alone"
            ),
        )
    try:
        target = resolve_within_workspace(workspace_root, expected_artifact)
    except DdeError as exc:
        return ReconciliationOutcome(
            verified=False,
            present=False,
            detail=f"expected artifact is not a workspace-local path: {exc.message}",
        )
    present = target.exists()
    return ReconciliationOutcome(
        verified=True,
        present=present,
        detail=(
            f"workspace artifact {expected_artifact!r} "
            f"{'present' if present else 'absent'} at {target}"
        ),
    )


def resolve_git_ref(*, repo_root: Path, ref_name: str) -> ReconciliationOutcome:
    git = shutil.which("git")
    if git is None:
        return ReconciliationOutcome(
            verified=False,
            present=False,
            detail="git executable not found on PATH -- cannot stat ref",
        )
    completed = subprocess.run(  # noqa: S603
        [git, "show-ref", "--verify", "--quiet", ref_name],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30.0,
    )
    present = completed.returncode == 0
    return ReconciliationOutcome(
        verified=True,
        present=present,
        detail=(
            f"git ref {ref_name!r} {'present' if present else 'absent'} in {repo_root}"
        ),
    )
