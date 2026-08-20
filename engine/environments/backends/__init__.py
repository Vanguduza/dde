"""ExecutionEnvironment backends (Chapter 7.3: `type` is the substrate).

Exactly one backend exists in this mission's scope: `local_process`. The
`docker`/`microvm`/`vm`/`device`/`ci_runner`/`remote_api` types Chapter 7.3
enumerates are real, valid `type` values a future `ExecutionEnvironment` row
may carry, but no backend implements them yet — deliberately. Chapter 7.2's
T2 containment (container/microVM isolation, egress proxy, zero ambient
credentials) is S2 scope (DDE-018) and depends on infrastructure (a verified
container runtime available in CI, Chapter 17.4) this mission's environment
does not yet guarantee, even though `docker version`/`docker info` succeed on
this particular developer machine today.
"""

from __future__ import annotations
