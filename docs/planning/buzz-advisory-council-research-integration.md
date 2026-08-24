# Buzz / advisory-council research integration — boardroom verdict and adopted-in-principle posture

**Date:** 2026-08-24. **Nature:** docs-only integration of completed web research into
planning; no engine code changes, no Project Truth rows, no new dependency. Recorded in
`docs/planning/gap-closure-record.md §6.9`.

**Orientation anchors:** `AGENTS.md` (forbidden list; no second source of truth);
`docs/blueprint/REV_2_0.md` Ch.2.2 (precedence ranks), Ch.5.6/5.7 (rank-9 evidence,
budget/eviction), Ch.13.1–13.4 (approval, standing approvals, non-blocking decisions,
attention economics), Ch.12.4 (durable effects); the blueprint's standing refusal of
"any agent framework, graph runtime or agent-to-agent message bus" for core state
transitions.

---

## 1. What Buzz is

Buzz is Block's (Square/Cash App parent) open-source, Nostr-based **human + agent
workspace**: agents and humans collaborate in shared, protocol-native conversation
spaces, with agent identities, permissions and auditability carried by the same fabric
that carries human messaging. Key facts as researched:

- Rust monorepo, Apache-2.0 licence, ~30.4k stars at research time.
- **Prototype maturity:** early-stage product surface; the interesting artifacts are the
  protocol-level patterns, not a production-proven deployment.
- Source-quality caveat: coverage is launch-announcement-heavy; no independent security
  audit; numbers are vendor-published. Patterns are the adoption candidate, never the
  dependency (Ch.9.6: no new dependency without licence, maintenance signal and why the
  stdlib/existing toolchain is insufficient).

## 2. Research verdict — watch and borrow

DDE's stance toward Buzz is **watch-and-borrow**: track its evolution as the most visible
attempt to standardize human+agent collaboration over an open protocol, adopt its
transferable patterns, adopt none of its runtime. Borrowed patterns, each mapped to DDE's
existing surfaces:

| Buzz pattern | Maps to in DDE |
|---|---|
| ACP-class harness abstraction (one uniform client contract for heterogeneous agents) | The existing `WorkerAdapter` normative contract (Ch.8.1) — any future worker-adapter mission evaluates ACP's interface shape as a donor before inventing a new seam |
| Signed agent identities bound to permissions | Principal model + worker admission (Ch.14.2/14.4): signed worker credentials bound to environment identity are already law; Buzz confirms the shape |
| Hash-chain audit logs | `audit_events` hash-chaining (`prev_hash`, `entry_hash`, Ch.3.7) — independently validates DDE's tamper-evident ledger design |
| Mention-batching (batching agent-addressed requests to protect human attention) | Attention budget + batch approval (Ch.13.1/13.4): batching is already how DDE treats approval throughput |

## 3. Boardroom analysis verdict — a deciding council violates DDE law

The research also evaluated the "boardroom" pattern Buzz-adjacent discourse proposes:
a panel of agents that deliberates and **decides scope** for other agents. Verdict:
**rejected as a decision-making body.** It violates DDE law on every axis it touches:

- **Ch.2.2 rank discipline:** agent output is rank 10 ("freely produced, never
  authoritative"). An agent panel whose consensus sets scope converts rank-10 material
  into rank-7 authority by conversation, which the rank table forbids regardless of how
  many models agreed.
- **Ch.13 approvals:** scope decisions are governance acts owned by human authority
  through the approvals surface (`scope_widening`, `architecture_change`,
  `budget_increase`...). Delegating them to an intra-agent forum bypasses the one
  mechanism the blueprint trusts.
- **No agent-to-agent conversation for core state transitions:** the blueprint refuses
  "any agent-to-agent message bus" for core state; a deliberating council is that
  pattern with extra steps.

## 4. Adopted in principle — bounded ADVISORY COUNCIL (shadow mode first)

What IS adopted, in principle only, is the defanged form: harnesses may produce
**structured position papers** as input *to* human decisions — advice, never verdicts.

1. **Rank-9 position papers with citations.** Each participating harness emits a
   structured artifact (position + cited evidence refs) that enters context exactly like
   donor material: ingested, never promoted automatically (Ch.2.2 rank 9), evictable
   before rank ≤8 content (Ch.5.7), conflicts between papers not adjudicated but recorded
   as provenance-tagged evidence (Ch.5.6).
2. **Deterministic aggregation.** Combining papers (agreement/disagreement clustering,
   residual-question extraction) is a deterministic function over the artifacts — no
   model judge, no negotiation loop, no side-channel consensus.
3. **≤2 rounds budget cap.** At most two paper rounds per decision point; the cap lives
   in the mission's overhead budget (Ch.16.4). A question still unresolved after two
   rounds becomes a human decision task, not a third round.
4. **Output feeds the existing human approve/decide surface.** The aggregated digest
   attaches to an `Approval`/decision task as supporting evidence. Nothing in the council
   path can transition state; only the existing human act can (Ch.13.3 rule 5: a made
   decision becomes an EDR).
5. **Shadow-mode start.** Runs first as an experiment on **replan decisions**
   (`RecoveryService.replan` triggers): papers and digests are produced and stored, but
   nothing consumes them beyond human review. Expansion beyond replan shadow mode
   requires its own charter + EDR.

**Cautionary tale (recorded verbatim in spirit):** Buzz's own history shows the failure
mode this design guards against — shipping agent autonomy ahead of wired approval paths.
Agents acting into shared spaces faster than humans can gate them is precisely what
Ch.13.2's "bounded standing authority", Ch.12.3's acknowledge-gated stops, and the
mission-chapter-gate rule ("CI green ≠ done") exist to prevent. Any DDE adoption that
gives agents conversational authority before the approval wiring exists would repeat that
mistake with higher stakes.

## 5. Explicitly not adopted

| Item | Reason |
|---|---|
| Buzz/Nostr runtime as dependency or relay | Prototype-maturity product; drags a protocol stack into `adapters/**`; DDE has no human-chat surface for core state (Ch.15 Gateway is the command surface) |
| Agent-deciding boardroom/council | Violates Ch.2.2 ranks, Ch.13 approval ownership, and the no-agent-to-agent-conversation law (§3 above) |
| Continuous multi-round deliberation loops | Attention-economics violation (Ch.13.4); capped at 2 rounds when the council runs at all |
