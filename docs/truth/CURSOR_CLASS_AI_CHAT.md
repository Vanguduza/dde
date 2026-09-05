# DDE Code — Cursor-Class AI Chat, Planning & Execution Control Plane

**Status:** USER-LOCKED CANONICAL DDE-069 EXTENSION — 2026-09-05
**Mission:** DDE-069 — DDE Code / Frontend Studio V2 + Live Design Foundation
**Parent authorities:** `BLUEPRINT_REV3.md`, `FRONTEND_STUDIO_REV3.md`, `SCREEN_AUDIT_ENGINE.md`
**Decision index:** AD-041
**Project Truth note:** this owner-directed product decision is documented here immediately; database-backed Project Truth/EDR ingestion remains pending on hosts without the Project Truth database runtime.

---

# 0. Decision

DDE Code shall provide a first-class AI Chat control plane with the professional interaction depth expected from Cursor-class developer environments, while preserving DDE's stronger authority, evidence, isolation and verification laws.

The chat is not a generic chatbot and not an escape hatch around DDE Core. It is the primary conversational client over DDE's existing project, context, planning, workspace, worker, verification, recovery, Frontend Studio, Screen Audit and governance domains.

The same durable conversation architecture serves DDE Code and Frontend Studio. The existing `frontend.chat.*` namespace remains the DDE-069 compatibility surface; capability ownership is model/provider-neutral and must be reusable by a future top-level DDE Code shell.

---

# 1. Product law

A user must be able to work from Chat without losing DDE guarantees:

```text
conversation
→ explicit context
→ Ask / Plan / Execute mode
→ model or deterministic router
→ governed tools / commands
→ isolated workspace
→ visible activity
→ visible diff
→ review / revert
→ verification
→ checkpoint / recovery
→ durable evidence
```

Chat may propose work. Chat may execute work only through authority already admitted by DDE. Chat never gains shell, database, network, credential, approval or promotion rights merely because a model emitted a tool call.

---

# 2. Cursor-class capability envelope

The production packet includes:

1. multiple durable conversations per mission/project;
2. history list, open, rename, archive and branch;
3. ordered durable turns and reload restoration;
4. drag/picker file attachment upload;
5. attachment persistence, hashing, scope validation and text extraction;
6. `@file`, `@folder`, `@screen`, `@candidate`, `@component`, `@finding`, `@plan`, `@workspace` references;
7. pinned context chips and explicit context removal;
8. Ask / Plan / Execute modes;
9. model/profile selection with AUTO and typed provider availability;
10. context-budget projection and truncation visibility;
11. durable plans with ordered/dependent steps;
12. plan approval before execution where policy requires it;
13. step-by-step governed execution through existing Gateway commands;
14. retry, pause/cancel and resumable activity state;
15. tool/activity timeline with inputs, outputs, errors and references;
16. workspace change list and unified diffs;
17. per-file accept/review/revert and revert-all;
18. checkpoints and branch-from-checkpoint;
19. conversation branching from a historical turn;
20. deterministic read queries without unnecessary model calls;
21. Frontend Studio mutation/design/audit integration;
22. TaskGraph / Mission / WorkerRun / VerificationRun integration;
23. no fabricated success, no hidden tool call and no silent context omission.

---

# 3. Modes

## 3.1 ASK

ASK is read-mostly. It may:

- inspect code/project/context;
- answer coverage, QA, Screen Audit and architecture questions;
- search admitted repository context;
- explain diffs, failures and verification evidence;
- prepare non-binding suggestions.

ASK may not mutate project/workspace state. A deterministic mutation-shaped request in ASK is returned as a proposal and requires a mode change or explicit Plan/Execute action.

## 3.2 PLAN

PLAN may create and update a durable `FrontendChatPlan`.

A plan is not execution. It contains:

- objective;
- exact scope/context;
- ordered steps;
- dependencies;
- proposed command/tool binding;
- expected verification;
- risk/approval notes;
- state and evidence references.

PLAN must not directly mutate the target workspace or accepted project.

## 3.3 EXECUTE

EXECUTE may run approved plan steps or an explicitly approved direct operation.

Every step must:

- bind to an allowed existing DDE command/tool;
- preserve the caller's principal/session;
- receive its own idempotency identity;
- appear in the activity timeline;
- expose failure/cancel state;
- never bypass ordinary locks, leases, approvals, workspace isolation or verification.

Commands requiring stronger scopes than the conversation owns are refused rather than inherited.

---

# 4. Durable domain objects

## 4.1 Extended `FrontendConversation`

Adds:

```yaml
title:
status: OPEN | ARCHIVED
mode: ASK | PLAN | EXECUTE
model_profile_id: string | null
active_workspace_id: uuid | null
active_plan_id: uuid | null
parent_conversation_id: uuid | null
branched_from_turn_id: uuid | null
pinned_context_refs: string[]
created_by: uuid | null
archived_at: datetime | null
```

A conversation is durable and mission/project scoped. Reload does not create a fake replacement thread.

## 4.2 `FrontendChatAttachment`

Stores attachment metadata and a scoped content-addressed object reference:

```yaml
attachment_id:
conversation_id:
turn_id_optional:
source_kind: UPLOAD | WORKSPACE_FILE | PASTED
filename:
media_type:
size_bytes:
content_hash:
storage_key:
workspace_path_optional:
extraction_state:
extracted_text_optional:
status:
created_by:
```

Attachment bytes are stored in DDE-managed object storage, not in chat markdown and not in a repository worktree by default.

## 4.3 `FrontendChatPlan`

A versioned/locked durable plan containing typed `PlanStep` rows inside its schema.

Plan lifecycle:

```text
DRAFT → READY → APPROVED → EXECUTING → COMPLETED
                     ↘ PAUSED / FAILED / CANCELLED
```

A step lifecycle:

```text
PENDING → READY → SUBMITTED → COMPLETED
              ↘ BLOCKED / FAILED / CANCELLED / SKIPPED
```

## 4.4 `FrontendChatActivity`

Append-only operator-visible activity stream:

- MODEL_REQUEST / MODEL_RESPONSE;
- CONTEXT_ASSEMBLED;
- TOOL_PROPOSED / TOOL_STARTED / TOOL_RESULT;
- COMMAND_ACCEPTED / COMMAND_FAILED;
- PLAN_CREATED / PLAN_STEP;
- ATTACHMENT_ADDED;
- CHECKPOINT_CREATED / RESTORED;
- DIFF_REFRESHED / FILE_REVERTED;
- VERIFICATION_STARTED / VERIFICATION_RESULT;
- ERROR / STATUS.

## 4.5 `FrontendChatCheckpoint`

Conversation/workspace checkpoint, distinct from the existing worker recovery `Checkpoint`.

It records:

- conversation and turn sequence;
- mode/model selection;
- active plan/workspace;
- pinned context refs;
- attachment refs;
- workspace revision and diff hash;
- context hash;
- note/creator.

It does not replace a WorkerRun recovery checkpoint. When execution owns a WorkerRun, Chat links to the real recovery checkpoint rather than duplicating it.

## 4.6 `FrontendChatChangeReview`

Persists review decisions over a specific workspace revision/path:

```text
PENDING | ACCEPTED | REVERTED
```

The actual diff is derived from the real workspace and current git state. Review state never invents a file mutation.

---

# 5. Attachment storage

Canonical object key:

```text
chat/<tenant>/<project>/<sha256>
```

Rules:

- max upload size is policy-bound;
- filename is display metadata, never a filesystem locator;
- content hash is computed server-side;
- duplicate bytes deduplicate at the object layer;
- cross-tenant/project storage keys fail closed;
- executable attachment content is evidence/context, never automatically executed;
- text extraction is bounded and explicit;
- binary/image/PDF attachments may remain `UNSUPPORTED` for text extraction while still being valid attachments;
- removal removes conversation visibility; object deletion follows retention policy.

---

# 6. Context references

Supported normalized refs:

```text
file:<workspace-relative-path>
folder:<workspace-relative-path>
screen:<pxg_key>
candidate:<uuid>
component:<pxg_key>
finding:<uuid>
plan:<uuid>
workspace:<uuid>
attachment:<uuid>
requirement:<ref>
edr:<ref>
```

The UI may offer `@` completion. The server resolves every ref to scoped authority before use.

No user-visible `@file` string is trusted as proof the file exists or is authorized.

---

# 7. Context assembly and budget

Chat context is compiled from:

- Project Truth / accepted requirements / EDRs;
- active mission/task graph where applicable;
- current conversation turns;
- pinned refs;
- current screen/candidate/PXG/contract/coverage/audit state;
- selected workspace files/folders;
- uploaded attachments;
- current diff/change set;
- recent tool activity;
- current plan;
- current verification evidence.

The context projection exposes:

```yaml
estimated_tokens:
budget_tokens:
included_refs:
omitted_refs:
omission_reasons:
index_version:
staleness:
```

Omitted context is visible. Truncation is never silent.

---

# 8. Model/provider selection

Chat stores a requested `model_profile_id` or `AUTO`.

DDE resolves actual providers through admitted worker/model policy. The UI must distinguish:

- AVAILABLE;
- APPROVAL_REQUIRED;
- RATE_LIMITED;
- UNAVAILABLE;
- NOT_CERTIFIED.

The existing broad Claude Code invocation remains subject to EDR-0001 per-invocation approval and may not become a standing Chat credential path. The existing Cursor adapter remains fail-closed until certified live invocation exists.

No model selector may imply a provider is available when Core has not attested it.

---

# 9. Plan execution protocol

A plan step may name an existing DDE command, but execution is two-phase:

```text
frontend.chat.plan.prepare_step
    ↓
server validates plan state, dependencies, scope and command allowlist
    ↓
returns exact proposed command envelope + idempotency key
    ↓
client sends that command through normal /v1/commands
    ↓
client records command_id via frontend.chat.plan.record_step
    ↓
server verifies CommandLedger result before advancing the plan
```

This prevents Chat from acquiring an internal backdoor dispatcher.

Plan execution can automate the two-phase protocol in the UI while preserving independent command identities.

Forbidden automatic step classes include:

- approval decisions;
- credential capture;
- destructive irreversible admin operations;
- any command requiring a stronger scope than the conversation session;
- unregistered command types.

---

# 10. Workspace and diff integration

A conversation may bind one active DDE `Workspace`.

Reads:

- changed paths;
- status;
- unified diff;
- file content previews;
- current/base revision.

Mutations:

- revert one changed file;
- revert all uncommitted changes only with explicit confirmation;
- create checkpoint before destructive revert;
- never write outside workspace path jail.

“Accept” is a review decision, not a hidden git commit or promotion.

---

# 11. History / branching

Required operations:

- list conversations for mission/project;
- open by id;
- rename;
- archive/unarchive;
- branch from any turn;
- branch from checkpoint;
- preserve parent/branch lineage;
- search titles/turn text;
- never delete history as a way to hide failed work.

Branching copies context pointers, not mutable state blobs. Workspace branching requires a new isolated workspace or an explicit existing workspace choice.

---

# 12. Retry / cancel / stop

Retry is typed:

- retry model request;
- retry failed plan step;
- retry deterministic read;
- retry verification.

A retry gets a new activity identity and reuses the logical idempotency key only when the operation is genuinely the same mutation.

Cancel must distinguish:

- cancelling a queued/submitted chat activity;
- cancelling a plan;
- cancelling a WorkerRun through its existing adapter/control path.

Chat cannot claim a synchronous backend was cancelled after it already completed.

---

# 13. Gateway command surface

All mutation commands target the mission and ride existing `mission.control` unless the command is read-only.

Required commands:

```text
frontend.chat.open
frontend.chat.rename
frontend.chat.archive
frontend.chat.branch
frontend.chat.set_mode
frontend.chat.set_model
frontend.chat.set_context
frontend.chat.pin_context
frontend.chat.unpin_context
frontend.chat.send
frontend.chat.attachment.remove
frontend.chat.plan.create
frontend.chat.plan.update
frontend.chat.plan.approve
frontend.chat.plan.prepare_step
frontend.chat.plan.record_step
frontend.chat.plan.cancel
frontend.chat.activity.cancel
frontend.chat.retry
frontend.chat.checkpoint.create
frontend.chat.checkpoint.restore
frontend.chat.changes.accept
frontend.chat.changes.revert_file
frontend.chat.changes.revert_all
```

The existing `frontend.chat.open|set_context|send` remain compatible.

---

# 14. HTTP/read surface

Required reads:

```text
GET /v1/missions/{mission}/frontend/chats
GET /v1/missions/{mission}/frontend/chats/search?q=
GET /v1/missions/{mission}/frontend/chat/{conversation}
GET /v1/missions/{mission}/frontend/chat/{conversation}/attachments
GET /v1/missions/{mission}/frontend/chat/{conversation}/plans
GET /v1/missions/{mission}/frontend/chat/{conversation}/activities
GET /v1/missions/{mission}/frontend/chat/{conversation}/checkpoints
GET /v1/missions/{mission}/frontend/chat/{conversation}/changes
GET /v1/missions/{mission}/frontend/chat/{conversation}/context-budget
```

Upload:

```text
POST /v1/missions/{mission}/frontend/chat/{conversation}/attachments
Content-Type: <actual media type>
X-File-Name: <display filename>
<raw bytes>
```

The server computes the hash and storage identity. No client-supplied storage path is accepted.

---

# 15. UI contract

The permanent composer contains:

- conversation/history button;
- Ask / Plan / Execute segmented mode control;
- model/profile selector;
- `+` attachment/context button;
- `@` context completion;
- textarea;
- Stop button while a cancellable activity is active;
- Send/Plan/Execute action label appropriate to mode.

Expanded Chat contains:

- conversation title and branch lineage;
- turns;
- attachment cards;
- plan panel with step states/dependencies;
- activity/tool timeline;
- changed-files/diff review;
- context-budget inspector;
- checkpoint list;
- retry/refusal/error controls.

No tool activity is hidden behind generated prose.

---

# 16. Frontend Studio integration

Existing Frontend Chat behavior remains:

- deterministic Inspector-equivalent edits use `MutationPlanner`;
- `/design` shares the conversation and stays typed unavailable without a certified provider;
- selected `pxg_key`, candidate, screen and viewport are stable context;
- Screen Audit findings become `@finding` context;
- live candidate edits rerender and trigger DDE-068 verification;
- Chat cannot resolve an audit finding or promote a candidate by assertion.

---

# 17. DDE planning / worker integration

Cursor-class Plan mode does not invent a parallel planner.

Where the requested work is broader than a frontend-local deterministic mutation, Chat plans should map to DDE TaskGraph/task concepts and, when execution begins, to existing ExecutionPlan/Workspace/WorkerRun/VerificationRun machinery.

The Chat plan is the conversational/operator projection and orchestration record; DDE planning/execution remains authoritative for development work.

---

# 18. Security and privacy

- tenant/project/mission scope on every read/write;
- no cross-project attachment refs;
- path-jail all workspace file access;
- no ambient credentials in model/workspace context;
- no whole-repository export merely because a model asks;
- no untrusted attachment text treated as system instruction;
- attachment MIME/extension is metadata, not trust;
- no approval/credential/promotion action auto-executed from a model plan;
- explicit audit trail for provider/model, plan, tool and command lineage.

---

# 19. Failure honesty

Typed states include:

- CONTEXT_INCOMPLETE;
- ATTACHMENT_TOO_LARGE;
- ATTACHMENT_UNSUPPORTED;
- PROVIDER_UNAVAILABLE;
- APPROVAL_REQUIRED;
- PLAN_NOT_APPROVED;
- PLAN_DEPENDENCY_BLOCKED;
- COMMAND_NOT_ALLOWED;
- WORKSPACE_UNAVAILABLE;
- STALE_REVISION;
- DIFF_STALE;
- ACTIVITY_NOT_CANCELLABLE;
- CHECKPOINT_STALE.

A provider failure does not erase the user's turn. A failed step remains visible and retryable where policy permits.

---

# 20. Verification / Definition of Done

The packet is not complete until tests prove at least:

1. conversation create/list/open/rename/archive/branch/reload;
2. uploaded attachment hash/storage/scope/extraction and removal;
3. `@` reference resolution and path-jail negative cases;
4. Ask mode refuses mutation;
5. Plan mode creates durable non-executing steps;
6. Execute requires approved plan and dependencies;
7. prepared plan step routes through a separate normal Gateway command identity;
8. record-step verifies CommandLedger before completion;
9. model/profile unavailable/approval-required states are honest;
10. activity timeline records proposed/start/result/error;
11. context-budget omissions are visible;
12. real workspace diff list/read;
13. revert-file changes only the workspace and records review/activity;
14. checkpoint/restore and branch lineage;
15. retry/cancel semantics;
16. existing Frontend Chat mutation → rerender → DDE-068 verification still works;
17. `/design` authority remains unchanged;
18. production PostgreSQL E2E is never claimed on a host without PostgreSQL.

---

# 21. Final product law

DDE is AI-first, therefore Chat must be a first-class operating surface rather than a decorative assistant.

But DDE is not model-first. The model is replaceable; authority, history, plans, workspaces, evidence, verification and recovery belong to DDE.

The Cursor-class experience is therefore:

> conversational speed and context richness, with DDE-grade explicit authority, provenance, isolation, evidence and recovery.
