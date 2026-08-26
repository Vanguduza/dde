# DDE-054 chapter gate — Termux edge node (device client + offline queue)

**Mission:** §18.3 S6 / `DDE-054` — Termux edge node. **Charter:**
Ch.14.2 device principal (`device.read` / `device.command`); Ch.13.7
`android.offline_queue.enabled`; Ch.15.1/15.2 Gateway session +
idempotent command flush; Ch.3.6 `interfaces/termux` (additive to the
listed layout). **Not** human Mission Control (DDE-053), messaging
adapters (DDE-055), or multi-client golden parity (DDE-056).

**CI / local proofs (2026-08-26):**

- `just check` green — ruff / mypy (352 files) / **1066 passed, 2
  skipped** (unit+contract+recovery) / `generate_contracts --check` /
  design-lints baseline / dde-studio `tsc --noEmit`
- `tests/unit/test_termux_edge_offline_queue.py`: **6 passed**
- `tests/unit/test_termux_device_gateway.py`: **6 passed** (live ASGI
  device session + heartbeat + idempotency + mission-scope refusal)

## What landed

- `interfaces/termux/`: `DeviceClient` + durable `OfflineQueue` (JSONL),
  `reconnect_and_flush` (resume then flush; never invents keys).
- Gateway: `device.heartbeat` in `COMMAND_SCOPES` → `device.command`,
  `COMMAND_TARGET_TYPE` → `device`; dispatcher acceptance-only (no
  Project Truth / mission mutation); `_resolve_project` binds
  `parameters.project_id` + session `device_id` match.
- Session open: `client_type=device` **requires** `device_id`; mission
  scopes rejected by baseline subset (Ch.14.2).
- Ch.13.7 flag: `RuntimeFlags.android_offline_queue_enabled` (default
  false) + client env twin `DDE_ANDROID_OFFLINE_QUEUE_ENABLED`.

## Rule disposition

| Rule | Production call site |
|---|---|
| Ch.14.2 device baseline only | `GatewaySessionService.open_session` — `BASELINE_SCOPES["device"]`; rejects mission scopes + missing `device_id` |
| Ch.13.7 offline queue flag | `OfflineQueue.enqueue` / `offline_queue_enabled()` gated on env twin; flag named on `RuntimeFlags.android_offline_queue_enabled` |
| Ch.15.2 acceptance ≠ completion + idempotency | `GatewayCommandService.accept` + `CommandLedger` for `device.heartbeat`; Termux `flush_offline` replays same `command_id`/`idempotency_key` |
| Ch.15.1 no stale local authority | `DeviceClient.resume` / `reconnect_and_flush` — resume before flush; fresh snapshot is caller's re-sync signal |
| Ch.15.1 sequence/WS/SSE full replay | Deferred **EDR-0027** (Core gap) |
| Rich device command surface | Deferred **EDR-0030** |

## Deferred (proposed EDRs)

| ID | Item |
|---|---|
| **EDR-0027** | Sequence/WS/SSE gap replay (Core) — shared with DDE-053 |
| **EDR-0030** | Rich device command surface beyond heartbeat/status |

## Verdict

**PASS-WITH-EDR** — Termux device edge client + offline queue + live
Gateway `device.heartbeat` under `device.command`; full stream/sequence
replay and richer device commands deferred. Auto-proceed to DDE-055
authorized under the standing order.

**Landed:** 2026-08-26 on `dde-054-termux-edge-node-wt` (FF to `main`).
