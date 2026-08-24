# Orca-Router Research Integration — design priors for DDE-057/058/059

**Date:** 2026-08-24. **Nature:** docs-only integration of completed web research into
planning; no engine code changes, no Project Truth rows, no new dependency. The four
adopted patterns below are design inputs **and** acceptance-criteria seeds for the
routing-learning charters; recorded in `docs/planning/gap-closure-record.md §6.7`.

**Orientation anchors:** `AGENTS.md` (Ch.9.6 dependency admission; patterns-not-packages);
`docs/blueprint/REV_2_0.md` Ch.6 (gate pipeline; §6.5 day-one telemetry; §6.7
exploration/propensity; §6.8 learning eligibility; §6.9 staged activation), §5.11
failure attribution; `engine/routing/**`, `engine.telemetry`,
`engine.contracts.routing_decision_outcome`.

---

## 1. Disambiguation — which "Orca"

Two real referents surfaced; they live at different layers and must not be conflated:

1. **OrcaRouter** (Continuum AI) — a production LLM router/AI gateway
   ([product](https://www.orcarouter.ai/)) with an MIT-licensed self-hosted edition
   ([OrcaRouter-Lite](https://github.com/Continuum-AI-Corp/OrcaRouter-Lite)) and a
   vendor-authored technical report ([arXiv 2605.30736](https://arxiv.org/html/2605.30736v1),
   **non-peer-reviewed**). Decides *which model serves a request* — the same decision
   layer as DDE's Chapter 6 router. This is the relevant candidate.
2. **Orca, OSDI'22** ([USENIX](https://www.usenix.org/conference/osdi22/presentation/yu))
   — iteration-level scheduling inside a GPU serving system (origin of continuous
   batching). It schedules *iterations within one server*, never selects among models;
   it has no official open-source release (proprietary inside FriendliAI's engine) and
   **does not map onto model-selection routing**. Successor work
   ([Sarathi-Serve, OSDI'24](https://www.usenix.org/system/files/osdi24-agrawal.pdf))
   matters here only as a conceptual note (§3a).

Confidence: high (~80%) that "Orca routing intelligence" in a model-routing sense means
OrcaRouter; the OSDI'22 system is covered for completeness only.

## 2. Adopted patterns — design priors with acceptance-criteria language

Each pattern states what it is, where it lands in DDE, and how a charter should phrase
its acceptance criterion.

### Pattern 1 — Full-information offline warmup precedes any online update

OrcaRouter evaluates every candidate arm on a curated prompt set, builds a full reward
matrix, and initializes the policy closed-form before any partial-information bandit
update ([paper §2.5](https://arxiv.org/html/2605.30736v1)). Their honest negative
result is the load-bearing finding: **cold-start LinUCB scored 69.81 vs 70.31 for an
always-cheapest constant policy** — a cold-start learner loses to a constant baseline —
while the full-information warmup fit reached 74.05 on the same pool (Table 1).

- **Maps to:** DDE-057 (ExperienceRecord eligibility filtering, Ch.6.8) produces the
  training population; DDE-058 (Ch.6.9 `OBSERVE → TRAIN → OFFLINE EVALUATE → …`)
  consumes it. DDE's §6.5 day-one telemetry already records every candidate with its
  elimination gate — exactly the counterfactual substrate a full-information fit needs.
  This validates the record-everything posture as the prerequisite for learning.
- **Acceptance-criteria language for DDE-058's charter:** the learner's offline phase
  MUST be a full-information fit over recorded candidate sets (post-Ch.6.8 eligibility
  filtering); any partial-information/online-update path is unreachable until that fit
  exists and is evaluated; a cold-start-trained policy is rejected at OFFLINE EVALUATE.
- **Baseline definition:** comparisons include the best constant policy on the pool,
  not only the incumbent deterministic policy table.

### Pattern 2 — Frozen-exploitation-first rollout; continued-update behind a switch

OrcaRouter ships warmed-up policies either **frozen** (θ fixed, exploration disabled —
deterministic argmax with well-defined propensities) or **continued-update** (bandit
feedback mutates the selected arm after each request), treating frozen as the safe
default ([paper §2.5](https://arxiv.org/html/2605.30736v1)).

- **Maps to:** DDE-058's canary/rollback story and Ch.6.9's mode progression. A frozen
  learned policy is still a deterministic selector: propensities stay well-defined,
  Stage-1 determinism guarantees survive the transition, and rollback semantics are
  trivial (reload the previous certified artifact).
- **Acceptance-criteria language:** DDE-058's first promotable mode is frozen
  exploitation; continued-update requires an explicit configuration switch plus its own
  canary evidence, and never runs during a canary window of a policy that has never
  been frozen-evaluated.

### Pattern 3 — Margin-based tie-breaker for pick stability

When the top two arms score within ε=0.02, prefer the arm with the higher historical
mean reward; their paraphrase pick-flip rate fell 16.7% → 2.4% at ≈0.86 arena-point
cost ([paper §3.2](https://arxiv.org/html/2605.30736v1)). Cheap, deterministic, and
measurable with telemetry DDE already lands.

- **Maps to:** DDE-058 shadow evaluation. Flip rate under replayed/paraphrased inputs
  becomes an attributable signal alongside §5.11 failure attribution; the tie-breaker
  is a benchmarkable stability lever, adopt-or-drop on measured flip rates.
- **Acceptance-criteria language:** DDE-058's shadow suite measures pick-flip rate on a
  paraphrase/replay set; the margin tie-breaker is benchmarked against it, and a
  stability threshold may be set from that data rather than assumed.

### Pattern 4 — Standing assertion: the learner must beat the constant policy

Directly informed by Pattern 1's negative result: "is the learner beating the best
constant policy?" is a standing shadow-evaluation assertion, not a one-off experiment.

- **Maps to:** DDE-058's promotion gate. Ch.6.9 already mandates "Holdout uplift vs
  deterministic baseline — no material regression"; this adds the stricter floor that
  the learned policy must also beat the best *constant* policy on the same evaluation
  window (constant policies are embarrassingly strong cost-wise, as their own numbers
  show).
- **Acceptance-criteria language:** every shadow/canary evaluation reports learner vs
  incumbent-policy-table vs best-constant-policy on the identical window; failing the
  constant-policy comparison fails the promotion gate regardless of other metrics.

## 3. Conceptual notes — context, not adoption commitments

**(a) SLO-derived budgets for the capacity gate.** Sarathi-Serve derives its per-batch
token budget τ from the latency SLO it must protect, then admits work only within that
budget ([OSDI'24 paper](https://www.usenix.org/system/files/osdi24-agrawal.pdf)). The
transferable framing for DDE's gate 5: compute per-workload-class capacity budgets
*from the SLO the class must protect*, rather than from static configuration guesses.
Scheduling machinery itself (chunked prefills, stall-free batching) stays
serving-layer and out of scope.

**(b) Observe→shadow→enforce is the converged rollout lifecycle.** Independent
corroboration for the lifecycle DDE-058/059 already plan. Note the boundary honestly:
OrcaRouter documents observe/shadow/enforce modes for its guardrail/firewall policies
([enforcement-modes docs](https://docs.orcarouter.ai/security/concepts/enforcement-modes.md))
and shadow/canary for Routing-DSL changes — **not** shadow evaluation of the learned
policy itself. Do not credit them for learned-policy shadowing they have not
documented; DDE's Ch.6.9 shadow machinery remains ahead of theirs on that axis.

## 4. Source-quality caveats

- The technical report is **vendor-authored and non-peer-reviewed**
  ([arXiv 2605.30736](https://arxiv.org/html/2605.30736v1)); leaderboard claims (#2
  RouterArena, 72.08 arena score) are self-reported.
- Unresolved whether the LinUCB adaptive strategy ships in the MIT edition at all:
  the [repo README](https://github.com/Continuum-AI-Corp/OrcaRouter-Lite) route table
  lists only heuristic strategies (`balanced`/`cheapest`/`fastest`/`quality`), while
  secondary sources claim LinUCB is configurable. Treat the learner as possibly
  hosted-only until the code is inspected directly.
- Repo youth: created 2026-05-03, ≈3 human contributors (+ AI-assisted commits), zero
  published releases as of 2026-08-24 — **fails the Ch.9.6 maintenance-signal bar for
  dependency admission today**, which is why everything above is adopted as patterns
  and benchmark methodology, never as packages.

## 5. Explicitly not adopted (with reasons)

| Item | Reason |
|---|---|
| LinUCB/bandit code as a dependency | Fails Ch.9.6 now (age, bus factor, zero releases); LinUCB is textbook-implementable when DDE-058 needs it |
| Fallback chains à la OrcaRouter | DDE's deterministic gates + Ch.6.5 health-based eviction/fallback amendment already subsume the need with hash-pinned policy tables |
| `gated_adaptive` difficulty tiers between weak/strong pools | Watchlist only; revisit if DDE-058 evidence shows workload-class granularity is insufficient |
| Anything from OSDI'22/Sarathi scheduling internals | Serving-layer machinery; no mapping onto a control-plane model-selection router |
