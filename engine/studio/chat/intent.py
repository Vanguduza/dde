"""DDE-069 intent classification and reference resolution -- pure.

Frontend Chat is a control plane, not a chatbot. Most of what a user types
in a design tool is deterministic and needs no model at all: "set the gap
to space6" is a mutation, "how many screens are uncovered?" is a read.
Sending those to a provider would be slower, costlier and less reliable
than doing them.

So classification happens here, deterministically, and only genuinely
generative intents reach the DesignGateway. Ambiguity is refused rather
than guessed: acting on a misread instruction in a design tool silently
changes the user's work.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final


class Intent(StrEnum):
    EXPLAIN = "EXPLAIN"
    INSPECT = "INSPECT"
    COVERAGE_QUERY = "COVERAGE_QUERY"
    QA_QUERY = "QA_QUERY"
    MUTATE_DETERMINISTIC = "MUTATE_DETERMINISTIC"
    DESIGN_DIVERGENT = "DESIGN_DIVERGENT"
    DESIGN_REFINE = "DESIGN_REFINE"
    LOCK_CHANGE = "LOCK_CHANGE"
    UNDO_REVERT = "UNDO_REVERT"
    PROMOTE = "PROMOTE"
    SEARCH_SOURCE = "SEARCH_SOURCE"
    UNKNOWN = "UNKNOWN"


#: Intents that must not run without an unambiguous target.
NEEDS_TARGET: Final[frozenset[Intent]] = frozenset(
    {
        Intent.MUTATE_DETERMINISTIC,
        Intent.DESIGN_DIVERGENT,
        Intent.DESIGN_REFINE,
        Intent.LOCK_CHANGE,
        Intent.INSPECT,
    }
)

#: Intents routed to a design provider. Everything else is answered
#: deterministically, so an ordinary edit never spends a model call.
DESIGN_INTENTS: Final[frozenset[Intent]] = frozenset(
    {Intent.DESIGN_DIVERGENT, Intent.DESIGN_REFINE}
)

# The value class deliberately admits literals the token catalogue will
# reject -- hex colours, px lengths. A user who types `#ff0000` should get
# the token rule explained by the mutation planner, not "I could not
# understand that": the second answer hides the actual constraint.
_SET_PROPERTY = re.compile(
    r"\b(?:set|change|make)\s+(?:the\s+)?(?P<property>[a-z_]+)\s+"
    r"(?:to|=)\s+(?P<value>[#A-Za-z0-9_.%\-]+)",
    re.IGNORECASE,
)
_SLASH_DESIGN = re.compile(r"^\s*/design\b", re.IGNORECASE)
_DEICTIC = re.compile(r"\b(this|that|it|here|the selection|selected)\b", re.IGNORECASE)
_CANDIDATE_REF = re.compile(r"\bcandidate\s+([A-F])\b", re.IGNORECASE)


@dataclass(frozen=True)
class ChatContext:
    """What the studio knows when a turn arrives."""

    selected_node_keys: tuple[str, ...] = ()
    active_candidate_id: str | None = None
    screen_key: str | None = None
    viewport: str = "desktop-1440"


@dataclass(frozen=True)
class Classification:
    intent: Intent
    #: Keys the turn resolved to. Empty when nothing could be resolved.
    target_keys: tuple[str, ...] = ()
    #: A deterministic mutation the turn compiles to, when it is one.
    mutation: dict[str, object] | None = None
    #: Why the turn cannot proceed, if it cannot.
    refusal_code: str | None = None
    refusal_detail: str | None = None
    references: dict[str, str] = field(default_factory=dict)

    @property
    def routable(self) -> bool:
        return self.refusal_code is None and self.intent is not Intent.UNKNOWN


def classify(text: str, context: ChatContext) -> Classification:
    """Classify one turn and resolve its references."""
    stripped = text.strip()
    if not stripped:
        return Classification(
            intent=Intent.UNKNOWN,
            refusal_code="INTENT_AMBIGUOUS",
            refusal_detail="empty message",
        )

    intent = _intent_of(stripped)
    references: dict[str, str] = {}

    candidate_match = _CANDIDATE_REF.search(stripped)
    if candidate_match:
        references["candidate"] = candidate_match.group(1).upper()

    targets = _resolve_targets(stripped, context, references)

    if intent in NEEDS_TARGET and not targets:
        return Classification(
            intent=intent,
            refusal_code="AMBIGUOUS_REFERENCE",
            refusal_detail=(
                "nothing is selected and the message names no element, so "
                "there is no unambiguous target for this instruction"
            ),
            references=references,
        )

    mutation: dict[str, object] | None = None
    if intent is Intent.MUTATE_DETERMINISTIC:
        match = _SET_PROPERTY.search(stripped)
        if match is None:
            return Classification(
                intent=intent,
                target_keys=targets,
                refusal_code="INTENT_AMBIGUOUS",
                refusal_detail=(
                    "the instruction looks like an edit but names no "
                    "property and value the studio can act on"
                ),
                references=references,
            )
        mutation = {
            "operation": "SET_PROPERTY",
            "payload": {
                "property": match.group("property").lower(),
                "value": match.group("value"),
            },
        }

    return Classification(
        intent=intent,
        target_keys=targets,
        mutation=mutation,
        references=references,
    )


def _intent_of(text: str) -> Intent:
    lowered = text.lower()
    if _SLASH_DESIGN.match(text):
        return Intent.DESIGN_DIVERGENT
    if any(word in lowered for word in ("undo", "revert", "roll back")):
        return Intent.UNDO_REVERT
    if "promote" in lowered:
        return Intent.PROMOTE
    if "lock" in lowered or "unlock" in lowered:
        return Intent.LOCK_CHANGE
    if "coverage" in lowered or "uncovered" in lowered:
        return Intent.COVERAGE_QUERY
    if any(word in lowered for word in ("qa", "finding", "issue", "warning")):
        return Intent.QA_QUERY
    if _SET_PROPERTY.search(text):
        return Intent.MUTATE_DETERMINISTIC
    if any(
        word in lowered
        for word in ("redesign", "alternative", "variation", "direction", "restyle")
    ):
        return Intent.DESIGN_DIVERGENT
    if any(word in lowered for word in ("refine", "tweak", "polish")):
        return Intent.DESIGN_REFINE
    if any(word in lowered for word in ("find", "search", "look for")):
        return Intent.SEARCH_SOURCE
    if any(word in lowered for word in ("what", "show", "inspect", "why", "how")):
        return Intent.INSPECT if _DEICTIC.search(text) else Intent.EXPLAIN
    return Intent.UNKNOWN


def _resolve_targets(
    text: str, context: ChatContext, references: dict[str, str]
) -> tuple[str, ...]:
    """Resolve what the turn is about.

    An explicit key in the message wins over the selection, because a user
    who names something means it. A deictic reference resolves to the
    current selection, and only to it — guessing at a screen when nothing
    is selected is how a chat edits the wrong thing.
    """
    explicit = re.findall(r"\b(screens/[A-Za-z0-9._#/-]+)", text)
    if explicit:
        references["explicit"] = explicit[0]
        return tuple(dict.fromkeys(explicit))
    if _DEICTIC.search(text) and context.selected_node_keys:
        references["deictic"] = "selection"
        return context.selected_node_keys
    if context.selected_node_keys:
        return context.selected_node_keys
    return ()
