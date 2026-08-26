# DDE web dashboard (DDE-052)

Thin **browser** operator surface for DDE Core. Gateway-client only —
never opens a database connection, never imports `engine/**`, never
fabricates mission/fleet rows.

## What it is

| Item | Choice |
|---|---|
| Placement | `interfaces/dashboard/` (blueprint Ch.3.6 tree) |
| Hosting | Static assets mounted by Gateway at `/dashboard/` |
| Transport | Same live `/v1` surface as `dde-studio/shared/gatewayClient.ts` |
| Auth (v1) | Principal UUID in the form (studio parity). OIDC deferred (EDR-0026) |
| `client_type` | `human` |
| Scope | By-id mission + mission-control reads; pause/resume/cancel via commands |

## What it is not

- Not Frontend Studio (DDE-065..068)
- Not the Electron EXE or VS Code extension (`interfaces/dde-studio/**`)
- Not a mission/run list UI — Core has no list endpoints yet (honesty-empty)

Golden CLI/web/Android parity is covered by DDE-056
(`tests/unit/test_client_parity_fixture.py`).

## Run

With Core listening on `:8000`:

```
http://127.0.0.1:8000/dashboard/
```

Enter a principal UUID that holds a project grant, open a session, paste a
mission id, Load. Cross-tenant reads fail closed with the Gateway error
family (Ch.13.9 dashboard auth-scope clause).

## Files

| Path | Role |
|---|---|
| `static/index.html` | Operator shell |
| `static/app.js` | UI wiring |
| `static/gateway.js` | Browser `/v1` client (existing endpoints only) |
| `static/styles.css` | Token-aligned chrome (palette from `schemas/design/tokens.json`) |
