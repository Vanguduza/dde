"""DDE-069 — the design gateway refuses rather than substitutes.

The properties under test are the ones that decide whether `/design` is a
capability or a label: no certified provider means a typed refusal and no
fallback; a malformed artifact is quarantined rather than accepted; a
design artifact reaches code only through Try live's isolated candidate;
and a design-system change makes an old artifact stale rather than
silently applicable.

The egress boundary is tested too. What a provider receives is compiled
from an allowlist, and a test asserts that internal attributes and
identifiers stay behind.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from engine.core.errors import DdeError
from engine.studio.candidates.service import CandidateService
from engine.chat.service import FrontendChatService
from engine.studio.design.context import compile_context, design_system_snapshot
from engine.studio.design.gateway import DesignGateway
from engine.studio.design.providers import (
    ClaudeDesignProvider,
    DesignProviderRegistry,
    DesignRequest,
    ProviderArtifact,
    ProviderState,
    default_registry,
)
from engine.studio.mutations.executor import MutationExecutor
from engine.studio.pxg.service import NodeInput, PxgGraph, PxgService
from tests.support.db import new_engine, seed_tenant
from tests.support.pxg_fixtures import node


class StubDesignProvider:
    """A certified provider, so the accepted path is exercised too.

    It is a stand-in for a transport, not for the gateway's rules: every
    assertion below still runs through the real quarantine, staleness and
    candidate-isolation logic.
    """

    provider_id = "claude-design"

    def __init__(self, artifacts: tuple[ProviderArtifact, ...]) -> None:
        self._artifacts = artifacts
        self.seen: list[DesignRequest] = []

    async def status(self):
        from engine.studio.design.providers import DesignProviderStatus

        return DesignProviderStatus(
            provider_id=self.provider_id,
            display_name="Claude Design (stub transport)",
            state=ProviderState.CERTIFIED,
            detail="stub transport registered for tests",
            version="test-1",
        )

    async def generate(self, request: DesignRequest):
        self.seen.append(request)
        return self._artifacts


def _artifact(label: str, content: dict | None = None) -> ProviderArtifact:
    return ProviderArtifact(
        direction_label=label,
        content=content if content is not None else {"nodes": [], "notes": label},
        provider_version="test-1",
    )


async def _project(engine):
    fixture = await seed_tenant(engine)
    scope = {"tenant_id": fixture.tenant_id, "project_id": fixture.project_id}
    await PxgService(engine).apply(
        **scope,
        nodes=[
            NodeInput(pxg_key="screens/checkout", node_kind="screen", title="Checkout"),
            NodeInput(
                pxg_key="screens/checkout#hero",
                node_kind="region",
                title="Hero",
                parent_key="screens/checkout",
                attributes={"spacing": "space2", "internal_note": "do not export"},
                provenance={"source": "internal", "authored_by_task_id": "secret"},
            ),
            NodeInput(pxg_key="screens/other", node_kind="screen", title="Other"),
        ],
    )
    return fixture, scope


# --- the egress boundary ----------------------------------------------


def test_only_allowlisted_context_leaves_dde() -> None:
    graph = PxgGraph(
        revision=3,
        nodes=(
            node("screens/a", "screen"),
            node(
                "screens/a#hero",
                "region",
                parent="screens/a",
                attributes={"spacing": "space2", "internal_note": "secret"},
            ),
            node("screens/elsewhere", "screen"),
        ),
        edges=(),
    )
    context = compile_context(scope_keys=["screens/a"], graph=graph, contract=None)
    keys = {item["pxg_key"] for item in context.nodes}
    assert keys == {"screens/a", "screens/a#hero"}
    assert "screens/elsewhere" not in keys, "out-of-scope nodes stay behind"

    hero = next(item for item in context.nodes if item["pxg_key"] == "screens/a#hero")
    assert hero["attributes"] == {"spacing": "space2"}
    assert "internal_note" not in hero["attributes"]


def test_an_unscoped_design_request_is_refused() -> None:
    graph = PxgGraph(revision=1, nodes=(node("screens/a", "screen"),), edges=())
    with pytest.raises(DdeError) as excinfo:
        compile_context(scope_keys=[], graph=graph, contract=None)
    assert excinfo.value.error_code == "VALIDATION_FAILED"
    assert "whole project" in excinfo.value.message


def test_design_system_tokens_export_as_names_not_literals() -> None:
    """A provider designing against `space6` produces something DDE can
    validate; one designing against `24px` has already escaped the token
    discipline."""
    snapshot = design_system_snapshot()
    for values in snapshot.tokens.values():
        for value in values:
            assert not value.endswith("px"), value
            assert not value.startswith("#"), value


# --- provider certification -------------------------------------------


@pytest.mark.asyncio
async def test_claude_is_uncertified_in_this_build_and_says_why() -> None:
    status = await ClaudeDesignProvider().status()
    assert status.state is ProviderState.NOT_CERTIFIED
    assert status.usable is False
    assert "section 23" in status.detail


@pytest.mark.asyncio
async def test_an_uncertified_provider_is_refused_with_no_fallback() -> None:
    registry = default_registry()
    with pytest.raises(DdeError) as excinfo:
        await registry.resolve("claude-design")
    assert excinfo.value.error_code == "CAPABILITY_UNAVAILABLE"
    assert excinfo.value.details["state"] == "NOT_CERTIFIED"


@pytest.mark.asyncio
async def test_an_unknown_provider_is_refused() -> None:
    with pytest.raises(DdeError) as excinfo:
        await default_registry().resolve("some-other-provider")
    assert excinfo.value.error_code == "CAPABILITY_UNAVAILABLE"
    assert "known" in excinfo.value.details


@pytest.mark.asyncio
async def test_the_gateway_writes_nothing_when_the_provider_is_uncertified() -> None:
    """A refusal must not leave a half-open session behind."""
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        gateway = DesignGateway(engine)
        with pytest.raises(DdeError) as excinfo:
            await gateway.request(
                **scope,
                scope_keys=["screens/checkout"],
                instruction="three hero alternatives",
            )
        assert excinfo.value.error_code == "CAPABILITY_UNAVAILABLE"

        artifacts = await gateway.artifacts_for(**scope, session_id=uuid4())
        assert artifacts == ()
    finally:
        await engine.dispose()


# --- the accepted path -------------------------------------------------


@pytest.mark.asyncio
async def test_directions_are_recorded_with_provenance_and_neutral_labels() -> None:
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        provider = StubDesignProvider((_artifact("A"), _artifact("B"), _artifact("C")))
        gateway = DesignGateway(engine, registry=DesignProviderRegistry((provider,)))
        outcome = await gateway.request(
            **scope,
            scope_keys=["screens/checkout"],
            instruction="three hero alternatives",
        )
        assert [item.direction_label for item in outcome.artifacts] == [
            "A",
            "B",
            "C",
        ]
        for artifact in outcome.artifacts:
            assert artifact.status == "GENERATED"
            assert artifact.provenance["provider_id"] == "claude-design"
            assert artifact.provenance["design_system_hash"]
            assert artifact.content_hash
            # A neutral direction carries no score: there is no evidence
            # for one, and inventing it is forbidden by section 17.2.
            assert "score" not in artifact.content

        # The session records exactly what was exported.
        assert outcome.session.context_manifest["node_count"] == 2
        assert outcome.session.design_system_hash

        # And the provider received only the scoped slice.
        assert len(provider.seen) == 1
        exported = {item["pxg_key"] for item in provider.seen[0].context.nodes}
        assert "screens/other" not in exported
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_a_malformed_artifact_is_quarantined_not_accepted() -> None:
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        provider = StubDesignProvider(
            (
                _artifact("A"),
                ProviderArtifact(
                    direction_label="B", content={}, provider_version="test-1"
                ),
                ProviderArtifact(
                    direction_label="C",
                    content={"nodes": "not-a-list"},
                    provider_version="test-1",
                ),
            )
        )
        gateway = DesignGateway(engine, registry=DesignProviderRegistry((provider,)))
        outcome = await gateway.request(
            **scope,
            scope_keys=["screens/checkout"],
            instruction="three directions",
        )
        by_label = {item.direction_label: item for item in outcome.artifacts}
        assert by_label["A"].status == "GENERATED"
        assert by_label["B"].status == "QUARANTINED"
        assert "empty" in (by_label["B"].quarantine_reason or "")
        assert by_label["C"].status == "QUARANTINED"
        assert "list" in (by_label["C"].quarantine_reason or "")
        assert {item.direction_label for item in outcome.usable} == {"A"}

        with pytest.raises(DdeError) as excinfo:
            await gateway.try_live(**scope, artifact_id=by_label["B"].artifact_id)
        assert excinfo.value.error_code == "DESIGN_SOURCE_REJECTED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_try_live_creates_an_isolated_candidate_not_accepted_code() -> None:
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        provider = StubDesignProvider((_artifact("A"),))
        gateway = DesignGateway(engine, registry=DesignProviderRegistry((provider,)))
        outcome = await gateway.request(
            **scope, scope_keys=["screens/checkout"], instruction="a hero"
        )
        artifact = outcome.artifacts[0]
        before = await PxgService(engine).current_revision(**scope)

        _, candidate_id = await gateway.try_live(
            **scope, artifact_id=artifact.artifact_id
        )

        candidate = await CandidateService(engine).get(
            **scope, candidate_id=candidate_id
        )
        assert candidate.origin == "DESIGN_ARTIFACT"
        assert candidate.state == "REQUESTED"
        assert candidate.scope_keys == ["screens/checkout"]
        assert candidate.provenance["design_artifact_id"] == str(artifact.artifact_id)

        # The accepted graph is untouched: a design artifact never becomes
        # accepted state by being tried.
        assert await PxgService(engine).current_revision(**scope) == before

        # Trying the same artifact twice is refused rather than forking.
        with pytest.raises(DdeError) as excinfo:
            await gateway.try_live(**scope, artifact_id=artifact.artifact_id)
        assert excinfo.value.error_code == "POLICY_DENIED"
    finally:
        await engine.dispose()


# --- chat and design share one session ---------------------------------


@pytest.mark.asyncio
async def test_chat_routes_a_deterministic_edit_through_the_mutation_path() -> None:
    """The same governed path as the inspector — no chat-specific writer."""
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        candidates = CandidateService(engine)
        candidate = await candidates.create(
            **scope,
            title="Working",
            origin="DIRECT_EDIT",
            scope_keys=["screens/checkout"],
        )
        from engine.studio.candidates.lifecycle import CandidateState

        for target in (
            CandidateState.GENERATING,
            CandidateState.GENERATED,
            CandidateState.MATERIALIZING,
            CandidateState.RENDERING,
            CandidateState.READY,
        ):
            await candidates.transition(
                **scope, candidate_id=candidate.candidate_id, target=target
            )

        chat = FrontendChatService(engine)
        conversation = await chat.open(**scope)
        await chat.set_context(
            **scope,
            conversation_id=conversation.conversation_id,
            selected_node_keys=["screens/checkout#hero"],
            active_candidate_id=candidate.candidate_id,
        )

        result = await chat.send(
            **scope,
            conversation_id=conversation.conversation_id,
            text="set the spacing to space6",
        )
        assert result.turn.outcome == "ROUTED"
        assert result.turn.intent == "MUTATE_DETERMINISTIC"
        assert len(result.produced_refs) == 1

        # The edit went through the real executor onto the candidate.
        history = await MutationExecutor(engine).history(
            **scope, candidate_id=candidate.candidate_id
        )
        assert [item.status for item in history] == ["APPLIED"]
        assert history[0].origin == "CHAT"

        # An off-token value gets the same refusal the inspector would get.
        refused = await chat.send(
            **scope,
            conversation_id=conversation.conversation_id,
            text="set the color to #ff0000",
        )
        assert refused.turn.outcome == "REFUSED"
        assert refused.turn.refusal_code == "OFF_TOKEN_REFUSED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_chat_design_intent_surfaces_the_gateway_refusal_verbatim() -> None:
    """ "No certified provider" and "the design system moved" call for
    different actions, so the refusal is not softened into a generic
    failure."""
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        chat = FrontendChatService(engine)
        conversation = await chat.open(**scope)
        await chat.set_context(
            **scope,
            conversation_id=conversation.conversation_id,
            selected_node_keys=["screens/checkout"],
        )
        result = await chat.send(
            **scope,
            conversation_id=conversation.conversation_id,
            text="/design three hero alternatives",
        )
        assert result.turn.outcome == "REFUSED"
        assert result.turn.refusal_code == "CAPABILITY_UNAVAILABLE"
        assert result.turn.intent == "DESIGN_DIVERGENT"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_chat_and_design_share_one_session() -> None:
    """A `/design` request from the composer joins the conversation rather
    than starting a second one."""
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        provider = StubDesignProvider((_artifact("A"), _artifact("B")))
        chat = FrontendChatService(
            engine,
            design=DesignGateway(engine, registry=DesignProviderRegistry((provider,))),
        )
        conversation = await chat.open(**scope)
        await chat.set_context(
            **scope,
            conversation_id=conversation.conversation_id,
            selected_node_keys=["screens/checkout"],
        )
        result = await chat.send(
            **scope,
            conversation_id=conversation.conversation_id,
            text="/design two hero alternatives",
        )
        assert result.turn.outcome == "ROUTED"
        assert len(result.produced_refs) == 2

        turns = await chat.history(
            **scope, conversation_id=conversation.conversation_id
        )
        assert len(turns) == 2
        assert [turn.role for turn in turns] == ["user", "studio"]
        assert turns[0].resolved_context["target_keys"] == ["screens/checkout"]
        assert turns[1].text == "2 direction(s) generated"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_a_chat_edit_with_no_active_candidate_is_refused() -> None:
    """The accepted design is never edited in place, including from chat."""
    engine = new_engine()
    try:
        _, scope = await _project(engine)
        chat = FrontendChatService(engine)
        conversation = await chat.open(**scope)
        await chat.set_context(
            **scope,
            conversation_id=conversation.conversation_id,
            selected_node_keys=["screens/checkout#hero"],
        )
        result = await chat.send(
            **scope,
            conversation_id=conversation.conversation_id,
            text="set the spacing to space6",
        )
        assert result.turn.outcome == "REFUSED"
        assert result.turn.refusal_code == "NO_ACTIVE_CANDIDATE"
        assert "never edited in place" in (result.turn.refusal_detail or "")
    finally:
        await engine.dispose()
