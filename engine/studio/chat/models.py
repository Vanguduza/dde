"""Honest model/profile catalog for Cursor-class DDE Chat."""

from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass

from engine.routing.registry import OPENROUTER_FREE_MODELS, PROFILES

CLAUDE_CODE_PROFILE = "profile.claude_code_cli"
AUTO_PROFILE = "AUTO"


@dataclass(frozen=True)
class ChatModelOption:
    option_id: str
    label: str
    provider: str
    profile_id: str | None
    model_id: str | None
    status: str
    reason: str
    requires_approval: bool
    capabilities: tuple[str, ...]


class FrontendChatModelCatalog:
    """Projection only; selecting an option never grants invocation authority."""

    def options(self) -> tuple[ChatModelOption, ...]:
        rows: list[ChatModelOption] = [
            ChatModelOption(
                option_id=AUTO_PROFILE,
                label="Auto",
                provider="dde",
                profile_id=None,
                model_id=None,
                status="AVAILABLE",
                reason=(
                    "DDE deterministic routing is available; generative work still "
                    "requires an admitted provider at execution time"
                ),
                requires_approval=False,
                capabilities=("deterministic", "routing"),
            )
        ]
        claude_present = shutil.which("claude") is not None
        rows.append(
            ChatModelOption(
                option_id=CLAUDE_CODE_PROFILE,
                label="Claude Code subscription seat",
                provider="anthropic-cli",
                profile_id=CLAUDE_CODE_PROFILE,
                model_id=None,
                status="APPROVAL_REQUIRED" if claude_present else "UNAVAILABLE",
                reason=(
                    "EDR-0001 requires fresh human approval per Claude Code invocation"
                    if claude_present
                    else "claude executable is not available on this DDE host"
                ),
                requires_approval=True,
                capabilities=("reasoning", "implementation", "repository"),
            )
        )
        for profile_id, profile in sorted(PROFILES.items()):
            rows.append(
                ChatModelOption(
                    option_id=profile_id,
                    label=profile_id,
                    provider=profile.harness_class or "dde-worker",
                    profile_id=profile_id,
                    model_id=None,
                    status="NOT_CERTIFIED",
                    reason=(
                        "routing profile is declared, but no process-wide certified "
                        "live Chat adapter is bound to this profile"
                    ),
                    requires_approval=False,
                    capabilities=tuple(sorted(profile.capabilities)),
                )
            )
        for spec in OPENROUTER_FREE_MODELS:
            rows.append(
                ChatModelOption(
                    option_id=f"model:openrouter:{spec.model_id}",
                    label=spec.model_id,
                    provider="openrouter",
                    profile_id=None,
                    model_id=spec.model_id,
                    status="UNAVAILABLE",
                    reason=(
                        "model is declared for routing, but the OpenRouter credential/"
                        "live Chat provider binding is not implemented"
                    ),
                    requires_approval=False,
                    capabilities=tuple(sorted(spec.strengths)),
                )
            )
        return tuple(rows)

    def require_known(self, option_id: str | None) -> str | None:
        if option_id is None:
            return None
        normalized = option_id.strip()
        known = {item.option_id for item in self.options()}
        if normalized not in known:
            from engine.core.errors import DdeError

            raise DdeError(
                "VALIDATION_FAILED",
                "unknown Chat model/profile selection",
                retryable=False,
                details={"model_profile_id": normalized},
            )
        return normalized

    def as_projection(self) -> tuple[dict[str, object], ...]:
        return tuple(asdict(item) for item in self.options())
