# DDE-065 chapter gate -- generation-prompt compiler
# ⟨product-studio-charter.md; Ch.4.3; Ch.15.5; playbook §1.1 / §4.2 / §10.1;
# design-tooling-integration.md Phase 1⟩

**Mission:** appended Frontend Studio track / `DDE-065` -- deterministic
generation-prompt compiler. **Charter:** `docs/planning/product-studio-charter.md`
(DDE-065). **Not** DDE-066 donor discovery, **not** DDE-067 GUI, **not**
DDE-068 Definition-of-Polished executors.

**Status:** CLOSED on `dde-065-generation-prompt-compiler`.

**CI / local proofs (2026-08-27):**

- `just check` green -- ruff / mypy (**387** files) / **1196 passed, 3
  skipped** (unit+contract+recovery) / `generate_contracts --check` /
  `generate_design_tokens --check` / contract pytest **206 passed** /
  design-lints baseline / dde-studio tests **67 passed** / desktop
  `tsc --noEmit`
- `tests/unit/test_generation_prompt_compiler.py` +
  `tests/contract/test_generation_prompt_compiler.py`: fail-closed
  refusals, byte-stable hash, nevers embed, off-token scan, no
  network/skill/graph imports.

## Prior landings this chain

| Mission | SHA | Verdict |
|---|---|---|
| DDE-064 | `8075815` | PASS-WITH-EDR (EDR-0002, 0003, 0005, 0027, 0033) |

## What this mission wires

- `compile_generation_prompt` (`engine.studio.compiler`): the only
  function that may mint a compiled UI generation prompt. Fail-closed
  on missing art-direction, unresolved tokens pin, unknown playbook
  version, no approved requirements, missing dials/Design Read/palette
  roles, undeclared layout pattern, or Inter-as-display without an
  explicit flag. Typed refusal is `CONTEXT_INCOMPLETE` (Ch.15.5 CONTEXT
  family) via `CompileRefusedError`; `details.missing_artifact` names
  the unresolved input. No WorkerRun is created on this path.
- Art-direction schema + font corpus + nevers + copy law + layout
  pattern map under `schemas/design/`. Motion-identity presets
  (`restrained` / `measured` / `expressive`, spring pinned `none`) on
  `schemas/design/tokens.json`.
- Preview catalog HTML from the product's own sheet
  (`engine.studio.preview.render_preview_catalog`).
- Composition constraint: this package does not import
  `engine.planning.registry` / `service` / `planner`. Decomposition
  remains DDE-040 `submit_draft` → `validate_draft` → `promote_draft`.

## Charter MUST/shall at production call sites

| Rule | Production call site |
|---|---|
| Byte-stable output for identical inputs (hash recorded) | `compile_generation_prompt` returns `content_hash = sha256(prompt_body)`. Contract test pins equality across two calls. |
| Refuse when PRD has no approved Requirements or unknown token/playbook version | `compile_generation_prompt`: `approved_requirements` / `tokens` / `playbook` refusals. |
| Refuse when art-direction absent or tokens pin does not resolve; name the missing artifact | `compile_generation_prompt` + `resolve_tokens_pin` + `validate_art_direction`. No stub/degraded compile path. |
| Refuse when dials, Design Read, or semantic palette roles are missing | `validate_art_direction`, called from `compile_generation_prompt`. |
| Embed every §1.1 never and token-sheet reference so the prompt cannot instruct off-token values | `_assemble_prompt` lists every never id/statement and semantic token names only. Contract scan: every `#hex`/`rgb()` in the prompt is a token-sheet (or never-catalog `#fff/#000`) literal. |
| Record provenance so a screen traces to its PRD | `GenerationPrompt.provenance`: prd_id/version, requirement ids/slugs, feature ids, art-direction id/version, playbook and tokens pins, font pairing, layout patterns. |
| MUST NOT network or model call in the compile path | AST scan of `engine/studio/**`; no http/sdk imports. |
| MUST NOT load third-party design skills | AST/haystack scan; encodings only. |
| MUST NOT mint TaskGraphs | AST scan: no import of planning registry/service/planner. |
| Inter banned as default display | `validate_art_direction` / font corpus `inter-explicit` requires `explicit_inter_display`. |

## Adversarial self-check

- A new `WorkerRun` or new idempotency key cannot bypass these controls.
  The compiler is not on a worker/retry path. The only mint is
  `compile_generation_prompt`; every refusal is typed and non-retryable.
- Re-running compile with identical inputs yields the same hash. It
  still refuses stubbed art-direction.
- `compile_generation_prompt` is a real mint of the compiled-prompt
  artifact (content-addressed return value). It is not a read/helper.
  It does **not** insert a Core table row. Persistence onto Gateway /
  Studio Intake is DDE-067 and is not claimed here.
- `missing_artifact="approved_requirements"` is used instead of the
  Truth table name `requirements`, so Ch.3.8 ownership scan stays
  honest.

## Deferred (proposed / still-open EDRs)

| ID | Item |
|---|---|
| **EDR-0002 / 0003 / 0005 / 0027 / 0033** | Unchanged |
| Donors → screen provenance | DDE-066 grouped donors + DDE-067 authoring. This mission records PRD → requirements → features → prompt. No new EDR. |
| Durable Gateway persistence of the compiled prompt | DDE-067 Intake surface. Compiler return value is the artifact. No new EDR. |
| DD207+ / silhouette / density / VLM | DDE-068; EDR-0016 still proposed. |
| Donor-search egress | **EDR-0015 ACCEPTED** (2026-08-24). DDE-066 may start after this gate. |

## Verdict

**PASS-WITH-EDR.** EDR-0002, EDR-0003, EDR-0005, EDR-0027, EDR-0033
remain open (unchanged). DDE-065 charter MUST/shall rules are named at
`compile_generation_prompt` / `validate_art_direction` /
`resolve_tokens_pin`. Art-direction record is no longer a pacing stub:
the first real compile is possible when a product supplies a valid
record plus a tokens pin. EDR-0015 is already accepted, so DDE-066 is
the next sequential mission under standing auto-resume.

**Landed:** 2026-08-27 on `dde-065-generation-prompt-compiler`.
