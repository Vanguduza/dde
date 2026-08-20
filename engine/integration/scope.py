"""Chapter 10.3's overlap rule: "Two concurrently scheduled tasks may not
hold overlapping exclusive scopes. Overlap is computed on normalised path
globs and is deterministic."

Chapter 4.5/4.7 already define exactly this normalised-prefix comparison for
`Task.expected_write_scope` (`engine.planning.validate.scopes_overlap`/
`in_scope`) -- reused here rather than reimplemented, per this mission's
"reuse established patterns" constraint. The one real difference Chapter
10.3 introduces is the `/**` glob suffix its own example uses
(`"engine/routing/**"`); `_strip_glob_suffix` reduces that to the same
directory-prefix shape `scopes_overlap`/`in_scope` already understand, so a
single-file pattern with no suffix (e.g.
`"schemas/objects/route_decision.json"`) still matches by exact equality.
"""

from __future__ import annotations

from engine.planning.validate import in_scope, scopes_overlap

_GLOB_SUFFIXES: tuple[str, ...] = ("/**", "/*")


def _strip_glob_suffix(pattern: str) -> str:
    normalised = pattern.replace("\\", "/")
    for suffix in _GLOB_SUFFIXES:
        if normalised.endswith(suffix):
            return normalised[: -len(suffix)]
    return normalised


def normalise_patterns(patterns: list[str]) -> list[str]:
    return [_strip_glob_suffix(pattern) for pattern in patterns]


def leases_overlap(left: list[str], right: list[str]) -> bool:
    """Chapter 10.3's conflict-detection rule, over normalised globs."""
    return scopes_overlap(normalise_patterns(left), normalise_patterns(right))


def path_in_scope(path: str, patterns: list[str]) -> bool:
    """Chapter 10.3's `SCOPE_VIOLATION` check: is a real changed path
    covered by one of the lease's normalised scope patterns?"""
    return in_scope(path, normalise_patterns(patterns))
