# DDE-054 chapter gate — Termux edge node (device client + offline queue)

**Mission:** §18.3 S6 / `DDE-054` — Termux edge node. **Charter:**
Ch.14.2 device principal (`device.read` / `device.command`); Ch.13.7
`android.offline_queue.enabled`; Ch.15.1/15.2 Gateway session +
idempotent command flush; Ch.3.6 `interfaces/termux` (additive to the
listed layout). **Not** human Mission Control (DDE-053), messaging
adapters (DDE-055), or multi-client golden parity (DDE-056).

**Status:** IN PROGRESS (kicked off after DDE-053 PASS-WITH-EDR).

## In charter

| In | Out |
|---|---|
| `interfaces/termux/` POSIX/Termux Python edge client | Compose human operator (DDE-053) |
| `client_type=device` + required `device_id` | `mission.*` scopes on a device session |
| Durable offline command queue when flag enabled | Full WS/SSE sequence replay (EDR-0027) |
| Flush on reconnect preserving `idempotency_key` | Standing device credentials that bypass Gateway |
| Minimal `device.heartbeat` (or equivalent) under `device.command` | New authority plane / Core mission mutations via device |

## Rule disposition (target)

| Rule | Production call site (to name at land) |
|---|---|
| Ch.14.2 device baseline only | Gateway session open rejects mission scopes for `client_type=device` |
| Ch.13.7 offline queue flag | Queue armed only when `android.offline_queue.enabled` (or DDE env twin) is true |
| Ch.15.2 acceptance ≠ completion + idempotency | Offline flush replays same `command_id`/`idempotency_key`; never invents a second mutation |
| Ch.15.1 no stale local authority | After resume, discard unconfirmed local projection; re-sync by Gateway reads the device is allowed |

## Deferred (proposed EDRs)

| ID | Item |
|---|---|
| **EDR-0027** | Sequence/WS/SSE gap replay (Core) |
| **EDR-0030** | Rich device command surface beyond heartbeat/status (if product needs it) |

## Verdict

**OPEN** — do not declare PASS until call sites above are named and
proofs are green. Auto-proceed to DDE-055 only after this gate closes.
