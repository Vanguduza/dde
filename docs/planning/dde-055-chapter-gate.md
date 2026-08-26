# DDE-055 chapter gate — messaging adapters (transport only)

**Mission:** §18.3 S6 / `DDE-055` — messaging adapters (transport only,
no authority). **Charter:** Ch.15.1 Gateway is the only authority path;
Ch.14.2 messaging never requests `approval.decide`; Ch.3.6 additive
`interfaces/messaging` transport surface. **Not** Termux/device
(DDE-054), multi-client golden parity (DDE-056), or a new Core authority
plane.

**CI / local proofs (2026-08-26):**

- `just check` green — ruff / mypy (352 files) / **1074 passed, 2
  skipped** (unit+contract+recovery) / `generate_contracts --check` /
  design-lints baseline / dde-studio `tsc --noEmit`
- `tests/unit/test_messaging_transport.py`: **5 passed**
- `tests/unit/test_messaging_gateway.py`: **3 passed**

## What landed

- `interfaces/messaging/`: allowlisted scopes, `InMemoryChannel` stub,
  `MessagingBridge` (status / pause / resume / cancel dialect; refuses
  approve/decide/capture-secret).
- Never imports `engine.*`.
- Live Gateway: service session opens with `MESSAGING_SCOPES`;
  `approval.decide` rejected at session open; `mission.cancel` accepted
  under messaging scopes; `approval.batch_decide` FORBIDDEN.

## Rule disposition

| Rule | Production call site |
|---|---|
| Ch.15.1 transport only | `interfaces/messaging/**` — no engine imports (unit proof) |
| Ch.14.2 no decide authority | `assert_messaging_scopes` + `MessagingBridge.connect`; Gateway `open_session` rejects decide for service; `GatewayCommandService.accept` FORBIDDEN on `approval.batch_decide` without scope |
| Ch.15.2 idempotency on mutations | Bridge control envelopes use durable `msg-{verb}-{message_id}` keys |
| Vendor Slack/Telegram SDKs | Deferred **EDR-0031** |
| Multi-client golden parity | Deferred **EDR-0028** (DDE-056) |

## Deferred (proposed EDRs)

| ID | Item |
|---|---|
| **EDR-0031** | Production Slack/Telegram/webhook vendor adapters (SDK + brokered credentials) |
| **EDR-0028** | CLI/web/Android/messaging golden parity (DDE-056) |

## Verdict

**PASS-WITH-EDR** — messaging transport surface is Gateway-only and
cannot hold decide authority; production vendor SDKs and multi-client
parity deferred. Auto-proceed to DDE-056 authorized under the standing
order.

**Landed:** 2026-08-26 on `dde-055-messaging-adapters` (FF to `main`).
