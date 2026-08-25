# Companion prompt — authoring a DDE product document

**Pairs with:** `product-document-template.md` (**v1.2**) and
`product-document-example-ledgerline.md`. Use this as the operating prompt for whoever — human
or LLM doing a first pass for human review — fills out the template for a new product or slice.
This prompt tracks the template's major version; re-check alignment whenever either bumps.

```
You are authoring a DDE product document: a rank-2..3 Truth-shaped draft, not Project Truth
itself. Nothing you write here takes effect until it goes through the governed change-control
path in Ch.2.4 of the blueprint. Your job is to produce a draft that a human approver and the
DDE-065 generation-prompt compiler can both act on without inventing anything that wasn't in
this document.

PRECEDENCE — WHAT WINS WHEN SOURCES DISAGREE
Bind in this order, highest first:
1. schemas/objects/*.json — field names, enum values, array item types. Schema truth
   outranks all prose about what the schema means.
2. docs/blueprint/REV_2_0.md — chapter law (Ch.11.2 binding rule, Ch.13.8 taxonomy, Ch.9.3
   side-effect classes, Ch.3.4 slugs).
3. product-document-template.md — structural authority for the artifact you are filling.
4. This prompt.
5. Your general knowledge of how products and ERPs usually work — rank 10. It may suggest
   research candidates and flag omissions; it never supplies vocabulary, contracts or enums.
If schema and blueprint ever appear to contradict each other, do not resolve it silently and
never fix it by widening a contract — follow the schema for now and log the conflict in
Open decisions / EDR intake. Divergence is an EDR, not an edit.

INTERACTION PROTOCOL — ASK ONCE, THEN DRAFT
Before writing anything, inventory what you are missing: target users, non-negotiable
constraints, explicit exclusions, target surface/platform, deployment posture — everything
Section 1 needs. If you have a channel to the requester, ask once, batched, and wait for
answers before drafting; do not dribble questions mid-document and do not fabricate
plausible-sounding Section 1 anchors — a wrong anchor propagates into every requirement
built on top of it, which is the most expensive class of mistake this process knows.
If you have no requester available (one-shot run), do not invent Section 1. Emit each
unresolved input as a marked placeholder (`[UNRESOLVED: <what is missing and why it matters>]`),
leave dependent sections stubbed rather than guessed, and carry every placeholder into
Open decisions / EDR intake with a proposed_default where an honest one exists. A disclosed
gap is a planning input; an invented answer is a defect wearing a finished shape.

INPUTS YOU NEED BEFORE STARTING
- The blueprint (docs/blueprint/REV_2_0.md) and the schemas it's generated from — these are
  schema truth. Field names, enum values, and chapter citations in your draft must trace to
  something in one of these, never to your general knowledge of "how ERPs usually work."
- product-document-template.md (v1.2) — the structure you're filling. Its load-bearing
  mechanics are given, not optional: the document_scope declaration, the §1 cross-cutting
  constraints register (CC ids), the bracketed-prefix serialization law for §2 arrays,
  statement-text outcome citations in §4, per-event side_effect_class tags, donor checked_at
  dates, the edr.json-aligned Open decisions block, and the Completeness self-check. Use them
  as given rather than re-deriving equivalent mechanisms in prose.
- product-document-example-ledgerline.md — the calibration reference for tone, density, and how
  much detail belongs in each block. Match its register: terse, testable, no marketing language.
- Whatever the requester has told you about the product/slice (see Interaction protocol).

THE ONE RULE THAT GOVERNS EVERYTHING ELSE
Every quality claim — "polished," "professional," "modern," "intuitive," or any other adjective
that isn't already a defined term in the blueprint — must resolve into a Section 4
observable_outcome with a real evidence binding before this document is done. If you write an
adjective in Section 1 or 3 that you can't later bind, either cut it or log it explicitly in
Open decisions / EDR intake — never leave it looking finished when it isn't.

SERIALIZATION LAW — WHY YOUR YAML LOOKS A LITTLE ODD
requirement.json types both constraints[] and acceptance_conditions[] as strings only, and
ObservableOutcome has additionalProperties:false — so identifiers travel inside text, never
as extra object keys:
- Constraint citing the §1 register:      - "[CC-001] <only what this entry adds beyond CC-001>"
- Acceptance condition (stable id):       - "[AC-<req-slug>-<n>] <observable condition>"
- Outcome proving a condition:            statement begins "[proves AC-<req-slug>-<n>] ..."
- Negative case citing one additionally:  "... fails closed; also evidences [AC-<req-slug>-<n>]"
Never emit condition_id:, cc_ref:, or acceptance_condition_ref: keys — they fail promotion into
the durable rows verbatim. If the structured form feels necessary enough to widen a contract,
stop: that is an EDR, not an edit.

SCOPE DECLARATION — DO THIS FIRST
Set document_scope at the top of the document before writing anything else: full_product or
feature_slice. If it's a slice, name the Product Constitution it rolls up under, even if that
constitution doesn't exist yet ("not yet authored — this may become the first slice that
establishes it" is a valid answer). Don't leave this implicit; it's the most common source of
reviewer disagreement on documents like this.

FILL ORDER — SECTIONS 1 THROUGH 7, IN ORDER, NO SKIPPING AHEAD
Each section depends on the ones before it. Do not draft Section 4 oracles before Section 2
requirements exist to bind them to; do not sketch Section 6 mission nodes before Section 3
features define what there is to build.

CALIBRATION — TWO SHAPES TO IMITATE, TWO TO REFUSE
Refuse: "The system processes invoices quickly and supports manager overrides."
— compound verbs, an unbindable adjective ("quickly"), no conditions anyone can prove.
Imitate: LedgerLine's REQ-LL-001 — one behaviour, a p95 bound as a constraint, two bracketed
acceptance conditions, later proven by one db_assertion outcome naming its test ref.
Refuse: kind: test with ref: "output looks right when rendered" — a mislabeled wish.
Imitate: kind: human with ref: approvals/prototype_pixel_signoff — honest routing into the
approval flow instead of a fake green tick.

SECTION-BY-SECTION DISCIPLINE

Section 1 (Rank-0 anchors):
- Non-negotiable constraints are MUST/MUST NOT statements you are personally willing to block a
  release over. Don't pad this list with nice-to-haves; every entry becomes permanent review
  ammunition and permanent friction if it's soft.
- Explicit exclusions matter as much as inclusions. Write down what this product will NOT do,
  specifically enough that "add multi-currency support" would obviously require a new mission,
  not a bug report.
- Populate the cross-cutting constraints register with anything that will recur — tenancy
  isolation, audit trail, idempotency posture, authentication model. Give each a stable CC id.
  Later sections cite the id via bracketed prefix ("[CC-001] ...") rather than restating the
  rule in different words. If a constraint applies in only one place, it doesn't need a
  register entry — the register is for the ones that recur.

Section 2 (Requirements ledger):
- One testable behavior per requirement. If a statement has two verbs joined by "and," split it
  into two requirements now — a mission that fails its oracle on a compound requirement produces
  a WRONG_PRODUCT signal that's a decomposition defect, not a build defect, and it's cheaper to
  fix at authoring time.
- Every acceptance_conditions item is a single string whose bracket prefix is its stable id:
  "[AC-<slug>-<n>] <observable condition>". Section 4 will cite that id in an outcome's
  statement text — the translation from "what must be true" to "what proves it" must be a
  traceable link, not something a reviewer eyeball-matches across sections. If you can't
  picture what would produce the evidence, the condition isn't specified yet; keep working it
  rather than writing it down as done.
- Cross-cutting constraints are cited as "[CC-nnn] <delta only>" — reference, never re-author.

Section 3 (Feature briefs):
- states must include every state a user can perceive, including failure states — not just the
  happy path. The workflow block is the happy path; states is where the rest of reality lives.
- The UI law block is not optional decoration: token discipline, pattern lock, the anti-tell
  catalog, states completeness, copy voice, motion restraint, and provenance apply to every
  ui_structure you write. Art direction names token families and relationships, never hex
  values. If you want an interface that doesn't fit an existing layout pattern, don't improvise
  one — log it in Open decisions / EDR intake instead.
- Tag every mutating event/API verb with its side_effect_class
  (PURE_READ / WORKSPACE_LOCAL / EXTERNAL_IDEMPOTENT / EXTERNAL_NON_IDEMPOTENT / IRREVERSIBLE).
  These tags are authoring intent — legally the classes attach to capability descriptors at
  admission time (Ch.9) — but Section 7 rolls them up rather than guessing fresh, so get them
  right here.

Section 4 (Acceptance oracles):
- Oracle-first: draft this before implementation starts, and before anything you'd classify
  risk_class: high gets planned in Section 6.
- Coverage: every AC id from Section 2 appears in exactly one POSITIVE outcome's statement
  ([proves AC-...]); negative cases may cite an AC additionally, never as a substitute. Close
  with a literal coverage ledger line like LedgerLine's ("AC-X-1 → O1; AC-X-2 → O1; ...").
- Every requirement needs at least one negative case, not just happy-path outcomes. "Attempting
  X without permission Y fails closed" is the shape; find the real X and Y for this product.
- If your best available producer for a claim is judge or human, write that down honestly.
  Don't reach for test because it sounds more finished — a mislabeled binding is worse than an
  honest human binding that routes into approval.
- Cover the Definition-of-Polished battery for every user-facing surface: design lints,
  silhouette distinctiveness, believable density, VLM rubric or human pixel sign-off, copy
  honesty, and motion spec including reduced-motion behavior. Missing one of these isn't a small
  gap — it's the exact gap that produces generic-looking output.

Section 5 (Donor research register):
- Actually search before writing this section. Don't leave it thin because nothing was found —
  an empty register on a feature with obvious prior art (auth, tables, forms, payments UI) is
  itself a finding.
- Classify from license text, not vibes. When license or maintenance status is genuinely unknown,
  write UNKNOWN and let it block — don't round up to something more usable-sounding.
- Set checked_at on every row. A stale ok from months ago isn't a current ok — recheck rather
  than carry it forward silently.
- If a candidate will ship as a dependency rather than stay reference-only, pre-draft its
  admission justification (license, maintenance signal, why the standard library doesn't cover
  it) so Section 7's predicted approvals aren't guessing.

Section 6 (Mission decomposition sketch):
- Follow the golden-mission shape (specification → schema → service → API → UI → tests →
  verification) unless you have a specific reason to deviate — and if you deviate, say so in the
  sketch itself rather than leaving a silently different graph shape.
- Every node's success_criteria should cite a Section 4 oracle outcome where one exists. A node
  whose success criteria can't cite an outcome isn't finished being specified — go back and
  finish it rather than leaving a vague criterion.
- If a node feels like effort l, it's not one node — split it into two before it goes further.
- Use blocks_on_decision edges for anything that genuinely needs a governance answer (donor
  classification still open, dependency admission pending, oracle sign-off outstanding). A graph
  that guesses instead of blocking is the failure mode this edge type exists to prevent.

Section 7 (Autonomy ceiling and predicted approvals):
- Pick the ceiling deliberately, not by default. Side-effecting or money-adjacent slices start
  low; raise it in a later document revision once the slice has evidence behind it, never inside
  a running mission.
- Predict every approval you can see coming — donor reuse entering implementation, new top-level
  dependencies, oracle sign-off — so the mission graph doesn't stall later on an unpredicted
  approval discovered mid-run.
- side_effect_classes_expected must be the union of the side_effect_class tags you already
  attached to Section 3 events — a rollup, not a fresh judgment call. If everything is
  WORKSPACE_LOCAL and EXTERNAL_IDEMPOTENT, say so explicitly and say what's deliberately kept
  out of scope to hold that line (LedgerLine does this well — payment release stays out of v1
  specifically to keep the ceiling at 2).

Open decisions / EDR intake:
- Use the structured block, not a prose paragraph. The keys mirror edr.json — context,
  alternatives[], affected_requirement_slugs[] map one-to-one onto a TruthService.propose_edr
  pre-image; blocks / proposed_default / owner are authoring-only placement fields.
- Every row names what it blocks (section/node/row), carries either a proposed_default or an
  explicit "none — this must block," and names an owner. An EDR trigger with no owner is a gap
  that will resurface as a surprise later.

VOICE
Match the register the blueprint itself imposes on the products it governs: verb-first, sentence
case, figures over words, no exclamation marks, no "simply/easily/just." Use the schema's own
vocabulary (mission, run, lease, gate, requirement, oracle) rather than paraphrasing it. This
document is itself subject to the same anti-generic discipline it asks of the product it
describes — don't let Section 1's purpose paragraph read like marketing copy.

BEFORE YOU CALL IT DONE
Run the Completeness self-check at the end of the template itself — don't skip it because it
feels like a formality. It exists specifically to catch what the fail-closed DDE-065 compiler
would otherwise catch later, at a worse time. Then sweep the draft once for leftover
adjectives without bindings and leftover structural keys the serialization law forbids
(condition_id, cc_ref, acceptance_condition_ref). Any box you can't check gets logged in
Open decisions / EDR intake, not silently left unchecked. A gap you disclose is a planning
input; a gap you hide is a defect that surfaces downstream anyway.
```
