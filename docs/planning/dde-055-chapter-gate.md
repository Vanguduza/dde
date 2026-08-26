# DDE-055 chapter gate — messaging adapters (transport only)

**Mission:** §18.3 S6 / `DDE-055` — messaging adapters (transport only,
no authority). **Charter:** Ch.15.1 Gateway is the only authority path;
Ch.14.2 messaging never requests `approval.decide`; Ch.3.6 additive
`interfaces/messaging` transport surface. **Not** Termux/device
(DDE-054), multi-client golden parity (DDE-056), or a new Core authority
plane.

**Status:** OPEN (kicked off after DDE-054 PASS-WITH-EDR @ `39ac5a2`).

## In charter

| In | Out |
|---|---|
| Channel transports (stub + contract) under `interfaces/messaging/` | Standing `approval.decide` via chat |
| Map inbound text ↔ Gateway envelopes with idempotency keys | Writing Project Truth / Core tables |
| Allowlisted scopes: `mission.read` / `mission.control` (service or human) | Inventing mission mutations without Gateway |
| Explicit refusal of `approval.decide` / credential capture on this surface | Full Slack/Telegram production SDKs (vendor adapters may follow behind the same contract) |

## Rule disposition (target)

| Rule | Production call site (to name at land) |
|---|---|
| Ch.15.1 transport only | Messaging bridge posts only through Gateway transport Protocol — never imports `engine.*` |
| Ch.14.2 no decide authority | Allowlist excludes `approval.decide`; session open refuses decide scopes |
| Ch.15.2 idempotency on mutations | Control commands carry durable `command_id` + `idempotency_key` |
| Vendor SDK containment | Live Slack/Telegram SDKs deferred behind transport Protocol (EDR if product picks a vendor) |

## Deferred (proposed EDRs)

| ID | Item |
|---|---|
| **EDR-0031** | Production Slack/Telegram/webhook vendor adapters (SDK + credentials via broker) |
| **EDR-0028** | CLI/web/Android/messaging golden parity (DDE-056) |

## Verdict

**OPEN** — do not declare PASS until call sites above are named and
proofs are green. Auto-proceed to DDE-056 only after this gate closes.
