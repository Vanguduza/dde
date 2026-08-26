# DDE Termux edge node (DDE-054)

Gateway-only **device** edge client for Termux / POSIX hosts. Twin of
the DDE-053 Android *human* operator, but with Ch.14.2 device scopes
and a durable offline command queue (Ch.13.7
`android.offline_queue.enabled`).

## Scope

| In | Out |
|---|---|
| `client_type=device` + `device_id` | `mission.read` / `mission.control` |
| Offline queue + idempotent flush | Compose UI (DDE-053) |
| `device.heartbeat` (minimal command) | Messaging transports (DDE-055) |

## Offline queue contract

1. When the flag is enabled and the Gateway is unreachable, enqueue the
   command envelope (including `command_id` and `idempotency_key`).
2. On reconnect, resume the session, then flush oldest-first.
3. A repeated flush of the same key must not create a second mutation
   (Gateway idempotency ledger is authoritative).
4. Never treat `202 Accepted` as completion.

## Layout

```text
interfaces/termux/
  __init__.py
  offline_queue.py   # durable queue + flush
  device_client.py   # Gateway session + heartbeat
```
