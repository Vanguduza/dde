# DDE-048 chapter gate — Android/APK analysis capabilities

**Mission:** §18.3 S5 / `DDE-048` — Android/APK analysis capabilities.
**Charter:** blueprint `REV_2_0.md` §18.3 S5 line; Ch.9.8 portfolio
("mobile/Android tooling"); Appendix A implementation candidates
(JADX/Apktool/ADB/MobSF are *candidates behind contracts*, never core).

**CI:** ruff check/format · mypy · 1007 passed / 2 skipped
(unit+contract+recovery, Postgres up) · `generate_contracts --check` ·
`generate_design_tokens --check` · design lints (within baseline budget) ·
dde-studio + desktop typecheck/tests — all green.

## What landed

- `capability.android_analysis` seeded descriptor: PURE_READ, T1,
  egress none (`engine/capabilities/seed.py`).
- `adapters/android`: in-process static APK analyzer over stdlib
  `zipfile` — manifest permission strings from the AXML pool, native ABIs,
  v1-signature presence, DEX presence, and the Chapter 9.7 secret classes
  over asset entries. No vendor binary is invoked (Ch.9.6 discipline,
  same as DDE-045's no-SAST-binary rule).
- Fail-closed dynamic modes: `dynamic`/`adb`/`instrumentation` refuse with
  `POLICY_DENIED` — no device attack surface exists in this mission.
- `AndroidWorkerAdapter` (T1): lease-gated `start()` against
  `capability.android_analysis`, smoke-tier clean, synchronous handle.
- Verification surface: `android_scan` oracle kind (schema enum +
  regenerated contract), executed through `run_check(..., android=...)`
  and the injected capability on `VerificationRunner`.
- Worker plumbing: `WorkerAction.android_mode`,
  `_required_capability_ids` maps it to exactly the android capability,
  journal scope and request hash include the mode, and PURE_READ scans
  skip `assert_clear_to_mutate` identically to security scans.

## Rule disposition (Ch.9.3 / 9.6 / 7.2 / 13.8)

1. **Side-effect class declared** — PURE_READ at the descriptor; the only
   writes are DDE-internal WorkerRun/evidence rows.
2. **No vendor SDK in engine/** — analyzer lives in `adapters/android`;
   `engine.capabilities.android` is a stdlib Protocol; verification
   imports only the protocol.
3. **Lease before side effect** — `require_active` inside `start()`;
   denial is a normal control outcome.
4. **Donor governance holds** — an APK ingested as donor material keeps
   rank 9 + taint; analysis here reads workspace files, never executes
   them; injection screening from DDE-047 applies upstream at ingest.
5. **Containment** — static-only means no network, no device, no
   subprocess; the T2 boundary is not needed for this surface.

## Deferred (with proposed EDR)

- **Dynamic analysis** (ADB/instrumentation/on-device execution):
  requires a device/isolation profile — covered by proposed **EDR-0017**
  (donor/analysis isolation profile, filed on the DDE-047 gate record),
  which must land before any executable-analysis mission enables it.
- **Vendor-grade depth** (JADX decompile, MobSF report): the in-process
  analyzer is honest about scope (permissions/assets/signing/ABIs);
  deeper static passes can join as additional pure-read evaluators
  without contract change when a real need appears.

## Verdict

**PASS-WITH-EDR** — in-charter MUSTs enforced at named production call
sites; dynamic analysis deferred under EDR-0017 rather than silently
absent. Auto-proceed to DDE-049 authorized under the standing order.
