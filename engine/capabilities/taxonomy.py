"""Chapter 9.3's side-effect taxonomy and Chapter 9.1's other enumerated
`CapabilityDescriptor` fields this registry validates at registration time.

Only `side_effect_class` is a literal, chapter-enumerated table (9.3); this
module treats it as the load-bearing enum AGENTS.md's Definition of Done
names directly ("every new side-effecting capability declares a
`side_effect_class`"). `risk_class` reuses the same four-level vocabulary
Chapter 4.2 already assigns to `Task.risk_class` (low/medium/high/critical)
-- the blueprint gives capabilities no separate risk taxonomy of their own,
and duplicating four already-established literal values here (rather than
importing `engine.missions`/`engine.planning` internals across an unrelated
module boundary) keeps `engine.capabilities` dependency-free, matching
Chapter 3.6's independent module layout.

`enforcement_tier` is exactly Chapter 7.2's two enforcement tiers -- T1
(brokered) and T2 (contained). `audit_only` (7.2's development-only escape
hatch) is a property of an *ExecutionPlan*'s own `enforcement_tier` field,
never of a capability's own declared descriptor, so it is deliberately
excluded from this enum.

`certification_status` and `lifecycle_status` are both required fields in
9.1's field list, but neither is given a literal enum by the chapter (unlike
9.3's table). The values below are this mission's flagged interpretation,
chosen to mirror mechanisms the blueprint *does* name elsewhere for the
closest analogous concept -- not invented from nothing:
  - `certification_status` mirrors 9.5's admission pipeline's terminal
    outcome ("... certify -> register") and echoes 8.5's `STALE`
    re-certification concept (a different object -- worker profile
    certification -- but the same "went stale after a change" mechanism
    9.5 explicitly says applies to capabilities too: "Re-admission is
    required on any descriptor or version change."). This mission
    registers a value at admission time and validates it is one of these
    four; it does not implement the admission pipeline itself (9.5/9.6/9.7
    execution is out of this mission's scope -- see
    `engine.capabilities.service`'s module docstring).
  - `lifecycle_status` is this registry's own real, enforced state machine
    (`engine.capabilities.states`): a capability descriptor is `ACTIVE`
    until superseded by a new version of the same `capability_id` (which
    the registry deprecates automatically -- Chapter 3.10's "a material
    change creates a new version ... it never overwrites") or explicitly
    `retire()`-d.
"""

from __future__ import annotations

#: Chapter 4.2's risk_class vocabulary, reused verbatim for a capability's
#: own declared risk_class (9.1).
RISK_CLASSES: frozenset[str] = frozenset({"low", "medium", "high", "critical"})

#: Chapter 9.3's side-effect taxonomy, transcribed exactly -- the five rows
#: of the chapter's table, nothing invented, nothing omitted. "A capability
#: without a declared class cannot be admitted" (9.3): this is the enum
#: `engine.capabilities.service.CapabilityRegistryService.register`
#: validates against before ever constructing a row.
SIDE_EFFECT_CLASSES: frozenset[str] = frozenset(
    {
        "PURE_READ",
        "WORKSPACE_LOCAL",
        "EXTERNAL_IDEMPOTENT",
        "EXTERNAL_NON_IDEMPOTENT",
        "IRREVERSIBLE",
    }
)

#: Chapter 9.3's "Journal" column, transcribed: which side_effect_class
#: values require an external effect journal entry (Chapter 12.4). Chapter
#: 9.3's closing sentence -- "Recovery rules in Chapter 12 dispatch on this
#: field" -- is DDE-017/DDE-018 territory (lease enforcement, out of this
#: mission's scope); this mapping exists now so that future caller has one
#: real, already-correct place to read it from instead of re-deriving it.
JOURNALED_SIDE_EFFECT_CLASSES: frozenset[str] = frozenset(
    {"EXTERNAL_IDEMPOTENT", "EXTERNAL_NON_IDEMPOTENT", "IRREVERSIBLE"}
)

#: Chapter 7.2's two enforcement tiers for a capability's own descriptor.
#: `audit_only` is excluded -- see module docstring.
ENFORCEMENT_TIERS: frozenset[str] = frozenset({"T1", "T2"})

#: Flagged interpretation -- see module docstring.
CERTIFICATION_STATUSES: frozenset[str] = frozenset(
    {"PENDING", "CERTIFIED", "REJECTED", "STALE"}
)

#: This registry's own real lifecycle -- see module docstring and
#: `engine.capabilities.states.LIFECYCLE_TRANSITIONS`.
LIFECYCLE_STATUSES: frozenset[str] = frozenset({"ACTIVE", "DEPRECATED", "RETIRED"})

#: Chapter 3.2: "Global registries are tenant-agnostic by design but carry
#: `visibility` (`global` / `tenant`) and a nullable `owner_tenant_id`."
VISIBILITIES: frozenset[str] = frozenset({"global", "tenant"})
