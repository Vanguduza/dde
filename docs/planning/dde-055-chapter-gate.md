# DDE-055 chapter gate — messaging adapters (transport only)

**Mission:** §18.3 S6 / `DDE-055` — messaging adapters (transport only,
no authority). **Charter:** Ch.15.1 Gateway is the only authority path;
Ch.14.2 messaging never requests `approval.decide`; Ch.3.6 additive
`interfaces/messaging` transport surface. **Not** Termux/device
(DDE-054), multi-client golden parity (DDE-056), or a new Core authority
plane.

**CI / local proofs (pending `just check` close):**

- `tests/unit/test_messaging_transport.py`: **5 passed**
- `tests/unit/test_messaging_gateway.py`: **3 passed** (service
  allowlist open; decide rejected; mission.cancel via messaging scopes;
  `approval.batch_decide` forbidden)

## What landed (scaffold)

- `interfaces/messaging/`: `MESSAGING_SCOPES` allowlist, `InMemoryChannel`,
  `MessagingBridge` (status / pause / resume / cancel dialect; refuses
  approve/decide/capture-secret verbs).
- Never imports `engine.*`.

## Rule disposition

| Rule | Production call site |
|---|---|
| Ch.15.1 transport only | `interfaces/messaging/**` — no engine imports (unit proof) |
| Ch.14.2 no decide authority | `assert_messaging_scopes` + `MessagingBridge.connect` scopes; Gateway session rejects `approval.decide` for service; `approval.batch_decide` FORBIDDEN without scope |
| Ch.15.2 idempotency on mutations | Bridge control envelopes use `msg-{verb}-{message_id}` keys |
| Vendor Slack/Telegram SDKs | Deferred **EDR-0031** |
| Multi-client golden parity | Deferred **EDR-0028** (DDE-056) |

## Deferred (proposed EDRs)

| ID | Item |
|---|---|
| **EDR-0031** | Production Slack/Telegram/webhook vendor adapters (SDK + brokered credentials) |
| **EDR-0028** | CLI/web/Android/messaging golden parity (DDE-056) |

## Verdict

**OPEN** — awaiting green `just check` before PASS-WITH-EDR land.
Auto-proceed to DDE-056 only after this gate closes.
