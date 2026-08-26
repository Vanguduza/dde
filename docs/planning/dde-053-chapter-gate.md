# DDE-053 chapter gate — Android thin client (API parity + reconnect)

**Mission:** §18.3 S6 / `DDE-053` — Android thin client with API parity
and reconnect ⟨Ch.15.1⟩. **Charter:** Ch.15.1 reconnect; Ch.3.6
`interfaces/android`; API parity with DDE-052 web allowlist. **Not**
Termux/offline queue (DDE-054) or multi-client golden parity (DDE-056).

**CI:** Python Gateway reconnect suite green; Kotlin sources scaffolded.
Full `assembleDebug` / Compose UI APK requires JDK 17 + Android SDK —
deferred under EDR-0029 (this host had no JDK; winget install did not
complete).

## What landed

- `interfaces/android/`: README + Kotlin Gateway allowlist,
  `ReconnectCoordinator` (resume then always by-id re-sync), models
  matching the DDE-052 `/v1` surface, app placeholder package.
- `tests/unit/test_android_gateway_reconnect.py`: allowlist parity with
  `dashboard/static/gateway.js`; resume + by-id re-sync against live
  Gateway; cross-tenant read still fails closed after resume.

## Rule disposition

| Rule | Status |
|---|---|
| Ch.15.1 never invent local authority after reconnect | **YES** — `ReconnectCoordinator.reconnectAndResync` always re-GETs mission + mission-control by id after resume |
| Ch.15.1 sequence cursor + WS/SSE + unreplayable-gap snapshot | **NO** — Core resume uses `last_event_at`; no live stream; named under EDR-0027 |
| API parity with web dashboard allowlist | **YES** — `GatewayAllowlist.ALLOWED_PATHS` mirrors dashboard `ALLOWED_PATHS` |
| Ch.13.9 same authz as API | **YES** — same Gateway path; cross-tenant proof after resume |
| Shipable Compose APK on CI | **NO** — EDR-0029 |

## Deferred (proposed EDRs)

| ID | Item |
|---|---|
| **EDR-0027** (continued) | Sequence-based resume, WS/SSE, server-enforced fresh snapshot on unreplayable gap |
| **EDR-0029** | JDK 17 + Android SDK CI job (`assembleDebug`, instrumented tests); Compose operator screens wired to `GatewayTransport` |
| **EDR-0028** | CLI/web/Android golden parity (DDE-056) |

## Verdict

**PASS-WITH-EDR** — Android client package + reconnect coordinator +
Gateway proofs for the Ch.15.1 subset Core supports; APK/Compose CI and
full reconnect stream deferred. Auto-proceed to DDE-054 only if humans
accept APK-deferred PASS-WITH-EDR; otherwise install JDK/SDK and complete
EDR-0029 before claiming a device-installable client.
