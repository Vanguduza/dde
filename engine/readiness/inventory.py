"""Named S7 landings and §18.6 removal-test candidates.

DDE-064 does not re-implement prior missions. The inventory is the
production catalog that names which landings already satisfy S7 exit
rows other than the removal test itself.

Chapter 18.2 S7 exit: learning activation gates (refusal when unmet),
chaos suite green, DR drill executed, all Chapter 16.5 SLOs met.
Chapter 18.3 S7 also includes DDE-057, DDE-058, and DDE-060; they are
named here so a readiness review cannot silently omit them.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: S7 numbered landings already closed (named, not re-run here).
S7_PRIOR_LANDINGS: dict[str, str] = {
    "experience_record": "docs/planning/dde-057-chapter-gate.md",
    "routing_activation_gates": "docs/planning/dde-058-chapter-gate.md",
    "context_activation_gates": "docs/planning/dde-059-chapter-gate.md",
    "flight_lab": "docs/planning/dde-060-chapter-gate.md",
    "chaos_suite": "docs/planning/dde-061-chapter-gate.md",
    "dr_drill": "docs/planning/dde-062-chapter-gate.md",
    "chapter_16_5_slos": "docs/planning/dde-063-chapter-gate.md",
}

#: Chapter 18.6 candidates to re-examine at this gate.
REMOVAL_CANDIDATES: dict[str, str] = {
    "context_critic": "engine/context/service.py",
    "route_critic": "engine/overhead/service.py",
    "model_assisted_planning": "engine/planning/registry.py",
    "simulation_model": "engine/simulation/service.py",
    "retriever": "engine/context/retrievers/lexical.py",
}


def missing_inventory_files() -> list[str]:
    missing: list[str] = []
    for relative in (*S7_PRIOR_LANDINGS.values(), *REMOVAL_CANDIDATES.values()):
        if not (ROOT / relative).is_file():
            missing.append(relative)
    return missing
