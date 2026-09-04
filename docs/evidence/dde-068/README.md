# DDE-068 — end-to-end visual verification evidence

Produced by `scripts/dde068_evidence_run.py` against real candidates, with
**no stand-ins anywhere in the chain**: real Playwright render, real
screenshot, real deterministic analysis, real multimodal critique through
`capability.visual_critique`, real schema-validated verdict, real
deterministic policy, real promotion decision.

    real HTML candidate
      -> Playwright render + screenshot      (capability.browser)
      -> silhouette fingerprint + density    (deterministic, model-free)
      -> multimodal critique                 (capability.visual_critique)
      -> schema-validated structured verdict
      -> deterministic policy (playbook §8: any dimension <4 blocks)
      -> bounded-revision decision (<=3 cycles, then escalate)
      -> promotion decision

Reproduce with (spends real model quota — see EDR-0017's resource note):

    uv run python -m scripts.dde068_evidence_run
    uv run python -m scripts.dde068_evidence_run --only good-candidate --cycle 1

## Results

| Candidate | Cycle | Verdict | Lowest dimension | Promotion |
|---|---|---|---|---|
| `poor-candidate` | 0 | BLOCK (0.92) | `token_discipline`/`data_presentation`/`copy_voice`/`states_completeness`/`believable_density` = 1 | **DENIED** |
| `good-candidate` | 0 | BLOCK (0.72) | `accessibility` = 3 | **DENIED** |
| `good-candidate` | 1 | PASS (0.72) | all dimensions >= 4 | **ELIGIBLE** |

Records: `evidence-run.json` (cycle 0, both candidates),
`evidence-run-good-candidate-cycle1.json` (cycle 1).
Screenshots: `poor-candidate.png`, `good-candidate.png`.

## What each result proves

**Rejection path.** The poor candidate carries the playbook's own named
generic tells (centered hero + three identical cards, emoji-as-icons,
pill-spam, lorem/"Item 1" filler, marketing copy, raw hex literals). The
critic scored `believable_density = 1`, `token_discipline = 1`,
`data_presentation = 1`, `copy_voice = 1`, `states_completeness = 1` and
blocked it. A visually poor candidate cannot enter the product on code
validity alone.

**Repair path — a real, unscripted loop.** The good candidate was *not*
written to fail, and the deterministic layer passed it (silhouette
similarity 0.47, no near-match). The live critic nonetheless blocked it on
`accessibility = 3`, correctly identifying that secondary label text was
low-contrast grey on an off-white ground, below the AA 4.5:1 bar. Cycle 1
applied that critique's own `repair_instructions` — darkened secondary text
to a dedicated `--dde-text-secondary-aa` token, rebalanced vertical rhythm,
added loading-skeleton and disabled-control states, moved status colours
onto semantic tokens — and the re-rendered screen passed with
`accessibility` 3 -> 4 and every dimension >= 4. The bounded-revision policy
moved `REVISE (cycle 1 of 3)` -> `PROMOTE` accordingly.

**The two density layers cooperating.** The critic's non-blocking
`hierarchy_and_rhythm` finding quoted the deterministic density evidence
back verbatim ("top_half_ratio 0.67 vs bottom_half_ratio 0.40"). The
deterministic layer measured; the rubric layer judged. Neither impersonated
the other, which is exactly the separation EDR-0017 requires.

## Measured cost

Real, reported by the runtime — never estimated:

| Run | Cost (USD) |
|---|---|
| good-candidate cycle 0 | 0.1949 |
| poor-candidate cycle 0 | 0.0779 |
| good-candidate cycle 1 | 0.0903 |
| **total** | **0.3631** |

Model: `claude-sonnet-5`. Note that a nested critique invocation draws on
the operator's own rate-limited pool, which is why the bounded caps in
EDR-0017 guardrail 7 are enforced rather than advisory.

## Environment note

The sandbox ships Playwright browser build 1194 while the pinned
`playwright` package expects 1234. The evidence run used a shim browser root
(symlinks mapping the expected 1234 layout onto the available 1194 build)
via `PLAYWRIGHT_BROWSERS_PATH`. That is an environment workaround only — no
production code was changed to accommodate it.
