"""Credential Broker (Chapter 14.3) -- DDE-019.

AGENTS.md's literal boundary rule -- "Nothing except `engine/capabilities/
broker/**` reads secret material" -- names this exact package. Chapter 3.6's
repository layout lists `capabilities/` as holding "registry, leases, proxy,
broker" together; Chapter 3.8's ownership matrix gives "Credential handle"
its own row with owner module `capabilities/broker`, created by "Credential
Broker", "Status only", transaction boundary "Broker" -- distinct from
`CapabilityLease`'s own `capabilities` / "Lease manager" row one line above
it. This subpackage is that distinct owner.

**Scope determination (read `engine.capabilities.broker.service`'s module
docstring for the full argument).** This codebase has no real external
provider integration anywhere yet -- DDE-016's seeded Stage 1 capability
portfolio (`engine.capabilities.seed.SEED_CAPABILITIES`: `run_local_process`,
`workspace_filesystem`, `git_operations`) needs no external credential to
function, and no Stage 2/3 mission in the S2-S3 range charters one either.
Chapter 14.3's own preference order for what a broker hands out --
"workload identity -> OIDC-exchanged short-lived token -> provider-issued
temporary credential -> signed execution handle -> static secret behind the
broker" -- explicitly includes "a static secret behind the broker" as its
own last, legitimate tier; it does not mandate a live OAuth/OIDC federation
for every broker to exist. This mission therefore builds the broker's real
mechanics (issuance, scoping, expiry, renewal, revocation, audit) in full,
proven end-to-end against one real, working, low-stakes `CredentialProvider`
implementation (`provider.LocalSecretProvider`) that generates a genuine
short-lived random secret without any external network call or third-party
account -- the honest, buildable instance of that lowest preference tier,
clearly labelled as a local/synthetic provider rather than a claim of real
cloud integration. Real external provider integration (AWS/GCP/a named SaaS)
is deferred to whichever future mission actually charters a capability that
needs one; there is none today."""

from __future__ import annotations
