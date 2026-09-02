"""DDE-068 OpenRouter implementation of VisualCriticCapability.

Provider-specific HTTP syntax is isolated here, while authentication remains
inside `engine.capabilities.broker.http`: this adapter never receives or
reads the raw OpenRouter API key.

The request is intentionally strict:
- one explicitly pinned multimodal model;
- JSON-schema structured output;
- providers must support the requested parameters;
- provider data collection denied and Zero Data Retention required;
- no model fallbacks that silently change the judging model;
- measured OpenRouter usage/cost must be present in the response.
"""

from __future__ import annotations

import base64
import json
from typing import Protocol
from uuid import UUID

from engine.capabilities.broker.capture_hashing import OPENROUTER_API_KEY_PROVIDER
from engine.capabilities.broker.http import BrokeredJsonResponse
from engine.capabilities.visual_critic import (
    VisualCriticDimensionResult,
    VisualCriticResult,
    VisualCriticSpec,
)
from engine.core.errors import DdeError

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_PROVIDER_ID = "openrouter"
DEFAULT_VISUAL_CRITIC_MODEL = "z-ai/glm-5.3-flash"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_COMPLETION_TOKENS = 1400


class BrokeredJsonClient(Protocol):
    async def post_json(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        provider_id: str,
        url: str,
        body: dict[str, object],
        headers: dict[str, str] | None = None,
    ) -> BrokeredJsonResponse: ...


def _response_schema(spec: VisualCriticSpec) -> dict[str, object]:
    rubric_ids = [item.rubric_id for item in spec.rubric]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["verdict", "score", "dimensions", "findings"],
        "properties": {
            "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
            "score": {"type": "number", "minimum": 0, "maximum": 5},
            "dimensions": {
                "type": "array",
                "minItems": len(rubric_ids),
                "maxItems": len(rubric_ids),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["rubric_id", "score", "finding"],
                    "properties": {
                        "rubric_id": {"type": "string", "enum": rubric_ids},
                        "score": {"type": "number", "minimum": 0, "maximum": 5},
                        "finding": {"type": "string"},
                    },
                },
            },
            "findings": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 12,
            },
        },
    }


def _prompt(spec: VisualCriticSpec) -> str:
    rubric = [
        {
            "rubric_id": item.rubric_id,
            "title": item.title,
            "instruction": item.instruction,
            "weight": item.weight,
        }
        for item in spec.rubric
    ]
    payload = {
        "statement": spec.statement,
        "rubric_version": spec.rubric_version,
        "context": spec.context,
        "rubric": rubric,
    }
    return (
        "You are an independent visual product-design verifier. Judge only "
        "the supplied rendered screenshot and declared context. Do not infer "
        "hidden behavior. Deterministic functional/accessibility/security/"
        "layout gates are evaluated elsewhere and cannot be waived by you. "
        "Score every rubric dimension from 0 to 5. The overall verdict must "
        "be FAIL when the weighted visual quality is below a professional "
        "production-ready standard. Findings must be concise, visible, and "
        "actionable. Input:\n"
        + json.dumps(payload, sort_keys=True, separators=(",", ":"))
    )


def _number(value: object, *, field: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    return float(value)


def _integer(value: object, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    return value


class OpenRouterVisualCritic:
    """Real multimodal critic using a broker-authenticated OpenRouter call."""

    def __init__(self, broker: BrokeredJsonClient) -> None:
        self._broker = broker

    async def critique(self, spec: VisualCriticSpec) -> VisualCriticResult:
        if not spec.png_bytes or len(spec.png_bytes) > MAX_IMAGE_BYTES:
            raise DdeError(
                "POLICY_DENIED",
                "visual critic screenshot is empty or exceeds the image ceiling",
                retryable=False,
                details={"max_image_bytes": MAX_IMAGE_BYTES},
            )
        if not spec.rubric:
            raise DdeError(
                "POLICY_DENIED",
                "visual critic requires a non-empty versioned rubric",
                retryable=False,
            )
        if spec.max_cost_usd <= 0:
            raise DdeError(
                "POLICY_DENIED",
                "visual critic max_cost_usd must be positive",
                retryable=False,
            )

        image = base64.b64encode(spec.png_bytes).decode("ascii")
        body: dict[str, object] = {
            "model": spec.model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _prompt(spec)},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image}",
                            },
                        },
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": MAX_COMPLETION_TOKENS,
            "usage": {"include": True},
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "dde_visual_critic",
                    "strict": True,
                    "schema": _response_schema(spec),
                },
            },
            "provider": {
                "require_parameters": True,
                "data_collection": "deny",
                "zdr": True,
                "allow_fallbacks": False,
                "sort": "price",
                "max_price": {
                    "prompt": 0.20,
                    "completion": 0.70,
                },
            },
        }
        response = await self._broker.post_json(
            tenant_id=spec.tenant_id,
            project_id=spec.project_id,
            provider_id=OPENROUTER_API_KEY_PROVIDER,
            url=OPENROUTER_CHAT_URL,
            body=body,
            headers={
                "HTTP-Referer": "https://dde.local",
                "X-Title": "DDE Visual Verification",
            },
        )
        if response.status_code < 200 or response.status_code >= 300:
            error = response.body.get("error")
            error_type = type(error).__name__
            return VisualCriticResult(
                exit_code=-1,
                verdict="ERROR",
                score=0.0,
                dimensions=(),
                findings=(),
                model_id=spec.model_id,
                provider_id=OPENROUTER_PROVIDER_ID,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                duration_ms=response.duration_ms,
                timed_out=False,
                stderr=(
                    f"OpenRouter HTTP {response.status_code}: {error_type}"
                ),
            )

        try:
            choices = response.body["choices"]
            if not isinstance(choices, list) or not choices:
                raise ValueError("choices must be a non-empty list")
            first = choices[0]
            if not isinstance(first, dict):
                raise ValueError("choices[0] must be an object")
            message = first["message"]
            if not isinstance(message, dict):
                raise ValueError("message must be an object")
            content = message["content"]
            if not isinstance(content, str):
                raise ValueError("structured response content must be a string")
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise ValueError("structured response must be an object")

            verdict = str(parsed["verdict"])
            score = _number(parsed["score"], field="score")
            raw_dimensions = parsed["dimensions"]
            raw_findings = parsed["findings"]
            if not isinstance(raw_dimensions, list):
                raise ValueError("dimensions must be an array")
            if not isinstance(raw_findings, list) or not all(
                isinstance(item, str) for item in raw_findings
            ):
                raise ValueError("findings must be an array of strings")
            dimensions: list[VisualCriticDimensionResult] = []
            seen: set[str] = set()
            expected = {item.rubric_id for item in spec.rubric}
            for item in raw_dimensions:
                if not isinstance(item, dict):
                    raise ValueError("dimension must be an object")
                rubric_id = str(item["rubric_id"])
                if rubric_id not in expected or rubric_id in seen:
                    raise ValueError("dimension rubric ids must match exactly once")
                seen.add(rubric_id)
                dimensions.append(
                    VisualCriticDimensionResult(
                        rubric_id=rubric_id,
                        score=_number(item["score"], field="dimension.score"),
                        finding=str(item["finding"]),
                    )
                )
            if seen != expected:
                raise ValueError("not every rubric dimension was returned")

            usage = response.body["usage"]
            if not isinstance(usage, dict):
                raise ValueError("usage must be an object")
            input_tokens = _integer(usage["prompt_tokens"], field="prompt_tokens")
            output_tokens = _integer(
                usage["completion_tokens"], field="completion_tokens"
            )
            cost_usd = _number(usage["cost"], field="usage.cost")
            actual_model = str(response.body.get("model") or spec.model_id)
            provider = str(
                response.body.get("provider") or OPENROUTER_PROVIDER_ID
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return VisualCriticResult(
                exit_code=-1,
                verdict="ERROR",
                score=0.0,
                dimensions=(),
                findings=(),
                model_id=spec.model_id,
                provider_id=OPENROUTER_PROVIDER_ID,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                duration_ms=response.duration_ms,
                timed_out=False,
                stderr=f"invalid structured OpenRouter response: {exc}",
            )

        if actual_model != spec.model_id:
            return VisualCriticResult(
                exit_code=-1,
                verdict="ERROR",
                score=score,
                dimensions=tuple(dimensions),
                findings=tuple(raw_findings),
                model_id=actual_model,
                provider_id=provider,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                duration_ms=response.duration_ms,
                timed_out=False,
                stderr="provider returned a model different from the pinned critic",
            )
        if cost_usd > spec.max_cost_usd:
            raise DdeError(
                "BUDGET_EXCEEDED",
                "visual critic exceeded the per-cycle EDR-0016 cost ceiling",
                retryable=False,
                details={
                    "cost_usd": cost_usd,
                    "max_cost_usd": spec.max_cost_usd,
                    "model_id": actual_model,
                },
            )
        exit_code = 0 if verdict == "PASS" else 1
        return VisualCriticResult(
            exit_code=exit_code,
            verdict=verdict,
            score=score,
            dimensions=tuple(dimensions),
            findings=tuple(raw_findings),
            model_id=actual_model,
            provider_id=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            duration_ms=response.duration_ms,
            timed_out=False,
        )
