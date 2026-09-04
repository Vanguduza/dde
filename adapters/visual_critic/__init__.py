"""Narrow multimodal visual-critique adapter package (DDE-068, EDR-0017).

Runtime-specific naming lives only in this tree (AGENTS.md: "Vendor code
lives in `adapters/**` behind the WorkerAdapter or Capability contract."),
so `engine.verification` depends only on
`engine.capabilities.visual_critic.VisualCriticCapability` and a different
qualified critic can be substituted later without touching the engine.
"""

from adapters.visual_critic.adapter import (
    CAPABILITY_VISUAL_CRITIQUE,
    LocalMultimodalVisualCritic,
    VisualCriticBinding,
)

__all__ = [
    "CAPABILITY_VISUAL_CRITIQUE",
    "LocalMultimodalVisualCritic",
    "VisualCriticBinding",
]
