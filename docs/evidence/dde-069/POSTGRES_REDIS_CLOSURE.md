# DDE-069 PostgreSQL + Redis Closure Evidence

**Date:** 2026-09-05

This evidence closes the earlier host-infrastructure `UNAVAILABLE` state for DDE-069 PostgreSQL/Redis integration proof. It does not certify unrelated external providers.

## Isolated runtime

The authorized Oracle host already runs Dial services, so DDE proof was isolated instead of reusing or modifying them.

- isolated LXD container: `dde-infra`;
- PostgreSQL: **16.15**;
- Redis: **7.0.15**;
- host loopback-only proxies: PostgreSQL `127.0.0.1:55432`, Redis `127.0.0.1:56379`;
- no Dial service, Dial database, host firewall policy or production credential was modified.

## Defects exposed by real persistence

1. Fresh migration to `0031` failed because regenerated stage-1 SQL already contained Cursor-class Chat columns. Migrations `0031`–`0034` are now idempotent against a fresh regenerated-schema install while preserving incremental upgrade behavior.
2. Universal DDE Chat attempted to persist UUID-bearing resolved context directly to JSONB. The persistence boundary now serializes the full context safely instead of dropping information.
3. Command idempotency persisted UUID-bearing command results directly to JSONB. The generic ledger boundary now JSON-normalizes result payloads before storage.
4. Three PostgreSQL characterization assertions were stale after M8/Screen Audit/Ask-Plan-Execute hardening and were updated to assert the stronger current behavior.
## Verification

Against the isolated real services:

- Alembic fresh-database migration: `0034 (head)` — **PASS**;
- M8 Source Intelligence PostgreSQL lifecycle: **1/1 PASS**;
- DDE-069 PostgreSQL + Redis focused suite: **34/34 PASS**;
- Redis stream publisher against real Redis: **PASS**;
- Gateway Redis readiness probe: **PASS**;
- Ruff on changed runtime/migration/test paths: **PASS**;
- mypy on changed persistence paths: **PASS**.

The focused database suite includes candidate verification, Cursor-class Chat, mutation engine, characterization, domain, Gateway E2E, Frontend Studio, Screen Audit, Source Intelligence and Redis stream persistence.

## Remaining external states

These are not converted to PASS by this evidence:

- live R2 object-store certification requires complete scoped R2 credentials;
- 21st source execution still requires an exact certified MCP source transport;
- Claude `/design` still requires a certified `DesignProvider` transport;
- pixel-reference conformance requires the exact approved golden image to be pinned in repository truth.
