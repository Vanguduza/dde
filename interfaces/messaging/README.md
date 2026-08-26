# DDE messaging transports (DDE-055)

Gateway-only **messaging** edge: channel adapters ferry operator text
to/from the Gateway. They never own Project Truth, never hold
`approval.decide`, and never invent mission authority.

## Scope

| In | Out |
|---|---|
| Transport Protocol + in-memory stub channel | Vendor Slack/Telegram SDKs (EDR-0031) |
| Allowlisted `mission.read` / `mission.control` | `approval.decide`, `credential.capture` |
| Idempotent control command envelopes | Direct Core / engine imports |

## Layout

```text
interfaces/messaging/
  __init__.py
  scopes.py          # allowlisted scopes (no decide)
  transport.py       # ChannelTransport + InMemoryChannel
  bridge.py          # inbound text → Gateway envelopes
```
