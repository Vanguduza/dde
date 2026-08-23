# EDR-0011 — T2 network-egress and container-level containment: gate the
# remaining ambient surfaces a local-process backend cannot reach

> **Location note.** Per Chapter 3.6, an EDR is a row in the `edrs` table,
> written only by `engine/truth/`. Following the convention established in
> `EDR-0001`–`EDR-0010`, this file is a **markdown pre-image** of the eventual
> `edrs` row, filed as the proposal itself (AGENTS.md forbids editing
> `docs/truth/**` as a side effect). **This file is not itself an accepted
> EDR.** `status` is `proposed`; only a human decision can move it to
> `accepted`.

- **slug:** `EDR-0011` (provisional)
- **status:** `proposed`
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
