# DDE-056 chapter gate — client parity fixture (CLI/web/Android)

**Mission:** §18.3 S6 / `DDE-056` — client parity fixture across
CLI/web/Android on the golden mission. **Charter:** identical Gateway
outcomes for the same golden-mission control sequence via CLI,
`interfaces/dashboard`, and `interfaces/android` (Ch.15.1/15.2
acceptance semantics). Messaging (DDE-055) may be included as an
optional fourth client if the fixture stays thin. **Not** full WS/SSE
sequence replay (EDR-0027) or production Slack/Telegram SDKs (EDR-0031).

**CI / local proofs (2026-08-26):**

- `just check` green — ruff / mypy (352 files) / **1077 passed, 2
  skipped** (unit+contract+recovery) / `generate_contracts --check` /
  design-lints baseline / dde-studio `tsc --noEmit`
- `tests/unit/test_client_parity_fixture.py`: **3 passed**
  (allowlist sync; golden identical outcomes; reconnect without
  duplicate commands)

## What landed

- `interfaces/cli/gateway_client.py` — CLI Gateway `/v1` twin of
  dashboard `gateway.js` / Android `GatewayAllowlist` (six paths only).
- Golden fixture: one mission; CLI/web/Android sessions agree on
  authoritative mission + mission-control slices; activate → pause;
  all three observe `PAUSED`.
- Reconnect proof: session resume + by-id re-sync; same
  `command_id`/`idempotency_key` pause replay returns first acceptance
  without a second mutation (`lock_version` unchanged).
- Dashboard `app.js` + Android `OperatorViewModel` now send
  `lock_version` on control commands (production honesty for Ch.15.2).

## Rule disposition

| Rule | Production call site |
|---|---|
| Ch.15.2 acceptance ≠ completion | Fixture asserts HTTP 202 then re-GETs mission/control by id; dashboard/Android reload after accept |
| Identical outcomes (S6 exit) | `tests/unit/test_client_parity_fixture.py` — shared `ALLOWED_PATHS`; one golden mission; CLI/web/Android slices equal |
| Allowlist parity (no invented lists) | `interfaces/cli/gateway_client.ALLOWED_PATHS` ≡ dashboard `ALLOWED_PATHS` ≡ Android `GatewayAllowlist.ALLOWED_PATHS` |
| Ch.15.1 reconnect without duplicate commands | Resume + by-id (`ReconnectCoordinator` pattern); mutation replay via `GatewayCommandService.accept` / command ledger idempotency |
| Ch.15.1 sequence/WS/SSE full replay | Deferred **EDR-0027** (Core gap) |
| **EDR-0028** (parity itself) | **Closed** by this mission |

## Deferred (proposed EDRs)

| ID | Item |
|---|---|
| **EDR-0027** | Sequence/WS/SSE gap replay (Core) — unchanged |
| **EDR-0031** | Production Slack/Telegram SDKs — unchanged (DDE-055) |

## S6 exit criteria review

| Criterion | Status |
|---|---|
| Multi-tenant isolation suite green | Met (DDE-051) |
| CLI/web/Android identical authoritative outcomes on same golden mission | Met (this fixture) |
| Reconnect recovers without duplicate commands | Met for Core-supported subset (idempotency + by-id); full stream replay remains EDR-0027 |

**S6 client track:** complete after this land. Do **not** auto-start
Stage 7 (DDE-057+) — standing order stops after S6 client exit unless
the user authorizes S7.

## Verdict

**PASS-WITH-EDR** — golden CLI/web/Android Gateway parity fixture green;
EDR-0028 closed; full WS/SSE sequence replay remains EDR-0027. Stop
after land (S6 client exit closed).

**Landed:** 2026-08-26 on `dde-056-client-parity` (FF to `main`).
S6 client exit closed; do not auto-start S7.
