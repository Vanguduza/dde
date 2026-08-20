"""`ExternalEffect.status`'s state machine (Chapter 12.4), transcribed
verbatim from the chapter's own diagram:

```
PREPARED -> SENT -> CONFIRMED
                  -> FAILED
                  -> UNKNOWN -> RECONCILING -> RECONCILED
```

`RECONCILING` is re-enterable at the service level, not in this table: a
prior `reconcile()` call that could not determine the true external state
raises without transitioning the row, so a second call against an already-
`RECONCILING` effect retries the resolver. `IRREVERSIBLE` verification
failure is that same `RECONCILING` row plus a distinct
`ExternalEffectIrreversibleEscalated` event / `EFFECT_IRREVERSIBLE` error
(see `ExternalEffectService.reconcile`); other classes raise
`EFFECT_UNKNOWN`. There is no edge back to `UNKNOWN` or forward to
`FAILED` from `RECONCILING`: the chapter names exactly one resolution,
`RECONCILED`, for both a verified-present and a verified-absent finding.
Verified-present sets `confirmed_at`; verified-absent leaves it null --
that is how the recovery gate distinguishes "do not mutate again" from
"a new attempt is permitted" without a second status value.
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
