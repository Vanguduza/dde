# DDE-053 chapter gate — Android thin client (API parity + reconnect)

**Mission:** §18.3 S6 / `DDE-053` — Android thin client with API parity
and reconnect ⟨Ch.15.1⟩. **Charter:** Ch.15.1 reconnect; Ch.3.6
`interfaces/android`; API parity with DDE-052 web allowlist. **Not**
Termux/offline queue (DDE-054) or multi-client golden parity (DDE-056).

**CI / local proofs (2026-08-26):**

- `ruff` / `mypy` (352 files) / **1054 passed, 2 skipped**
  (unit+contract+recovery) / `generate_contracts --check` — green
- Python `tests/unit/test_android_gateway_reconnect.py`: **5 passed**
  (`DDE_DATABASE_URL` / `DDE_REDIS_URL` from `.env`)
- Kotlin `:gateway:test`: **2 passed** (`GatewayAllowlistTest`)
- `:app:assembleDebug`: **BUILD SUCCESSFUL** — APK at
  `interfaces/android/app/build/outputs/apk/debug/app-debug.apk`
  (~10.1 MB; build outputs gitignored). Tooling: Temurin JDK 17 at
  `.tooling/jdk-17`, Android SDK 35 at `.tooling/android-sdk` (both
  gitignored).

## What landed

- `interfaces/android/`: Gradle multi-module project (`:gateway` JVM +
  `:app` Compose).
- `OkHttpGatewayTransport` — same six `/v1` paths as
  `dashboard/static/gateway.js` (OkHttp kept off the public constructor
  so `:app` compile classpath stays clean).
- `ReconnectCoordinator` — resume then always by-id re-sync (never trusts
  stale local projection).
- Compose `OperatorScreen` — session open, load mission/control, pause/
  resume/cancel with idempotency keys, Reconnect button.
- Tests: `tests/unit/test_android_gateway_reconnect.py` + Kotlin
  `GatewayAllowlistTest`.

## Rule disposition

| Rule | Production call site |
|---|---|
| Ch.15.1 no stale local authority after reconnect | `ReconnectCoordinator.reconnectAndResync` → re-GET mission + mission-control |
| API parity with web allowlist | `GatewayAllowlist.ALLOWED_PATHS` ≡ dashboard `ALLOWED_PATHS` |
| Ch.15.2 acceptance ≠ completion | `OperatorViewModel.control` shows 202 then reloads by id |
| Ch.13.9 same authz as API | Same Gateway path; cross-tenant proof in Python suite |
| Ch.15.1 sequence/WS/SSE full replay | Deferred EDR-0027 (Core gap) |

## Deferred (proposed EDRs)

| ID | Item |
|---|---|
| **EDR-0027** | Sequence-based resume, WS/SSE, server-enforced fresh snapshot |
| **EDR-0028** | CLI/web/Android golden parity (DDE-056) |
| **EDR-0029** | Optional: GitHub Actions Android job (this landing proves local assemble) |

## Verdict

**PASS-WITH-EDR** — installable Compose APK + Gateway reconnect client
behaviour for the Ch.15.1 subset Core supports; full stream/sequence
reconnect and multi-client parity deferred. Auto-proceed to DDE-054
authorized under the standing order.
