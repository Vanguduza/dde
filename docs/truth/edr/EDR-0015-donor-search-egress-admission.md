# EDR-0015 — Donor-search egress admission: brokered, allowlisted outbound
# access for DDE-066's donor discovery fan-out

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. Following the convention established in
> `EDR-0001`–`EDR-0014`, this file is a **markdown pre-image** of the eventual
> `edrs` row, filed as the proposal itself (AGENTS.md forbids editing
> `docs/truth/**` as a side effect). **This file is not itself an accepted
> EDR.** `status` is `proposed`; only a human decision via
> `scripts/accept_owner_edrs.py` can move it to `accepted`.

- **slug:** `EDR-0015`
- **status:** `proposed`
- **supersedes/amends:** none superseded; **amends proposed EDR-0011** for one
  specific surface — see "Relationship to EDR-0011" below.
- **affected_requirement_slugs:** none filed yet
- **raised during:** Frontend Studio charter v3 sign-off (2026-08-24).
  Charter §5 guardrail 1 requires this instrument filed at DDE-066 charter
  time; DDE-066 cannot start implementation before acceptance (the
  EDR-0008 accept-first pattern).

## Context

DDE-066 (Donor Discovery & Feature-Function Taxonomy) is the first Stage 5
mission that requires routine, recurring **outbound network egress from the
control plane**: search fan-out over donor sources classified per Chapter
13.8. The hosts in scope are narrow and enumerable:

| Host class | Use | Source class |
|---|---|---|
| GitHub API (`api.github.com`) | repos/tools/libraries search and metadata | per-result Ch.13.8 classification |
| shadcn-ecosystem registry endpoints | registry JSON for OPEN_REUSE components | `OPEN_REUSE` |
| Commercial-template product sites' public catalogue/metadata endpoints | metadata only, never bundles or assets | `CONDITIONAL_REUSE`, metadata only |

Marketplace bundles are excluded entirely (`REJECTED`). No executing donor
code, no ingesting code into the generator, no asset downloads on this
surface.

Today no production path can make these calls honestly: Chapter 7.2 rule 2
("All egress through the proxy ... direct IP egress is dropped") is recorded,
not enforced; `LocalProcessBackend` discloses its egress gap
(`NETWORK_ISOLATION_GAP`) rather than claiming enforcement; and EDR-0011 — the
general T2 containment decision — remains **proposed with its precondition
deferred by human decision 2026-08-23** (gap-closure-record §6.3), because its
full scope (per-run namespace/proxy admission for *worker* runs) is gated on
the first non-DDE-native execution substrate landing.

Donor search does not fit that deferral: it is a **control-plane capability**
with known hosts, human-auditable queries and no worker-controlled payload —
and DDE-066 needs it before the general containment substrate exists.

## Decision (proposed)

Admit exactly the three host classes above as **broker-admitted, allowlisted,
journal-recorded egress**, under all seven constraints below. Anything not
named here stays forbidden; widening the allowlist is itself an EDR-class
change (no silent network widening, AGENTS.md).

1. **Broker-issued credentials only.** Every outbound call authenticates with
   short-lived credentials minted by the capability broker (GitHub tokens
   included); no long-lived secret is ever passed to anything executing
   model-generated code (AGENTS.md forbidden list), and no ambient
   environment credential is reachable by the search path.
2. **Placement: control-plane service, not T2 worker boundary.** Donor search
   runs inside the control plane behind a new side-effecting capability with
   a declared `side_effect_class` (Chapter 9.3), NOT through the deferred
   per-run proxy machinery. The T2/EDR-0011 boundary continues to govern
   *worker* egress; nothing here widens it.
3. **Rate/quota ownership named.** Each admitted host gets an explicit owner
   of rate limits and quotas (per-project budget accounting, Chapter 16.4),
   recorded in the capability registration — quota exhaustion is a typed,
   observable state, never a silent empty result.
4. **Ch.12.4 journal per outbound query.** Every outbound query carries an
   idempotency key and writes an ExternalEffect journal row before retry;
   replaying a duplicated query asserts exactly one effect.
5. **Fail-closed posture.** Classifier unreachable → empty results plus a
   typed refusal, never degraded classification; UNKNOWN source defaults to
   `SOURCE_REFERENCE_ONLY`/`REJECTED` and can never silently upgrade
   (Ch.13.8 classify-before-use ordering).
6. **Injection screening precedes model-visible surfaces.** Registry JSON,
   READMEs and descriptions are untrusted rank-10 material (Ch.14.5 invariant
   6): screening happens before any result reaches a model-visible context.
7. **Revocation.** Removing an allowlist entry stops future queries at the
   admission gate; already-journal-recorded effects remain queryable audit
   history.

### Relationship to EDR-0011

This EDR **amends** EDR-0011's deferred trigger for exactly this surface:
donor-search egress is admitted now, ahead of the general containment
substrate, because it is a bounded control-plane surface that can be gated
structurally (allowlist + broker + journal) without the per-run proxy. It
does **not** supersede EDR-0011: the container/T2 residuals (worker-run
egress, process-tree reach) remain governed there, and if EDR-0011's Option B
lands later, this capability migrates onto the same egress boundary. If
EDR-0011 is rejected, this EDR's admission stands on its own for this
surface only.

## Consequences

- If adopted: DDE-066 can start implementation after acceptance, with every
   query durable, budgeted, screened and auditable from day one; the
   blueprint's Chapter 7.2/13.8 chapters gain a concrete admitted-surface
   record (a Project Truth edit to be proposed through the normal chapter
   amendment path, not made here).
- If rejected: DDE-066 stays unimplementable until either EDR-0011 lands
   (general substrate first) or a differently-shaped admission is decided;
   its charter may still be written but no code moves.
- Open questions for the deciding human: exact endpoint allowlist granularity
   (host vs host+path), whether commercial-template metadata endpoints are
   enumerated explicitly or admitted as a curated list maintained in-repo,
   and the default per-project query budget numbers.
