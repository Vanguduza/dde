"""DDE-069 — chat is a control plane, and it refuses rather than guesses.

Pure tests over classification and reference resolution. Two properties
matter: an ordinary edit is handled deterministically and never spends a
model call, and an ambiguous instruction is refused rather than acted on —
guessing in a design tool silently changes the user's work.
"""

from __future__ import annotations

from engine.studio.chat.intent import (
    DESIGN_INTENTS,
    ChatContext,
    Intent,
    classify,
)

SELECTED = ChatContext(selected_node_keys=("screens/checkout#hero",))
NOTHING_SELECTED = ChatContext()


def test_an_ordinary_property_edit_is_deterministic_not_a_design_call() -> None:
    result = classify("set the spacing to space6", SELECTED)
    assert result.intent is Intent.MUTATE_DETERMINISTIC
    assert result.intent not in DESIGN_INTENTS
    assert result.mutation == {
        "operation": "SET_PROPERTY",
        "payload": {"property": "spacing", "value": "space6"},
    }
    assert result.target_keys == ("screens/checkout#hero",)
    assert result.routable


def test_slash_design_is_a_design_intent_from_the_same_composer() -> None:
    """`/design` is a capability inside the chat control plane, not a
    second conversation."""
    result = classify("/design three hero alternatives", SELECTED)
    assert result.intent is Intent.DESIGN_DIVERGENT
    assert result.intent in DESIGN_INTENTS
    assert result.mutation is None


def test_an_instruction_with_no_resolvable_target_is_refused() -> None:
    result = classify("set the spacing to space6", NOTHING_SELECTED)
    assert result.routable is False
    assert result.refusal_code == "AMBIGUOUS_REFERENCE"
    assert "nothing is selected" in (result.refusal_detail or "")


def test_an_explicit_key_beats_the_current_selection() -> None:
    """A user who names something means it."""
    result = classify("set the spacing to space6 on screens/settings#panel", SELECTED)
    assert result.target_keys == ("screens/settings#panel",)
    assert result.references["explicit"] == "screens/settings#panel"


def test_a_deictic_reference_resolves_to_the_selection() -> None:
    result = classify("what is this?", SELECTED)
    assert result.intent is Intent.INSPECT
    assert result.target_keys == ("screens/checkout#hero",)
    assert result.references["deictic"] == "selection"


def test_an_unmapped_candidate_reference_is_captured_and_refused() -> None:
    result = classify("use Candidate B's sidebar", SELECTED)
    assert result.references["candidate"] == "B"
    assert result.refusal_code == "AMBIGUOUS_REFERENCE"
    assert "stable candidate id" in (result.refusal_detail or "")


def test_read_only_intents_do_not_compile_a_mutation() -> None:
    for text, expected in (
        ("how much coverage do we have?", Intent.COVERAGE_QUERY),
        ("show me the open QA findings", Intent.QA_QUERY),
        ("undo that", Intent.UNDO_REVERT),
        ("promote this candidate", Intent.PROMOTE),
    ):
        result = classify(text, SELECTED)
        assert result.intent is expected, text
        assert result.mutation is None, text


def test_a_lock_instruction_is_classified_as_a_lock_change() -> None:
    result = classify("lock the hero section", SELECTED)
    assert result.intent is Intent.LOCK_CHANGE


def test_an_uninterpretable_message_is_refused_not_guessed() -> None:
    result = classify("asdfgh qwerty", SELECTED)
    assert result.intent is Intent.UNKNOWN
    assert result.routable is False


def test_an_empty_message_is_refused() -> None:
    result = classify("   ", SELECTED)
    assert result.refusal_code == "INTENT_AMBIGUOUS"


def test_an_edit_shaped_message_with_no_property_is_refused() -> None:
    """Better to say "I could not act on that" than to pick a property."""
    result = classify("make it nicer", SELECTED)
    # Classified as something, but never compiled into a blind mutation.
    assert result.mutation is None
