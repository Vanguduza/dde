# EDR-0011 — T2 network-egress and container-level containment: gate the
# remaining ambient surfaces a local-process backend cannot reach

> **ACCEPTED 2026-08-24 by explicit human project-owner standing directive
> ("accept and fix all EDRs according to best recommended solutions").** The
> authoritative record is the accepted row in the Project Truth `edrs` table
> (`edr_id=01a0341c-702d-7b9d-a457-0ca85a215fcc`, owner project
> `9b6f1a58-e29a-4a35-a8e2-8e6c0f4b7d11`, written via
> `engine.truth.service.TruthService.propose_edr` + `accept_edr`). This file
> remains as readable documentation; where wording differs, the `edrs` row
> outranks it. Acceptance adopts **Option B** (per-run namespace/proxy
> admission) with its machinery deferred to the first non-DDE-native
> execution substrate (gap-closure-record §6.3); the one wired-now egress
> surface is EDR-0015's broker-admitted control-plane donor search. The full
> accepted decision is recorded in the ACCEPTANCE section at the end of this
> file.

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. Following the convention established in
> `EDR-0001`–`EDR-0010`, this file was filed as a **markdown pre-image** of
> the eventual `edrs` row (AGENTS.md forbids editing `docs/truth/**` as a
> side effect). The durable row now exists (see the acceptance note above);
> this file stays as the readable pre-image of that row.

- **slug:** `EDR-0011`
- **status:** `accepted (2026-08-24)`
- **supersedes:** none
- **affected_requirement_slugs:** none filed yet
- **raised during:** the T2-containment queue item in the capabilities
  territory. Chapter 14/T2's ambient-credential containment now covers
  environment-variable filtering (`LocalProcessBackend._contained_environment`),
  lease/credential admission gating (kill flag at checkout and broker
  admission), and — as of this mission — arm-time termination of registered
  in-flight local subprocesses (`engine.capabilities.process_registry`,
  wired into `CapabilityLeaseService.arm_run_stop`). Two ambient surfaces
  remain **ungated**, and both are outside what a stdlib-only local backend
  can ever reach.

## Context

Chapter 7.2's T2 tier promises that for any autonomous run the Execution
Environment is the enforcement boundary: container/microVM isolation,
workspace-only bind mount, non-privileged user, seccomp profile, resource
limits, and an egress proxy with per-environment allowlists; revocation
latency is "bounded — revocation kills the egress allowlist entry and
terminates the run". This repository's one real substrate,
`LocalProcessBackend`, is an honest plain-subprocess implementation: it
filters the environment, registers live children for arm-time termination,
and records everything it cannot enforce on `IsolationReport.gaps`
(`NETWORK_ISOLATION_GAP`, `RESOURCE_LIMIT_GAP`, `AMBIENT_ENVIRONMENT_GAP`)
rather than claiming it.

Two T2 surfaces stay genuinely open:

1. **Network egress.** A spawned subprocess shares the host network stack.
   Nothing gates which hosts it may reach, so a worker-controlled command
   can exfiltrate whatever secret material its containment left reachable.
   Chapter 7.2 rule 2 ("All egress through the proxy ... direct IP egress is
   dropped") is recorded, not enforced. The kill flag does not consult
   egress either — an armed stop cannot un-send packets already flowing.
2. **Container-scoped runs.** When a run executes inside a container (a
   `devcontainer-postgres-1`-style sidecar, a future `docker` backend), DDE
   today has no policy object that says what isolation that container must
   carry, no way to enumerate or terminate processes inside it from the
   control plane's process registry, and no per-run network namespace. The
   registry keyed by `(tenant, project, run, lease)` sees only pids that are
   direct children of the DDE process; a command's own grandchildren and any
   container it enters are disclosed residuals (`process_registry` module
   docstring), not enforced boundaries.

## Decision (proposed)

Adopt **Option B: per-run network namespace/proxy admission**, with Option A
recorded as rejected-for-now rather than forbidden.

| Option | Mechanism | Trade-offs |
|---|---|---|
| **A. Container policies first** | Declare per-container isolation policies (bind mounts, capabilities, network mode) checked at admission by a new `docker` backend; egress gated by the daemon's network config | Matches where the industry ecosystem already is; but on this codebase it makes the *daemon* the trust root, gives per-run revocation latency bounded by Docker's own tooling, and leaves every non-container run (today: all of them) with no egress story at all |
| **B. Per-run namespace/proxy admission (recommended)** | Every run-scoped spawn — local or containerized — is admitted through one egress boundary: DNS pinned to a DDE-owned resolver, HTTP(S) through a local allowlist proxy whose entries derive from the ExecutionPlan's capability set (Chapter 7.2 rule 2 verbatim); container backends additionally run each run in its own namespace so the boundary is structural, not advisory | One enforcement point for all substrates; revocation = drop the run's proxy entries + sweep (already built); cost: a real proxy component to operate, and POSIX-only namespaces (Windows dev loops keep the proxy without the namespace) |

Consequences of acceptance (Option B):

- New component ownership: an egress proxy/resolver becomes part of the
  control plane surface, with its own availability and audit obligations;
  its allowed-request log becomes the Chapter 12.4 effect record for T2
  workers (Chapter 7.2 rule 5).
- `LocalProcessBackend.run_for_authority` gains an env-injection step
  pointing the child at the proxy; `IsolationReport.network_policy.enforced`
  flips to true only when the proxy is actually in path — never before.
- Process-tree reach grows honestly: namespace-scoped kills can address
  grandchildren that today survive the sweep; the disclosed residual shrinks
  to nothing only when the container backend lands (Option A's machinery
  remains available for exactly that substrate later).
- Windows caveat: no user-space namespaces; enforcement there is
  proxy-admission only, disclosed per-platform on `IsolationReport`.
- Rejection keeps today's honest state: egress ungated, container runs
  outside the registry's reach, both named as gaps rather than silently
  relied upon.

## Consequences

- Human decision required before any code moves: accepting this EDR is what
  authorizes a new long-running control-plane component; rejecting it should
  simultaneously retire the phrase "T2" from any descriptor that cannot meet
  Chapter 7.2 on this platform.
- Either option implies a blueprint-visible change to Chapter 7.2's
  enforcement-mechanism table (naming the chosen mechanism), which is a
  Project Truth edit proposed here, not made here.

## ACCEPTANCE (2026-08-24)

**Accepted — Option B (per-run namespace/proxy admission), the recommended
option**, by the project owner's standing directive of 2026-08-24 ("accept
and fix all EDRs according to best recommended solutions"). The authoritative
row is `edr_id=01a0341c-702d-7b9d-a457-0ca85a215fcc`; where this section and
the row differ in wording, the row outranks this file.

**OpenSandbox-informed posture (donor pattern, named).** The acceptance memo
obligation from `docs/planning/opensandbox-graft-research-integration.md`
(Pattern 1, egress sidecar) is discharged as follows: OpenSandbox ships in
production almost exactly what Option B sketches — FQDN/wildcard allow-deny
egress sidecar, DNS-pinned resolution plus nftables enforcement of resolved
IPs/CIDRs, a runtime policy API (`GET/PATCH /policy`), NET_ADMIN stripped
from the main sandbox container so only the sidecar mutates network rules,
and a credential vault injecting outbound credentials at the sidecar so real
secrets never enter sandbox env/commands/files/logs. This is adopted as the
donor design for DDE's future proxy/resolver component and the strongest
known implementation of Ch.7.2 rules 1–5. Their documented gVisor×nftables
incompatibility is also adopted: isolation-tier choice and egress mechanism
are interacting axes, not independent ones.

**Wired now vs deferred.**

- Wired now by this acceptance: nothing in code. Acceptance authorizes the
  posture only; the single live admitted egress surface in the system is
  EDR-0015's broker-admitted control-plane donor search, which migrates onto
  this boundary when it lands.
- Deferred, with its trigger (gap-closure-record §6.3): the egress
  proxy/resolver component itself, env-injection pointing
  `LocalProcessBackend` children at the proxy,
  `IsolationReport.network_policy.enforced` flipping true only when the proxy
  is actually in path, namespace-scoped kills reaching grandchildren, and the
  Ch.7.2 enforcement-mechanism-table amendment. **Trigger: the first mission
  that lets a non-DDE-native execution substrate execute real commands on
  this deployment.** That mission MUST evaluate the OpenSandbox reference
  implementation of the hard parts before specifying DDE's own component;
  any divergence must be justified in its memo, not silent.
- Windows keeps proxy-admission-only enforcement (no user-space namespaces),
  disclosed per-platform on `IsolationReport`.

Until the substrate lands, "T2" remains a descriptor no local substrate may
claim, and `NETWORK_ISOLATION_GAP` stays the truthful disclosure for
worker-run egress.
