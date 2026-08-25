# DDE-047 chapter gate — donor licence/reuse classifier + taint propagation

**Mission:** §18.3 S5 / `DDE-047` — donor licence/reuse classifier +
taint propagation. **Charter:** blueprint `REV_2_0.md` §18.3 S5 line,
anchored on Chapter 13.8.

**CI:** ruff check/format · mypy · 993 passed / 2 skipped
(unit+contract+recovery, Postgres up) · `generate_contracts --check` ·
`generate_design_tokens --check` · design lints (within baseline budget) ·
dde-studio + desktop typecheck/tests — all green on commit `063d17c`.

## Rule-by-rule disposition (Chapter 13.8)

1. **Machine-readable classification BEFORE implementation use**
   (six-value scale) — wired at the ingest mutation site
   `DonorLabService.submit_uri` (`engine/donor/service.py`: classify runs
   before artifact/Feature DNA persistence; nothing downstream can read an
   unclassified artifact because none is ever written).
2. **UNKNOWN/conflicting defaults to SOURCE_REFERENCE_ONLY/REJECTED;
   never silently OPEN_REUSE** — `classify_donor_content`
   (`engine/donor/classify.py`) applies the configured unknown policy,
   refuses requested OPEN_REUSE without evidence or a signed decision
   (`POLICY_DENIED`), and refuses OPEN_REUSE inferred from
   conflicting/policy-default evidence.
3. **Taint persists into Feature DNA, tasks, diffs and evidence** —
   Feature DNA `taint_tags` at ingest; `donor_taints` rows written only by
   `DonorTaintService.link` (idempotent on subject×artifact);
   task→diff_gate_report propagation at
   `engine/integration/gate_service.py` (`DiffGateService.evaluate`);
   task→evidence propagation at `engine/verification/runner.py`;
   merge-queue gate `scan_donor_taint` fed by task taints plus
   content-hash influence matching (`influences_for_blobs`) over proposed
   blobs. Answering "which donor evidence influenced this artifact" is a
   query over these rows (`list_for_subject`).
4. **Signed reuse decision before donor-derived implementation enters an
   autonomous production task** —
   `assert_reuse_approved_for_production_task` is called inside both
   WorkerRun mutation paths of `engine/workers/service.py` (execution and
   attempt issue), blocking implementation/integration/repair classes on
   tainted tasks without an APPROVED `donor_reuse` approval scoped to
   (mission, task, artifact); REJECTED/SOURCE_REFERENCE_ONLY/UNKNOWN
   taints are blocked outright.
5. **Prompt injection inside donor content cannot elevate authority** —
   `screen_donor_text` findings are recorded at ingest and carried on the
   artifact/Feature DNA; no code path derives capability or authority from
   donor content (Ch.14.5 invariant 6 preserved by construction).
6. **Recovery/migration discipline** — `0019_donor_taint` verified
   forward-on-empty and downgrade-reversible through the READY-gate
   verifier (`tests/recovery/test_product_env_migration_verification_recovery.py`,
   head=0019).

## Deferred (with proposed EDR)

- **Isolated environments for donor analysis** (Ch.13.8): today DDE never
  executes donor material — classification/screening are in-process text
  passes, so there is no donor-code execution to isolate. The requirement
  becomes binding the moment donor code is analyzed/executed (DDE-048 APK
  analysis, DDE-066 discovery fetches). Proposed **EDR-0017**: donor
  analysis isolation profile (environment class, egress allow-list,
  artifact quarantine) required before either mission enables code-level
  analysis.
- **Model-provider data handling hard gate** (donor-classified material to
  ineligible providers, routing level 0): owned by the routing/policy
  chain (S4 surface), not the 047 charter. Proposed **EDR-0018**: extend
  project routing policy with donor-confidentiality eligibility and wire
  the level-0 refusal in the routing gate.

## Verdict

**PASS-WITH-EDR** — all in-charter MUSTs enforced at named production
mutation sites; two adjacent Ch.13.8 obligations deferred with proposed
EDRs above. Auto-proceed to DDE-048 authorized under the standing order.
