"""Chapter 9 narrow multimodal visual-critique capability contract
(DDE-068, EDR-0017 Option C) -- no vendor SDK.

This is the typed seam `engine.verification` calls so `engine.core` and
`engine.verification` never import a model runtime (AGENTS.md). The
concrete runtime lives in `adapters/visual_critic/**`, exactly as the
browser runtime lives in `adapters/playwright/**` behind
`engine.capabilities.browser`.

**Why this is a separate capability from `capability.claude_code_invoke`.**
EDR-0017 Option C: the broad Claude Code capability grants arbitrary
development execution against a human's own rate-limited seat, and keeps
its mandatory, non-standing, per-invocation human `Approval`
(`external_model_invocation`, `STANDING_FORBIDDEN_TYPES`) for exactly that
reason. That gate must not be weakened to let an unattended verification
loop run. This capability is the narrow alternative: its entire permitted
action set is "bounded visual evidence + a versioned rubric in, one
schema-validated structured verdict out." It cannot run commands, mutate a
workspace, edit source, touch git, carry an arbitrary prompt, or spawn a
nested agent -- so it is safe for bounded machine use under the ordinary
Chapter 9 lease path rather than a per-invocation human decision.

The two capabilities may share the narrowest underlying transport (a real
subprocess spawn), but they are never aliases: distinct `capability_id`,
distinct authorization, distinct request/response schemas, distinct
adapters.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class VisualCritiqueRequest:
    """The complete, least-privilege input a critic is allowed to receive.

    Deliberately *not* a prompt: the caller supplies evidence and a rubric
    reference, never free-form instructions. The adapter composes the fixed
    system contract around this; no field here can introduce a new
    instruction to the model (see `adapters.visual_critic.adapter` for the
    injection-hardening rules that keep rendered candidate content as data).
    """

    screenshot_png: bytes
    rubric_version: str
    candidate_ref: str
    viewport_width: int
    viewport_height: int
    #: Results the deterministic layer already produced (silhouette verdict,
    #: visual_diff ratio, deterministic density evidence). Context for the
    #: perceptual judgment -- never a substitute for it.
    deterministic_evidence: Mapping[str, object] = field(default_factory=dict)
    #: Set only on a bounded re-evaluation cycle, so the critic can judge
    #: whether the previous cycle's blocking defects were actually repaired.
    prior_critique: Mapping[str, object] | None = None


@dataclass(frozen=True)
class VisualCritiqueResult:
    """Raw transport-level outcome. `verdict_json` is *unvalidated* here on
    purpose -- `engine.verification.visual_critique.parse_verdict` is the
    single place that validates it, so a malformed response fails closed in
    one auditable place rather than being trusted at the boundary."""

    exit_code: int
    verdict_json: str
    stderr: str
    duration_ms: int
    timed_out: bool
    #: Real, measured resource consumption reported by the runtime. `None`
    #: means the runtime did not report it -- never fabricate a number
    #: (EDR-0017: "If it is not known, do not invent it").
    cost_usd: float | None = None
    model: str | None = None


class VisualCriticCapability(Protocol):
    """T1-brokered narrow visual critique. Callers must hold an active
    `capability.visual_critique` lease before invoking -- this protocol
    does not grant authority."""

    async def critique(
        self, request: VisualCritiqueRequest
    ) -> VisualCritiqueResult: ...
