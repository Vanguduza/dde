"""Mission Kernel and mission state machine.

`MissionService` (backed by PostgreSQL) is the production writer of
`missions` and `tasks` (Chapter 3.8). `task_graphs` and `task_graph_edges`
are `engine.planning.service.TaskGraphService`'s to write; `MissionService`
composes that service under a shared unit of work rather than writing those
tables itself. `MissionKernel` and `MissionStore` are an in-memory test
double only — they never touch a database and must not be used as a
production store.
"""

from engine.missions.kernel import MissionKernel, MissionStore
from engine.missions.service import MissionService

__all__ = ["MissionKernel", "MissionService", "MissionStore"]
