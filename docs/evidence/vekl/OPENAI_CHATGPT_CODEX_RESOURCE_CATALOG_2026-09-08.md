# OpenAI ChatGPT / Codex resource-catalog integration evidence

Date: 2026-09-08
Upstream repository: `https://github.com/openai/plugins`
Pinned upstream commit: `1e285826e604f66f7208f7ac4dba0fe8341d1f57`
Runtime catalogue ID: `dde.openai-chatgpt-codex-plugin-catalog`

## Finding

Production VEKL canon already named OpenAI first-party skills/resources as a candidate
source family, but the runtime had no concrete OpenAI/ChatGPT/Codex catalogue. The
Anthropic engineering-playbook tranche therefore did **not** mean ChatGPT Skills,
plugins, apps or tools were already operationally represented.

OpenAI's current plugin model packages repeatable workflows as plugins. A plugin may
include Skills/instructions, connected apps, app templates and, in the public Codex
plugin repository, optional MCP/app/agent/command/hook surfaces. Those surfaces map
well to VEKL only when decomposed: knowledge about a bundle is separate from permission
to ingest its Skill text and separate again from permission to execute a tool/app/MCP.
## Pinned engineering subset

The first concrete snapshot records 10 high-value application-engineering bundles and
98 direct `plugins/<name>/skills/<skill>/SKILL.md` paths:

- `build-ios-apps` 0.1.2 — 9 Skills, MIT, MCP present;
- `build-macos-apps` 0.1.4 — 11 Skills, MIT;
- `build-web-apps` 0.1.2 — 6 Skills, MIT;
- `build-web-data-visualization` 0.1.21 — 18 Skills, MIT;
- `openai-developers` 1.2.3 — 5 Skills, proprietary, app + MCP present;
- `product-design` 0.1.52 — 10 Skills, proprietary;
- `codex-security` 0.1.22 — 14 Skills, proprietary, app + MCP present;
- `test-android-apps` 0.1.2 — 2 Skills, MIT;
- `plugin-eval` 0.1.2 — 5 direct Skills, MIT;
- `data-analytics` 0.2.8 — 18 Skills, proprietary, app + MCP present.

The same pinned audit records **component-surface presence only** across these bundles:
10 Skill surfaces, 10 agent-material surfaces, 7 script surfaces, 4 MCP surfaces, 3 app
surfaces and 1 command surface. No hook surface was observed in this selected subset.
These are bundle-presence facts, not executable-component qualifications or counts of
individual MCP tools/agent definitions/scripts. Each concrete component must still be
resolved and qualified independently before activation.

Representative useful resources include SwiftUI patterns and simulator proof, frontend
build/debug/visual QA, React/shadcn/Supabase/Stripe guidance, Android emulator QA,
ChatGPT Apps SDK scaffolding, product-design image-to-code + design-QA loops, security
scan/remediation workflows, analytics/reporting, and skill/plugin evaluation.
## Implemented boundary

`engine/vekl/openai_catalog.py` stores only deterministic DDE-authored metadata about
the pinned snapshot. `vekl.openai.install_catalog_candidates` persists those entries as:

`PACKAGE_METADATA + S7_DISCOVERY_ONLY + SOURCE_REFERENCE_ONLY + DISCOVERY_ONLY`.

Every candidate has `source_uri=None`, no required capability, no filesystem/network/
secret scope, `PURE_READ` side-effect class, and no executable activation mode. The row's
`component_surfaces` metadata records only which kinds of upstream bundle surfaces were
observed at the pinned commit; it grants none of them authority. Repeated
installation reuses the exact content hash/revision. No OpenAI plugin, Skill body, app,
MCP server, tool, hook or command is fetched, installed, authenticated or executed by
this command.

To become usable guidance, an upstream Skill must later be resolved to an exact source
artifact, admitted through Source Intelligence, licence/provenance screened, prompt-
injection screened and reference-qualified. Executable plugin/app/MCP/tool components
must additionally be decomposed and pass the normal execution quarantine/evaluation,
capability, scope, sandbox, external-effect and verification gates.

## Social-media `AppCreator` disposition

The supplied social-media screenshot attributes a fast iOS build to an `AppCreator`
Skill. That name is **not** present in this pinned first-party OpenAI engineering subset
and is not treated as an OpenAI-owned Skill. Public search evidence points to community
references to “AppCreator buildability ideas,” which is consistent with a personal or
third-party Skill. VEKL therefore classifies it as unresolved third-party provenance
until an exact publisher/repository/revision/licence is supplied and qualified.
## Verification obligations

Five focused unit tests prove the catalogue is pinned, deterministic, metadata-only and
zero-authority; that the high-value engineering families, representative Skill IDs and
audited component-surface counts are present; and that `AppCreator` is not silently
relabeled first-party. The
The PostgreSQL integration contract proves installation creates only `DISCOVERED` metadata
rows and is idempotent on a second installation. It is now service-backed evidence rather
than only committed test code: GitHub Actions run `34234702640` passed this case as part
of the complete **6/6** VEKL PostgreSQL test set.

This catalogue is deliberately a first tranche, not a claim that every plugin currently
visible in the ChatGPT Plugin Directory is already ingested. The public repository is
larger and evolves. Future catalogue refreshes must pin a new commit, diff manifests,
re-evaluate licences/components, and never auto-promote `main`/`latest` into active VEKL.

## Final non-service verification

At this continuation boundary: 54 focused VEKL/playbook/catalogue/contract tests pass;
the full pure-unit run is 731 passed / 5 skipped / 562 integration deselected; all 223
contract tests pass; Ruff and formatting are clean; strict MyPy is clean across 581
engine source files; generated contract/design-token/binding drift checks pass; the
committed design-lint baseline remains at 70 with no increase; extension/shared tests are
77/77; desktop and UI TypeScript checks pass; and the React/Vite production build passes.

The local shell still exposes no PostgreSQL/Redis/Docker runtime, but that no longer blocks
this catalogue's persistence evidence. Service-capable CI run `34234702640` passed all
**6/6** VEKL PostgreSQL tests, the full database-backed unit/contract/recovery gate
(**1550 passed / 7 skipped**), **5/5** integration tests, and a live reversible Alembic
`head -> base -> head` cycle including migration `0038`. No catalogue candidate gained
additional execution, network, secret or tool authority as a result of this certification.

## CI portability closure

The first pushed continuation exposed two pre-existing Windows-only CI defects outside
the OpenAI catalogue logic. Windows CPython does not ship the IANA timezone database,
so `ZoneInfo("UTC")` failed despite passing on Linux. DDE now declares `tzdata>=2025.2`;
the lock resolved `tzdata 2026.3`, published by the Python Software Foundation under
Apache-2.0. The dependency is required for cross-platform IANA timezone semantics rather
than replacing stdlib `zoneinfo`.

The same Windows checkout converted the one DDE component-library TSX source to CRLF,
invalidating its content-addressed catalogue hash. `.gitattributes` now pins
`schemas/design/library/**` to LF so the exact repository-byte hash remains deterministic
across Linux and Windows. Neither repair broadens VEKL authority or egress.
