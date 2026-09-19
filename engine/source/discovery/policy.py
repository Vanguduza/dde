"""Discovery lifecycle, trust and disposition policy.

The load-bearing rule of EDR-0019 Epic C lives here: lifecycle maturity and source
trust are independent axes. `assign_trust` deliberately takes no trial, sandbox or
lifecycle argument, so there is no expression in which a passing trial could raise
trust. Qualification may only cap authority downwards, never lift it.
"""

from __future__ import annotations

from types import MappingProxyType

from engine.core.errors import DdeError

TRUST_ORDER: tuple[str, ...] = (
    "S1_NORMATIVE",
    "S2_FIRST_PARTY",
    "S3_VERIFIED_REGISTRY",
    "S4_MAINTAINED_OSS",
    "S5_MAINTAINER_COMMUNITY",
    "S6_COMMUNITY_CORROBORATED",
    "S7_DISCOVERY_ONLY",
    "S8_UNTRUSTED",
)
_TRUST_RANK = MappingProxyType({name: index for index, name in enumerate(TRUST_ORDER)})

# Open-world discovery starts at discovery-only. A host may lower the rank a
# candidate starts at, never raise it past S2: S1_NORMATIVE is Project Truth and is
# unreachable for anything discovered externally.
_FIRST_PARTY_DOC_HOSTS = frozenset(
    {
        "docs.python.org",
        "peps.python.org",
        "developer.mozilla.org",
        "docs.djangoproject.com",
        "kubernetes.io",
        "docs.docker.com",
        "www.postgresql.org",
    }
)
_REGISTRY_SCHEMES = frozenset({"PACKAGE_COORDINATE"})

LIFECYCLE_TRANSITIONS: MappingProxyType[str, frozenset[str]] = MappingProxyType(
    {
        "DISCOVERED": frozenset({"TRIAGED", "REJECTED", "SUPERSEDED"}),
        "TRIAGED": frozenset({"PROVENANCE_CHECKED", "REJECTED", "SUPERSEDED"}),
        "PROVENANCE_CHECKED": frozenset({"CONTENT_ACQUIRED", "REJECTED", "SUPERSEDED"}),
        "CONTENT_ACQUIRED": frozenset({"SANITIZED", "REJECTED", "SUPERSEDED"}),
        "SANITIZED": frozenset({"ARCHITECTURE_CHECKED", "REJECTED", "SUPERSEDED"}),
        # A non-executable resource is qualified straight from the architecture
        # check; only an executable candidate needs a trial.
        "ARCHITECTURE_CHECKED": frozenset(
            {"TRIAL_ELIGIBLE", "QUALIFIED", "REJECTED", "SUPERSEDED"}
        ),
        "TRIAL_ELIGIBLE": frozenset({"SANDBOX_TESTED", "REJECTED", "SUPERSEDED"}),
        "SANDBOX_TESTED": frozenset({"QUALIFIED", "REJECTED", "SUPERSEDED"}),
        "QUALIFIED": frozenset({"ADMITTED", "REJECTED", "SUPERSEDED", "REVOKED"}),
        "ADMITTED": frozenset({"SUPERSEDED", "REVOKED"}),
        "REJECTED": frozenset({"SUPERSEDED"}),
        "SUPERSEDED": frozenset(),
        "REVOKED": frozenset(),
    }
)

_ADMITTING = frozenset(
    {
        "ADMIT_EXECUTABLE",
        "ADMIT_POSITIVE_GUIDANCE",
        "ADMIT_REFERENCE_ONLY",
        "ADMIT_OBSERVATION_ONLY",
        "ADMIT_ANTI_PATTERN",
    }
)
_HOLDING = frozenset(
    {
        "HOLD_FOR_CORROBORATION",
        "HOLD_FOR_VERSION",
        "HOLD_FOR_LICENSE",
        "HOLD_FOR_SECURITY",
    }
)
_REJECTING = frozenset({"REJECT_MALICIOUS", "REJECT_IRRELEVANT", "REJECT_UNVERIFIABLE"})

# Disposition -> (polarity, allowed uses, forbidden uses). Anti-pattern and
# observation material stays retrievable and can never fill a positive slot.
_DISPOSITION_RULES: MappingProxyType[str, tuple[str, tuple[str, ...], tuple[str, ...]]]
_DISPOSITION_RULES = MappingProxyType(
    {
        "ADMIT_EXECUTABLE": (
            "POSITIVE",
            ("DISCOVERY", "REFERENCE", "CORROBORATION", "EXECUTABLE_ACTIVATION"),
            ("SECURITY_AUTHORITY",),
        ),
        "ADMIT_POSITIVE_GUIDANCE": (
            "POSITIVE",
            ("DISCOVERY", "REFERENCE", "CORROBORATION", "NORMATIVE_IMPLEMENTATION"),
            ("EXECUTABLE_ACTIVATION", "SECURITY_AUTHORITY"),
        ),
        "ADMIT_REFERENCE_ONLY": (
            "OBSERVATION_ONLY",
            ("DISCOVERY", "REFERENCE", "CORROBORATION"),
            ("NORMATIVE_IMPLEMENTATION", "EXECUTABLE_ACTIVATION", "SECURITY_AUTHORITY"),
        ),
        "ADMIT_OBSERVATION_ONLY": (
            "OBSERVATION_ONLY",
            ("DISCOVERY",),
            ("NORMATIVE_IMPLEMENTATION", "EXECUTABLE_ACTIVATION", "SECURITY_AUTHORITY"),
        ),
        "ADMIT_ANTI_PATTERN": (
            "ANTI_PATTERN",
            ("DISCOVERY", "ANTI_PATTERN", "FAILURE_SIGNATURE"),
            ("NORMATIVE_IMPLEMENTATION", "EXECUTABLE_ACTIVATION", "SECURITY_AUTHORITY"),
        ),
    }
)
_HOLD_RULE = (
    "OBSERVATION_ONLY",
    ("DISCOVERY",),
    ("NORMATIVE_IMPLEMENTATION", "EXECUTABLE_ACTIVATION", "SECURITY_AUTHORITY"),
)
_REJECT_RULE = (
    "OBSERVATION_ONLY",
    (),
    (
        "DISCOVERY",
        "NORMATIVE_IMPLEMENTATION",
        "EXECUTABLE_ACTIVATION",
        "SECURITY_AUTHORITY",
    ),
)


def assign_trust(*, identity_scheme: str, host: str) -> str:
    """Initial source trust, derived only from where the material comes from.

    This signature takes no lifecycle state and no trial result on purpose: there
    must be no code path by which sandbox success becomes authority.
    """
    if host.lower() in _FIRST_PARTY_DOC_HOSTS:
        return "S2_FIRST_PARTY"
    if identity_scheme in _REGISTRY_SCHEMES:
        return "S3_VERIFIED_REGISTRY"
    return "S7_DISCOVERY_ONLY"


def is_legal_transition(from_state: str | None, to_state: str) -> bool:
    if from_state is None:
        return to_state == "DISCOVERED"
    allowed = LIFECYCLE_TRANSITIONS.get(from_state)
    if allowed is None:
        return False
    return to_state in allowed


def require_legal_transition(from_state: str | None, to_state: str) -> None:
    if not is_legal_transition(from_state, to_state):
        raise DdeError(
            "POLICY_DENIED",
            f"illegal discovery transition {from_state or '<new>'} -> {to_state}",
            retryable=False,
            details={"from_state": from_state, "to_state": to_state},
        )


def cap_authority(candidate_trust: str, requested_ceiling: str) -> str:
    """Authority may be capped downwards; it may never exceed the candidate's trust."""
    if requested_ceiling not in _TRUST_RANK:
        raise DdeError(
            "VALIDATION_FAILED",
            f"unknown authority ceiling {requested_ceiling}",
            retryable=False,
        )
    if _TRUST_RANK[requested_ceiling] < _TRUST_RANK[candidate_trust]:
        return candidate_trust
    return requested_ceiling


def disposition_rule(disposition: str) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Return `(guidance_polarity, allowed_uses, forbidden_uses)` for a disposition."""
    if disposition in _DISPOSITION_RULES:
        return _DISPOSITION_RULES[disposition]
    if disposition in _HOLDING:
        return _HOLD_RULE
    if disposition in _REJECTING or disposition == "SUPERSEDED":
        return _REJECT_RULE
    raise DdeError(
        "VALIDATION_FAILED",
        f"unknown discovery disposition {disposition}",
        retryable=False,
    )


def admits(disposition: str) -> bool:
    return disposition in _ADMITTING


def terminal_state_for(disposition: str) -> str:
    if disposition in _ADMITTING:
        return "ADMITTED"
    if disposition in _HOLDING:
        return "QUALIFIED"
    if disposition == "SUPERSEDED":
        return "SUPERSEDED"
    return "REJECTED"
