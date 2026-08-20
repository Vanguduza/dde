"""Chapter 12's recovery module: the external effect journal (12.4), and the
sole writer of `external_effects` (Chapter 3.8). Checkpoints (12.1) and
replay (12.5/12.6) beyond `CommandLedger` reuse are out of this mission's
scope -- see `engine.recovery.service`'s module docstring.
"""

from __future__ import annotations
