# DDE-069 Cursor-class AI Chat — implementation evidence

Date: 2026-09-05
Authority: `docs/truth/CURSOR_CLASS_AI_CHAT.md`, AD-041, `FRONTEND_STUDIO_REV3.md`

## Result

DDE Frontend Chat is now a durable Cursor-class conversational control plane rather than a single composer thread. DDE owns conversation history, modes, plans, workspace authority, evidence and recovery; model/provider processes remain replaceable and cannot widen authority.

Implemented user-facing capabilities:

- durable multiple conversations, search, rename, archive and immutable branch lineage;
- explicit Ask / Plan / Execute modes;
- model/profile selection with honest AVAILABLE / APPROVAL_REQUIRED / NOT_CERTIFIED / UNAVAILABLE states;
- native VS Code file selection through opaque pick tokens, scoped attachment reservation and extension-host byte upload;
- attachment persistence, content hashing, bounded extraction and turn binding;
- durable plans with dependent steps, approval, retry, cancellation and exact command identity;
- operator-visible activity/tool timeline with cancellation where the underlying activity is cancellable;
- isolated-workspace changed-file review, unified diffs, patch validation/apply, accept metadata, file revert and checkpoint-gated revert-all;
- durable conversation checkpoints and context restore without secretly rewinding workspace bytes;
- pinned `@` context references and visible context-budget inclusion/omission;
- candidate workspace binding plus existing mutation → preview → DDE-068 re-verification integration.
## Authority and safety properties

- Chat plans execute only commands admitted by Gateway mission-control policy.
- Plan execution is two-phase: prepare exact command/idempotency/request-hash identity, execute through normal Gateway, then reconcile the real CommandLedger row.
- Retry creates a new attempt identity without changing the logical approved command.
- Ask mode cannot mutate. Plan mode cannot execute. Execute still uses existing governed DDE services.
- `capability.claude_code_invoke` was not widened. If the local Claude Code seat is present it remains `APPROVAL_REQUIRED` per EDR-0001; it is never silently treated as an always-on Chat model or `/design` transport.
- `/design` remains typed unavailable until a certified DesignProvider transport exists.
- attachment filenames never become storage paths; storage identity is tenant/project/content-hash scoped.
- the webview never receives arbitrary native file paths from the VS Code picker.
- workspace patch/revert operations remain inside the existing Workspace path jail.

During verification, the new invariant tests found and corrected two production defects: unknown plan commands previously reached Gateway target lookup before allowlist refusal and could raise a raw `KeyError`; and Git porcelain output was stripped before parsing, removing the leading status-column whitespace and the first character of modified paths. Both now fail/parse correctly.

## Runnable evidence

- generated contract drift: PASS;
- generated binding-matrix drift: PASS;
- Ruff over changed Chat/Gateway/workspace paths: PASS;
- mypy over changed Chat/Gateway/workspace paths: PASS;
- focused Python Chat/Gateway/core suite: **29 passed**;
- UI TypeScript: PASS;
- Cursor + existing Frontend Studio Playwright: **33 passed** (5 dedicated Cursor scenarios + 28 existing regressions);
- extension TypeScript: PASS;
- extension transport/package tests: **77 passed**;
- real VSIX packaging: PASS, **1.56 MB**, 89 files;
- `git diff --check`: PASS.
## Browser proof

`interfaces/dde-studio/ui/visual/cursor-chat.spec.ts` proves:

1. Ask refuses a deterministic mutation without changing the preview.
2. Plan creates a durable governed plan without changing candidate bytes.
3. Approval + prepared exact command executes through the host bridge/Gateway envelope, records completion, rerenders the candidate, reaches LIVE, and produces a fresh DDE-068 PASSED verification.
4. history search, rename and branching operate on durable thread identities;
5. native attachment reservation + opaque-token upload binds an active attachment to the sent turn;
6. context pin/budget and checkpoint create/restore are visible and actionable;
7. provider selection exposes Claude Code as approval-required rather than silently available;
8. activity cancellation and changed-file acceptance act through registered commands.

## Production-runtime boundary

`tests/unit/test_cursor_chat_postgres.py` is committed as the PostgreSQL persistence proof for conversations, attachments, plans and branches. On this host it is **UNAVAILABLE**, not PASS/FAIL, because `DDE_DATABASE_URL` and `DDE_REDIS_URL` are unset; settings validation fails before a database connection can be attempted.

Therefore the 99-control Chat rows keep their final `BOUND` state where E2E is the missing layer. This packet does not convert unavailable production infrastructure into VERIFIED evidence.

Screen Audit and M8 Source Intelligence remain separate incomplete DDE-069 packets. `@finding` remains fail-closed until the Screen Audit authority is restored/completed. AD-039 still blocks exact pixel-reference conformance because the approved golden image is absent.
