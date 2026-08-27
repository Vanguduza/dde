# DDE-066 chapter gate -- donor discovery & feature-function taxonomy
# ⟨product-studio-charter.md; Ch.13.8; Ch.12.4; Ch.9.3; EDR-0015⟩

**Mission:** appended Frontend Studio track / `DDE-066` -- classified
donor-search fan-out grouped by PRD feature. **Charter:**
`docs/planning/product-studio-charter.md` (DDE-066). **Not** DDE-067 GUI,
**not** DDE-068 Definition-of-Polished executors.

**Status:** CLOSED on `dde-066-donor-discovery`.

**CI / local proofs (2026-08-27):**

- `just check` green -- ruff / mypy (**392** files) / **1212 passed, 3
  skipped** (unit+contract+recovery) / `generate_contracts --check` /
  `generate_design_tokens --check` / contract pytest **211 passed** /
  design-lints baseline / dde-studio tests **67 passed** / desktop
  `tsc --noEmit`
- `tests/unit/test_donor_discovery.py` +
  `tests/unit/test_donor_discovery_postgres.py` +
  `tests/contract/test_donor_discovery.py`: allowlist, journal-before-fetch
  ordering, UNKNOWN not blind-retried, fail-closed classifier, quota
  exhaustion typed (not empty), pins in the same inventory, no engine
  httpx, adapter does not read process env.

## Prior landings this chain

| Mission | SHA | Verdict |
|---|---|---|
| DDE-065 | `9a8bb86` | PASS-WITH-EDR (EDR-0002, 0003, 0005, 0027, 0033) |

## What this mission wires

- `DonorDiscoveryService.search` (`engine.donor.discovery_service`): the
  production fan-out. Requires a real `WorkerRun` + grants
  `capability.donor_discovery` (`EXTERNAL_IDEMPOTENT`). Each outbound
  URI is allowlisted, a broker credential is minted, an ExternalEffect
  row is `prepare`d and `mark_sent` **before** the GET, then classified
  and grouped. DDE-046 pins load into the same inventory. Search-hit
  metadata is ingested so taint tags persist on Feature DNA.
- Host+path allowlist `schemas/design/donor_search_allowlist.json`
  (EDR-0015). Marketplace hosts (`themeforest.net`, …) are REJECTED at
  admission; fetch never runs.
- HTTP transport `adapters/donor/http.py` (httpx). `engine/donor/**`
  does not import httpx; the adapter does not read `os.environ`.
- Query ceiling `donor_search_max_queries` on `execution_plans.token_budget`
  (default 32). Exhaustion is `BudgetExhaustedError`, not an empty list.
- Grouped-results schema `schemas/design/grouped_donor_results.schema.json`.

## Charter MUST/shall at production call sites

| Rule | Production call site |
|---|---|
| Classify every source on the six-value scale BEFORE usable; UNKNOWN never silently OPEN_REUSE | `group_discovery_hits` (`engine.donor.grouping`), called from `DonorDiscoveryService.search` after fetch. Empty content defaults to `SOURCE_REFERENCE_ONLY`. |
| Group by PRD feature id; ungroupable → explicit `unmatched` | `group_discovery_hits`. Pins with no feature hint land in `unmatched` (not dropped). |
| Persist taint tags | `DonorDiscoveryService._persist_search_hits` → `DonorLabService.submit_uri` → `DonorTaintService.link` on Feature DNA. Pins already carry taint from DDE-046/047. |
| Classifier unreachable → empty results + typed refusal | `group_discovery_hits` returns empty groups / unmatched plus `refusals=("classifier_unreachable",)`. `ClassifierUnreachableError` remains the typed `CONTEXT_INCOMPLETE` refusal. |
| Every outbound query: idempotency key + ExternalEffect journal **before** retry/fetch (Ch.12.4) | `DonorDiscoveryService._journaled_get`: `ExternalEffectService.prepare` then `mark_sent` then transport. Timeout → `mark_unknown`. A new WorkerRun / new key for the same mission+URI+GET while UNKNOWN is `EFFECT_CONFLICT` (postgres proof). Same search key replays the ledger and does not fetch again. |
| EDR-0015 broker-issued credentials, no ambient env | `CredentialBrokerService.issue` after `require_active` on `capability.donor_discovery`. Secret is passed once into the injected transport; adapter never reads process env. |
| EDR-0015 control-plane (not T2 worker sandbox) | `DonorDiscoveryService.search` runs in-process. It journals against the caller's existing `WorkerRun` + a granted lease — the same pattern as `IntegrationQueueService.submit`. No synthetic run UUID. |
| Side-effect class declared | `capability.donor_discovery` in `SEED_CAPABILITIES`: `EXTERNAL_IDEMPOTENT`. |
| Injection screening before model-visible surfaces | `screen_donor_text` in `_classify_hit` before `classify_donor`. Findings blank the summary used for classification. |
| Manual DDE-046 pins in the same grouped inventory | `_pin_hits` loads project artifacts as `DiscoveryHit(pin=True)` into `group_discovery_hits`. |

## Adversarial self-check

- A new `WorkerRun` or new idempotency key **cannot** blind-retry an
  `UNKNOWN` GET: journal scope is `(mission, donor_search, uri, GET)`.
  Proven in `test_unknown_get_is_not_blind_retried`.
- A new key after `CONFIRMED` may refresh (GET is idempotent; CONFIRMED
  is not a blocking status). Replay of the **same** search key does not
  fetch.
- Classifier crash cannot yield OPEN_REUSE: grouping returns empty +
  refusal and skips persist.
- Marketplace URIs never reach fetch (`assert_uri_admitted` before
  prepare).
- `search` is a real mutation (journal + optional ingest), not a
  read/helper.

## Deferred (proposed / still-open EDRs)

| ID | Item |
|---|---|
| **EDR-0002 / 0003 / 0005 / 0027 / 0033** | Unchanged |
| Gateway command `frontend.donors.run_discovery` + Studio Donors view | **DDE-067**. Engine service is the mutation; GUI/Gateway wiring is the next mission. No new EDR. |
| Captured GitHub PAT in the broker vault (vs LocalSecretProvider synthetic mint) | Same DDE-019 lowest-tier provider already used for brokered issuance. Search refuses ambient `GITHUB_TOKEN`. Live GitHub 200s wait on a captured secret through the existing broker capture path — not a silent env read. No new EDR. |
| DD207+ / silhouette / density / VLM | DDE-068; **EDR-0016** still proposed. |
| EDR-0011 T2 worker proxy | Unchanged; this surface stays control-plane per EDR-0015 until that machinery lands. |

## Verdict

**PASS-WITH-EDR.** EDR-0002, EDR-0003, EDR-0005, EDR-0027, EDR-0033
remain open (unchanged). DDE-066 charter MUST/shall rules are named at
`DonorDiscoveryService.search` / `_journaled_get` / `group_discovery_hits`
/ `DonorLabService.submit_uri`. EDR-0015 is accepted and wired (allowlist,
broker issue, journal-before-fetch, fail-closed classifier, quota).
DDE-067 is the next sequential mission under standing auto-resume.
DDE-068 stays gated on EDR-0016.

**Landed:** 2026-08-27 on `dde-066-donor-discovery`.
