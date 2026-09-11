# EDR-0018 — Exact-pinned public automation-corpus snapshot acquisition

> **ACCEPTED 2026-09-11 by explicit project-owner instruction:** "Implement rev 2 fully" after review of `DDE Production VEKL × Zie619/n8n-workflows Integration Plan — Rev 2`. This EDR is the repository-readable acceptance record for the additional acquisition surface Rev 2 requires beyond EDR-0015. The authoritative durable Project Truth row must be provisioned through the ordinary TruthService acceptance path in service-capable environments; CI/provisioning tests must prove that row before production acquisition is considered enabled.

- **slug:** `EDR-0018`
- **status:** `accepted (2026-09-11)`
- **supersedes/amends:** amends EDR-0015 only for the exact-pinned public corpus snapshot surface defined below; EDR-0015 remains authoritative for donor search/metadata reads.
- **scope:** Production VEKL `TARGET_APPLICATION` source acquisition only.

## Decision

DDE may acquire exact, immutable public repository snapshots for Production VEKL corpus qualification only through a dedicated control-plane capability. The initial admitted source is `Zie619/n8n-workflows`; no wildcard repository or arbitrary host authority is granted.

The admitted initial transport is:

- `GET https://codeload.github.com/Zie619/n8n-workflows/zip/<40-char-commit-sha>`;
- redirects are forbidden because the final codeload endpoint is pinned directly;
- repository revision must be a lowercase 40-character Git SHA, never a branch/tag/ref alias;
- maximum compressed snapshot: **96 MiB**;
- maximum uncompressed quarantine bytes: **512 MiB**;
- maximum workflow JSON files per acquisition: **10,000**;
- maximum single workflow JSON: **2 MiB**;
- maximum acquisition frequency for one project/source/revision: one confirmed effect; replay reuses immutable evidence;
- anonymous public HTTPS is the default authentication mode for this source; credentials are forbidden for generated code/workers and any future authenticated corpus source requires a separate authority decision;
- acquisition bytes are retained only in the project-scoped quarantine/object store under content-addressed keys; model-visible projections use sanitized derivatives only;
- every outbound acquisition is preceded by a granted `CapabilityLease` and `ExternalEffect(PREPARED)` row, then transitions through SENT/CONFIRMED or FAILED/UNKNOWN using existing recovery law;
- acquisition is refused for `DDE_CONTROL_PLANE`, unpinned revisions, non-admitted host/path/method, quota/size excess, missing source authority, revoked source, or unresolved prior effect;
- prompt/security/secret/PII screening is mandatory before source text can enter search, embeddings, GraphRAG, or worker context;
- revoking this authority or the source admission stops future acquisition and invalidates affected derived VEKL resources without deleting historical evidence.

## Source Intelligence decision

The existing DDE-069 `design_sources` / `design_source_artifacts` / `design_source_admissions` contracts remain Frontend Studio specializations and MUST NOT be used to mislabel automation corpora as design-system artifacts.

DDE SHALL introduce a domain-neutral Source Intelligence base (`SourceRecord`, `SourceArtifact`, `SourceAdmission`). Frontend design sources may bridge/mirror into that base for VEKL compatibility, but Production VEKL external-resource qualification must depend on the domain-neutral authority. Automation-corpus qualification uses profile `AUTOMATION_CORPUS_REFERENCE` and does not require frontend-only accessibility/design-token semantics.

## Non-authority / non-execution law

Snapshot admission grants no Project Truth authority, task creation authority, capability authority, credential authority, worker-harness role, donor-code execution, n8n runtime execution, or positive implementation guidance by itself. Raw workflows remain quarantined evidence. Only separately hashed sanitized descriptors may become qualified non-executable VEKL resources after policy checks.

## Consequences

This EDR unblocks Rev 2 Phase 2+ only after schema/service implementation and accepted-row provisioning are green. It does not make `Zie619/n8n-workflows` canonical, does not permanently select a revision, and does not widen ordinary worker egress.
