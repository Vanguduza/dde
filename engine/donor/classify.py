"""Chapter 13.8 six-value licence/reuse classifier (DDE-047).

Classification happens BEFORE implementation use. UNKNOWN or conflicting
licence evidence defaults to SOURCE_REFERENCE_ONLY or REJECTED per policy
and never silently becomes OPEN_REUSE. A signed donor_reuse decision is a
separate gate for autonomous production use — see DonorTaintService.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

from engine.core.errors import DdeError

SOURCE_CLASSES = frozenset(
    {
        "OPEN_REUSE",
        "CONDITIONAL_REUSE",
        "SOURCE_REFERENCE_ONLY",
        "RESTRICTED",
        "UNKNOWN",
        "REJECTED",
    }
)

DEFAULT_SOURCE_CLASS = "UNKNOWN"
UnknownPolicy = Literal["SOURCE_REFERENCE_ONLY", "REJECTED"]
DEFAULT_UNKNOWN_POLICY: UnknownPolicy = "SOURCE_REFERENCE_ONLY"

OPEN_SPDX = frozenset(
    {
        "MIT",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "Unlicense",
        "0BSD",
        "CC0-1.0",
        "PSF-2.0",
    }
)
REJECT_SPDX = frozenset(
    {
        "GPL-2.0",
        "GPL-2.0-only",
        "GPL-2.0-or-later",
        "GPL-3.0",
        "GPL-3.0-only",
        "GPL-3.0-or-later",
        "AGPL-3.0",
        "AGPL-3.0-only",
        "AGPL-3.0-or-later",
        "SSPL-1.0",
        "BUSL-1.1",
    }
)
CONDITIONAL_SPDX = frozenset(
    {
        "MPL-2.0",
        "LGPL-2.1",
        "LGPL-2.1-only",
        "LGPL-2.1-or-later",
        "LGPL-3.0",
        "LGPL-3.0-only",
        "LGPL-3.0-or-later",
        "EPL-2.0",
        "CDDL-1.0",
    }
)
HOST_CLASS: dict[str, str] = {
    "ui.shadcn.com": "OPEN_REUSE",
    "www.shadcn.com": "OPEN_REUSE",
    "shadcn.com": "OPEN_REUSE",
    "tailwindui.com": "CONDITIONAL_REUSE",
    "tailwindplus.com": "CONDITIONAL_REUSE",
    "cruip.com": "CONDITIONAL_REUSE",
    "godly.site": "SOURCE_REFERENCE_ONLY",
    "lapa.ninja": "SOURCE_REFERENCE_ONLY",
    "mobbin.com": "SOURCE_REFERENCE_ONLY",
    "land-book.com": "SOURCE_REFERENCE_ONLY",
}

_SPDX_RE = re.compile(
    r"SPDX-License-Identifier:\s*([A-Za-z0-9.+-]+)",
    re.IGNORECASE,
)
_LICENCE_NAME_RE = re.compile(
    r"\b(MIT|Apache(?:\s*License)?(?:\s*2\.0)?|BSD[- ][23]-Clause|"
    r"ISC|Unlicense|MPL[- ]?2\.0|GPL[- ]?[23](?:\.0)?|AGPL[- ]?3(?:\.0)?|"
    r"LGPL[- ]?[23](?:\.[01])?|BUSL|SSPL|proprietary|all rights reserved)\b",
    re.IGNORECASE,
)
_NAME_TO_SPDX: dict[str, str] = {
    "mit": "MIT",
    "apache": "Apache-2.0",
    "apache license": "Apache-2.0",
    "apache 2.0": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd 2-clause": "BSD-2-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "bsd 3-clause": "BSD-3-Clause",
    "isc": "ISC",
    "unlicense": "Unlicense",
    "mpl-2.0": "MPL-2.0",
    "mpl 2.0": "MPL-2.0",
    "gpl-2": "GPL-2.0",
    "gpl-2.0": "GPL-2.0",
    "gpl 2.0": "GPL-2.0",
    "gpl-3": "GPL-3.0",
    "gpl-3.0": "GPL-3.0",
    "gpl 3.0": "GPL-3.0",
    "agpl-3": "AGPL-3.0",
    "agpl-3.0": "AGPL-3.0",
    "agpl 3.0": "AGPL-3.0",
    "lgpl-2.1": "LGPL-2.1",
    "lgpl 2.1": "LGPL-2.1",
    "lgpl-3.0": "LGPL-3.0",
    "lgpl 3.0": "LGPL-3.0",
    "busl": "BUSL-1.1",
    "sspl": "SSPL-1.0",
    "proprietary": "PROPRIETARY",
    "all rights reserved": "PROPRIETARY",
}


@dataclass(frozen=True)
class ClassificationResult:
    source_class: str
    licence_class: str
    licence_ids: tuple[str, ...]
    conflicting: bool
    evidence: tuple[str, ...]
    policy_default_applied: bool
    taint_tags: tuple[str, ...]

    @property
    def rationale(self) -> str:
        return ";".join(self.evidence) if self.evidence else "unspecified"


def build_taint_tags(
    *,
    donor_artifact_id: UUID | str | None,
    source_class: str,
    licence_class: str,
    source_uri: str | None = None,
) -> list[str]:
    tags: list[str] = []
    if donor_artifact_id is not None:
        tags.append(f"donor:{donor_artifact_id}")
    if source_uri:
        tags.append(f"uri:{source_uri}")
    tags.append(f"class:{source_class}")
    tags.append(f"licence:{licence_class}")
    return tags


def classify_donor_content(
    text: str,
    *,
    source_uri: str = "",
    requested: str | None = None,
    signed_reuse_decision_id: UUID | None = None,
    unknown_policy: UnknownPolicy = DEFAULT_UNKNOWN_POLICY,
) -> ClassificationResult:
    """Classify material on the six-value scale from content + URI evidence."""
    if unknown_policy not in ("SOURCE_REFERENCE_ONLY", "REJECTED"):
        raise DdeError(
            "POLICY_DENIED",
            f"Invalid unknown_policy {unknown_policy!r}",
            details={"unknown_policy": unknown_policy},
        )
    if requested is not None and requested != "" and requested not in SOURCE_CLASSES:
        raise DdeError(
            "POLICY_DENIED",
            f"Unknown donor source_class {requested!r}",
            details={"source_class": requested},
        )

    licence_ids = _detect_licences(text)
    host_class = _host_class(source_uri)
    evidence: list[str] = []
    if licence_ids:
        evidence.append(f"spdx:{','.join(licence_ids)}")
    if host_class is not None:
        evidence.append(f"host:{host_class[0]}={host_class[1]}")

    from_licences = _class_from_licences(licence_ids)
    conflicting = from_licences == "CONFLICTING"
    inferred: str | None = None
    if conflicting:
        inferred = None
    elif from_licences is not None:
        inferred = from_licences
    elif host_class is not None:
        inferred = host_class[1]

    policy_default_applied = False
    source_class: str
    if inferred is None:
        source_class = str(unknown_policy)
        policy_default_applied = True
        licence_class = "CONFLICTING" if conflicting else "UNKNOWN"
        evidence.append(f"policy_default:{unknown_policy}")
    else:
        source_class = inferred
        licence_class = (
            licence_ids[0]
            if len(licence_ids) == 1
            else (",".join(licence_ids) if licence_ids else "HOST")
        )

    if requested and requested != "":
        if requested == "OPEN_REUSE" and source_class != "OPEN_REUSE":
            if signed_reuse_decision_id is None:
                raise DdeError(
                    "POLICY_DENIED",
                    "OPEN_REUSE refused: evidence does not support open reuse "
                    "and no signed donor_reuse decision was supplied "
                    "(Chapter 13.8 / DDE-047)",
                    details={
                        "requested": requested,
                        "inferred": source_class,
                        "licence_ids": list(licence_ids),
                    },
                )
            source_class = "OPEN_REUSE"
            evidence.append("signed_reuse_override:OPEN_REUSE")
        elif _rank(requested) > _rank(source_class):
            source_class = requested
            evidence.append(f"requested_stricter:{requested}")
        elif requested != source_class and requested != "OPEN_REUSE":
            evidence.append(f"requested_ignored:{requested}")

    if source_class == "OPEN_REUSE" and signed_reuse_decision_id is None:
        if policy_default_applied or conflicting:
            raise DdeError(
                "POLICY_DENIED",
                "OPEN_REUSE requires clear licence/host evidence or a signed "
                "reuse decision; refusing silent upgrade from UNKNOWN/"
                "conflicting (Chapter 13.8 / DDE-047)",
                details={
                    "requested": requested,
                    "inferred": inferred,
                    "policy_default": unknown_policy,
                },
            )

    tags = build_taint_tags(
        donor_artifact_id=None,
        source_uri=source_uri or None,
        source_class=source_class,
        licence_class=licence_class,
    )
    return ClassificationResult(
        source_class=source_class,
        licence_class=licence_class,
        licence_ids=tuple(licence_ids),
        conflicting=conflicting,
        evidence=tuple(evidence),
        policy_default_applied=policy_default_applied,
        taint_tags=tuple(tags),
    )


def classify_donor(
    text: str,
    *,
    requested_source_class: str | None = None,
    signed_reuse_decision_id: UUID | None = None,
    donor_artifact_id: UUID | None = None,
    source_uri: str = "",
    unknown_policy: UnknownPolicy = DEFAULT_UNKNOWN_POLICY,
) -> ClassificationResult:
    """Ingest-facing classifier used by DonorLabService.submit_uri."""
    result = classify_donor_content(
        text,
        source_uri=source_uri,
        requested=requested_source_class,
        signed_reuse_decision_id=signed_reuse_decision_id,
        unknown_policy=unknown_policy,
    )
    if donor_artifact_id is None:
        return result
    tags = build_taint_tags(
        donor_artifact_id=donor_artifact_id,
        source_uri=source_uri or None,
        source_class=result.source_class,
        licence_class=result.licence_class,
    )
    return ClassificationResult(
        source_class=result.source_class,
        licence_class=result.licence_class,
        licence_ids=result.licence_ids,
        conflicting=result.conflicting,
        evidence=result.evidence,
        policy_default_applied=result.policy_default_applied,
        taint_tags=tuple(tags),
    )


def resolve_source_class(
    requested: str | None,
    *,
    signed_reuse_decision_id: UUID | None,
    text: str = "",
    source_uri: str = "",
    unknown_policy: UnknownPolicy = DEFAULT_UNKNOWN_POLICY,
) -> str:
    """Back-compat entry; delegates to classify_donor_content."""
    return classify_donor_content(
        text,
        source_uri=source_uri,
        requested=requested,
        signed_reuse_decision_id=signed_reuse_decision_id,
        unknown_policy=unknown_policy,
    ).source_class


def _detect_licences(text: str) -> list[str]:
    found: list[str] = []
    for match in _SPDX_RE.finditer(text):
        spdx = match.group(1).strip()
        if spdx not in found:
            found.append(spdx)
    for match in _LICENCE_NAME_RE.finditer(text):
        raw = match.group(1).strip().lower()
        spdx = _NAME_TO_SPDX.get(raw)
        if spdx is None:
            continue
        if spdx not in found:
            found.append(spdx)
    return found


def _host_class(source_uri: str) -> tuple[str, str] | None:
    if not source_uri:
        return None
    try:
        host = (urlparse(source_uri).hostname or "").lower()
    except ValueError:
        return None
    if not host:
        return None
    if host in HOST_CLASS:
        return host, HOST_CLASS[host]
    if any(
        token in host
        for token in ("themeforest", "creative-tim", "envato", "ui8.net", "gumroad")
    ):
        return host, "REJECTED"
    return None


def _class_from_licences(licence_ids: list[str]) -> str | None:
    if not licence_ids:
        return None
    mapped: set[str] = set()
    for lid in licence_ids:
        if lid == "PROPRIETARY" or lid in REJECT_SPDX:
            mapped.add("REJECTED")
        elif lid in OPEN_SPDX:
            mapped.add("OPEN_REUSE")
        elif lid in CONDITIONAL_SPDX:
            mapped.add("CONDITIONAL_REUSE")
        else:
            mapped.add("UNKNOWN")
    if "UNKNOWN" in mapped and len(mapped) == 1:
        return None
    if len(mapped) > 1:
        return "CONFLICTING"
    return next(iter(mapped))


def _rank(source_class: str) -> int:
    order = {
        "OPEN_REUSE": 0,
        "CONDITIONAL_REUSE": 1,
        "SOURCE_REFERENCE_ONLY": 2,
        "RESTRICTED": 3,
        "UNKNOWN": 4,
        "REJECTED": 5,
    }
    return order.get(source_class, 4)
