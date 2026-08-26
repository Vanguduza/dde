# DDE Android thin client (DDE-053)

Gateway-only Mission Control operator on Android. Twin of the DDE-052
web dashboard allowlist, plus **session resume + by-id re-sync** for
Ch.15.1 reconnect behaviour that Core actually supports today.

## Scope

| In | Out |
|---|---|
| `interfaces/android/` Kotlin/Compose app | Termux / offline queue (DDE-054) |
| Same `/v1` allowlist as `interfaces/dashboard/static/gateway.js` | Full sequence/WS/SSE replay (EDR-0027) |
| `client_type=human` + mission scopes | `client_type=device` (no mission scopes) |
| Resume session → re-GET mission/control by id | Invented list/stream endpoints |

Golden CLI/web/Android parity: DDE-056
(`tests/unit/test_client_parity_fixture.py`).

## Reconnect contract (honest)

1. Persist `session_id` and last `last_event_at` cursor locally.
2. On reconnect call `POST /v1/sessions/{id}/resume` with that cursor.
3. If `fresh_snapshot` is true **or** retained events cannot rebuild UI,
   discard local projection and `GET` mission + mission-control by id.
4. Never treat command `202 Accepted` as completion; never retry a
   mutation without the same `idempotency_key`.

Core today resumes on **timestamps**, not event sequences, and does not
serve a live event stream. Chapter gate must name that gap (EDR), not
claim full Ch.15.1.

## Build

Requires JDK 17+ and Android SDK (local checkout used Temurin 17 +
platform 35 under gitignored `.tooling/`). Set `JAVA_HOME` /
`ANDROID_HOME`, write `local.properties` `sdk.dir=…`, then from this
directory:

```text
./gradlew.bat :gateway:test :app:assembleDebug
```

Debug APK: `app/build/outputs/apk/debug/app-debug.apk`.

CI without the SDK still runs the Python Gateway reconnect proofs under
`tests/unit/test_android_gateway_reconnect.py`.
