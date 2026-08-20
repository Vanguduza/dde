"""Sole writer of Project Truth records.

`TruthService` (backed by PostgreSQL) is the production writer. `TruthEngine`
and `TruthStore` are an in-memory test double only — they never touch a
database and must not be used as a production store.
"""

from engine.truth.engine import TruthEngine, TruthStore
from engine.truth.service import TruthService

__all__ = ["TruthEngine", "TruthService", "TruthStore"]
