"""Token-bound value sets for Frontend Studio authoring (Ch.13.8 §4.5).

Picker option lists come from `schemas/design/tokens.json` via the same
sheet the compiler pins. Freehand literals are unrepresentable here —
`assert_token_value` is the production refusal for off-sheet values.
"""

from __future__ import annotations

from functools import lru_cache

from engine.core.errors import DdeError
from engine.studio.tokens_pin import load_token_sheet

DURATION_TOKENS = frozenset(
    {
        "motion-duration-fast",
        "motion-duration-base",
        "motion-duration-slow",
    }
)
EASING_TOKENS = frozenset(
    {
        "motion-easing-arrival",
        "motion-easing-state",
        "motion-easing-linear",
    }
)
STYLE_PROPERTIES = frozenset(
    {
        "color",
        "spacing",
        "radius",
        "shadow",
        "type",
        "duration",
        "easing",
        "z_index",
    }
)
VARIANTS = frozenset({"primary", "secondary", "ghost"})
BASE_KINDS = frozenset({"layout", "text", "button"})


def _kebab(name: str) -> str:
    chars: list[str] = []
    for index, char in enumerate(name):
        if char.isupper() and index:
            chars.append("-")
        chars.append(char.lower())
    return "".join(chars)


@lru_cache(maxsize=1)
def color_aliases() -> frozenset[str]:
    """CSS custom-property names components may reference (never palette hexes)."""
    return frozenset(
        f"--{_kebab(name)}" for name in load_token_sheet().semantic_role_names
    )


@lru_cache(maxsize=1)
def spacing_tokens() -> frozenset[str]:
    properties = load_token_sheet().raw["properties"]["spacing"]["properties"]
    return frozenset(properties)


@lru_cache(maxsize=1)
def radius_tokens() -> frozenset[str]:
    properties = load_token_sheet().raw["properties"]["radius"]["properties"]
    return frozenset(properties)


@lru_cache(maxsize=1)
def type_tokens() -> frozenset[str]:
    scale = load_token_sheet().raw["properties"]["typography"]["properties"]["scale"][
        "properties"
    ]
    return frozenset(scale)


@lru_cache(maxsize=1)
def shadow_tokens() -> frozenset[str]:
    properties = load_token_sheet().raw["properties"]["shadow"]["properties"]
    return frozenset(properties)


@lru_cache(maxsize=1)
def z_index_tokens() -> frozenset[str]:
    properties = load_token_sheet().raw["properties"]["zIndex"]["properties"]
    return frozenset(properties)


def allowed_values(property_name: str) -> frozenset[str]:
    if property_name == "color":
        return color_aliases()
    if property_name == "spacing":
        return spacing_tokens()
    if property_name == "radius":
        return radius_tokens()
    if property_name == "shadow":
        return shadow_tokens()
    if property_name == "type":
        return type_tokens()
    if property_name == "duration":
        return DURATION_TOKENS
    if property_name == "easing":
        return EASING_TOKENS
    if property_name == "z_index":
        return z_index_tokens()
    if property_name == "variant":
        return VARIANTS
    raise DdeError(
        "POLICY_DENIED",
        "Unknown authoring property",
        retryable=False,
        details={"property": property_name},
    )


def assert_token_value(property_name: str, value: str) -> None:
    """Refuse freehand literals. Production call site for conformance-by-construction."""
    if property_name == "label":
        if not value.strip():
            raise DdeError(
                "POLICY_DENIED",
                "label must be a non-empty string",
                retryable=False,
                details={"property": property_name},
            )
        return
    allowed = allowed_values(property_name)
    if value not in allowed:
        raise DdeError(
            "POLICY_DENIED",
            "value is not a token-sheet alias; freehand literals are unauthorable",
            retryable=False,
            details={
                "property": property_name,
                "value": value,
                "allowed": sorted(allowed),
            },
        )


def css_var_for(property_name: str, value: str) -> str:
    """Map a picker value onto the generated CSS custom-property name."""
    if property_name == "color":
        return value
    if property_name == "spacing":
        number = value.removeprefix("space")
        return f"--space-{number}"
    if property_name == "radius":
        return f"--radius-{value}"
    if property_name == "shadow":
        return f"--shadow-{value}"
    if property_name == "type":
        return f"--type-{value}"
    if property_name in {"duration", "easing"}:
        return f"--{value}" if not value.startswith("--") else value
    if property_name == "z_index":
        kebab = _kebab(value)
        return f"--z-{kebab}"
    raise DdeError(
        "POLICY_DENIED",
        "property has no CSS mapping",
        retryable=False,
        details={"property": property_name},
    )
