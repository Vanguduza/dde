# Repo Mining

Load before consulting ANY external repository or AI-generator output for UI
work. Authority: `docs/planning/dde-frontend-ux-playbook.md` §2, §3, §6.2.

## Steps

1. Classify the intended extraction against the layer table (playbook §2.1).
   Theme values, screen layouts, navigation graphs, motion specs, microcopy:
   NOT MINABLE — stop. Test-harness patterns, gallery structure, schema
   validation patterns, component discipline, CSS technique, theme code
   structure: minable with provenance.
2. Licence check BEFORE deep reading (§3): MIT/Apache-2.0 fine with
   attribution; MPL-2.0 fine as dependency; GPL family = ideas only, zero code
   transfer; unlicensed = ask the owner first.
3. Extract the minimal reference; write the adaptation plan (renames to DDE
   conventions, token conformance, lint compliance) before coding.
4. Implement the adaptation. More than ~40% of the copied file surviving
   verbatim requires justification in the PR body — or split the extraction.
5. Append one row to `docs/design/provenance-ledger.md`
   (`repo@commit/path`, layer mined, licence, adaptation summary) and close
   the PR with a `References:` footer naming each extracted item.

## Red flags

- "I'll just adapt their palette slightly" — palettes are never-minable.
- Generator output pasted directly — re-express through DDE tokens first.
- Licence discovered after implementation — rewrite every touched file.
