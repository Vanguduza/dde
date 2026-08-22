# EDR-0001 — Subscription/session-based worker credentials (Claude Code Pro seat)

> **ACCEPTED 2026-08-22 by explicit human project-owner decision.** The
> authoritative record is the accepted row in the Project Truth `edrs` table
> (`edr_id=01a028c4-9fe5-7aa5-b35b-73a0b152f044`, owner project
> `9b6f1a58-e29a-4a35-a8e2-8e6c0f4b7d11`, written via
> `engine.truth.service.TruthService.propose_edr` + `accept_edr`). This file
> remains as readable documentation of the proposal and its history; where
> wording differs, the `edrs` row outranks it. Acceptance covers the designs
> and deferrals **as documented** — Path B implementation, remaining promotion
> gates and similar follow-ons stay gated on their own missions.

> **Location note (read before anything else).** This repository has **no existing
> markdown-file EDR convention**. Per Chapter 3.6 of `docs/blueprint/REV_2_0.md`,
> an EDR is a **row in the `edrs` table** (`schemas/objects/edr.json`,
> `engine/contracts/edr.py`), written only by `engine/truth/` (the chapter's
> "sole writer"), surfaced to humans via an "EDR" panel (see
> `docs/planning/dde-vscode-extension-suite.md`) and referenced elsewhere only
> by its human-facing `slug` (e.g. `EDR-024`). No `docs/decisions/` or
> `docs/truth/edr/` directory existed before this file, and `docs/truth/`
> otherwise contains only a `.gitkeep`. Because the task requires a
> documentation artifact and not a database write (and because AGENTS.md
> forbids editing `docs/truth/**` "as a side effect of implementing a task" —
> this file is the proposal itself, not a side effect), this proposal is filed
> here as a **markdown pre-image of the eventual `edrs` row**, shaped to match
> `edr.json`'s required fields (`context`, `alternatives`, `decision`,
> `rationale`, `consequences`, `affected_requirement_slugs`, `status`) so a
> human or `engine.truth` operation can transcribe it into a real row with no
> re-interpretation. **This file is not itself an accepted EDR.** `status`
> below is `proposed`; only a human decision (Chapter 20 / Chapter 3.4's
> authority ranking) can move it to `accepted`, at which point the durable
> record belongs in `edrs`, not here — this file should then be deleted or
> reduced to a pointer, matching the chapter's "never a second source of
> truth" rule (AGENTS.md forbidden list).

- **slug:** `EDR-0001` (provisional — the real value is assigned when a human
  or `engine.truth` transcribes this into the `edrs` table; sequence is
  whatever the table's next free human-facing EDR number is at that time)
- **status:** `proposed` — **partially resolved by human decision** on
  2026-08-21: primary/fallback provider order for the Claude/Anthropic
  capability is decided (see "Decision — human resolution on primary/fallback
  order" below). The EDR as a whole is still `proposed`, not `accepted` —
  the foundational "Open questions / risks" (storage-at-rest legality,
  device-flow API existence, per-seat ToS/rate-limit risk) are unresolved and
  block acceptance.
- **supersedes:** none
- **affected_requirement_slugs:** none yet formally filed — this EDR should be
  linked to whatever requirement(s) charter "Claude Code as a routable
  worker profile" once those exist. Flagged as an open gap in itself: there is
  currently no Requirement in Project Truth that asks for Claude Code
  specifically, only the mission narrative in the task that produced this EDR.

---

## Decision — human resolution on primary/fallback order (2026-08-21)

The project owner (human authority, per AGENTS.md's "Project Truth... outranks
all code, all agent memory, and all model opinion" and Chapter 3.4/20's
authority ranking) has made an explicit decision on part of this EDR's
design. This narrows, but does not close, the EDR — see the still-open
"Open questions / risks" section below, which this decision does **not**
resolve.

**Resolved:** For the Claude/Anthropic capability, **delegated-session
(subscription) credential is the primary provider** for all work
routed/assigned to a Claude Code worker profile. A **static Anthropic API
key provider** (the same static-secret tier already used by DeepSeek/Hermes
— Chapter 14.3's existing lowest machine-mintable tier) is a **secondary /
fallback provider only**, attempted solely when the delegated session is
unavailable, expired, or otherwise fails. It is not an equally-weighted
alternative, not the default path, and not something a worker/operator
chooses per-call — it is the broker's own fallback behavior when the primary
fails.

This inverts the tentative ranking implied by the original "Decision
(proposed)" section immediately below, which treated the delegated-session
tier as strictly *lower*-preference than every static-secret tier ("used
only where a machine-mintable credential cannot exist at all"). For
Claude/Anthropic specifically, that generic Chapter 14.3 ordering is
superseded by this explicit human decision: **delegated session first,
static API key second.** The API key does not disappear as an option for
this capability — it moves from "not applicable" to "backup" — but it is
never the first thing attempted while a usable delegated session exists.

**Scope of this decision.** This is a decision about *preference order*
only. It does not resolve, and should not be read as implicitly resolving,
any item in "Open questions / risks" below (storage-at-rest legality,
whether a suitable device-flow/token-exchange API exists, or per-seat
ToS/rate-limit risk) — those remain open human decisions in their own right.
See the explicit note at the top of that section: if Open Question #1 (may
DDE hold session material at rest at all) comes back negative, the
delegated-session-as-primary design in this EDR needs to be reworked from
its foundations, not just have its fallback ordering adjusted.

See "### Fallback ordering at the broker/provider level" below (under
"Decision (proposed)") for how this preference order is proposed to be
implemented, still as a design only — no code in `engine/`, `adapters/`, or
`schemas/` has been written or changed for this decision.

## Context

Chapter 14.3 (Credential Broker) defines exactly one shape of secret material
the broker is allowed to mint or hold: something **DDE itself creates and can
revoke** — workload identity, an OIDC-exchanged short-lived token, a
provider-issued temporary credential, a signed execution handle, or, as the
lowest tier, "a static secret behind the broker." Every existing
implementation matches this shape:

- `engine/capabilities/broker/provider.py`'s `CredentialProvider` protocol has
  exactly two operations, `issue(scope) -> ProviderIssuedCredential` and
  `revoke(provider_ref)`. `issue()` is documented to "mint a new, real
  short-lived secret value. Never returns the same value twice." — i.e. the
  provider is assumed to be the **origin** of the secret, not a custodian of
  one a human obtained elsewhere.
- The only real provider, `LocalSecretProvider`, mints a fresh
  `secrets.token_urlsafe(32)` per call — a synthetic stand-in for "static
  secret behind the broker," Chapter 14.3's own lowest preference tier.
- `engine/contracts/credential_handle.py`'s `CredentialHandle` never persists
  a raw secret (`secret_hash` only, "Audit records store metadata and hashes,
  never secret material"), assumes a fixed, broker-computed `expires_at`
  derived from a `CapabilityLease`'s own expiry
  (`engine/capabilities/broker/service.py`: `expires_at = min(now + ttl,
  lease.expires_at)`), and only ever reaches a terminal state by expiring,
  being revoked, or being superseded by a *new broker-minted* handle
  (`engine/capabilities/broker/states.py`). Nothing in this state machine
  models "the same underlying credential renewed by refreshing it," only
  "replace with a brand-new mint."
- `adapters/cursor/adapter.py`'s `CursorWorkerAdapter` is the one adapter that
  already anticipates a real vendor call and it fail-closes with
  `POLICY_DENIED` specifically because "a live model invocation would
  require a brokered credential (Chapter 14.3) and would put an API key on a
  path this adapter is forbidden to take" — i.e. today's only defined path
  for a worker to authenticate to a vendor is a broker-minted API-key-shaped
  secret. There is **no Anthropic/Claude adapter of any kind** yet.
- `packaging/windows/DdeSetupWizard/Pages/CredentialsPage.cs` and
  `Services/ConfigWriter.cs` collect exactly one shape of vendor credential —
  a pasted static API key per provider (`AnthropicApiKey`, `OpenAiApiKey`,
  `DeepSeekApiKey`, `CursorApiKey`, `GitHubToken`) — written into
  `config.toml` and a plaintext `.env` file. There is no login/OAuth step in
  the installer at all.

The new requirement is that **Hermes and DeepSeek** harnesses authenticate
with a **DeepSeek API key** — this fits the existing static-secret tier
exactly and needs no new abstraction; the installer field
(`DeepSeekApiKey`/`deepseek_api_key`) already anticipates it, and the correct
provider is a `DeepSeekApiKeyProvider` implementing the existing
`CredentialProvider` protocol (out of scope for this EDR — no divergence to
record).

**Claude Code is different in kind, not degree.** It must authenticate using
the entitlement of a human's already-logged-in Claude Code / Anthropic
account — a Pro (or whatever tier the account has) subscription session, most
plausibly obtained via the Claude Code CLI's own OAuth/device-login flow —
not an API key DDE mints or even holds in the traditional sense. This is a
credential:

1. **DDE does not originate.** A human authenticates out-of-band (browser or
   device-code flow against Anthropic), not the broker.
2. **DDE cannot freely mint copies of.** There is one subscription seat behind
   one human's login; the broker cannot "issue" a second independent
   instance the way `LocalSecretProvider.issue()` mints a fresh random token
   on every call.
3. **Is long-lived and refreshable**, not short-lived-by-construction — the
   opposite of Chapter 14.3's "short-lived" framing for every tier it names.
4. **May not be revocable by DDE at all** — revocation may only be possible
   by the human logging out at the vendor, not by anything `revoke()` can do
   locally beyond "stop presenting it."

None of Chapter 14.3's five tiers, and none of the current
`CredentialProvider`/`CredentialHandle` mechanics, describe this. This is a
genuine gap, not an oversight in an existing tier — per AGENTS.md, "the
blueprint outranks convenience... a divergence is an EDR, not a commit."

## Alternatives considered

1. **Force-fit Claude Code onto the static-secret tier** by asking the human
   to generate a long-lived Anthropic API key instead of using their Pro
   subscription. Rejected: contradicts the explicit requirement ("NOT an API
   key... the entitlement of a human's already-authenticated... account") and
   an Anthropic *API* key bills/rate-limits differently from a Pro seat — it
   is not "roughly the same shape, priced differently," it is a different
   product surface.
2. **Have the adapter hold and use the vendor CLI's session directly,
   bypassing the broker entirely** (e.g. adapter shells out to `claude` and
   never touches `engine/capabilities/broker`). Rejected: this puts a
   long-lived credential's usage path outside the one component AGENTS.md
   authorizes to read secret material ("Nothing except
   `engine/capabilities/broker/**` reads secret material") and outside
   Chapter 14.5's audit invariant ("every security-relevant decision...
   produces an `audit_event`"). It would also make `emergency_revoke`
   (14.3) structurally unable to reach this credential's usage at all.
3. **Extend `CredentialHandle`/`CredentialProvider` to also *originate* a
   subscription session by capturing a human's login once, and then broker
   every subsequent use exactly like any other tier** — treating the
   difference as *provenance* (human-obtained vs. DDE-minted) rather than a
   parallel authentication system. **This is the proposed direction below.**
   It reuses `issue`/`revoke`/`inspect`/`emergency_revoke`,
   `CredentialHandle`'s status machine, and the broker's audit trail
   unchanged; it only adds a new tier to the preference order and a new
   provider implementation, which is exactly the extension point Chapter
   14.3 already names ("Providers sit behind a `CredentialProvider` contract
   so no core logic couples to one secret manager").

## Decision (proposed)

Introduce a new, explicitly-named **"delegated session" tier**, ranked
*below* "static secret behind the broker" in Chapter 14.3's preference order
(it is a fallback used only where a machine-mintable credential cannot exist
at all — a subscription seat has no machine-identity or OIDC equivalent to
prefer), implemented as a new `CredentialProvider`:

```
DelegatedSessionProvider(provider_id="anthropic_claude_code_session")
```

**What it does NOT do**, by construction:

- It never *mints* a new secret the way `LocalSecretProvider.issue()` does.
  There is exactly one underlying session per configured human account, and
  `issue()` on this provider returns a **broker-scoped, short-lived derived
  access artifact bound to that session**, never the session's own raw
  refresh material. Two acceptable shapes, in preference order, mirroring
  Chapter 14.3's own "prefer the narrowest safe thing" structure:
  - (a) **Token exchange**, if Anthropic's Claude Code OAuth surface supports
    minting a short-lived, narrowly-scoped access token from the long-lived
    session on demand (an OAuth2 "token exchange" / refresh-token-for-
    access-token pattern) — the provider holds the refresh material *once*
    (see storage below) and calls out to mint a fresh short-lived token per
    `issue()`, exactly like `LocalSecretProvider` mints a fresh token per
    call, except the entropy source is Anthropic's own token endpoint, not
    `secrets.token_urlsafe`.
  - (b) **Mediated call only**, if no such exchange exists: `issue()` returns
    a `CredentialHandle` whose `provider_ref` identifies the session, but the
    handle carries **no independently usable secret value at all** — every
    actual vendor call is instead proxied through the broker process (the
    only process ever holding the raw session material), and the "credential"
    a worker/adapter receives is a capability to ask the broker to perform
    one call, not a bearer value it can present itself. This is the
    conservative option and should be assumed correct unless a human
    confirms (a) is available (see Open Questions).
- It never returns raw, long-lived session/refresh material to a caller —
  the AGENTS.md rule ("Passing a long-lived credential to anything that
  executes model-generated code") is honored by construction under both (a)
  and (b): under (a), the artifact handed out is short-lived and scoped,
  structurally identical to every other tier's output; under (b), nothing
  leaves the broker process at all.

**How the session material is originated and refreshed** (this is the actual
new capability Chapter 14.3 does not have today):

- A new, narrow **`register_delegated_session(...)` broker operation**
  (sixth operation alongside `issue`/`renew`/`revoke`/`inspect`/
  `emergency_revoke`) accepts an already-obtained session/refresh artifact —
  it never performs the interactive login itself. The interactive step (see
  deployment-shape differences below) happens *outside* the broker, once, by
  a human or an installer-driven subprocess; the broker only custodies the
  result from that point on, inside the same trust boundary that already
  holds `LocalSecretProvider`'s state (`engine/capabilities/broker/**`,
  the one module AGENTS.md authorizes to read secret material).
- `renew()` on a delegated-session handle re-runs the *token-exchange* step
  (shape (a)) or is a no-op status refresh (shape (b)) — it never re-runs the
  human's interactive login. If the underlying session itself has expired or
  been revoked at Anthropic (the human logged out, the refresh token was
  invalidated, the seat was removed), `renew()` fails closed with
  `POLICY_DENIED`, exactly like today's `renew()` fails closed on a
  non-`ACTIVE` lease — and the resulting `AttentionItem`/operator escalation
  is "a human needs to re-run `register_delegated_session`," not "DDE will
  retry automatically." This directly avoids the Ch.12.4 failure pattern
  named in `mission-chapter-gate.mdc` ("UNKNOWN never blind-retried; only
  verified absence permits a new mutation") applied to auth: an
  ambiguous/expired session is never blindly re-presented to Anthropic.
- `CredentialHandle` itself needs **no schema change**. `provider_id` already
  distinguishes providers; `provider_ref` already exists for "opaque,
  non-secret, provider-side identifier `revoke()` can use." A delegated
  session's `provider_ref` would hold a stable, non-secret handle to *which*
  registered session it derives from (e.g. an internal session-registration
  id), never the token itself. `expires_at` on an *issued* handle remains
  short-lived exactly like every other tier (the derived-access-artifact's
  own TTL, or, under shape (b), a short "this mediation grant is live"
  window) — only the underlying session material, held separately and never
  represented as a `CredentialHandle` row at all, is long-lived. That
  separation is itself the point: **the long-lived material is a new,
  separate, more tightly-scoped concept ("registered delegated session"),
  never conflated with the existing short-lived `CredentialHandle` records.**
- **Anthropic adapter policy shell.** Mirroring
  `adapters/cursor/adapter.py` exactly: a new `adapters/claude/adapter.py`
  (or `adapters/anthropic/adapter.py`) should be added as a **fail-closed
  policy shell** — `register()`/`health()`/`capabilities()` real,
  `start()` raising `POLICY_DENIED` with a clear "no delegated session
  registered / live invocation not certified" message — until
  `register_delegated_session` and its call site are real. This gives
  routing a certified-but-inert profile to reason about without a live
  vendor call existing anywhere, exactly as the Cursor adapter does today.

## Rationale

- Reuses every existing broker mechanic (`CredentialHandle`'s status machine,
  the broker's sole-writer boundary, the audit-event trail, the
  `CommandLedger` idempotency pattern) rather than inventing a parallel
  authentication system — satisfies AGENTS.md's "introducing a second source
  of truth for any mutable state" prohibition and "no new dependency without
  stating licence/maintenance/why-stdlib-insufficient" by not introducing a
  new subsystem at all, only a new `CredentialProvider` implementation plus
  one new broker operation.
- Keeps the "never hand a long-lived credential to anything executing
  model-generated code" invariant true by construction under either token-
  exchange or full-mediation shape, rather than by policy/reviewer discipline
  alone.
- Treats DeepSeek/Hermes and Claude Code as genuinely different tiers rather
  than stretching one abstraction to cover both badly — DeepSeek needs zero
  new mechanism; Claude Code needs a real new tier. Keeping them separate
  avoids the alternative failure mode of loosening the static-secret tier's
  semantics until it accidentally also fits sessions, which would blur the
  auditability the chapter is built around.

## Consequences

- Chapter 14.3's preference order gains a sixth, explicitly-lowest,
  explicitly-different-in-kind tier: *"delegated human session (subscription
  entitlement), mediated or token-exchanged by the broker — used only where
  no machine-mintable credential exists."* This is a blueprint change, not
  just an implementation detail, and should be reflected in
  `docs/blueprint/REV_2_0.md` §14.3 if/when this EDR is accepted (per
  AGENTS.md: "Public behaviour change is reflected in the blueprint chapter
  it belongs to").
- The broker gains a sixth operation (`register_delegated_session`, name
  TBD) beyond the chapter's current five — needs its own contract test per
  AGENTS.md's Definition of Done, and its own `audit_event` type
  (`DelegatedSessionRegistered`/`DelegatedSessionRefreshed`, mirroring
  `CredentialIssued`/`CredentialRenewed`).
- A new "registered delegated session" durable record is needed
  (own table, own RLS, own tenant/project scoping per Chapter 3.2 — **not**
  a `CredentialHandle` row, see Decision above). This is new schema surface
  requiring its own `schemas/objects/*.json` + migration, out of scope for
  this EDR to design in full but flagged as required follow-on work.
- Routing/worker-profile certification (Chapter 8.5 / 14.4) needs to treat
  "delegated session not registered" as a legitimate reason a Claude Code
  profile is a visible-but-unselectable candidate, exactly like an
  uncertified configuration today.
- The Windows installer (`CredentialsPage.cs`) needs a materially different
  UI branch for Claude Code than for DeepSeek — see below — which is a
  second, smaller decision this EDR flags but does not fully design (installer
  UX is not itself a blueprint contract, but the *data* it must hand the
  broker is, and that hand-off is this EDR's concern).

### Deployment-shape differences

**Windows local install (`packaging/windows/DdeSetupWizard/`).** Interactive
login is possible during or right after setup. `CredentialsPage.cs`
currently collects a pasted `AnthropicApiKey` into `ConfigWriter.cs`, which
writes it into both `config.toml` (`anthropic_api_key = "..."`) and a
plaintext `.env` (`DDE_ANTHROPIC_API_KEY=...`) — this plaintext-file pattern
is already a poor fit for a static API key and would be actively wrong for
long-lived session/refresh material (Chapter 14.3: "a static secret never
enters... a log... an artifact"; a session token is more sensitive still).
Proposed shape for Claude Code specifically, replacing (not extending) the
`_anthropic` `PasswordBox` field:
- A "Sign in with Claude Code" button that shells out to the vendor CLI's own
  login (e.g. `claude login`, if such a command and flow exist — see Open
  Questions) or opens a browser to Anthropic's OAuth page, exactly the same
  externally-triggered-once pattern the installer already uses for Docker
  detection (`DockerPage.cs`/`DockerService.cs`).
- On success, the installer does **not** write the resulting session/refresh
  material into `config.toml`/`.env` the way it does today for API keys.
  Instead it either (a) leaves the material exactly where the vendor CLI
  already persisted it (its own session file) and only records *that DDE
  should look there* plus which OS account, or (b) hands it once to a local
  broker bootstrap call (`register_delegated_session`) so it ends up solely
  inside the broker's own secret-holding boundary, never in `ProgramData`
  plaintext. (b) is preferred — it keeps "only `engine/capabilities/broker/**`
  reads secret material" true even for the installer's own write path, and
  keeps a single custody boundary rather than two (vendor CLI's file +
  DDE's file).
- DeepSeek/Hermes keep the existing `PasswordBox` → `config.toml`/`.env`
  path unchanged — this EDR does not touch that flow.

**Cloud deployment (Codespace/server, no interactive browser server-side).**
There is no human sitting at the machine to complete a browser redirect.
Two sub-options, both requiring a device-code-shaped flow rather than a
browser redirect:
- If Anthropic's login flow supports an OAuth **device authorization grant**
  (the same shape as `gh auth login`'s device flow, or Cursor's own CLI/IDE
  session pattern referenced in the task context): the cloud DDE instance
  displays a short code and verification URL (via an `AttentionItem`,
  Chapter 13, or a one-time setup CLI command run by an operator from their
  own machine), the human completes the browser step on *any* device, and
  the resulting session is registered with the broker the moment the device
  flow completes — no server-side browser needed at any point.
- If no such device flow exists: the only remaining option is a human
  completing the login once on a machine that *does* have a browser (their
  laptop, or the same local install flow above), exporting the resulting
  session/refresh artifact, and an operator registering it with the cloud
  broker out-of-band (e.g. a one-time authenticated setup command) — this is
  materially less good (the artifact transits somewhere the broker did not
  originate it) and should be treated as a fallback only, not the target
  design.
- Either way, refresh in the cloud case is fully automatic once registered
  (broker-side token exchange, shape (a) above) or fully mediated (shape
  (b)) — no repeated human interaction should be needed for as long as the
  underlying session at Anthropic remains valid.

### Fallback ordering at the broker/provider level (human-decided primary/fallback)

This section designs, in doc form only, how the human decision above
("Decision — human resolution on primary/fallback order") would be
implemented against the actual, existing broker code — no code in this
section has been written; every symbol named below is either an existing
file/class (cited with its path) or a new one proposed here.

**Today's shape, precisely.** `engine.capabilities.broker.service
.CredentialBrokerService.__init__` accepts exactly **one**
`provider: CredentialProvider` (`engine/capabilities/broker/service.py`,
`self._provider: CredentialProvider = provider or LocalSecretProvider()`).
`issue()`/`renew()` call `self._provider.issue(scope)` once, with no retry
or alternate-provider concept anywhere in the module. There is currently no
fallback-selection mechanism to design around — this is new surface, not an
extension of an existing chain.

**Proposed composition point.** A new provider, itself implementing the
existing `CredentialProvider` Protocol
(`engine/capabilities/broker/provider.py`: `provider_id: str`, `issue(scope)
-> ProviderIssuedCredential`, `revoke(provider_ref)`), so the broker's own
`issue()`/`renew()`/`revoke()` code in `service.py` needs **no** change to
call it — only its construction (which concrete `CredentialProvider` is
passed to `CredentialBrokerService(...)`) changes for the Claude/Anthropic
capability:

```
FallbackCredentialProvider(
    provider_id="anthropic_claude_code",  # exact value TBD at implementation
    providers=[
        DelegatedSessionProvider(provider_id="anthropic_claude_code_session"),
        AnthropicApiKeyProvider(provider_id="anthropic_api_key"),
    ],
)
```

`issue(scope)` on this wrapper attempts `providers[0].issue(scope)` first.
It treats the following as "primary failed, try the next provider" rather
than "issuance failed" — expired session, no session registered yet,
refresh/token-exchange failure, and a session revoked at the vendor (the
same failure set `DelegatedSessionProvider.renew()`/`issue()` already fail
closed on per the "Decision (proposed)" section above). It calls
`providers[1].issue(scope)` (the static `AnthropicApiKeyProvider`) only on
one of those specific failures, and **only if** an API key provider has
actually been configured for this broker instance (Chapter 14.3's static
tier is optional per install, unlike the delegated session which this
decision makes mandatory-first). If both fail, or the delegated session
fails for a reason that is *not* one of the enumerated "try fallback"
conditions (e.g. a scope/policy rejection, which is not a credential-source
problem), the wrapper raises rather than degrading further — the same
un-caught-exception path `_op` in `service.py`'s `issue()`/`renew()` already
uses to fail the whole operation closed (no partial `CredentialHandle` row
is ever inserted; `AGENTS.md`: "Broadening a capability lease scope to make
a test pass" and "Silently widening autonomy_level... policy" are both
forbidden — a silent, unbounded fallback chain that keeps trying providers
until *something* works would violate that same spirit even though it is
phrased about lease scope specifically).

**The observability gap this creates, named precisely.** `CredentialHandle`
(`engine/contracts/credential_handle.py`) already has a `provider_id: str`
field, and `service.py`'s `issue()`/`renew()` already set it from
`self._provider.provider_id` (`service.py` lines ~203 and ~302) — so in
principle "which provider served this lease" is already a persisted,
auditable field, and the `CredentialIssued`/`CredentialRenewed` audit events
(`engine/contracts/audit_event.py`'s free-form `payload: dict[str, object]`,
populated in `service.py`'s `issue()`/`renew()`) already copy that same
`provider_id` into the audit trail. **But** `self._provider.provider_id` is
a single, static string on whichever one `CredentialProvider` object the
broker was constructed with — for a `FallbackCredentialProvider`, that
would always read as the *wrapper's own* `provider_id`
(`"anthropic_claude_code"` in the example above), never the specific
component (`"anthropic_claude_code_session"` vs. `"anthropic_api_key"`) that
actually served a given call. That is exactly the audit gap the task asked
to be named, not invented in the abstract:

- `engine.capabilities.broker.provider.ProviderIssuedCredential`
  (`@dataclass(frozen=True)`, fields today: `secret_value: str`,
  `provider_ref: str | None`) carries **no field identifying which
  provider produced it** — it doesn't need one today because exactly one
  provider object is ever configured per broker instance.
- The fix, named at the field level rather than left abstract: add a field
  to `ProviderIssuedCredential` — e.g. `served_by_provider_id: str` — that
  every `CredentialProvider.issue()` implementation populates with its own
  `provider_id` (a one-line addition to `LocalSecretProvider.issue()` and
  every future provider), and that `FallbackCredentialProvider.issue()`
  passes through unchanged from whichever component provider actually
  succeeded (never overwritten to the wrapper's own id).
- `service.py`'s `issue()`/`renew()` would then set
  `CredentialHandle.provider_id = issued.served_by_provider_id` (falling
  back to `self._provider.provider_id` for any provider that predates this
  field) instead of always using `self._provider.provider_id` directly, and
  would copy the same value into the `CredentialIssued`/`CredentialRenewed`
  event payload's existing `"provider_id"` key.
- This needs **no** change to `credential_handle.py`'s schema
  (`provider_id` is already a plain `str`) and **no** change to
  `audit_event.py`'s schema (`payload` is already an unconstrained
  `dict[str, object]`) — it is a `ProviderIssuedCredential` dataclass field
  addition plus a small `service.py` behavior change, both inside
  `engine/capabilities/broker/**`, the one module AGENTS.md already
  authorizes to read secret material and reason about provider identity.
- Optionally, to audit *why* a fallback happened (not just which provider
  ultimately served it), the same event payload could gain a new key —
  e.g. `"fallback_from_provider_id"` and a short, non-secret
  `"primary_failure_reason"` — populated only on the calls where
  `FallbackCredentialProvider` actually fell through. This is additive to
  the payload dict, not a contract change, but is flagged as a distinct,
  smaller follow-on decision, not assumed necessary by this EDR.

**This design is provisional.** It is written to show the fallback ordering
is *implementable* against real, existing code with a small, precisely
located change — not to declare it ready to build. See the next section:
if the foundational open questions come back negative, this whole
subsection may need to be redesigned around full mediation only, or
discarded if delegated sessions cannot be held at all.

## Open questions / risks (require an explicit human decision)

**Note:** the human decision recorded above (delegated session primary,
static API key fallback) resolves *only* the preference order between two
already-designed providers. It does **not** resolve any item below. In
particular, if Open Question #1 (session material at rest) is answered
"no," the delegated-session-as-primary design — and the fallback ordering
section just above, which assumes a working `DelegatedSessionProvider`
exists to be primary over — needs fundamental rework, not a fallback-order
tweak. Similarly, if Open Question #2 (device-flow/token-exchange API) comes
back negative, "primary" still means full mediation (shape (b)) rather than
a token-exchange handle, which changes the broker's latency/availability
posture materially even though the preference order itself is unaffected.
Treat every item below as still fully open and still blocking acceptance of
this EDR, regardless of the primary/fallback decision above.

1. **Is DDE allowed to hold a raw Claude Code session/refresh token at rest
   at all, even encrypted, inside the broker boundary?** AGENTS.md's
   forbidden list bars "passing a long-lived credential to anything that
   executes model-generated code" — this proposal's whole design is built to
   keep that true for *usage*, but it does not resolve whether *storage
   itself*, even fully custodied and never released, is acceptable under this
   codebase's risk posture. This is the single largest open question and
   should block implementation until answered.
2. **Does Anthropic's Claude Code CLI expose any documented device-flow or
   token-exchange API suitable for this at all?** This EDR's shape (a) (token
   exchange) depends entirely on such an API existing; if it does not, shape
   (b) (full mediation, broker proxies every call) is the only safe option,
   which is a materially heavier integration (the broker becomes a live
   pass-through for every Claude Code invocation, not just a credential
   minter) and may affect latency/availability characteristics routing needs
   to know about. Needs vendor-documentation research before implementation,
   not assumption.
3. **Per-seat/per-account rate-limit and Terms-of-Service implications of
   DDE routing multiple automated tasks through one human's Pro seat.** A
   subscription seat is priced and rate-limited for one human's interactive
   use; DDE's routing/concurrency model (multiple `WorkerRun`s potentially
   wanting Claude Code concurrently) could silently violate Anthropic's
   terms of service or exhaust the seat's rate limit in a way that starves
   the human's own interactive use. Needs an explicit concurrency policy
   (e.g. "at most one live Claude Code `WorkerRun` at a time, queued
   otherwise") and, separately, a legal/ToS read the engineering team is not
   positioned to make unilaterally.
4. **Revocation semantics when DDE cannot revoke at the provider at all.**
   Chapter 14.3's `revoke()`/`emergency_revoke()` assume "invalidate at the
   provider where semantics permit; always invalidates locally" — for a
   human-owned session, "at the provider" may mean nothing DDE can trigger
   (only the human logging out at Anthropic actually ends the session).
   `emergency_revoke` should still locally quarantine (stop presenting the
   derived artifact / stop mediating calls) even when it cannot touch the
   underlying session — this should be explicit in the eventual design, not
   assumed.
5. **What happens when the registered human leaves, changes their password,
   or revokes access out-of-band?** Needs an explicit "session health check"
   / reconciliation story (echoing Chapter 12.4's reconciliation-read
   philosophy) rather than only discovering the break the next time
   `issue()`/`renew()` is called.

### Research findings (2026-08-21)

This subsection answers Open Questions #1–#3 above with actual vendor
documentation, changelog/policy text, and community/GitHub-issue evidence
gathered 2026-08-21 (via live web research, not assumption). It resolves
enough of the ambiguity to make a concrete recommendation below, but does
**not** itself constitute the human sign-off Open Questions #1–#3 require —
that sign-off is still a separate, explicit human act on the design this
research makes possible.

**Finding 1 — a Pro/Max-authenticated, non-interactive invocation path does
exist, but it is not "silently reuse whatever session is already open."**
The real `claude` CLI supports two subscription-backed, non-API-key
authentication paths, both documented at
[code.claude.com/docs/en/authentication](https://code.claude.com/docs/en/authentication):

- **Interactive OAuth login** (`claude` on first run, or `/login`): opens a
  browser, authorizes against the Claude.ai account, and persists
  `accessToken`/`refreshToken`/`expiresAt`/`subscriptionType` in
  `~/.claude/.credentials.json` (Windows: the equivalent per-user Claude
  config directory; on macOS this can instead live in Keychain). This is
  exactly the file the original "Decision (proposed)" section above
  anticipated as shape (a)'s storage location.
- **`claude setup-token`**: opens the *same* browser OAuth authorization,
  but instead of persisting a refreshable session, it prints a **long-lived
  (about one year), single-use-to-copy OAuth token once and saves it
  nowhere** — the human is expected to export it as
  `CLAUDE_CODE_OAUTH_TOKEN` themselves. This is Anthropic's own documented
  answer to "how do I use my subscription in CI/headless," per
  [code.claude.com/docs/en/authentication](https://code.claude.com/docs/en/authentication)
  ("Use this for CI pipelines and scripts where browser login isn't
  available"). It requires a Pro, Max, Team, or Enterprise plan, and
  explicitly **cannot** open Remote Control / claude.ai-connector sessions —
  it is scoped to model requests only.

However, multiple independently-filed, still-open GitHub issues against
`anthropics/claude-code` show the **interactive** session's own
`refreshToken` is *not* reliably usable non-interactively even though the
field exists in the credentials file:
[#50743](https://github.com/anthropics/claude-code/issues/50743) and
[#53063](https://github.com/anthropics/claude-code/issues/53063) both
report a 401 with no auto-refresh attempt when `claude -p` is invoked
headless/as a subprocess after the ~6–8 hour `accessToken` expires, even
though a valid `refreshToken` is present in the file;
[#21765](https://github.com/anthropics/claude-code/issues/21765) documents
that Anthropic's refresh tokens are **single-use and rotate on redemption**
(RFC 9700 §2.2.2 practice, confirmed by a maintainer comment in the issue
thread) — meaning copying `.credentials.json` to a second machine, or two
processes racing to refresh it, actively breaks the *other* holder, not
just fails safely; and
[#79685](https://github.com/anthropics/claude-code/issues/79685), filed
most recently, reports headless `claude -p` permanently unable to refresh
even while a **concurrent interactive session on the same machine** keeps
working, with no documented recovery path other than a human re-running
`/login`. **Conclusion for this EDR:** the CLI's *ordinary* interactive
session file is not a safe non-interactive credential source to depend on
programmatically (it was never designed to be shared across processes or
redeemed by an automated caller) — but genuinely running the human's own
foreground-equivalent, currently-valid `claude` CLI process (not reading
its credential file, just invoking the binary, the same way a human would
invoke it in a terminal) sidesteps this whole failure class entirely,
because it never touches the refresh path at all in the common case where
the access token is still live. `claude setup-token`'s long-lived token is
the only path Anthropic documents as *intended* for genuinely detached
headless use.

**Finding 2 — automating the real, official `claude` binary is explicitly
Anthropic-endorsed; extracting or relaying its credential to anything else
is explicitly prohibited, and headless invocation is billed differently
from interactive invocation as of 2026-06-15.** Anthropic's Consumer Terms
of Service §3.7 (mirrored at
[code.claude.com/docs/en/legal-and-compliance](https://code.claude.com/docs/en/legal-and-compliance)
and reported in detail by
[The Register, 2026-02-20](https://www.theregister.com/software/2026/02/20/anthropic-clarifies-ban-on-third-party-tool-access-to-claude/5014546))
reads: *"Except when you are accessing our Services via an Anthropic API
Key or where we otherwise explicitly permit it, [you may not] access the
Services through automated or non-human means, whether through a bot,
script, or otherwise."* Anthropic's own Claude Code docs then explicitly
exercise the "otherwise explicitly permit it" carve-out for their **own
CLI**: the official docs describe piping logs into `claude -p`, running it
from cron, and wiring it into GitHub Actions / GitLab CI as supported
patterns — the Register piece and a detailed community writeup
([Daimon Legal](https://www.daimonlegal.com/blog/anthropic-banned-my-account-for-using-openclaw-heres-what-to-do-if-it-happens-to-you))
both note this is precisely why the clause cannot mean "no automation of
Claude Code at all." What Anthropic clarified in February 2026, after
banning accounts using a third-party harness ("OpenClaw") that reused
extracted OAuth tokens, is narrower and sharper: *"OAuth authentication is
intended exclusively for purchasers of Claude Free, Pro, Max, Team, and
Enterprise subscription plans and is designed to support ordinary use of
Claude Code and other native Anthropic applications... Anthropic does not
permit third-party developers to offer Claude.ai login or to route
requests through Free, Pro, or Max plan credentials on behalf of their
users"* ([legal-and-compliance](https://code.claude.com/docs/en/legal-and-compliance)).
The dividing line the evidence converges on is **not** "was a human
present" or "automated vs. manual" in the abstract — it is **whether the
real, unmodified `claude`/Claude Code binary is the thing making the
call**, versus a reimplemented client, SDK integration, or extracted-token
relay standing in for it. A live, still-open GitHub issue
([#43556](https://github.com/anthropics/claude-code/issues/43556)) from a
Max subscriber running `claude -p` from cron on their own server — no
wrapper, the literal official binary — shows Anthropic's own billing
classifier initially misfired and treated that as a "third-party harness";
the surrounding discussion and Anthropic engineer quotes make clear the
*intended* rule is that the official binary invoked directly is not a
harness, even from cron. Separately, **as of 2026-06-15** Anthropic split
billing lanes for Pro/Max/Team/Enterprise subscribers
([Developers Digest](https://www.developersdigest.tech/blog/claude-agent-sdk-credit-meter)):
interactive Claude Code in a terminal/IDE continues to draw the ordinary
subscription session/weekly limits, while **headless/programmatic
invocation — `claude -p`, cron jobs, Claude Code GitHub Actions, and any
Agent SDK caller — draws from a separate, smaller monthly "Agent SDK
credit" pool**, with overflow billed at API rates (only offered as an
opt-in on some tiers) once that pool is exhausted. No source found states
or implies a distinct ToS carve-out for "a human reviews/approves each
output" versus fully autonomous use — the documented distinction is
entirely about *which binary is making the network call*, not about
approval workflow around it. A mandatory `ApprovalService` gate is
therefore a **DDE-side safety and audit control this EDR still wants for
its own reasons (Chapter 13, and the human's explicit instruction)**, not
something that changes Anthropic's own compliance analysis one way or the
other — it neither is required by, nor exempts DDE from, Anthropic's
terms; it is orthogonal to them and independently justified.

**Finding 3 — no local, credential-free "ask the already-logged-in
process to run inference for me" socket exists; subprocess invocation of
the real binary is the only clean shape, and it is quota-metered
separately from interactive use.** Anthropic publishes no absolute
token/message figures for Pro/Max — official language expresses higher
tiers only as multipliers of Pro ("Max 5x provides 5 times more usage per
session than Pro") — but every source agrees on the *mechanism*: a
**rolling 5-hour session window** plus a **separate weekly cap**, shared
across claude.ai, Claude Desktop, the CLI, and IDE integrations, with a
further separate Opus-specific weekly sub-cap
([continuumcode.ai](https://continuumcode.ai/guides/claude-code-limits/),
[allthings.how](https://allthings.how/claude-code-usage-limits-explained-pro-max-and-weekly-caps/)).
Stale (pre-May-2026) community estimates cited alongside the mechanism
description put Pro at roughly 40–80 Sonnet-hours/week, Max 5x at
140–280 hours/week, Max 20x at 240–480 hours/week — useful only as an
order-of-magnitude floor, not a number this EDR should build a concurrency
budget around directly, and now stale given the 2026-05-06 session-limit
doubling and 2026-06-15 Agent SDK credit split described in Finding 2. The
practical implication for DDE is that **whatever budget a single
delegated seat has is smaller for headless/scripted invocation than the
same human's interactive terminal use enjoys**, further reinforcing Open
Question #3's existing recommendation ("at most one live Claude Code
`WorkerRun` at a time, queued otherwise") as a hard requirement, not a
nice-to-have — DDE will exhaust the *smaller* of the two pools quickly if
it runs more than one concurrent invocation. On the "local server/socket"
question specifically: Claude Code does run local sockets, but none of
them do what would be needed here. The **IDE bridge**
(`~/.claude/ide/*.lock`, a local WebSocket/SSE endpoint authenticated by a
short-lived JWT — [claude-code-explain.helmcode.com](https://claude-code-explain.helmcode.com/bridge-ide/),
[instructkr-claude-code.mintlify.app](https://instructkr-claude-code.mintlify.app/guides/ide-integration))
exists so an *editor* can hand Claude Code file/cursor context and receive
diffs back — it is a tool-context channel into an existing session, not an
inference-request channel a second process can use to get Claude to do
independent work. `claude mcp serve` similarly exposes Claude Code's own
*tools* to an MCP client — the inverse direction of what DDE would need
(DDE handing Claude Code a task), not a way to reuse someone else's
already-authenticated session to run a different task without spawning a
new `claude` process. No documented or credibly-reverse-engineered
mechanism lets a second local process piggyback on an already-running,
already-authenticated `claude` process's credential to perform a
*different* inference call than the one that process is already doing.
**The only construction that matches "DDE never touches the raw
credential" is therefore literally what the task's candidate design
proposed: spawn `claude` (or `claude -p ...`) as a subprocess**, the same
shape `ScriptedWorkerAdapter` (`engine/workers/scripted_adapter.py`)
already uses for `capability.run_local_process`, and let the OS-level
already-logged-in CLI process do its own authentication exactly as it
would for a human typing at a terminal.

<a id="candidate-design-evaluation"></a>
**Evaluating the task's candidate design against these findings.** The
proposed shape — `adapters/claude/adapter.py` never touches Anthropic
credentials at all; it shells out to an already-`claude login`-
authenticated local CLI process; every invocation is gated by a mandatory
human approval — **is confirmed as the most concrete, buildable path**,
with two refinements Findings 1–3 make necessary:

1. It resolves Open Question #1 (may DDE hold session material at rest?)
   **by construction, not by argument**: there is no session material for
   DDE to hold, so the question does not arise for this shape. It does
   **not**, however, retroactively answer Open Question #1 for the
   `DelegatedSessionProvider`/broker design in "Decision (proposed)"
   above — that design still needs its own answer if it is ever built (see
   the deferred path below).
2. It sidesteps Open Question #2 (does a device-flow/token-exchange API
   exist suitable for DDE to use?) for the **local-human-present**
   deployment shape specifically, because DDE never originates or
   exchanges anything — the human's own `claude login` already did that,
   out of band, the same way it would for their own manual terminal use.
   Finding 1 shows a token-exchange-shaped mechanism (`claude setup-token`)
   *does* exist, but it is a different, heavier-weight design (Path B,
   below) that reintroduces Open Question #1, not a prerequisite for this
   one.
3. Finding 2 shows the ToS risk of this shape is genuinely low **only if
   the adapter invokes the literal, unmodified `claude` binary** — never
   reads `~/.claude/.credentials.json` itself, never sets
   `CLAUDE_CODE_OAUTH_TOKEN` from a value DDE captured itself, and never
   reimplements any part of Claude Code's own request-shaping. The
   moment DDE reads or relays the credential file or a captured token
   itself, this reverts to exactly the "third-party harness relaying
   subscription credentials" pattern Anthropic's February 2026
   clarification targets — a materially different (and prohibited) shape,
   not a variant of this one. This must be an explicit, checkable
   constraint on the adapter (see structural sketch below), not an
   assumption.
4. Finding 3 makes the existing "at most one live Claude Code `WorkerRun`
   at a time" idea (already named as a needed policy in Open Question #3)
   a concrete, small piece of required design, not a deferred nicety —
   named explicitly in the structural sketch below.

**A materially better alternative was not found.** The research surfaced
`claude setup-token` as a real, Anthropic-documented, more
"headless-native" mechanism (Path B below), but it is strictly *heavier*
than the subprocess shape for the one deployment case this EDR's
"Recommendation" targets first (a human-present machine) — it requires
deliberate human action to mint a token, reintroduces credential-at-rest
custody, and still lands in the same "Agent SDK credit" billing lane per
Finding 2. It remains documented here as the fallback for the
no-human-present (cloud/server) deployment shape from "Deployment-shape
differences" above, not discarded, but is not the smallest safe next step.

#### Structural sketch — `adapters/claude/` policy shell + mandatory approval gate

Described in prose/pseudocode only, per this task's scope — no source
files are added or changed by this EDR update. Named against real,
existing constructs wherever one exists:

- **New module, `adapters/claude/adapter.py`**, mirroring
  `adapters/cursor/adapter.py`'s already-established "fail-closed policy
  shell" pattern (`CursorWorkerAdapter`) and reusing
  `engine/workers/scripted_adapter.py`'s already-established "real
  subprocess spawn behind a capability/approval gate" pattern
  (`ScriptedWorkerAdapter.start`/`_journaled_execute`) — this is a
  synthesis of two patterns that already exist separately in this
  codebase, not a new one:
  - `register()`/`health()`/`capabilities()` are real: `health()` can do
    the same class of honest, cheap check `ScriptedWorkerAdapter.health()`
    already does for its own subprocess dependency (e.g. `claude
    --version` exits 0), rather than asserting a live session is usable
    (that would require touching credential state, which this shape
    forbids itself from doing — a stale/expired session is discovered
    only by the invocation itself failing, which is then surfaced as a
    normal run failure plus an `AttentionItem`, not specially inspected in
    advance).
  - `start(worker_run)` is where the new mandatory gate lives:
    1. Compute a `scope_hash` over the exact prompt/spec/task content
       about to be handed to `claude` (mirroring
       `engine.governance.hashing.approval_scope_hash`'s existing role of
       binding an approval to the *exact* thing it authorizes, per
       `ApprovalService.decide`'s own "Approval cannot be reused for a
       materially different plan" check).
    2. Call `ApprovalService.require_approved(tenant_id=..., project_id=...,
       scope_hash=..., approval_type=...)` — the exact fail-closed gate
       pattern `engine/governance/service.py`'s own docstring calls out
       ("Fail-closed gate used by production mutation sites") — **before**
       any subprocess is spawned, exactly where `ScriptedWorkerAdapter
       .start()` calls `self._leases.require_active(...)` before its own
       side effects. A missing/expired/mismatched approval raises
       `POLICY_DENIED`, the same error the Cursor adapter already uses for
       "no credential path available," and no `claude` process is ever
       spawned.
    3. `approval_type` needs an explicit name. None of
       `engine/governance/types.py`'s current `APPROVAL_TYPES` (
       `architecture_change`, `production_change`, `scope_widening`,
       `capability_grant`, `oracle_approval`, `irreversible_effect`,
       `dependency_addition`, `donor_reuse`) is a precise fit for "invoke
       an external vendor's model on my behalf using a human's personal
       subscription seat" — `capability_grant` is the closest existing
       value but would blur a distinct risk shape (spend against a human's
       personal, rate-limited, ToS-bounded seat) into a broader bucket.
       This EDR flags, but does not itself decide, whether a new literal
       (e.g. `external_model_invocation`) should be added to that
       frozenset — a small, additive change inside
       `engine/governance/types.py`, not a new mechanism, and squarely a
       human decision per this codebase's own pattern for extending an
       enumerated vocabulary.
    4. Per Chapter 13.2 as already encoded in
       `engine/governance/types.py`'s `STANDING_FORBIDDEN_TYPES`, this new
       approval_type should very likely be added to that forbidden set (or
       simply never granted a `StandingApproval` in practice) so that
       `authorize_standing()` can never pre-authorize a batch of Claude
       Code invocations without a human `decide()` on each one — this is
       the literal mechanism satisfying the human's explicit instruction
       ("a human manually approve every piece of work routed to Claude
       Code"), enforced the same way `irreversible_effect` and
       `production_change` already are un-standing-able today.
    5. Only after `require_approved` returns does `start()` spawn
       `claude` (most plausibly `claude -p "<task prompt>" --output-format
       stream-json` or equivalent non-interactive-but-still-the-real-CLI
       invocation, run inside the already-provisioned `Workspace`
       directory exactly as `ScriptedWorkerAdapter._workspaces.execute(...)`
       already does for its own subprocess) and captures stdout/stderr/
       exit code into `RunHandle`/`ArtifactManifest`, the same shapes
       `ScriptedWorkerAdapter` already produces from a real subprocess.
       `collect_usage()` should report `cost_usd=0.0` honestly (per the
       existing `ScriptedWorkerAdapter.collect_usage` docstring's own
       "honestly zero... not fabricated, not omitted" convention) or an
       explicit `"subscription-metered, cost unknown to DDE"` sentinel
       rather than fabricating a token-cost figure DDE cannot see —
       Finding 3 establishes DDE has no visibility into which of the
       human's two (interactive vs. Agent-SDK-credit) usage pools a given
       invocation drew from or how much it consumed.
  - **Serialization.** Per Finding 3 and Open Question #3's existing
    recommendation, this adapter should enforce "at most one live
    invocation at a time" itself (e.g. a simple in-process lock/queue
    around `start()`, mirroring the fact that `ScriptedWorkerAdapter`
    already runs its subprocess synchronously inside `start()` with no
    in-flight window per run) rather than deferring that to routing —
    naming it here as a required property of this specific adapter, not
    an assumed one.
  - **What this adapter must never do**, stated as an explicit,
    testable constraint per Finding 2 point 3 above: read
    `~/.claude/.credentials.json` or any OS keychain entry Claude Code
    uses; read, set, or forward `CLAUDE_CODE_OAUTH_TOKEN`,
    `ANTHROPIC_API_KEY`, or `ANTHROPIC_AUTH_TOKEN` from any value DDE
    itself captured or derived; or call any Anthropic API endpoint
    directly. Its only supported interaction with Anthropic is "spawn the
    unmodified `claude` executable as a subprocess and read its
    stdout/stderr/exit code," identical in kind to how
    `ScriptedWorkerAdapter` treats an arbitrary local command today.
- **Path B (deferred, not built now).** The "Decision (proposed)"
  section's `DelegatedSessionProvider`/`register_delegated_session`/
  broker-mediation design remains the documented answer for the
  no-human-present (cloud/server) deployment shape, now understood
  concretely as: a human deliberately runs `claude setup-token` once,
  and *chooses* to hand DDE the resulting long-lived token to register.
  This is real, Anthropic-documented, and lower ToS risk than extracting
  an interactive session's refresh token (Finding 1) — but it still
  requires DDE to custody a long-lived secret, which is exactly Open
  Question #1, unresolved by this research and still blocking. Path A
  (subprocess-only, above) should be built first and independently of
  whether Path B is ever approved.

## Recommendation — smallest safe next step

**Updated 2026-08-21** (second update, following "### Research findings
(2026-08-21)" above). The primary/fallback *order* was already decided by
the human (see the top-level "Decision" section). This update narrows the
recommendation further: research now shows a genuinely smaller, sooner,
lower-risk buildable slice than "the full broker/`DelegatedSessionProvider`
contract" — a **subprocess-only adapter with a mandatory per-invocation
human approval gate, and no broker/credential involvement at all** (Path A
in "### Research findings" above). This EDR is **still not accepted** —
Open Questions #1 and #2 remain formally open for the broker/`Delegated
SessionProvider` design (Path B) — but Path A does not depend on either
answer, because it never gives DDE custody of any Anthropic credential in
the first place. The human has explicitly accepted a manual-approval-gated
(non-fully-autonomous) flow as sufficient, which is exactly Path A's shape.

**Recommended concrete path (Path A): build this first, independently of
Path B.**

1. Land `adapters/claude/adapter.py` as a fail-closed policy shell,
   structured exactly as sketched in "#### Structural sketch" above:
   `register()`/`health()`/`capabilities()` real; `start()` calling
   `engine.governance.service.ApprovalService.require_approved(...)` —
   the module's own documented "fail-closed gate used by production
   mutation sites" — as the **mandatory human-approval enforcement point**,
   immediately before spawning `claude` as a subprocess, and never before
   an `Approval` row exists with `status == "APPROVED"` bound (via
   `scope_hash`) to that exact task's prompt/spec. No `StandingApproval`
   path for this `approval_type` — every single invocation requires its
   own human `ApprovalService.decide(decision="APPROVED", ...)` call,
   satisfying the human's explicit "approve every piece of work routed to
   Claude Code" instruction literally, not just in spirit.
2. As a small, explicitly-flagged prerequisite decision (not a new
   mechanism): add one literal — proposed `external_model_invocation` —
   to `APPROVAL_TYPES` in `engine/governance/types.py`, and to
   `STANDING_FORBIDDEN_TYPES` alongside `irreversible_effect` and
   `production_change`, so this approval class can structurally never be
   pre-authorized by a `StandingApproval`. This is the one schema-adjacent
   change Path A needs; it is additive to an existing enum, not a new
   contract, table, or migration.
3. `adapters/claude/adapter.py` must satisfy, and should be tested against,
   the explicit negative constraint from Finding 2/point 3 above: it never
   reads `~/.claude/.credentials.json` or any OS keychain Claude Code
   entry, never reads or forwards `CLAUDE_CODE_OAUTH_TOKEN` /
   `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` from a value DDE captured
   itself, and never calls an Anthropic API endpoint directly — its only
   supported vendor interaction is spawning the unmodified `claude`
   executable and reading its stdout/stderr/exit code, mirroring
   `ScriptedWorkerAdapter`'s existing subprocess pattern
   (`engine/workers/scripted_adapter.py`). This is what keeps this design
   inside Anthropic's own documented "official CLI, automated" carve-out
   (Finding 2) rather than the prohibited "third-party harness relaying
   subscription credentials" pattern.
4. Enforce "at most one live Claude Code `WorkerRun` at a time" inside the
   adapter itself (not deferred to routing), per Finding 3's confirmation
   that headless/subscription usage is quota-constrained and shared with
   the human's own interactive use.
5. `collect_usage()` reports cost honestly as unknown/zero-to-DDE
   (mirroring `ScriptedWorkerAdapter.collect_usage`'s existing "honestly
   zero... not fabricated" convention) rather than a fabricated per-token
   figure — DDE has no visibility into a subscription-metered
   invocation's actual cost (Finding 3).
6. This deployment shape only covers the human-present case from
   "### Deployment-shape differences" above (the operator's own machine,
   or the Windows-installer machine, with an already-`claude login`-
   authenticated OS user). It does not extend to unattended cloud/server
   deployment with no human locally logged in — that remains Path B's
   problem, deferred below.

**Path B — the broker/`DelegatedSessionProvider` contract from "Decision
(proposed)" above — remains deferred, not discarded**, as the answer for
the no-human-present (cloud/server) case only, now concretely understood
(per Finding 1) as "a human deliberately runs `claude setup-token` once and
chooses to hand DDE the resulting ~1-year OAuth token via
`register_delegated_session`." Do not build any part of Path B — no
`DelegatedSessionProvider`, no `register_delegated_session`, no persisted
session table with real data — until a human explicitly answers Open
Question #1 (may DDE hold that long-lived token at rest at all, even
custodied and never released) for that specific, narrower shape. The
`AnthropicApiKeyProvider` fallback tier and the `FallbackCredentialProvider`
composition wrapper (see "### Fallback ordering..." above) remain
buildable as ordinary static-secret contract work independent of Path A/B,
exactly as already described, and are unaffected by this update.

Do not touch `CredentialsPage.cs`/`ConfigWriter.cs` or attempt any
installer UX change until Path A's adapter has passed its own contract
tests (a real subprocess spawn behind a real, decided `Approval`, and a
test asserting the negative "never touches a credential file/env var"
constraint above). The installer question remains downstream of, and does
not need to precede, this adapter work — if anything, Path A *simplifies*
the eventual installer story, since there is no session/token material for
`ConfigWriter.cs` to ever write anywhere; the installer's only remaining
job for Claude Code is confirming a human has already run `claude login`
in the relevant OS account, not collecting or persisting any secret.

This still mirrors how `adapters/cursor/adapter.py` was sequenced (real,
honest, fail-closed shell before any live vendor call) and now additionally
mirrors `engine/workers/scripted_adapter.py`'s already-proven "real
subprocess behind a real, checked gate" pattern — Path A substitutes
`ApprovalService.require_approved` for `CapabilityLeaseService
.require_active` as the gate, because the resource being protected here is
a human's personal, rate-limited, ToS-bounded subscription seat, not a
workspace-scoped capability lease, and a human decision per invocation is
the more precise control for that resource than a machine-checked lease
would be.

## Status update — Path A implemented (2026-08-21)

The human has explicitly approved implementing Path A (see this file's
opening decision note); it is now built, per the "Recommended concrete
path (Path A)" list above:

- `adapters/claude/adapter.py` (`ClaudeCodeWorkerAdapter`,
  `ClaudePromptBinding`, `claude_invocation_scope_hash`) and
  `adapters/claude/__init__.py` — the fail-closed-until-approved
  `WorkerAdapter` implementation described in "#### Structural sketch"
  above. `start()` calls `ApprovalService.require_approved(...)` before
  spawning anything; on approval it spawns the configured `claude` binary
  (default `claude -p "<prompt>"`, both overridable, not hardcoded) via
  `WorkspaceService.execute()` inside the run's own workspace, mirroring
  `ScriptedWorkerAdapter`'s real-subprocess pattern. It never reads a
  credential file, keychain entry, or `CLAUDE_CODE_OAUTH_TOKEN`/
  `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`, and never calls an Anthropic
  API directly (see the module's class docstring for the explicit,
  checkable negative constraint).
- `engine/governance/types.py` — added `external_model_invocation` to both
  `APPROVAL_TYPES` and `STANDING_FORBIDDEN_TYPES`, per item 2 of the
  Recommendation. No `StandingApproval` can ever cover this class; every
  invocation requires its own `ApprovalService.decide(...)` call.
- `engine/capabilities/seed.py` — registered `capability.claude_code_invoke`
  (`side_effect_class="EXTERNAL_NON_IDEMPOTENT"`, `enforcement_tier="T1"`)
  in the seeded capability portfolio, satisfying AGENTS.md's "every new
  side-effecting capability declares a `side_effect_class`."
- `tests/unit/test_claude_adapter_requires_approval.py` — contract tests
  proving `start()` fails closed (`POLICY_DENIED`) without an approved
  `Approval`, that a differently-scoped approval cannot authorise a
  different prompt, that a matching decided `Approval` allows a real
  (test-double) subprocess to run, and — the regression test — that
  `external_model_invocation` cannot be granted as a `StandingApproval`
  (`grant_standing` fails closed; `STANDING_FORBIDDEN_TYPES` membership is
  asserted directly).
- `tests/unit/test_layout.py` — added a boundary case asserting `engine/**`
  never imports `adapters.claude`, mirroring the existing `adapters.cursor`
  fencing.

No new JSON Schema/contract was needed: `approval_type` is stored as a
plain, unconstrained string in `schemas/objects/approval.json` (validated
only against the Python-side `APPROVAL_TYPES` frozenset), so adding this
literal did not require touching `schemas/` or regenerating
`engine/contracts/` (`scripts.generate_contracts --check` passes
unchanged).

Path B (the `DelegatedSessionProvider`/broker credential-holding design)
remains deferred, unbuilt, and blocked on Open Questions #1/#2 exactly as
this EDR already stated — nothing in this update resolves them.
