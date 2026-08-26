# DDE-056 chapter gate — client parity fixture (CLI/web/Android)

**Mission:** §18.3 S6 / `DDE-056` — client parity fixture across
CLI/web/Android on the golden mission. **Charter:** identical Gateway
outcomes for the same golden-mission control sequence via CLI,
`interfaces/dashboard`, and `interfaces/android` (Ch.15.1/15.2
acceptance semantics). Messaging (DDE-055) may be included as an
optional fourth client if the fixture stays thin. **Not** full WS/SSE
sequence replay (EDR-0027) or production Slack/Telegram SDKs (EDR-0031).

**Status:** OPEN (kicked off after DDE-055 PASS-WITH-EDR @ `41c52e4`).

## In charter

| In | Out |
|---|---|
| Shared golden-mission control sequence fixture | Inventing a second Gateway authority path |
| Assert CLI / web / Android (and optionally messaging) see the same acceptance identities / mission status | Full multi-client UX polish |
| Document allowlist parity already proven in DDE-052/053 | Closing EDR-0027 stream/sequence replay |

## Rule disposition (target)

| Rule | Production call site (to name at land) |
|---|---|
| Ch.15.2 acceptance ≠ completion | Each client surface treats 202 as acceptance; fixture re-reads by id |
| Identical outcomes | One golden sequence; CLI + dashboard JS path + Android allowlist/transport agree on command types + final mission status |
| Ch.15.1 reconnect subset | Reuse DDE-053 resume+by-id pattern where the fixture reconnects — not full sequence replay |

## Deferred (proposed EDRs)

| ID | Item |
|---|---|
| **EDR-0027** | Sequence/WS/SSE gap replay (Core) |
| **EDR-0028** | Was proposed for parity itself — close or supersede when this gate lands |

## Verdict

**OPEN** — do not declare PASS until the golden parity fixture is green
and call sites above are named. Auto-proceed past S6 only after Stage
exit criteria are independently reviewed.
