# DDE-052 chapter gate — web dashboard

**Mission:** §18.3 S6 / `DDE-052` — web dashboard. **Charter:** blueprint
`REV_2_0.md` Ch.15 (Gateway client rules), Ch.13.9 (dashboards apply the
same authorization scope as API reads), Ch.3.6 (`interfaces/…/dashboard`
placement). S6 full exit (CLI/web/Android identical outcomes + reconnect)
is **not** this mission — that is DDE-053/056.

**CI:** ruff check/format · mypy (352 files) · **1049 passed / 2 skipped**
(unit+contract+recovery) · `generate_contracts --check` · design tokens ·
dde-studio tests (67) · desktop `tsc` — green. One `studio-check` `npm ci`
EBUSY on Electron `default_app.asar` was environmental; desktop `ci`+`check`
re-ran clean.

## What landed

- `interfaces/dashboard/`: browser operator shell (static HTML/JS/CSS).
- Gateway mounts assets at `/dashboard/` (`engine/gateway/app.py`) —
  transport-only; no mission state in the static tree.
- Browser client (`static/gateway.js`) mirrors
  `dde-studio/shared/gatewayClient.ts` and only calls existing `/v1`
  endpoints (sessions, commands, mission + mission-control by id).
- UI distinguishes command acceptance from completion; never fabricates
  mission/fleet list rows (no list API yet).
- Tests: package boundary + honesty pins; mounted shell; happy-path
  mission/control reads; **cross-tenant mission/control read fails closed**
  on the same Gateway authz path the browser uses (Ch.13.9).

## Rule disposition

| Rule | Production call site |
|---|---|
| Ch.15.1 never owns mission state | Static assets + `/v1` only; no `engine`/SQL imports under `interfaces/dashboard/` |
| Ch.15.2 acceptance ≠ completion | `app.js` control commands show 202 acceptance then reload mission |
| Ch.15.5 error family | `GatewayApiError` surfaces `error_code` / detail to the operator |
| Ch.13.9 dashboard same authz as API reads | Browser → `GET /v1/missions/{id}` / `mission-control/{id}` → `GatewaySessionService.authorize_project` (same path as other clients). Proven by `test_dashboard_path_rejects_cross_tenant_mission_read` |
| Ch.3.6 dashboard placement | `interfaces/dashboard/` + Gateway mount |

**Not claimed:** ORGANIZATION grant sibling-tenant coverage at gateway
(still EDR-0022 from DDE-051). Dashboard inherits whatever Gateway
enforces today.

## Deferred (proposed EDRs)

| ID | Item | Rationale |
|---|---|---|
| **EDR-0026** | OIDC/Bearer browser login (Ch.14.2 / 15.3) | v1 uses principal UUID like studio; not OIDC |
| **EDR-0027** | Mission/run/event list + WS/SSE reconnect gap replay (Ch.15.1/15.4, Ch.16.5) | No list/stream endpoints; honesty-empty until Core grows them |
| **EDR-0028** | CLI/web/Android identical golden outcomes | DDE-056 parity fixture; Android client is DDE-053 |

## Verdict

**PASS-WITH-EDR** — in-charter web dashboard exists as a Gateway-only
browser client; Ch.13.9 scoped reads proven on the production authz path;
OIDC, reconnect/event stream, and multi-client parity deferred under
EDR-0026–0028. Auto-proceed to DDE-053 authorized under the standing
order.
