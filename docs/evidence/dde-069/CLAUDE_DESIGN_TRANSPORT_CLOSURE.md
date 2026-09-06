# DDE-069 Claude `/design` transport closure

**Date:** 2026-09-06

This closes the `CT-06` blocker that a certified Claude Design transport did not
exist, so `/design` refused with `NOT_CERTIFIED` and no end-to-end run was
possible. It does not close AD-039 golden-binary pixel conformance, live R2
object-store certification, or 21st source execution; those remain separate and
open.

## What was built

`engine/studio/design/claude_transport.py` — a dedicated transport, not a
general worker. The authenticated `claude` executable is used only as a bounded,
non-interactive **host process for the official `claude-design` MCP server**.
The blast radius is removed before the process starts:

| Flag | Effect |
|---|---|
| `--tools ToolSearch` | deletes every built-in tool that can touch a file, run a command or reach the network |
| `--strict-mcp-config` + ephemeral `--mcp-config` | exactly one MCP server is admitted: the official Claude Design endpoint |
| `--settings <generated>` | allows only `mcp__claude-design__*`, `ToolSearch` and the harness result emitter; denies `Bash`/`Edit`/`Write`/`Read`/`WebFetch`/`WebSearch`/`Task` |
| `--setting-sources ""` | user, project and local settings — and their hooks — cannot widen that |
| `--permission-mode dontAsk` + `--permission-prompts none` | anything not already allowed is denied, never escalated to an absent human |
| `--no-session-persistence` | no resumable session is left behind |
| `--json-schema <manifest>` | the return contract is a machine-readable manifest, not final prose |

Those flags are treated as a *claim*. `_certify` checks the returned
`stream-json` against them and refuses on disagreement:

- the `claude-design` MCP server must report `connected` in `system/init`;
- no MCP server outside the allowlist may appear;
- the offered tool surface must contain nothing but the allowlist;
- no non-allowlisted tool may have executed;
- `permission_denials` must be empty — a denied attempt invalidates the result;
- the terminal `result` must be a non-error success.

`engine/studio/design/manifest.py` is the explicit return contract
(`dde.design.manifest/1`). Two of its checks are boundaries rather than
formatting:

- **ingress scope** — a direction may only name PXG keys that
  `DesignEditContext` actually exported. `context.py` bounds what leaves DDE;
  this bounds what may come back and claim to be about the project.
- **deliverable backing** — every direction's `preview_path`, and the manifest
  path itself, must be tied to an observed *successful* `write_files` into the
  same provider project. A direction with no backing file is a claim with no
  artifact behind it.

`StructuredOutput` is admitted alongside `ToolSearch`. It is not requested; the
harness injects it whenever `--json-schema` is set, and it is the channel that
delivers the manifest. It is named explicitly rather than tolerated by a
wildcard.

### What was deliberately not done

- `capability.claude_code_invoke` is **not** used and remains forbidden as a
  `/design` fallback. That capability grants arbitrary development execution
  against a human's own seat and keeps its mandatory per-invocation approval for
  that reason (EDR-0001 Path A, EDR-0017).
- No terminal-keystroke automation, no interactive session, no TTY.
- No Anthropic credential is read, stored, forwarded or received. The
  already-`claude login`-authenticated local process authenticates itself. DDE
  observes only *whether* a login exists, through `claude auth status --json`.
- No accepted-state direct write. A design artifact still reaches code only
  through Try live's isolated candidate, and accepted state only through the
  promotion gate.

### Activation

Explicit and fail-closed by omission. No host path is hardcoded.

```
DDE_CLAUDE_DESIGN_ENABLED=1          # required; absent => no transport at all
DDE_CLAUDE_DESIGN_BINARY=claude      # resolved via PATH unless an explicit path is given
DDE_CLAUDE_DESIGN_MCP_URL=https://api.anthropic.com/v1/design/mcp
DDE_CLAUDE_DESIGN_MCP_SERVER=claude-design
DDE_CLAUDE_DESIGN_MODEL=sonnet       # optional
DDE_CLAUDE_DESIGN_TIMEOUT_SECONDS=900
DDE_CLAUDE_DESIGN_MAX_BUDGET_USD=5
DDE_CLAUDE_DESIGN_STATUS_TTL_SECONDS=60
```

A deployment that sets none of these registers no transport, so
`ClaudeDesignProvider` still reports `NOT_CERTIFIED` and the gateway still
refuses. Ordinary unit and CI runs therefore never reach a live provider.

### Typed provider states

| Condition | State |
|---|---|
| not enabled, or configured executable not on PATH | `NOT_CERTIFIED` |
| host Claude Code installation not signed in | `AUTH_REQUIRED` |
| auth probe or MCP health check fails / endpoint not connected | `UNAVAILABLE` |
| enabled, signed in, endpoint connected | `CERTIFIED` |

Per-invocation failures keep their own codes: `PROVIDER_TIMEOUT`,
`PROVIDER_UNAVAILABLE` (no result, MCP not connected), `POLICY_DENIED`
(non-allowlisted tool/server, permission denial), `PROVIDER_ERROR`
(unsuccessful result, contract violation, missing write evidence).

## Frontend Studio wiring

- `frontend.design.provider_status` is now read by `DdeStudioApp`, and the
  toolbar control enables **only** on `CERTIFIED`. Every other case renders a
  disabled control whose title names what is actually wrong.
- Pressing it sends `/design …` into the **existing Universal DDE Chat
  conversation**. It does not open a second conversation, does not call
  `frontend.design.request` around the chat, and does not mutate state
  directly. Scope defaults to the current selection, then the current screen,
  and the key is named in the turn text because the intent router treats an
  explicit key as authoritative.
- Conversation mode still governs: `/design` is a mutating intent, so an Ask
  conversation refuses it with `MODE_READ_ONLY` — the mode, not the provider.

## Live certification run

Real PostgreSQL (isolated `dde-infra`, `127.0.0.1:55432`), real Redis
(`127.0.0.1:56379`), real git worktrees, and the real `claude-design` MCP at
`https://api.anthropic.com/v1/design/mcp`.

```
DDE_LIVE_CLAUDE_DESIGN=1 DDE_CLAUDE_DESIGN_ENABLED=1 \
DDE_CLAUDE_DESIGN_MODEL=sonnet \
DDE_LIVE_DESIGN_EVIDENCE=docs/evidence/dde-069/claude-design-live-run.json \
DDE_DATABASE_URL=postgresql+asyncpg://dde:dde@127.0.0.1:55432/dde \
DDE_REDIS_URL=redis://127.0.0.1:56379/0 \
pytest tests/live/test_claude_design_live_e2e.py
```

Result: **1 passed in 398.46s**. Observations are recorded by the run itself in
`claude-design-live-run.json`; they are a by-product of the assertions, not a
separately authored claim. From that file:

1. **Provider CERTIFIED from discovery.** `state=CERTIFIED`,
   `version=claude-design-mcp/dde.design.manifest/1;auth=claude.ai;plan=max;org=d7950bb1-…`
   — an unauthenticated or unreachable host could not have produced it.
2. **`/design` through Universal DDE Chat.** Turn `intent=DESIGN_DIVERGENT`,
   `outcome=ROUTED`, `chat_mode=EXECUTE`, `target_keys=["screens/checkout"]`,
   3 produced refs.
3. **DesignSession + DesignArtifacts persisted.** Session
   `01a07783-1b39-75e0-aade-b6ed45be5483`; directions A/B/C all `GENERATED`
   (none quarantined), each carrying `provider_id=claude-design`,
   `design_system_hash=e64a0490c14bbae1e562eeacfbd5183d9cc3a6c8a2d62ba57ee1f99e67522f74`,
   `base_pxg_revision`, and
   `provider_version=…|harness=2.1.259|served=claude-sonnet-5`.
4. **A real Claude Design project backs them.** Project
   `7f0b875a-cd1c-4b5f-b5d4-28bec5341b4f`
   (`https://claude.ai/design/p/7f0b875a-…`), with `direction-a.html`,
   `direction-b.html`, `direction-c.html` and `dde-manifest.json` each tied to
   an observed successful `write_files`.
5. **Directions are proposals in the project's token vocabulary.** Per-node
   `pxg_key`/`intent`/`tokens` only, all keys within the exported scope, and no
   score on any artifact.
6. **Try live produced an isolated candidate.** Artifact A →
   candidate `01a07789-15ec-7595-97ba-4d2d5e414ccb`; accepted PXG stayed at
   revision 2 with `screens/checkout#hero` still `spacing=space2`.
7. **The preview is code-backed and LIVE is earned.** `source_path`
   `prototypes/screens/checkout.html`, `source_revision`
   `cf7a8e549f2d…`, `content_hash` `fc41541e6002…`; the session's hash equals the SHA-256 of the
   candidate worktree file read back from disk. A `LIVE` signal carrying a
   wrong hash was answered `STALE`, not `LIVE`; only a matching hash produced
   `state=LIVE`, `state_detail="browser loaded the exact code-backed candidate
   source"`.
8. **Promotion is still gated, and was refused.** `frontend.candidate.promote`
   returned `403 POLICY_DENIED` naming three blocking gates: `mutations`,
   `visual_verification` ("no verification run is attached; unavailable
   verification is not approval") and `source_provenance`. The accepted graph
   was unchanged afterwards.

Point 8 is the intended outcome, not a shortfall. A run in which a design
artifact reached accepted state without verification evidence would be a
failure of the system.

## Test results

| Suite | Command | Result |
|---|---|---|
| Transport boundary (no live provider) | `pytest tests/unit/test_claude_design_transport.py` | 25 passed |
| Design gateway + chat (real PostgreSQL) | `pytest tests/unit/test_design_gateway_postgres.py` | 15 passed |
| Binding ledger integrity | `pytest tests/unit/test_frontend_binding_matrix.py` | 14 passed |
| Frontend Studio visual suite | `npx playwright test --config visual/playwright.config.ts` | 58 passed |
| Live certification | `pytest tests/live/test_claude_design_live_e2e.py` | 1 passed |

The transport's governance properties are all asserted against a fake host
process, so CI proves them without spending a provider invocation. The live run
is the certification, not the regression suite.

## Stale tests updated

`tests/unit/test_design_gateway_postgres.py` predated two later changes and was
failing before this work: Universal DDE Chat now defaults to read-only Ask mode,
and `set_context` gained an explicit `set_active_candidate` flag. Four
conversations that exercise a mutating intent now open in `EXECUTE`, one
`set_context` call passes the explicit flag, and the mode gate itself gained its
own test asserting that Ask refuses `/design` **before the provider is
consulted** — a certified provider does not make Ask writable.

## Still open (unchanged by this evidence)

- **AD-039** golden-binary pixel-reference conformance — the approved golden
  image is still not pinned in repository truth.
- **R2** live object-store certification — requires complete scoped credentials.
- **21st** source execution — requires an exact certified MCP source transport
  and `API_KEY_21ST`.
- **Design-system sync** (`frontend.design.sync_system`) is not implemented. The
  manifest echoes and verifies the design-system hash, so an artifact generated
  against a different snapshot is refused, but pushing the allowlisted snapshot
  to the provider as a governed capability remains DDE-069 follow-on work.
