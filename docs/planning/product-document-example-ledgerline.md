# Product document example — LedgerLine (invoice approval ERP slice)

> **Work record, not Project Truth.** Filled worked example of
> [product-document-template.md](product-document-template.md) for a fictional product,
> "LedgerLine" — an invoice-approval ERP slice. Every structured block instantiates the
> template once; field names and enums are copied from `schemas/objects/*.json`. The
> requirement, mission and EDR slugs are illustrative; real slugs enter Project Truth only
> through the governed intake path.

- **version:** 1.0 (example)
- **product slug prefix:** `LL` (requirements `REQ-LL-NNN`, missions `MISSION-ERP-######`)
- **scope of example:** one feature — three-way-match invoice approval with an approval inbox

## 1. Rank-0 anchors — Product Constitution draft

- **purpose:** LedgerLine lets finance teams approve supplier invoices through a
  three-way match (purchase order, goods receipt, invoice) so that no payment leaves the
  company without a complete, auditable match trail.
- **target users:** accounts-payable clerks (daily, approval inbox), finance managers
  (weekly, exception review), auditors (quarterly, read-only trace export).
- **non-negotiable constraints:**
  - MUST NOT permit payment release on a failed or manually-overridden-failed match.
  - MUST record an immutable audit entry for every state transition of an invoice.
  - MUST enforce tenant isolation at row level; no cross-tenant query path exists.
  - MUST keep every externally visible mutation idempotent (`command_id` +
    `idempotency_key`, Ch.12.5).
- **core workflows:** receive invoice → automatic three-way match → clerk disposition →
  manager exception handling → payment scheduling.
- **UX principles:** operator-tooling grammar (no marketing surfaces); every screen declares
  all five states; density over decoration; errors name cause and next action.
- **security principles:** least-privilege roles; credentials only via brokered handles;
  audit trail is append-only.
- **explicit exclusions:** no general ledger posting; no OCR ingestion (out of scope v1); no
  multi-currency conversion.
- **cross-cutting constraints register:**

  ```yaml
  - id: CC-001
    statement: >-
      Row-level tenant isolation enforced at the database layer; no cross-tenant query path.
    applies_to: [requirements, feature_briefs]
  - id: CC-002
    statement: >-
      Every externally visible mutation carries command_id + idempotency_key (Ch.12.5).
    applies_to: [requirements, feature_briefs]
  ```


## 2. Requirements ledger

```yaml
- slug: REQ-LL-001
  statement: >-
    When an invoice arrives referencing a valid PO and goods receipt within tolerance,
    the system creates a matched approval task without human intervention.
  constraints:
    - "match evaluation completes p95 under 2 s for invoices with ≤ 200 lines"
    - "tolerance rules are tenant-configurable price/quantity bands"
  acceptance_conditions:
    - "[AC-LL-001-1] a seeded 3-way-matching invoice produces exactly one approval task"
    - "[AC-LL-001-2] the task references the PO line, receipt line and invoice line ids"
  status: draft
  supersedes_id: null

- slug: REQ-LL-002
  statement: >-
    An accounts-payable clerk can approve or reject any task assigned to their queue,
    and cannot act on tasks outside their tenant or role.
  constraints:
    - "[CC-001] authorisation additionally checked at the mutation boundary, not only in UI"
  acceptance_conditions:
    - "[AC-LL-002-1] approve/reject transitions persist with actor, timestamp and reason"
    - "[AC-LL-002-2] cross-tenant task access attempt is rejected with a typed authorisation error"
  status: draft
  supersedes_id: null

- slug: REQ-LL-003
  statement: >-
    A finance manager can resolve a mismatched invoice by recording an override decision
    with a mandatory reason code.
  constraints:
    - "override without reason code is rejected at the API boundary"
  acceptance_conditions:
    - "[AC-LL-003-1] overridden invoices display their override reason in the audit trail"
  status: draft
  supersedes_id: null

- slug: REQ-LL-004
  statement: >-
    Every invoice state transition appends one immutable audit row visible to auditors
    in chronological order.
  constraints:
    - "[CC-002] audit-relevant mutations are idempotent under key replay"
    - "audit rows carry actor principal, transition type and correlation_id"
  acceptance_conditions:
    - "[AC-LL-004-1] auditor export replays the full lifecycle for a sampled invoice"
  status: draft
  supersedes_id: null
```

## 3. Feature brief — three-way-match approval inbox

```yaml
- title: Three-way-match approval inbox
  purpose: route matched invoices to clerks and mismatches to managers with full context.
  actors: [accounts-payable clerk, finance manager]
  workflow:
    - step: invoice ingested and matched against PO + receipt
      actor: system
    - step: task appears in clerk inbox (matched) or manager exception queue (mismatch)
      actor: system
    - step: disposition recorded (approve / reject / override-with-reason)
      actor: clerk or manager
  states: [draft, matching, awaiting_approval, overridden, rejected, scheduled_for_payment]
  business_rules:
    - "price variance beyond tenant band forces mismatch regardless of quantity match"
    - "one invoice can hold mixed matched/mismatched lines; disposition is per invoice"
  data_model_sketch: >-
    invoices, invoice_lines, purchase_orders, po_lines, goods_receipts, receipt_lines,
    approval_tasks, overrides, audit_events — all carrying tenant_id/project_id with RLS.
  api_surface_sketch: >-
    POST /invoices (idempotent by supplier invoice number), POST /approval-tasks/{id}/decision
    (idempotency_key required), GET /audit-events?invoice_id=
  ui_structure:
    surfaces:
      - name: approval-inbox
        layout_pattern: columnar-worklist   # declared pattern; EDR if it does not exist
        states: [idle, loading, empty, error, disabled]
      - name: invoice-detail
        layout_pattern: document-panel-with-line-table
        states: [idle, loading, empty, error, disabled]
    art_direction: >-
      Three-step surface hierarchy from the token sheet; single accent reserved for the
      primary disposition action; monochrome stroke icons; tabular figures for amounts.
    motion_spec: >-
      Task-row settle on disposition via --motion-duration-fast with reduced-motion variant;
      no loops, no springs.
  permissions:
    - role: accounts-payable-clerk
      can: [read_assigned_tasks, record_disposition]
    - role: finance-manager
      can: [read_exception_queue, record_override]
    - role: auditor
      can: [read_audit_events]
  events:
    - name: invoice.matched
      side_effect_class: WORKSPACE_LOCAL
      audit_relevant: true
    - name: invoice.mismatch_detected
      side_effect_class: WORKSPACE_LOCAL
      audit_relevant: true
    - name: invoice.disposition_recorded
      side_effect_class: EXTERNAL_IDEMPOTENT
      audit_relevant: true
    - name: audit.appended
      side_effect_class: WORKSPACE_LOCAL
      audit_relevant: true
  security_requirements:
    - "RLS enforced on every table; cross-tenant probe covered by negative case ORC-1-N2"
    - "decision endpoint requires capability-scoped credential handle; no ambient token"
  requirement_refs: [REQ-LL-001, REQ-LL-002, REQ-LL-003, REQ-LL-004]
```

## 4. Acceptance oracle — mission scope

One mission oracle for the slice; task oracles hang off individual nodes in Section 6.

```yaml
- scope: mission
  oracle_version: <content-hash-of-definition-fields>
  requirement_refs: [REQ-LL-001, REQ-LL-002, REQ-LL-003, REQ-LL-004]
  feature_refs: [three-way-match-approval-inbox]
  minimum_confidence: 0.9
  human_assertions:
    - "inbox reads as operator tooling per playbook §8.1 dimensions (pixel sign-off)"
  domain_invariants:
    - "sum(line_totals) == invoice.total_cents for every persisted invoice"
    - "an invoice never has two open approval tasks"
  observable_outcomes:
    - outcome_id: <uuid-ORC-1-O1>
      statement: >-
        [proves AC-LL-001-1, AC-LL-001-2] Seeded matched invoice produces exactly one
        approval task referencing PO, receipt and invoice lines.
      evidence_binding:
        kind: db_assertion
        ref: tests/oracle/three_way_match.py::test_single_task_created
    - outcome_id: <uuid-ORC-1-O2>
      statement: >-
        [proves AC-LL-002-1] Clerk disposition persists with actor, timestamp and reason
        and appends one audit row.
      evidence_binding:
        kind: api_probe
        ref: probes/approval-decision
        command: ["pytest", "tests/oracle/test_decision_probe.py"]
    - outcome_id: <uuid-ORC-1-O3>
      statement: >-
        [proves AC-LL-003-1] Override reason recorded by a manager appears in the auditor-
        visible audit trail for the overridden invoice.
      evidence_binding:
        kind: db_assertion
        ref: tests/oracle/test_override_reason_visible.py
    - outcome_id: <uuid-ORC-1-O4>
      statement: >-
        [proves AC-LL-004-1] Auditor export replays the full invoice lifecycle in
        chronological order with actor and correlation ids.
      evidence_binding:
        kind: test
        ref: tests/oracle/test_audit_replay.py
    - outcome_id: <uuid-ORC-1-O5>
      statement: >-
        Approval inbox renders distinctively against the generic-layout corpus at both
        supported widths, idle/loading/empty/error/disabled all captured.
      evidence_binding:
        kind: visual_diff
        ref: visual/suites/approval-inbox
        independence: visual suite screenshots vs committed baselines, reviewed by VLM rubric
    - outcome_id: <uuid-ORC-1-O6>
      statement: >-
        Pixel sign-off on the inbox and detail surfaces records operator-tooling fit.
      evidence_binding:
        kind: human
        ref: approvals/prototype_pixel_signoff
  negative_cases:
    - outcome_id: <uuid-ORC-1-N1>
      statement: >-
        Override submitted without reason_code is rejected with a typed validation error
        and mutates nothing; also evidences [AC-LL-002-2] fail-closed authorisation shape.
      evidence_binding:
        kind: test
        ref: tests/oracle/test_override_requires_reason.py
    - outcome_id: <uuid-ORC-1-N2>
      statement: >-
        [proves AC-LL-002-2] Cross-tenant task fetch is rejected; no row leaks into any
        response body.
      evidence_binding:
        kind: security_scan
        ref: scans/tenant-isolation-suite
```

Coverage check: AC-LL-001-1 → O1; AC-LL-001-2 → O1; AC-LL-002-1 → O2; AC-LL-003-1 → O3;
AC-LL-004-1 → O4. Every AC has exactly one positive outcome (O1 carries two because the two
conditions are facets of one assertion); N1/N2 cite ACs additionally. The DoP battery rides
O5/O6.

Definition-of-Polished mapping for this slice: O5 carries the design-lint, silhouette and
density outcomes; O6 carries the explicit human pixel sign-off (`prototype_pixel_signoff`);
copy honesty rides the studio honesty suite bound to O5's visual run.

## 5. Donor research register

| source_uri | source_class | media_kind | licence | maintenance_signal | intended_use |
|---|---|---|---|---|---|
| shadcn-ui/ui (registry + blocks) | OPEN_REUSE | registry_json | MIT | ok | worklist/table primitives as generator input |
| TanStack/table | OPEN_REUSE | source_tree | MIT | ok | virtualised line-table behaviour reference |
| react-hook-form + zod | OPEN_REUSE | source_tree | MIT | ok | decision-form validation pattern |
| Tailwind Plus (Cruip-class commercial) | CONDITIONAL_REUSE | other | proprietary | ok | art direction only — spacing rhythm reference; never generator input |
| mobbin.com SaaS gallery captures | SOURCE_REFERENCE_ONLY | other | unverified | unknown | disposition-flow UX reference only |
| random marketplace "ERP dashboard bundle" | REJECTED | source_tree | unverified | critical | none — recorded to keep it rejected |

Notes: the two gallery/bundle rows demonstrate the classification-down law (`UNKNOWN`
licence ⇒ not `OPEN_REUSE`; marketplace bundle stays `REJECTED`). If TanStack/table ships as
a dependency it additionally needs a Ch.9.6 admission row with the justification triple —
predicted below.

## 6. Mission decomposition sketch

```yaml
template_key: ledgerline--three-way-match-slice
description: golden-mission-shaped slice implementing REQ-LL-001..004
nodes:
  - node_key: specification
    task_class: specification
    intent: pin match tolerance semantics and decision-state machine from REQ-LL slugs
    success_criteria:
      - "state machine doc names every §3 state with its legal transitions"
    estimated_effort: s
    blast_radius: local
    risk_class: low
    expected_write_scope: [docs/planning/ledgerline-spec.md]
    expected_read_scope: [docs/truth/**]

  - node_key: schema
    task_class: implementation
    intent: tables + RLS + migration for invoices/tasks/audit
    success_criteria:
      - "migration applies cleanly to empty db and reverses"
      - "RLS policies deny cross-tenant selects in contract test"
    estimated_effort: m
    blast_radius: module
    risk_class: medium
    expected_write_scope: [schemas/sql/, engine/adapters/db/]
    expected_read_scope: [schemas/objects/*.json]

  - node_key: service
    task_class: implementation
    intent: matcher + decision service with idempotent mutations
    success_criteria:
      - "seeded fixture yields exactly one approval task (ORC-1-O1 producer)"
    estimated_effort: m
    blast_radius: module
    risk_class: high
    expected_write_scope: [engine/services/ledgerline/]
    expected_read_scope: [engine/adapters/db/]

  - node_key: api
    task_class: implementation
    intent: typed endpoints incl. decision mutation with idempotency_key
    success_criteria:
      - "decision replay with same key returns first result, no duplicate audit row"
    estimated_effort: s
    blast_radius: module
    risk_class: medium
    expected_write_scope: [interfaces/gateway/routes/]
    expected_read_scope: [engine/services/ledgerline/]

  - node_key: ui
    task_class: implementation
    intent: inbox + detail surfaces per §3 ui_structure law
    success_criteria:
      - "all five states captured at both widths; fingerprints updated in-PR"
    estimated_effort: m
    blast_radius: module
    risk_class: medium
    expected_write_scope: [interfaces/dde-studio/shared/ui/, visual/fixtures/]
    expected_read_scope: [schemas/design/tokens.json]

  - node_key: verification
    task_class: verification
    intent: execute mission-oracle battery, independent of generators
    success_criteria:
      - "every ORC-1 outcome has green independent evidence or disclosed gap"
    estimated_effort: s
    blast_radius: local
    risk_class: high
    expected_write_scope: []
    expected_read_scope: [tests/oracle/, visual/]

edges:
  - {from_node_key: specification, to_node_key: schema, edge_type: depends_on}
  - {from_node_key: schema, to_node_key: service, edge_type: produces_contract_for, contract_ref: schemas/sql}
  - {from_node_key: service, to_node_key: api, edge_type: depends_on}
  - {from_node_key: api, to_node_key: ui, edge_type: depends_on}
  - {from_node_key: verification, to_node_key: service, edge_type: verifies}
  - {from_node_key: verification, to_node_key: api, edge_type: verifies}
  - {from_node_key: verification, to_node_key: ui, edge_type: verifies}
```

## 7. Autonomy ceiling and predicted approvals

```yaml
autonomy_ceiling: 2              # money-adjacent slice; humans disposition payments
predicted_approvals:
  - approval_type: donor_reuse            # TanStack/table entering implementation
  - approval_type: dependency_addition    # same package; justification triple pre-drafted
side_effect_classes_expected:
  - WORKSPACE_LOCAL                       # rollup of §3 event tags
  - EXTERNAL_IDEMPOTENT                   # keyed decision mutations
```

The decision endpoint itself is EXTERNAL_IDEMPOTENT by construction (same key replays the
first result) — matching the `invoice.disposition_recorded` tag in §3; the §7 list is exactly
the union of those tags. Nothing in this slice touches IRREVERSIBLE effects — payment release
stays outside v1 scope precisely to keep the ceiling at 2.
