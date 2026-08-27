"""DDE-066 donor discovery grouping — classify before use, unmatched bucket.

Network fan-out and ExternalEffect journaling live in
`engine.donor.discovery_service`. This module is the deterministic
inventory assembly every fan-out result and every DDE-046 pin must pass
through. Classifier crash returns empty groups plus a typed refusal
string — never a degraded OPEN_REUSE guess.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from engine.core.errors import DdeError
from engine.donor.classify import ClassificationResult, classify_donor
from engine.donor.injection import screen_donor_text

USABLE_CLASSES = frozenset({"OPEN_REUSE", "CONDITIONAL_REUSE"})
UNKNOWN_DEFAULT = "SOURCE_REFERENCE_ONLY"


@dataclass(frozen=True)
class DiscoveryHit:
    source_uri: str
    summary: str
    feature_hints: tuple[str, ...]
    pin: bool = False


@dataclass(frozen=True)
class FeatureCategory:
    feature_id: str
    title: str


@dataclass(frozen=True)
class GroupedHit:
    source_uri: str
    source_class: str
    licence_class: str
    taint_tags: tuple[str, ...]
    adoption_state: str
    usable: bool
    feature_id: str | None


@dataclass(frozen=True)
class GroupedDonorResults:
    prd_id: str
    groups: tuple[tuple[str, tuple[GroupedHit, ...]], ...]
    unmatched: tuple[GroupedHit, ...]
    refusals: tuple[str, ...]


Classifier = Callable[[str, str], ClassificationResult]


class ClassifierUnreachableError(DdeError):
    """Typed refusal when licence classification cannot run."""

    def __init__(self) -> None:
        super().__init__(
            "CONTEXT_INCOMPLETE",
            "donor licence classifier is unreachable",
            retryable=False,
            details={"missing_artifact": "classifier"},
        )


def _default_classifier(text: str, source_uri: str) -> ClassificationResult:
    return classify_donor(text, source_uri=source_uri)


def group_discovery_hits(
    *,
    prd_id: str,
    features: tuple[FeatureCategory, ...],
    hits: tuple[DiscoveryHit, ...],
    classifier: Classifier | None = None,
) -> GroupedDonorResults:
    """Assemble the grouped inventory. Classification runs BEFORE a hit
    is marked usable. UNKNOWN never becomes OPEN_REUSE here."""
    classify = classifier or _default_classifier
    feature_ids = {item.feature_id for item in features}
    buckets: dict[str, list[GroupedHit]] = {item.feature_id: [] for item in features}
    unmatched: list[GroupedHit] = []
    refusals: list[str] = []
    try:
        classified = [(_classify_hit(hit, classify), hit) for hit in hits]
    except ClassifierUnreachableError:
        return _empty_refusal(prd_id, features)
    except DdeError:
        raise
    except Exception:
        return _empty_refusal(prd_id, features)

    for result, hit in classified:
        source_class = result.source_class
        if source_class == "UNKNOWN":
            source_class = UNKNOWN_DEFAULT
        usable = source_class in USABLE_CLASSES
        adoption = "identified" if hit.pin else "screened"
        if source_class == "REJECTED":
            adoption = "rejected"
            usable = False
        grouped = GroupedHit(
            source_uri=hit.source_uri,
            source_class=source_class,
            licence_class=result.licence_class,
            taint_tags=result.taint_tags,
            adoption_state=adoption,
            usable=usable,
            feature_id=None,
        )
        matched = [fid for fid in hit.feature_hints if fid in feature_ids]
        if not matched:
            unmatched.append(grouped)
            continue
        for fid in matched:
            buckets[fid].append(
                GroupedHit(
                    source_uri=grouped.source_uri,
                    source_class=grouped.source_class,
                    licence_class=grouped.licence_class,
                    taint_tags=grouped.taint_tags,
                    adoption_state=grouped.adoption_state,
                    usable=grouped.usable,
                    feature_id=fid,
                )
            )
    groups = tuple(
        (item.feature_id, tuple(buckets[item.feature_id])) for item in features
    )
    return GroupedDonorResults(
        prd_id=prd_id,
        groups=groups,
        unmatched=tuple(unmatched),
        refusals=tuple(refusals),
    )


def _classify_hit(hit: DiscoveryHit, classify: Classifier) -> ClassificationResult:
    findings = screen_donor_text(hit.summary)
    screened = hit.summary if not findings else ""
    result = classify(screened, hit.source_uri)
    if result.source_class == "UNKNOWN":
        return ClassificationResult(
            source_class=UNKNOWN_DEFAULT,
            licence_class=result.licence_class,
            licence_ids=result.licence_ids,
            conflicting=result.conflicting,
            evidence=result.evidence + ("unknown_defaulted",),
            policy_default_applied=True,
            taint_tags=result.taint_tags,
        )
    return result


def _empty_refusal(
    prd_id: str, features: tuple[FeatureCategory, ...]
) -> GroupedDonorResults:
    return GroupedDonorResults(
        prd_id=prd_id,
        groups=tuple((item.feature_id, ()) for item in features),
        unmatched=(),
        refusals=("classifier_unreachable",),
    )


def grouped_results_from_dict(payload: dict[str, Any]) -> GroupedDonorResults:
    def parse_hit(raw: dict[str, Any]) -> GroupedHit:
        tags = raw.get("taint_tags")
        feature_id = raw.get("feature_id")
        return GroupedHit(
            source_uri=str(raw["source_uri"]),
            source_class=str(raw["source_class"]),
            licence_class=str(raw["licence_class"]),
            taint_tags=tuple(str(tag) for tag in tags)
            if isinstance(tags, list)
            else (),
            adoption_state=str(raw["adoption_state"]),
            usable=bool(raw["usable"]),
            feature_id=str(feature_id) if isinstance(feature_id, str) else None,
        )

    groups_raw = payload.get("groups")
    unmatched_raw = payload.get("unmatched")
    refusals_raw = payload.get("refusals")
    groups: list[tuple[str, tuple[GroupedHit, ...]]] = []
    if isinstance(groups_raw, list):
        for row in groups_raw:
            if not isinstance(row, dict):
                continue
            hits_raw = row.get("hits")
            hits = (
                tuple(parse_hit(item) for item in hits_raw if isinstance(item, dict))
                if isinstance(hits_raw, list)
                else ()
            )
            groups.append((str(row["feature_id"]), hits))
    unmatched = (
        tuple(parse_hit(item) for item in unmatched_raw if isinstance(item, dict))
        if isinstance(unmatched_raw, list)
        else ()
    )
    refusals = (
        tuple(str(item) for item in refusals_raw)
        if isinstance(refusals_raw, list)
        else ()
    )
    return GroupedDonorResults(
        prd_id=str(payload["prd_id"]),
        groups=tuple(groups),
        unmatched=unmatched,
        refusals=refusals,
    )


def grouped_results_as_dict(results: GroupedDonorResults) -> dict[str, Any]:
    def hit_dict(hit: GroupedHit) -> dict[str, object]:
        payload: dict[str, object] = {
            "source_uri": hit.source_uri,
            "source_class": hit.source_class,
            "licence_class": hit.licence_class,
            "taint_tags": list(hit.taint_tags),
            "adoption_state": hit.adoption_state,
            "usable": hit.usable,
        }
        if hit.feature_id is not None:
            payload["feature_id"] = hit.feature_id
        return payload

    return {
        "prd_id": results.prd_id,
        "groups": [
            {"feature_id": fid, "hits": [hit_dict(hit) for hit in hits]}
            for fid, hits in results.groups
        ],
        "unmatched": [hit_dict(hit) for hit in results.unmatched],
        "refusals": list(results.refusals),
    }
