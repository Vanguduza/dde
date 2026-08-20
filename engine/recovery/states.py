"""`ExternalEffect.status`'s state machine (Chapter 12.4), transcribed
verbatim from the chapter's own diagram:

```
PREPARED -> SENT -> CONFIRMED
                  -> FAILED
                  -> UNKNOWN -> RECONCILING -> RECONCILED
```

`RECONCILING` is re-enterable at the service level, not in this table: a
prior `reconcile()` call that could not determine the true external state
escalates (Chapter 12.4's IRREVERSIBLE rule) without transitioning the row
at all, so a second call against an already-`RECONCILING` effect finds it
still `RECONCILING` and simply retries the resolver -- `engine.recovery.
service.ExternalEffectService.reconcile` special-cases that "already there"
case instead of this table carrying an artificial self-loop. There is no
edge back to `UNKNOWN` or forward to `FAILED` from `RECONCILING`: the
chapter names exactly one resolution, `RECONCILED`, for both a
verified-present and a verified-absent finding (see `engine.recovery.
service`'s module docstring for how those two outcomes are distinguished
without a second status value).
"""

from __future__ import annotations

from typing import Final

EXTERNAL_EFFECT_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "PREPARED": frozenset({"SENT"}),
    "SENT": frozenset({"CONFIRMED", "FAILED", "UNKNOWN"}),
    "CONFIRMED": frozenset(),
    "FAILED": frozenset(),
    "UNKNOWN": frozenset({"RECONCILING"}),
    "RECONCILING": frozenset({"RECONCILED"}),
    "RECONCILED": frozenset(),
}
