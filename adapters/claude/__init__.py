"""Claude Code worker adapter package (EDR-0001 Path A).

Claude/Anthropic-specific naming lives only in this tree (AGENTS.md:
"Vendor code lives in `adapters/**` behind the WorkerAdapter or Capability
contract."), mirroring `adapters/cursor/**`'s existing boundary.
"""

from adapters.claude.adapter import (
    APPROVAL_TYPE_EXTERNAL_MODEL_INVOCATION,
    CAPABILITY_CLAUDE_CODE_INVOKE,
    ClaudeCodeWorkerAdapter,
    ClaudePromptBinding,
    claude_invocation_scope_hash,
)

__all__ = [
    "APPROVAL_TYPE_EXTERNAL_MODEL_INVOCATION",
    "CAPABILITY_CLAUDE_CODE_INVOKE",
    "ClaudeCodeWorkerAdapter",
    "ClaudePromptBinding",
    "claude_invocation_scope_hash",
]
