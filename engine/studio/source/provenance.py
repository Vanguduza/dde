"""M8 provenance admission law shared by write and promotion paths."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from engine.contracts.design_source import DesignSource
from engine.contracts.design_source_admission import DesignSourceAdmission
from engine.contracts.design_source_artifact import DesignSourceArtifact

REUSABLE_USAGE_KINDS = frozenset({"REUSED", "ADAPTED"})
EXTERNAL_SANDBOX_SOURCE_CLASSES = frozenset(
    {"DONOR", "EXTERNAL_REGISTRY", "MOBILE_REGISTRY", "FIGMA"}
)


@dataclass(frozen=True)
class ProvenanceAdmissionDecision:
    allowed: bool
    detail: str


def evaluate_reusable_provenance(
    *,
    artifact: DesignSourceArtifact,
    source: DesignSource,
    admission: DesignSourceAdmission | None,
    usage_kind: str,
    subject_kind: str,
    subject_ref: str,
    recorded_admission_id: UUID | None = None,
) -> ProvenanceAdmissionDecision:
    """Decide whether source evidence may claim reusable/adapted provenance.

    Project-native components are already accepted project material and do not
    manufacture an external admission. All other reusable source material must
    bind the exact current admission/content hash. External/donor code must also
    prove it was validated from a DDE-isolated sandbox tied to this candidate.
    """
    if usage_kind not in REUSABLE_USAGE_KINDS:
        return ProvenanceAdmissionDecision(True, "non-reuse provenance")

    if source.source_class == "PROJECT_NATIVE":
        return ProvenanceAdmissionDecision(True, "accepted project-native source")

    if admission is None or admission.state != "ADMITTED":
        return ProvenanceAdmissionDecision(
            False, "reused/adapted source requires an ADMITTED exact-content record"
        )
    if recorded_admission_id is None:
        return ProvenanceAdmissionDecision(
            False, "reused/adapted provenance does not pin its source admission"
        )
    if artifact.content_hash is None or admission.content_hash != artifact.content_hash:
        return ProvenanceAdmissionDecision(
            False, "source admission content hash does not match the current artifact"
        )
    if (
        recorded_admission_id is not None
        and recorded_admission_id != admission.admission_id
    ):
        return ProvenanceAdmissionDecision(
            False, "provenance is pinned to a stale source admission"
        )

    if source.source_class in EXTERNAL_SANDBOX_SOURCE_CLASSES:
        raw = artifact.metadata.get("sandbox_validation")
        if not isinstance(raw, dict):
            return ProvenanceAdmissionDecision(
                False, "external reusable source has no sandbox-validation evidence"
            )
        if raw.get("state") != "CURRENT_BYTES_VALIDATED":
            return ProvenanceAdmissionDecision(
                False, "external reusable source sandbox is not currently validated"
            )
        if raw.get("content_hash") != artifact.content_hash:
            return ProvenanceAdmissionDecision(
                False, "sandbox-validation hash is stale for the source artifact"
            )
        if subject_kind == "CANDIDATE" and raw.get("candidate_id") != subject_ref:
            return ProvenanceAdmissionDecision(
                False, "sandbox-validation evidence belongs to another candidate"
            )

    return ProvenanceAdmissionDecision(
        True, "source admission and provenance are current"
    )
