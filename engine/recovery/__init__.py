"""Chapter 12's recovery module: external effect journal (12.4),
checkpoints (12.1), TaskAttempt-aware replay (12.5), and MissionWorkflow
v1 (12.6).

What is enforced: reconstructible checkpoints with load-bearing
do_not_repeat; completed TaskAttempt / COMPLETED WorkerRun not re-run;
EVENT_WINDOW_EXPIRED fallback to checkpoint plus durable attempts; generic
retry refused. Chapter 12.3 recovery matrix is DDE-024.
"""

from __future__ import annotations
