"""Chapter 9.8's initial capability portfolio, narrowed to the three real,
already-implemented Stage 1 mechanisms this mission's brief names as
needing a descriptor home: running a local process (Chapter 7.5's
`execute()`, DDE-010's `engine.environments.backends.local_process.
LocalProcessBackend`), workspace filesystem read/write (Chapter 7.5's
`read()`/`write()`, `engine.workspaces.service.WorkspaceService`), and git
operations (Chapter 10's `engine.integration.git`/`engine.workspaces.git`).

This is a real registration path: `seed_capabilities()` calls
`CapabilityRegistryService.register()` for each entry -- the same validated
service call any other caller uses, never a hand-written SQL `INSERT`
bypassing the Chapter 9.3 taxonomy check. It stands in for whatever future
ops/bootstrap step invokes it for real; wiring it into that bootstrap step
is out of this mission's scope (no such bootstrap entrypoint exists yet in
Stage 1/2, and inventing one would be building ahead of the mission that
needs it).

**Flagged interpretation.** Chapter 9 does not classify these three concrete
operations against 9.3's taxonomy or assign them a `risk_class` -- that
mapping is this mission's own judgement call, stated here so it can be
checked:
  - `capability.run_local_process` / `capability.workspace_filesystem`:
    `WORKSPACE_LOCAL` -- both mutate only the task's own workspace
    (Chapter 7.5), never anything outside it.
  - `capability.git_operations`: `EXTERNAL_IDEMPOTENT` -- branch/ref
    mutations reach the shared mission-integration repository state
    (Chapter 10.2), beyond a single task's isolated workspace, but every
    operation `engine.integration.git`/`engine.workspaces.git` performs
    (`update-ref`, `branch -D`, a rebase re-run after abort) is safe to
    repeat with the same inputs -- 9.3's "provider honours an idempotency
    key" condition, with git's own ref-update semantics standing in for
    that key.
  - `enforcement_tier = "T1"` for all three: each is invoked directly by
    DDE's own code (`engine.workspaces`/`engine.environments`/
    `engine.integration`), never by a third-party harness -- Chapter 7.2's
    T1 definition ("DDE-native capabilities").
  - `certification_status = "CERTIFIED"`: these three are real,
    already-shipped Stage 1 mechanisms with existing test coverage, not
    novel or untrusted tools awaiting Chapter 9.5's admission pipeline
    (out of this mission's scope -- see `engine.capabilities.service`'s
    module docstring).

Visibility is left at `register()`'s default (`"global"`): all three are
native DDE mechanisms available to every tenant, not a tenant-private tool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from engine.capabilities.service import CapabilityRegistryService
from engine.contracts.capability_descriptor import CapabilityDescriptor
from engine.routing.policy import CAPABILITY_DOCS
from engine.truth.db import PostgresUnitOfWork

SEEDED_BY = "system:capability_registry_seed_v1"


@dataclass(frozen=True)
class SeedCapability:
    capability_id: str
    version: str
    category: str
    summary: str
    side_effect_class: str
    risk_class: str
    enforcement_tier: str
    implementations: tuple[str, ...] = ()
    supported_workloads: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    network_requirements: dict[str, object] = field(default_factory=dict)


SEED_CAPABILITIES: tuple[SeedCapability, ...] = (
    SeedCapability(
        capability_id="capability.run_local_process",
        version="1",
        category="process",
        summary=(
            "Execute a command inside a provisioned workspace via a local "
            "OS subprocess (Chapter 7.5 execute())."
        ),
        side_effect_class="WORKSPACE_LOCAL",
        risk_class="low",
        enforcement_tier="T1",
        implementations=(
            "engine.environments.backends.local_process.LocalProcessBackend",
        ),
        supported_workloads=("bulk_implementation", "verification"),
        network_requirements={"egress": "none"},
    ),
    SeedCapability(
        capability_id="capability.workspace_filesystem",
        version="1",
        category="filesystem",
        summary=(
            "Read and write files inside a task's provisioned workspace "
            "(Chapter 7.5 read()/write())."
        ),
        side_effect_class="WORKSPACE_LOCAL",
        risk_class="low",
        enforcement_tier="T1",
        implementations=("engine.workspaces.service.WorkspaceService",),
        supported_workloads=("bulk_implementation", "verification"),
        network_requirements={"egress": "none"},
    ),
    SeedCapability(
        capability_id="capability.git_operations",
        version="1",
        category="repository",
        summary=(
            "Run git branch, rebase, commit and ref-update operations "
            "against a workspace or the mission integration branch "
            "(Chapter 10)."
        ),
        side_effect_class="EXTERNAL_IDEMPOTENT",
        risk_class="medium",
        enforcement_tier="T1",
        implementations=("engine.integration.git", "engine.workspaces.git"),
        dependencies=("git",),
        supported_workloads=("bulk_implementation", "verification"),
        network_requirements={"egress": "none"},
    ),
    # EDR-0001 Path A: spawn the human's own already-`claude login`-
    # authenticated local Claude Code CLI as a real subprocess. Never
    # idempotent -- a repeated invocation is a new model completion that
    # consumes a fresh slice of the human's personal, rate-limited seat, not
    # a safely-repeatable read or ref update (contrast `capability.
    # git_operations`'s EXTERNAL_IDEMPOTENT). `enforcement_tier="T1"`: the
    # subprocess is spawned directly by `adapters.claude.adapter.
    # ClaudeCodeWorkerAdapter`, DDE's own code, exactly like `capability.
    # run_local_process` -- never by a third-party harness.
    SeedCapability(
        capability_id="capability.claude_code_invoke",
        version="1",
        category="external_model",
        summary=(
            "Invoke the human's own already-authenticated local `claude` "
            "CLI as a real subprocess, gated by a mandatory, "
            "non-standing-eligible human approval per invocation "
            "(EDR-0001 Path A). DDE never reads, stores or forwards any "
            "Anthropic credential; it only shells out to the CLI."
        ),
        side_effect_class="EXTERNAL_NON_IDEMPOTENT",
        risk_class="high",
        enforcement_tier="T1",
        implementations=("adapters.claude.adapter.ClaudeCodeWorkerAdapter",),
        dependencies=("claude",),
        network_requirements={
            "egress": "external:anthropic (via local claude CLI only)"
        },
    ),
    # DDE-068 / EDR-0017 Option C: the NARROW multimodal visual critic.
    # Deliberately a separate capability from `capability.claude_code_invoke`
    # rather than a relaxation of it -- that one keeps its mandatory,
    # non-standing, per-invocation human approval
    # (`external_model_invocation`, `STANDING_FORBIDDEN_TYPES`) precisely
    # because it grants arbitrary development execution against a human's
    # own rate-limited seat. This one is safe for bounded machine use under
    # the ordinary Chapter 9 lease path because its permitted action set is
    # intrinsically narrow, enforced by construction in its adapter:
    # bounded visual evidence + a versioned rubric in, one schema-validated
    # structured verdict out; a per-invocation scratch directory holding
    # only the screenshot; read-only tooling; no arbitrary prompt; no code
    # execution; no nested agent; a hard spend ceiling and timeout.
    # PURE_READ: a critique observes a rendered artifact and writes nothing
    # -- contrast `capability.claude_code_invoke`'s
    # EXTERNAL_NON_IDEMPOTENT. Its real consumable resource is model
    # invocation against a rate-limited seat, recorded in invocation counts
    # and whatever usage metadata the runtime actually reports (never an
    # invented dollar figure).
    SeedCapability(
        capability_id="capability.visual_critique",
        version="1",
        category="external_model",
        summary=(
            "Judge one rendered screenshot against the versioned "
            "visual-critique rubric and return a schema-validated "
            "structured verdict (DDE-068). Narrow by construction: no "
            "shell, no filesystem mutation, no source access, no arbitrary "
            "prompt, no nested agent -- evidence in, verdict out."
        ),
        side_effect_class="PURE_READ",
        risk_class="medium",
        enforcement_tier="T1",
        implementations=("adapters.visual_critic.adapter.LocalMultimodalVisualCritic",),
        dependencies=("claude",),
        supported_workloads=("verification", "visual_analysis"),
        network_requirements={
            "egress": "external:multimodal-critic (via local CLI runtime only)"
        },
    ),
    # DDE-043 / Chapter 9.8 web-browser class. Playwright is the blueprint's
    # named implementation (Ch.11 verification tooling, Appendix A). T1:
    # DDE's own adapter launches the browser, never a third-party harness
    # tool plane (those stay T2, Chapter 7.2). EXTERNAL_NON_IDEMPOTENT:
    # a page load/click can mutate a ProductEnvironment with no provider
    # idempotency key — Chapter 12.4 journal + no blind retry.
    SeedCapability(
        capability_id="capability.browser",
        version="1",
        category="browser",
        summary=(
            "Drive a headed-or-headless browser against an allowlisted URL "
            "(Playwright behind adapters.playwright). Used for E2E/api_probe "
            "checks; pixel visual_diff remains DDE-044."
        ),
        side_effect_class="EXTERNAL_NON_IDEMPOTENT",
        risk_class="medium",
        enforcement_tier="T1",
        implementations=("adapters.playwright.adapter.PlaywrightWorkerAdapter",),
        dependencies=("playwright",),
        supported_workloads=("verification", "visual_analysis"),
        network_requirements={"egress": "allowlist:http,https,file"},
    ),
    # DDE-045 / Chapter 9.8 security scanning class. SAST is in-process
    # (same rules as Ch.9.7). PURE_READ: a scan does not mutate the
    # product. DAST and agentic modes fail closed — no live attack plane.
    SeedCapability(
        capability_id="capability.security",
        version="1",
        category="security",
        summary=(
            "Scan a task workspace for secrets and blocking SAST findings "
            "(in-process evaluators; Semgrep/Gitleaks CLIs not required). "
            "DAST and agentic security workers are refused."
        ),
        side_effect_class="PURE_READ",
        risk_class="medium",
        enforcement_tier="T1",
        implementations=("adapters.security.adapter.SecurityWorkerAdapter",),
        supported_workloads=("verification",),
        network_requirements={"egress": "none"},
    ),
    # DDE-046 / Chapter 13.8 Donor Lab ingest. Control-plane durable write of
    # donor_artifacts + feature_dna stubs from human pin-by-URI or fixtures.
    # WORKSPACE_LOCAL: reads local/fixture content and writes DDE tables; no
    # remote fetch on this capability (network discovery is DDE-066).
    SeedCapability(
        capability_id="capability.donor_ingest",
        version="1",
        category="donor",
        summary=(
            "Ingest a human- or fixture-supplied donor URI into durable "
            "DonorArtifact + Feature DNA stub rows (engine.donor). Default "
            "source_class UNKNOWN; OPEN_REUSE requires a signed reuse "
            "decision. Remote http(s) fetch is refused here."
        ),
        side_effect_class="WORKSPACE_LOCAL",
        risk_class="medium",
        enforcement_tier="T1",
        implementations=("engine.donor.service.DonorLabService",),
        supported_workloads=("planning", "verification"),
        network_requirements={"egress": "none"},
    ),
    SeedCapability(
        capability_id="capability.donor_discovery",
        version="1",
        category="donor",
        summary=(
            "Control-plane donor-search fan-out over the EDR-0015 host "
            "allowlist. Classify-before-use; UNKNOWN defaults to "
            "SOURCE_REFERENCE_ONLY. EXTERNAL_IDEMPOTENT: each query is "
            "journaled with an idempotency key before fetch."
        ),
        side_effect_class="EXTERNAL_IDEMPOTENT",
        risk_class="medium",
        enforcement_tier="T1",
        implementations=(
            "engine.donor.discovery_service.DonorDiscoveryService.search",
        ),
        supported_workloads=("planning",),
        network_requirements={
            "egress": "allowlist",
            "edr": "EDR-0015",
            "allowlist": "schemas/design/donor_search_allowlist.json",
            "quota_key": "donor_search_max_queries",
            "default_max_queries": 32,
        },
    ),
    # DDE-048 / Chapter 9.8 mobile/Android class. Static APK analysis is
    # in-process (stdlib zipfile; no JADX/Apktool/MobSF/ADB binary).
    # PURE_READ: analysis never mutates the product or a device. Dynamic
    # modes fail closed — no device attack surface until EDR-0017.
    SeedCapability(
        capability_id="capability.android_analysis",
        version="1",
        category="android",
        summary=(
            "Static analysis of an .apk in the task workspace: manifest "
            "permissions, native ABIs, signing presence, secret scan of "
            "assets (adapters.android, stdlib-only). Dynamic/ADB modes "
            "are refused."
        ),
        side_effect_class="PURE_READ",
        risk_class="medium",
        enforcement_tier="T1",
        implementations=("adapters.android.adapter.AndroidWorkerAdapter",),
        supported_workloads=("verification",),
        network_requirements={"egress": "none"},
    ),
    # DDE-049 / Chapter 9.8 backend/database class + Chapter 11.2's
    # db_assertion binding. In-process read-only SQL assertions over a
    # product datastore (engine.capabilities.database). PURE_READ by
    # construction: non-SELECT statements are refused before execution.
    SeedCapability(
        capability_id="capability.database",
        version="1",
        category="database",
        summary=(
            "Run read-only db_assertion SELECTs against a product "
            "datastore URL and require a boolean result per statement. "
            "DDL/DML refused; no schema or data mutation authority."
        ),
        side_effect_class="PURE_READ",
        risk_class="medium",
        enforcement_tier="T1",
        implementations=(
            "engine.capabilities.database.assertions.InProcessDatabaseAsserter",
        ),
        supported_workloads=("verification",),
        network_requirements={"egress": "datastore_ref only"},
    ),
    # DDE-050 / Chapter 9.8 documentation/context-provider class + Ch.5.2's
    # Documentation retriever. Serves version-pinned external documentation
    # materialised on disk; no network fetch exists on this capability
    # (remote sync is EDR-0020's gated surface). PURE_READ: reads never
    # mutate a source or the product. Content stays rank-9 external
    # evidence (Ch.5.5: never current-state), and injection screening runs
    # at read time so injected instructions remain hypotheses (Ch.14.5).
    SeedCapability(
        capability_id=CAPABILITY_DOCS,
        version="1",
        category="docs",
        summary=(
            "Serve version-pinned external documentation read-only through "
            "the Chapter 5.2 documentation retriever (engine.capabilities."
            "docs). No network egress: sources are operator-materialised "
            "on disk, and content stays rank-9 external evidence that "
            "never satisfies a current-state coverage requirement."
        ),
        side_effect_class="PURE_READ",
        risk_class="low",
        enforcement_tier="T1",
        implementations=("engine.capabilities.docs.provider.InProcessDocsProvider",),
        supported_workloads=("planning", "verification"),
        network_requirements={"egress": "none"},
    ),
    SeedCapability(
        capability_id="capability.frontend_canvas",
        version="1",
        category="studio",
        summary=(
            "Human-authored prototype HTML and flows.json mutations from "
            "Frontend Studio (insert/move/update/remove/motion). Writes are "
            "jailed to the task workspace; values are token-sheet aliases "
            "only. Donor inserts require an APPROVED donor_reuse approval."
        ),
        side_effect_class="WORKSPACE_LOCAL",
        risk_class="medium",
        enforcement_tier="T1",
        implementations=("engine.studio.frontend.FrontendStudioService",),
        supported_workloads=("planning",),
        network_requirements={"egress": "none"},
    ),
)


_SEED_BY_CAPABILITY_ID: dict[str, SeedCapability] = {
    spec.capability_id: spec for spec in SEED_CAPABILITIES
}


def side_effect_class_for(capability_id: str) -> str:
    """DDE-020: the one place `engine.workers.scripted_adapter` and
    `engine.workspaces.service`'s snapshot journal (optional extra git
    read) and `engine.integration.service`'s update-ref journal (the
    Chapter 12.4 EXTERNAL_IDEMPOTENT mutation) read a capability's
    declared `side_effect_class` from -- the same seeded portfolio their
    own `require_active` calls are already gated against, never a second,
    independently-maintained mapping."""
    spec = _SEED_BY_CAPABILITY_ID.get(capability_id)
    if spec is None:
        raise KeyError(
            f"No seeded capability {capability_id!r} to read side_effect_class from"
        )
    return spec.side_effect_class


async def seed_capabilities(
    service: CapabilityRegistryService,
    *,
    tenant_id: UUID,
    project_id: UUID,
    registered_by: str = SEEDED_BY,
    uow: PostgresUnitOfWork | None = None,
) -> list[CapabilityDescriptor]:
    """Registers Chapter 9.8's Stage-1-relevant portfolio through the same
    validated `register()` path any other caller uses. Idempotent:
    re-running it returns the already-registered rows unchanged
    (`register()`'s own content-hash idempotency)."""
    registered: list[CapabilityDescriptor] = []
    for spec in SEED_CAPABILITIES:
        descriptor = await service.register(
            tenant_id=tenant_id,
            project_id=project_id,
            capability_id=spec.capability_id,
            version=spec.version,
            category=spec.category,
            summary=spec.summary,
            side_effect_class=spec.side_effect_class,
            risk_class=spec.risk_class,
            enforcement_tier=spec.enforcement_tier,
            implementations=list(spec.implementations),
            supported_workloads=list(spec.supported_workloads),
            dependencies=list(spec.dependencies),
            provenance={"source": "native", "mission": "DDE-016"},
            network_requirements=dict(spec.network_requirements),
            certification_status="CERTIFIED",
            registered_by=registered_by,
            uow=uow,
        )
        registered.append(descriptor)
    return registered
