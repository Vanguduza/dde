"""DDE command-line interface -- DDE-015's general command surface, built
around DDE-014's `dde mission trace`: `mission create`, `mission status`,
`mission trace`, `task list`. See `interfaces/cli/__main__.py` for the
`argparse` subcommand structure and every command's dispatch.

**Scope this mission did not add.** No `mission run` orchestration command
exists. Chapter 1's Day-1 walkthrough shows `dde mission run "<intent>"`
producing the whole spine (Mission through Evidence) from a single free-text
intent, but no blueprint component owns "drive context compile -> route ->
plan -> provision -> worker run -> verify -> integrate automatically" yet --
Chapter 2.6 is explicit that Mission Kernel "does not execute tools," and
Chapter 18.3 places the first durable, retryable execution-driving
machinery (`TaskAttempt durability + replay`, `failure taxonomy + recovery
matrix + replan`) at S3 (`DDE-023`/`DDE-024`), not S1. Building that
orchestration in this mission would mean inventing a component the
blueprint has not chartered yet. See `interfaces/cli/mission_create.py`'s
docstring for the full reasoning.

**Flagged boundary divergence (AGENTS.md / `interfaces/__init__.py`'s own
docstring: "Client-facing surfaces that consume the gateway, never core
tables").** Every module here reads/writes `engine.*` services and
repositories directly instead of going through Chapter 15's Gateway/API.
This is deliberate, not an oversight: Chapter 15.4's endpoint table lists
`GET /v1/evidence/{id}`, `GET /v1/mission-control/{id}`,
`GET /v1/missions/{id}/events`, `POST /v1/missions` etc., but none of them
are implemented yet -- `engine/gateway/app.py` only serves
`/healthz`/`/readyz` today, and building the whole read/write surface those
endpoints imply is far outside this mission's scope (DDE-027, Chapter 15,
is a later mission). Composing a full HTTP client against endpoints that do
not exist would not make these commands more correct, only more elaborate.
Once a later mission stands up the Gateway's mission/task/evidence
endpoints, these modules should be re-homed to call them instead of
`engine.*` directly, and this docstring's divergence notice should be
removed at that point.
"""
