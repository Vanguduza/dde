"""Chapter 12's recovery module: the external effect journal (12.4).

What is enforced: the live-journal recovery rule (no new mutation of a
blocked scope), `SIDE_EFFECT_UNKNOWN` on subprocess timeout, `abandon_sent`
for crash-abandoned `SENT`, production resolvers for `run_local_process`
and git `update-ref`, and a distinct `IRREVERSIBLE` escalation branch.
Checkpoints (12.1) and replay (12.5/12.6) beyond `CommandLedger` reuse are
out of this mission's scope -- see `engine.recovery.service`.
"""

from __future__ import annotations
