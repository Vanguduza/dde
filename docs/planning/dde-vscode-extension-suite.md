# DDE Code — VS Code / Cursor Extension Suite: Plan (REV 1)

**Status:** planning document. Not a line item in `docs/blueprint/historical/REV_2_0.md` Chapter 18 —
if this suite is later formalized as `DDE-0xx` missions, that's a follow-up edit to Ch.18,
not implied by this document.
**Scope:** (1) reviews the original "DDE VS Code extension suite" concept against REV 2.0,
(2) reconciles it against the `interfaces/dde-studio` scaffold that already exists in this
repo, (3) adds engineering research on what is actually buildable against the real VS Code
/ Cursor extension host in 2026, and (4) turns all of that into a concrete build order.
**Relationship to REV_2_0.md:** this document adds nothing to DDE's own object model. Every
correction below either points a UI element at a contract that already exists in REV 2.0,
or proposes a UI surface for a subsystem REV 2.0 already specifies. If anything here implies
a change to Chapter 2–20, that's a bug in this document, not a proposal to amend the
blueprint. One blueprint inconsistency this review surfaced (§1.5.4 vs Ch.18.3 on the MCP
server's stage) has already been fixed directly in `docs/blueprint/historical/REV_2_0.md`; see §1.

The original plan is sound at the architecture level: keep the editor as the editor, add DDE
as a control layer using native extension points, route model selection through DDE rather
than the editor's own picker, treat the UI as a projection of server-side state rather than
a second source of truth. All of that survives this review unchanged.

---

## §0 Summary of changes since the original chat-export plan

| # | Gap | What this document adds |
|---|---|---|
| G1 | Editor pane implied one coherent view, but Ch.10 gives every task its own isolated branch behind a serialized merge queue | **dde-integration** module: branch/queue awareness, conflict surfacing (§4.2) |
| G2 | No surface for `Approval`, `StandingApproval`, or the overnight-autonomy pattern Ch.13 is built around | **dde-approvals** module: approval queue, standing-approval config, morning review (§4.1) |
| G3 | No module appeared in Ch.18's S0–S7 build plan | Module-by-module staging table against real `DDE-0xx` milestones (§3.1), corrected against what's actually in this repo today (§2) |
| G4 | Silent on where the extension actually runs | Delivery-mode analysis + validation spike (§3.2) |
| G5 | Chat design assumed the VS Code Chat Participant API, unsupported/partial in Cursor | Webview-first chat design, backed by a **specific, reproducible 2026 Cursor defect** (§3.3), not just a compatibility guess |
| G6 | Appendix A registers Cursor itself as a certified worker profile — collides with "Cursor as the human's IDE" | Naming/identity decision, made explicit with a recommended default (§3.4) |
| G7 | Routing panel scored all candidates uniformly; Ch.6's gates 0–5 are hard eliminations, not low scores | Redrawn panel separating elimination from ranking (§5.1) |
| G8 | Context panel showed invented percentage metrics with no basis in Ch.5 | Redrawn panel using the real coverage contract and index-lag fields (§5.2) |
| G9 | Verification panel skipped stages and showed no independence signal | Redrawn panel with the full Ch.11 chain and generator/verifier independence badge (§5.3) |
| G10 | Worker panels exposed only **[Stop]**; the real `WorkerRun` lifecycle supports pause/checkpoint/resume | Lifecycle-correct worker panel actions (§5.4); harness views are Mission Control / fleet-manager rooms |
| G11 | No view of the running product itself | **ProductEnvironment** / preview surface (§6.1) |
| G12 | No commitment on credential handling in the extension | Explicit commitment against Ch.14 rules + concrete `SecretStorage` implementation (§6.2, §3.3) |
| G13 | Donor provenance mentioned but never shown | Classification badges from Ch.13.8's taxonomy (§6.3) |
| **R1** *(new)* | No audit of what already exists in this repo | §2 — line-by-line reconciliation against `interfaces/dde-studio` |
| **R2** *(new)* | No answer for how to actually implement 11 modules without it becoming unmaintainable | §3.5 — webview architecture pattern (shared React `webview-ui`, typed message bridge), modelled on the real architecture of Cline/Roo Code, the two most relevant prior-art extensions |
| **R3** *(new)* | No transport story for "real, not mocked" data before the Gateway exists (S3) | §3.1a — CLI-JSON transport bridges S1 through S3 |
| **R4** *(new)* | §1.5.4 said MCP arrives "Stage 3"; Ch.18.3 places `DDE-042` at S5 | **Resolved** — Ch.18.3 wins; blueprint text corrected (§1) |

---

## §1 Blueprint fix already applied

`docs/blueprint/historical/REV_2_0.md` §1.5.4 said *"Once DDE has an MCP server (Stage 3)..."* while
Ch.18.3 places `DDE-042` ("DDE MCP server") under **S5**. These are inconsistent, and the
inconsistency matters here because it decides when this plan's MCP-tool integration
(originally §2 of the chat-export plan) becomes real instead of aspirational.

**Resolution: S5 is correct.** Ch.15.6 is explicit that *"No MCP task bypasses Mission
Kernel, policy, leases or verification"* — every MCP tool call re-enters the same pipeline a
native call would. That pipeline isn't safely exposable to an external protocol until:

- the Gateway exists (`DDE-027`, S3) to authenticate and scope a connection at all,
- the capability/lease enforcement plane exists (`DDE-016`–`018`, S2) to bound what an MCP
  tool call can actually do, and
- durable run/approval semantics exist (S3) so an MCP-initiated action has the same
  idempotency and recoverability guarantees as any other.

S5's own gate ("MCP server passes contract suite", Ch.18.2) already assumes all of that is
in place. §1.5.4 has been corrected in place to say **Stage 5** and cite `DDE-042`
directly, so Cursor's own MCP configuration guidance in Chapter 1 now agrees with Chapter 18.
No other blueprint change was made.

---

## §2 Reconciliation against `interfaces/dde-studio`

This repo already has a running scaffold, not a blank slate. Before scoping anything new,
here's what it actually is today, read directly from `interfaces/dde-studio/src/`:

| File | What it does now |
|---|---|
| `extension.ts` | Activation, command registration, wires health polling to status bar + Overview + Connection + module webviews |
| `connection/settings.ts` | Resolves `dde.studio.{coreUrl,cloudUrl,preferredTarget,pollIntervalMs}` from VS Code config |
| `connection/healthClient.ts` | Polls `/healthz` + `/readyz` only — the one live, non-stub data source that exists |
| `connection/stubGateway.ts` | Explicitly-labelled stub client; every method has a `TODO(Stage-later)` pointing at the Ch.15 endpoint it will call |
| `status/statusBar.ts` | One status bar item, 5 states (`idle/checking/ok/unreachable/misconfigured`) |
| `shared/ui/overview.ts` | **Main Dashboard (Mission Overview)** — primary home: System, Missions, Spine, Work in flight, Fleet, Approvals, Verification, Integration, Activity, Attention; operator buttons disabled until Gateway |
| `webviews/html.ts`, `webviews/providers.ts` | Shared HTML + `WebviewViewProvider`/`WebviewPanel` per harness (Hermes / Claude Code / DeepSeek) as Mission Control rooms |

**This is a clean, honest S1-shaped skeleton**, and it already gets several things right that
the original chat-export plan didn't have to invent:

- It never touches Core tables or imports `engine/**` — client-only, exactly per
  `AGENTS.md`'s boundary rule.
- It names harnesses by **Appendix A role**, not by pretending a vendor product is embedded
  in Core (`appendixRole` field on `HarnessProfile`) — this is G6's naming discipline,
  already half-applied to the worker side.
- It puts dashboards behind the **activity bar**, not a secondary sidebar — which turns out
  to matter concretely: Cursor reserves its secondary sidebar for its own agent UI, and
  extensions that try to contribute a view container there simply fail to load in that
  panel (§3.3). The scaffold's activity-bar-container choice was right by construction.
- The stub client is scrupulous about not inventing REST shapes — every stub method cites
  the Ch.15 endpoint it's a placeholder for.

**What's genuinely missing, cross-referenced against what's real in the repo right now:**

1. `interfaces/api/__init__.py` is an **empty package** — there is no Gateway/REST
   implementation yet at all. `engine/missions`, `engine/context`, `engine/routing`,
   `engine/execution`, `engine/workers`, `engine/planning`, `engine/truth`, `engine/audit`,
   `engine/events`, `engine/workspaces`, `engine/environments`, `engine/governance` all have
   real scaffolding (tables, services, repositories, state machines) — the Core-side S1
   subsystems are substantially underway. The **client-facing transport** (`DDE-027`
   Gateway, S3) is the piece that doesn't exist yet, and it's the one every stub method in
   `stubGateway.ts` is waiting on.
2. `engine/workers/adapter.py` + `scripted_adapter.py` exist, but `adapters/cursor/**`
   (named in Appendix A as the reference Cursor worker adapter) does **not** exist in this
   repo yet, despite being referenced as if certified. Worth knowing before §3.4's naming
   decision is acted on: there's no adapter code today whose naming needs to be fixed —
   only the blueprint text and, later, the panel copy.
3. None of the 13 modules from the original plan (`dde-mission`, `dde-integration`,
   `dde-context`, `dde-routing`, `dde-workers`, `dde-verification`, `dde-approvals`,
   `dde-donor`, `dde-knowledge`, `dde-evaluation`, `dde-debug`, `dde-chat`,
   ProductEnvironment view) existed as named surfaces at first scaffold — the client now
   has rich empty shells for those modules **plus** a **Main Dashboard (Mission Overview)**
   as the primary activity-bar home (ahead of Connection), with honest empty lists and
   disabled operator commands until Gateway/CLI.

### §2.1 What this changes about sequencing

The original review's staging table (reproduced and kept at §3.1) assumed the extension
would be scoped from nothing. Given the actual state above, the corrected read is:

- **Renaming, not rebuilding, gets you `dde-mission`, `dde-workers` (basic) faster than a
  from-scratch build would** — the Connection view + harness dashboards are architecturally
  the right shape (`WebviewViewProvider` + activity bar + shared HTML helper); they need
  real data sources, not a redesign.
- **`dde-integration` (G1) is genuinely new** — there's nothing today about branches, queue
  state or "which workspace am I viewing." It's also the cheapest of the new modules to
  build once `DDE-013` (merge queue) exists, per the original review, and it's the module
  most worth building first once there's anything real to show.
- The blocking dependency for *everything* beyond health checks is `interfaces/api` — until
  something exposes mission/task/route/worker/verification state over a stable interface,
  every dashboard is either a stub or has to talk to Core some other way. §3.1a covers the
  bridge for that gap.

### §2.2 Reconciliation table

| Original module | Maps to existing code | Action |
|---|---|---|
| `dde-workers` (fleet, single profile) | `webviews/providers.ts` `HarnessViewProvider`/`HarnessPanel`, `shared/ui/missionControl.ts`, `stubGateway.ts` | Extend, don't replace. Each harness is a Mission Control / fleet-manager surface (status, activity, routing, observability, control). Swap `StubGatewayClient` for a real client once §3.1a's transport exists. |
| `dde-core-ui` (shell, connection status) | `extension.ts`, `status/statusBar.ts`, `connection/*`, **`shared/ui/overview.ts` (Mission Overview primary home)** | Already exists. Overview is first activity view; Connection remains health/auth. Add branch indicator (G1) when real. |
| `dde-mission` | *(none)* | New view, same `WebviewViewProvider` pattern. |
| `dde-integration` | *(none)* | New — see §4.2. |
| `dde-context`, `dde-routing`, `dde-verification` | *(none)* | New panels; corrected mockups at §5.1–§5.3. |
| `dde-approvals` | *(none)* | New — see §4.1. |
| `dde-chat` | *(none)* | New — webview-first per §3.3, not Chat-Participant-first. |

---

## §3 Engineering research: building this against the real 2026 extension host

The original plan's biggest risk wasn't architectural — it was assuming API surfaces without
checking their current, real behavior in the specific host (Cursor) this will run in daily.
Here's what's actually true as of this review.

### §3.1 Stage mapping (kept from the original review, corrected per §2)

Mapping each module to the earliest stage it can be built against **real** telemetry, not a
mock — per Ch.18.1 Rule 1 (*"A subsystem that cannot be exercised by the golden mission is
not started"*):

| Module | Earliest real stage | Depends on |
|---|---|---|
| `dde-mission` | **S1** | Mission Kernel + TaskGraph (`DDE-006`/`007`) — Kernel scaffolding exists (`engine/missions/`); TaskGraph/Planner does not yet |
| `dde-integration` | **S1** | Merge queue + WriteScopeLease (`DDE-013`) — not yet built |
| `dde-context` (basic) | **S1** | DCE with free/cheap retrievers (`DDE-008`) — `engine/context/` scaffolding exists |
| `dde-routing` (basic) | **S1** | Deterministic router (`DDE-009`) — `engine/routing/` scaffolding exists |
| `dde-workers` (single profile) | **S1** | First certified profile (`DDE-011`) — `engine/workers/` scaffolding exists, no certified profile yet |
| `dde-verification` (basic) | **S1** | AcceptanceOracle v1 (`DDE-012`) — not yet built |
| `dde-core-ui`, `dde-chat` (Gateway-bridged) | **S3** | Gateway, REST/WS API, session + reconnect (`DDE-027`) |
| `dde-approvals` | **S3** | Approvals, standing approvals, attention budget (`DDE-026`) |
| `dde-workers` (fleet comparison) | **S3** | Second/third worker adapters (`DDE-025`) |
| `dde-context` (Critic, coverage gates) | **S4** | Context Critic (`DDE-031`) |
| `dde-routing` (propensity, learning state) | **S4** | Routing telemetry (`DDE-035`) |
| `dde-verification` (mission oracle) | **S4** | Mission AcceptanceOracle (`DDE-037`) |
| ProductEnvironment / preview | **S4** | ProductEnvironment lifecycle (`DDE-038`) |
| `dde-knowledge` | **S4** | Knowledge graph (`DDE-033`) |
| `dde-donor` | **S5** | Donor Lab (`DDE-046`/`047`) |
| `dde-evaluation` | **S4 → S7** | Eval corpus (`DDE-032`), learning promotion (`DDE-057`–`058`) |
| `dde-debug` | **S1+** | Useful from the start |

Practical read, unchanged from the original: a thin extension (mission/task view, basic
context, basic routing, single-worker status, basic verification, `dde-integration`) is
realistic once S1 is running end to end. Chat and richer panels need the Gateway (S3).
Approvals is S3. Fleet dashboards, Context Critic, donor tooling are S4–S5.

### §3.1a The transport bridge for S1 (CLI-JSON, not Gateway)

`DDE-015` (CLI) is an S1 deliverable; `DDE-027` (Gateway) is S3. That gap matters for the
extension specifically: **the modules staged at S1 above have nothing to talk to over HTTP
until S3.** The blueprint's own S1 exit gate names the bridge: *"`dde mission trace`
reconstructs every step"* (Ch.18.2). The extension's S1-era data source should be the same
one a human would use at a terminal — invoke the `dde` CLI as a subprocess with a
machine-readable output flag (e.g. `dde mission trace <id> --json`) and parse structured
output, the same pattern VS Code's own Git extension uses to talk to the `git` binary before
falling back to richer transports.

This is why `dde-integration`, `dde-mission`, `dde-context` (basic), `dde-routing` (basic),
`dde-workers` (single profile) and `dde-verification` (basic) can be **real at S1** despite
Ch.18.3 not listing the Gateway until S3: they're not waiting on the Gateway, they're waiting
on the CLI having something to show, and on the CLI itself emitting `--json`. That's worth
confirming as a CLI requirement when `DDE-015` is scoped — it costs nothing extra to add a
JSON output mode to a CLI that already needs structured internal state, and it's what turns
this extension's roadmap from "blocked until S3" into "useful from S1."

At S3, swap the CLI-subprocess data source for the Gateway REST/WS client without changing
any panel — this is exactly what the `StubGatewayClient` abstraction in the existing scaffold
is already shaped to allow; only its implementation changes.

### §3.2 Delivery mode: where does this actually run?

The original plan never stated a host. Verified facts, current as of this review:

| Host | Extension host capability | Verdict |
|---|---|---|
| **VS Code Desktop**, full install | Full — every contribution point works | Not available without a local machine |
| **vscode.dev / github.dev** (pure browser) | Web-extension mode: no Node APIs, no local processes | Too limited — can't run the CLI-subprocess bridge in §3.1a |
| **GitHub Codespaces, via browser** | Full desktop-grade extension host on the Codespace's Linux container | Matches Ch.1 Step 3 and Ch.17.6's No-PC path already |
| **Cursor Desktop** | Near-full VS Code extension compatibility (~90% of the ecosystem per current comparisons); Microsoft-proprietary extensions (Pylance, C# Dev Kit, Remote-SSH, Live Share) are unavailable; the Chat Participant API is present but **partially implemented** (§3.3) | Everything in this plan except a native `@dde` chat participant works here |

Two consequences, unchanged from the original review:

1. **Target Codespaces-in-browser as the primary host.** This just confirms what Ch.1 Step 3
   and Ch.17.6 already committed to.
2. **Cursor's secondary sidebar is reserved for its own agent UI.** Confirmed directly:
   extensions that register a view container there fail to load in that panel; the primary
   activity bar (what `dde-studio` already uses) is the only reliable placement. No change
   needed — just confirms the existing choice was correct.

**Cheap validation before committing further:** the one-day spike from the original plan
(one Tree View, one Webview, one command, loaded in both a Codespace-backed browser session
and Cursor Desktop) is still worth doing, but the `dde-studio` scaffold already *is* that
spike — it has run in both environments in some form already. Treat the spike as "extend the
existing scaffold with one new real view and confirm it still loads cleanly in both hosts,"
not "build a throwaway prototype from zero."

#### Exception / delivery amendment (user-requested, 2026-08-20)

**Standalone Electron EXE is now a supported delivery path alongside the extension suite.**
The original review preferred the extension host and treated a competing Electron app as
deprecated. Product direction overrides that: Windows users must be able to double-click
**DDE Code** without opening VS Code or Cursor.

- **Primary Windows distribution:** `packaging/windows` → `DDE-Complete-Setup-*.exe`
  (Inno). One package installs DDE Code under `Program Files\DDE\dde-code\`, Core image tar,
  compose stack, and `DdeSetupWizard.exe`. First run in DDE Code offers the wizard, then
  **Start local Core**.
- Implementation (UI): `interfaces/dde-studio/desktop/` (also builds optional UI-only NSIS +
  portable for Cursor hosts that already have Core).
- Shared UI: `interfaces/dde-studio/shared/` — health client, stubs, module registry, HTML
  pages used by both the extension and the EXE.
- Honest Core boundary unchanged: Postgres, Redis, workers, and Gateway still live in Docker.
  DDE Code does not embed the stack; it shells to `Start-DdeLocal.ps1` / the wizard from the
  same install root.
- Full Code - OSS fork remains out of scope.

The extension suite is **not** replaced. Cursor/VS Code remains an optional authoring host;
the complete installer is the standalone Windows product.

### §3.3 Chat: hard evidence, not a compatibility guess

The original plan's whole chat design assumed `vscode.chat.createChatParticipant`. Current
finding, and it's sharper than "unsupported": **Cursor implements `createChatParticipant`
but returns a `ChatParticipant` object missing at least one real method
(`onDidReceiveFeedback`)**. Multiple third-party extensions (MongoDB for VS Code, Nx Console)
crashed their *entire activation* in 2026 because they called that method unconditionally
right after creating the participant — a single unguarded call took down unrelated,
non-chat functionality in the same extension. Cursor has acknowledged this as a confirmed
bug with no committed fix date at time of writing.

This changes the engineering rule from "feature-detect the API" to something stricter:

- **Never call any method on a created `ChatParticipant` without checking it exists first**
  (`if (typeof participant.onDidReceiveFeedback === "function")`), or wrap the whole
  post-creation configuration block in `try/catch` and log-and-continue on failure. A missing
  method must never be allowed to throw past extension activation.
- Treat chat-participant registration as **strictly additive and isolated**: register it in
  its own `try/catch` inside `activate()`, after all other views/commands/status bar items
  are already registered, so a chat-participant failure can never prevent the rest of the
  extension (mission tree, integration view, worker dashboards) from loading. This is a
  direct lesson from watching two real extensions get this wrong in production in 2026.
- Build `dde-chat` as a **`WebviewViewProvider` panel first** — own message protocol, own
  slash-command parsing in extension-host code, not VS Code's chat infrastructure. This
  works identically in Cursor and VS Code and has zero dependency on an API that's
  demonstrably still shifting under real extensions' feet. Register the native Chat
  Participant *in addition*, gated by the try/catch above, so real VS Code / Codespaces-web
  gets the nicer built-in integration where it's actually solid.
- Re-verify this at build time, not from this document — both editors ship continuously and
  this specific defect may be fixed by the time `dde-chat` is scheduled (S3).

### §3.4 The Cursor naming collision — recommended resolution

Appendix A lists a certified worker profile: *"Cursor models / agent (first certified
implementation worker) — `adapters/cursor` over `cursor-sdk` + `cursor-sdk-bridge` — T2,
local runtime only, `auto_create_pr` forbidden, API key never enters the
ExecutionEnvironment."* That's Cursor acting as an autonomous **worker** DDE dispatches tasks
to. This plan proposes Cursor as the **human's interactive host**. Same name, different role.

Confirmed while reconciling against the repo (§2): `adapters/cursor/**` does not exist yet.
**This is the cheapest possible moment to fix the naming** — before any code, UI copy, or
Appendix A cross-reference is built around it.

**Recommended default**, to unblock `dde-workers` before it ever needs a Cursor-profile card:

- The Cursor **worker** adapter, when it's built, is scoped to a headless/detached
  `cursor-sdk` agent session — structurally distinct from the interactive Cursor app the
  developer is typing in, consistent with the T2 containment Appendix A already requires
  (an interactive desktop session the human is actively using is not an isolated,
  unattended environment).
- In every DDE Code UI surface, that worker profile is always labelled **"Cursor Agent"**,
  never bare "Cursor." The extension host itself is never named in-product — panels say
  "your editor," not "Cursor," so the two meanings never collide under one label the
  developer sees.
- This is a naming/copy decision only; it does not require re-deciding anything about
  `adapters/cursor`'s actual runtime scoping, which is unbuilt and out of this document's
  scope.

### §3.5 UI implementation pattern — what "the perfect DDE Code" is actually built from

The relevant prior art here isn't a design inspiration exercise — Cline and Roo Code are the
two most architecturally similar shipping extensions (autonomous multi-surface AI control
panels inside VS Code), and their real, documented architecture is directly applicable:

- **A single shared `webview-ui` package** (React + Vite), not one hand-written HTML string
  per view. `interfaces/dde-studio/src/webviews/html.ts` is fine today at 2 view types
  (Connection, Harness) with manual `escapeHtml` calls — it will not scale cleanly to 11+
  modules with real interactivity (approve/reject buttons, branch trees, live-updating
  queues). The concrete signal to migrate is **`dde-integration` + `dde-approvals`**: both
  need stateful, multi-action UI (§4.1, §4.2) that outgrows string-templated HTML with
  `data-cmd` attributes.
- **One typed message contract** between extension host and webview (`StudioMessage` already
  exists as a start — extend its discriminated union rather than inventing a second
  protocol). Cline/Roo Code wrap this in generated gRPC-over-`postMessage` stubs; that's more
  machinery than this project needs at this scale, but the principle — one typed envelope,
  one state-sync path, webview never trusts anything it wasn't explicitly sent — is worth
  keeping from day one.
- **A single state-sync source of truth in the webview** (their `ExtensionStateContext`
  pattern) once the React migration happens, so panels re-render from one pushed state
  object instead of each view independently polling.
- Keep the **extension-host side thin**: no business logic, no policy decisions — it renders
  what Core/Gateway/CLI already decided, per REV 2.0 Ch.15.1's own Gateway design ("It never
  owns Project Truth or mission state") applied one layer further out. Correct as designed;
  worth stating as an explicit constraint on the webview layer too, not just the Gateway.

**Concretely, do not do the full React migration yet.** The current scaffold's approach is
appropriately minimal for what exists today (2 view shapes, no real data). Migrate when
`dde-integration` or `dde-approvals` is actually being built — introducing the React/Vite
toolchain now, before there's a second module that needs it, would be exactly the
"scaffolding that doesn't earn its place" Ch.16.4/Ch.18.6 warn against, applied to this
codebase instead of DDE's own.

### §3.6 Credentials — concrete implementation, not just a commitment

Ch.14.3 and Ch.14.5.8 forbid a secret ever entering a prompt, event, log, artifact or error
payload, and require credential material to be redacted before storage. This extension
renders Evidence, WorkerEvents and context items in webviews — screen-shareable,
screenshot-able surfaces — so two separate commitments are needed:

1. **What the extension renders:** it renders only what the server already scrubbed. It
   never attempts client-side redaction as a substitute for that scrubbing, and never
   fetches or displays a raw secret value even if an API technically returned one.
2. **What authenticates the extension itself:** today (`healthClient.ts`) there is nothing to
   store — `/healthz`/`/readyz` are unauthenticated. When Ch.15.2's Bearer/OIDC session
   lands (S3, alongside the Gateway), the session token must go into
   **`context.secrets`** (VS Code's `SecretStorage` API — OS keychain on all platforms,
   including remote/Codespaces, which don't have a local keychain but are handled
   transparently by the same API), never into `dde.studio.*` settings. It's worth adding a
   thin `connection/authService.ts` stub now (mirrors `connection/settings.ts`'s shape) so
   the seam exists before S3, rather than retrofitting secret storage onto a settings-based
   auth flow later.

---

## §4 Two modules the plan is missing

*(Kept largely as originally reviewed — these are correct against Ch.10 and Ch.13 and
nothing in §2's reconciliation or §3's research changes them.)*

### §4.1 `dde-approvals` (new)

Ch.13 is one of the densest chapters in the blueprint and none of it was represented in the
original plan. `Approval` has eight types; `StandingApproval` is the mechanism that makes
overnight autonomy safe; "attention debt" is a named, targeted metric (Ch.13.4, *"zero at
start of each working day"*). Given the working pattern this project is built around — kick
off work, step away, come back — this belongs in the editor more than almost anything else
in this plan.

```
DDE APPROVALS                                    Attention debt: 0 (Ch.13.4 target)
Pending (2)
┌──────────────────────────────────────────────────────────────────┐
│ scope_widening      MISSION-ERP-000421   requested 14m ago        │
│   Task wants to touch payments/** — outside declared scope        │
│   [Approve]  [Reject]  [View plan]                                 │
├──────────────────────────────────────────────────────────────────┤
│ irreversible_effect TASK-00430           requested 2m ago         │
│   Send supplier notification email — cannot be undone              │
│   Never pre-authorised (Ch.13.2) — needs your decision now        │
│   [Approve]  [Reject]  [View plan]                                 │
└──────────────────────────────────────────────────────────────────┘
Overnight run — configure a StandingApproval before you step away
  Blast radius ≤  [module ▾]     Risk ≤   [medium ▾]
  Cost ceiling    [$8.00]        Task count ≤ [6]
  Valid until     [07:00 tomorrow]
  Always excluded: IRREVERSIBLE effects, production changes, scope widening
  [Grant standing approval]                     [Revoke all — immediate]

> DDE: Morning Review — what ran overnight, what's blocked, and
                         today's attention debt, first thing tomorrow
```

Every field is a real column on `Approval`/`StandingApproval` (Ch.13.1–13.2). "Always
excluded" reflects the hard rule that a standing approval can never pre-authorise an
`IRREVERSIBLE` effect, a production change, a scope widening, or a `critical`-risk action —
the UI makes that non-negotiable, not just documented. `DDE: Morning Review` is a command,
not a dashboard you'd have to remember to check.

### §4.2 `dde-integration` (new)

Ch.10.1's first principle: *"Workers never write to a shared branch. A worker writes only
inside its own workspace."* The branching model is `main` → `mission/<id>` → `task/<id>-a/b/c`,
integrated one at a time through a serialized queue (Ch.10.4) with five conflict classes
(Ch.10.5). If a harness has twelve subagents running, they're not twelve cursors in one file
— they're twelve isolated worktrees, most not currently being looked at. A single
"CODE / DIFF / TERMINAL" pane never says which of these the developer is viewing, which is
the single most important orientation fact in a multi-agent editor.

```
DDE INTEGRATION — mission/ERP-000421
Queue (serialized — one proposal integrates at a time, Ch.10.4)
┌──────────────────────────────────────────────────────┐
│ 1  TASK-00421  VALIDATING          scope: inventory/**│
│ 2  TASK-00419  QUEUED              scope: reports/**  │
│ 3  TASK-00417  CONFLICT (semantic) ⚠ needs repair     │
└──────────────────────────────────────────────────────┘
Branches
main            ── protected, integration-manager only
 └ mission/ERP-000421 ── 3 tasks integrated, 1 conflicted
    ├ task/00421-a   ← you are viewing this workspace, not main
    ├ task/00419-a   queued
    └ task/00417-a   conflict: semantic — post-integration tests failed

[View mission branch]  [View main]  [Open conflict TASK-00417 → repair task]
```

"You are viewing this workspace, not main" is the whole point of this module — and per
§3.5, this queue view (multi-row live state, per-row actions) is one of the two modules
that justifies migrating off hand-written HTML strings when it's built.

The top-level shell mockup, updated with both new modules:

```
┌──────────────────────────────────────────────────────────────────┐
│ DDE Code        mission/ERP-000421 ▾   main +142 -38  ● Connected │
├──────────┬───────────────────────────────────────┬───────────────┤
│ DDE      │                                       │ DDE Inspector │
│ Mission  │          CODE / DIFF / TERMINAL       │               │
│ Tasks    │                                       │ Context       │
│ Context  │          Your ERP / DDE code          │ Routing       │
│ Workers  │                                       │ EDR           │
│ Verify   │                                       │ Evidence      │
│ Integr.  │  ← new (G1, §4.2)                     │ Verification  │
│ Approvals│  ← new (G2, §4.1) · 2 pending          │               │
│ Donors   │                                       │               │
│ EDR      │                                       │               │
│ Evaluate │                                       │               │
├──────────┴───────────────────────────────────────┴───────────────┤
│ DDE Chat: "Implement TASK-00421"                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## §5 Corrections to existing panels

*(Kept from the original review — grounded directly in Ch.6, Ch.5, Ch.11, Ch.8. Unaffected
by §2/§3's additions except where noted.)*

### §5.1 Routing panel

Ch.6.1's pipeline has a hard boundary: gates 0–5 are pass/fail (*"a candidate that fails any
of gates 0–5 is removed, not penalised"*); only gates 6–7 produce a score. Showing an
eliminated candidate next to a score implies it was merely outscored, not structurally
ineligible — a materially more reassuring, and wrong, story. It also matters for
**[Override]**: overriding among ranked survivors is legitimate; overriding a hard-gate
elimination shouldn't be an option the UI presents at all.

```
DDE ROUTING                                     selection_source: deterministic
Task: Implement inventory adjustment           workload_class: bulk_implementation
Risk: Medium                                          policy: ERP-IMPLEMENTATION-v4

Gates 0–5 — hard; a failure here is elimination, never a lower score
  DeepSeek   ✓ all gates
  Claude     ✓ all gates
  Hermes     ✗ eliminated at gate 3 — worker eligibility (no certified Kotlin profile)

Gates 6–7 — only survivors are scored and ranked
  DeepSeek   0.91 predicted success · low cost      ← selected
  Claude     0.87 predicted success · high cost

reason_codes: capability_fit · cost_advantage · low_ambiguity
fallback_plan: Claude        escalation_plan: Claude, after 2 verification failures

[Ask DDE why]   [Override — ranked candidates only]   [Escalate to Claude]
```

Once `selection_source` moves past Stage 1 (Ch.6.9), add a badge for whether the route came
from the certified deterministic policy, shadow learning, canary, or a promoted historical
policy — lets a developer trust or specifically distrust a route while learned routing is
still being proven out.

### §5.2 Context panel

The real coverage contract (Ch.5.8) is seven categories, each `satisfied | partial |
missing`, and any `missing` blocks autonomous execution outright. A single percentage hides
exactly which category is short.

```
DDE CONTEXT                     index_version: v14   lag: 2 commits behind HEAD
Mission: ERP-00421
Requirements: REQ-INV-001, REQ-INV-017
Feature DNA: Inventory Adjustment
EDRs: EDR-024, EDR-031
Business Rules: BR-INV-004, BR-INV-009
Related components: InventoryService, StockLedger, SyncQueue
Donor evidence: DONOR-17 (OPEN_REUSE)

Coverage (Ch.5.8 — any "missing" blocks autonomous execution)
  authoritative_requirements   satisfied
  applicable_domain_rules      satisfied
  impacted_code_and_deps       satisfied
  architecture_constraints     satisfied
  security_constraints         partial   ⚠ 1 unresolved question
  verification_obligations     satisfied
  known_unresolved_questions   "Is negative adjustment allowed pre-close?"

Context Critic: not triggered — risk medium, blast radius = module (Ch.5.9)
[Ask DDE why this file]  [Request more context]  [Show conflict, if any]
```

`index_version`/`lag` (Ch.5.4) are more actionable than a "Freshness" percentage — "2 commits
behind" is something a developer can act on. Showing whether the Context Critic fired (and
why) also surfaces a cost-relevant subsystem explicitly budgeted and capped (Ch.16.4: critic
invocation share ≤ 30% of tasks).

### §5.3 Verification panel

The real chain (Ch.11.1) is thirteen stages. It also needs a way to show Ch.11.4's
independence rule: a worker that wrote the code cannot be the sole judge of it, and
co-authored tests don't satisfy an oracle on a high-risk task. A green board that's secretly
self-graded is worse than a red one.

```
VERIFICATION — TASK-00421                          full chain, Ch.11.1
  Build                PASS
  Static analysis      PASS         Semgrep
  Diff gates           PASS         secrets · licence · forbidden-path
  Unit                 42/42
  Contract               1/1
  Integration           17/18
  E2E/browser           PASS
  Visual                PASS
  Security              PASS
  Domain invariants     23/24       ⚠ posting_balance — financial, needs your eyes (Ch.11.5)
  AcceptanceOracle      REPAIR      outcome "supplier_tax_rounding_correct" failed
  Requirement trace     18/18
  EDR consistency       PASS

  failure_class: VERIFICATION_FAILURE → repair, then re-verify (Ch.12.3)
  independence: tests co_authored by DeepSeek (same worker as the implementation) —
                not sufficient alone at this task's risk_class; Claude judge review
                pending (Ch.11.4)

  Task oracle: REPAIR      Mission oracle: not yet evaluated — task incomplete
[View failing outcome]  [View diff]  [Repair task: auto-queued]
```

The task/mission oracle split matters beyond cosmetics: if every task oracle eventually
passes but the **mission** oracle fails, that's `WRONG_PRODUCT` (Ch.11.3) — the mission
replans, it's not a repair loop. Those two outcomes should never look the same in the UI.

### §5.4 Worker panels / harness Mission Control

`WorkerRun`'s real lifecycle (Ch.8.2) is `PLANNED → PREPARING → READY → RUNNING →
COMPLETED|FAILED`, with `RUNNING` able to go to `CHECKPOINTING`, `PAUSING/PAUSED/RESUMING`, or
`CANCELLING/CANCELLED`. A single **[Stop]** button maps only to `cancel`; pause-and-checkpoint
is a first-class, safe operation the UI should offer.

**Design intent (authoritative for DDE Code):** each harness view (Hermes / Claude Code /
DeepSeek) is a **Mission Control and agent fleet manager** control room for that Appendix A
role — not a thin catalog card. Shared chrome across the three fleets:

1. **Standardised status reports** — fleet status strip (Core health live; mission/run
   counters bind when APIs exist)
2. **Unified event/activity streams** — audit / worker / outbox activity for this role
3. **Task routing** — Ch.6 gate elimination vs ranking into this fleet
4. **Agent observability** — missions, WorkerRuns, health for this fleet
5. **Agent control rooms** — lifecycle-correct pause/checkpoint/resume/cancel (disabled with
   honest reasons until Worker Manager APIs exist)

Do not invent fake missions, runs, or events. Empty states + live Core `/healthz`/`/readyz`
only for connection. Structure panels with stable `data-section` / `data-bind` hooks so
Gateway/CLI can bind cleanly later. Implementation lives in `shared/ui/missionControl.ts`
so extension and Electron stay in parity.

```
CLAUDE WORKER                         profile: claude-architecture-v1 · Standard-certified
Mission: M-421          run_id: run_9f2a          state: RUNNING
Task: Architecture review
Context: 87% of budget          Tools: Git, LSP, Terminal, DDE MCP
Current phase: Comparing architecture alternatives
Proposals: 1   Risks: 2   Cost so far: $1.84 of $6.00

[Inspect Context]  [View Diff]  [Review Findings]
[Pause → checkpoint]  [Resume from checkpoint]  [Cancel]
```

Same correction applies to every harness Mission Control already in the scaffold (Hermes,
Claude Code, DeepSeek). Two more fixes worth folding in while touching these:

- The autonomy toggle should read from the real 0–6 `autonomy_ceiling` scale (Ch.13.5), and
  selecting an overnight-capable level should open the standing-approval form in §4.1 rather
  than being a bare status dot.
- A worker-fleet "Active: 4 / 12" row should be scope-labelled (e.g. "Active (project)") so
  it doesn't misread against the per-mission/per-project concurrency ceilings in Ch.4.7
  (defaults 4 and 8). Add a **Certification** row (Smoke/Standard/Full/`STALE`) — a `STALE`
  profile (Ch.8.5) is *"selectable in development, not selectable by production routing,"*
  and that's a one-glance fact, not something to dig for.

---

## §6 New capabilities worth adding

### §6.1 ProductEnvironment / preview panel

Ch.11.6 defines `ProductEnvironment` with a real `base_url`, class
(`ephemeral_preview/integration/staging/production`) and TTL. A simple version: a panel or
status-bar item showing the current mission's `ephemeral_preview` status
(`PROVISIONING → READY → IN_USE`), its `base_url` as a clickable link, and time-to-live
before teardown. Given the whole point of this suite is a cockpit for watching DDE build
something, clicking through to the actual running result without leaving the editor is
high-value and the data already exists in the model.

### §6.2 Credential handling commitment

Covered concretely in §3.6 — restated here as the product commitment: this extension never
becomes the first place secret material could leak. It renders only what the server has
already scrubbed (Ch.14.3, 14.5.8), and its own session credential lives in `SecretStorage`,
never in a settings file.

#### Claude Code auth (product clarification)

**Primary:** Claude Code uses a **Claude.ai subscription** via the official CLI
(`claude auth login` / browser OAuth for email, GitHub, or Google; optional
`claude setup-token` for a long-lived `CLAUDE_CODE_OAUTH_TOKEN`). The Windows
setup wizard (`packaging/windows/DdeSetupWizard`) and DDE Code Connection /
Claude Code Mission Control invoke those official commands and verify with
`claude auth status` — they do **not** embed Anthropic IdP credentials.

**Backup only:** an Anthropic API key may be collected under an explicit
advanced/backup control when subscription login is unavailable
(`claude_code.auth_mode = subscription | api_key_backup` in appliance config).

**Honesty / limitations (2026-08):** Anthropic does not publish a third-party
OAuth client for Claude Code subscriptions
([authentication](https://code.claude.com/docs/en/authentication)).
Device-code auth is not available. DDE never shows “signed in” without a
verified `claude auth status` JSON (`loggedIn: true`) or a shape-validated
setup-token (`sk-ant-oat01-…`) in SecretStorage / Electron safeStorage /
Windows Credential Manager. Passwords are not collected or logged.

**What works now vs what Anthropic still blocks**

| Works now | Still blocked / deferred |
|---|---|
| `claude auth login` + `claude auth status` verify | Embeddable email/GitHub/Google IdP (no public OAuth client) |
| Paste/store `claude setup-token` as secure ref | Device-code (RFC 8628) — open request upstream |
| API key backup (`auth_mode=api_key_backup`) | Broker `register_delegated_session` (EDR-0001 Path B) |
| Config metadata (email, plan, refs — not raw secrets) | Worker forwarding of OAuth tokens (forbidden by EDR-0001 Path A) |

### §6.3 Donor provenance badges

Ch.13.8 defines six classification states (`OPEN_REUSE, CONDITIONAL_REUSE,
SOURCE_REFERENCE_ONLY, RESTRICTED, UNKNOWN, REJECTED`) with taint that propagates visibly. The
inline badge already sketched into §5.2's Context panel redraw (`DONOR-17 (OPEN_REUSE)`)
closes this gap for free once that panel is built; the donor dashboard can show the same
badge at repository/module level.

---

## §7 Revised module map

| Module | Role | Depends on (Ch.) | Earliest real stage | Repo status today |
|---|---|---|---|---|
| `dde-core-ui` | Shell, **Mission Overview (primary home)**, connection status, branch indicator | 15 | S1 (basic), S3 (auth) | **Exists** — Overview + Connection; extend |
| `dde-chat` | Webview-first chat, Chat Participant as gated enhancement | 15, §3.3 | S3 | Not built |
| `dde-mission` | Mission/Tasks tree, TaskGraph state | 4 | S1 | Not built; nearest analogue is the harness dashboards |
| `dde-integration` | Branch/queue awareness, conflict resolution | 10 | S1 | Not built |
| `dde-context` | Coverage contract, Critic status | 5 | S1 (S4 for Critic) | Not built |
| `dde-routing` | Gate/rank distinction | 6 | S1 (S4 for propensity) | Not built |
| `dde-workers` | Fleet Mission Control (status, activity, routing, observability, control), certification | 8 | S1 (S3 multi-adapter) | **Exists (Mission Control shells + live health)** — bind when Gateway/CLI land |
| `dde-verification` | Full chain, independence signal | 9, 11 | S1 (S4 mission oracle) | Not built |
| `dde-approvals` | Approvals queue, standing approval, morning review | 13 | S3 | Not built |
| `dde-donor` | Donor Lab, reuse classification | 13.8 | S5 | Not built |
| `dde-knowledge` | Knowledge graph (derived/asserted) | 5.10 | S4 | Not built |
| `dde-evaluation` | Eval corpus, promotion gates | 5.13, 6.9 | S4 → S7 | Not built |
| `dde-debug` | Raw event/trace inspection | 16 | S1+ | Not built |
| ProductEnvironment view | Live preview link | 11.6 | S4 | Not built |

---

## §8 Build order

A concrete, sequenced answer to "what do we actually build, in what order," given §2's
reconciliation and §3's transport/architecture research.

### §8.1 Now — before any S1 Core subsystem lands

These don't need new Core data; they're extension-side correctness/robustness work on what
already exists:

1. Guard chat-participant-adjacent code paths per §3.3 even though `dde-chat` isn't built
   yet — nothing to do here today, just don't add a Chat Participant later without the
   try/catch discipline.
2. Add a `connection/authService.ts` seam (§3.6) — no-op today (health checks are
   unauthenticated), but establishes where `context.secrets` plugs in before S3 auth lands,
   so it isn't retrofitted under time pressure.
3. Rename nothing yet. `dde-studio` as an extension id and `HARNESS_PROFILES` naming already
   match Appendix A's role names — no G6-driven renames are needed until an actual `Cursor
   Agent` worker card is built (S1+, once `adapters/cursor` exists).

### §8.2 As soon as `DDE-015` (CLI) exists

1. Add `--json` output to whichever `dde` CLI commands expose mission/task/route/worker
   state first (confirm this requirement when `DDE-015` is scoped — see §3.1a).
2. Build `dde-mission` (Mission/Tasks tree view) against CLI-JSON, replacing nothing —
   this is the first genuinely new module.
3. Build `dde-integration` (§4.2) against CLI-JSON once `DDE-013` (merge queue) exists.
   Recommended first of the two new modules (G1/G2) — it's cheaper (read-only queue state)
   and the one every other multi-task view depends on for orientation ("which workspace am
   I viewing").

### §8.3 As `DDE-008`/`009`/`011`/`012` land (still S1, CLI-bridged)

4. `dde-context` (basic coverage contract, §5.2), `dde-routing` (basic gate/rank
   distinction, §5.1), `dde-verification` (basic chain, §5.3) — same CLI-JSON pattern.
5. Extend `dde-workers` Mission Control rooms to show the real single certified profile
   instead of empty mission/run/event panels, and enable the lifecycle-correct actions
   from §5.4 when Worker Manager APIs exist.

### §8.4 At S3, when `DDE-027` (Gateway) lands

6. Swap CLI-subprocess data sources for the Gateway REST/WS client across every module built
   in §8.2–8.3 — panels don't change, only the client implementation behind
   `StubGatewayClient`'s eventual real replacement does.
7. Implement `connection/authService.ts` for real (Bearer/OIDC, `context.secrets`).
8. Build `dde-approvals` (§4.1) and `dde-chat` (§3.3, webview-first + gated Chat Participant).
9. **This is the trigger point for the React/Vite `webview-ui` migration (§3.5)** —
   `dde-integration` and `dde-approvals` together are the first two modules whose
   interactivity genuinely outgrows hand-written HTML strings.

### §8.5 S4 and later

10. `dde-context` (Critic, coverage gates), `dde-routing` (propensity), `dde-verification`
    (mission oracle), ProductEnvironment view (§6.1), `dde-knowledge`, `dde-evaluation` —
    each gated on its respective Core subsystem per §7's table, no new extension-architecture
    decisions needed beyond what §3.5 already establishes.
11. `dde-donor` (§6.3) at S5, once Donor Lab exists.

---

## §9 Open questions

Two of the original four are now resolved (§1 fixed the MCP stage; §3.4 gives a recommended
default for the naming collision, pending only actual `adapters/cursor` implementation work).
What's left:

1. **Host confirmation.** Extend the existing scaffold with one new real view (§3.2) and
   confirm it still loads cleanly in both a Codespace-backed browser session and Cursor
   Desktop, before `dde-mission`/`dde-integration` are built against it.
2. **Should this suite become formal `DDE-0xx` Chapter 18 line items?** This document treats
   it as planning-only per its own header. If/when it should be formalized into Ch.18 (e.g.
   as sub-items under the S1/S3 milestones each module rides alongside), that's a follow-up
   edit to `docs/blueprint/historical/REV_2_0.md` — not implied by writing this plan.
