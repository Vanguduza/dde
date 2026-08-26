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

**Two surfaces.** The Stage-1 ``dde mission create|status|trace`` and
``task list`` commands still call ``engine.*`` services directly (they
predate the Gateway and remain the Day-1 walkthrough path). DDE-056 adds
``gateway_client.py`` — the allowlisted ``/v1`` client twin of the web
dashboard and Android thin client — so the golden CLI/web/Android parity
fixture can prove identical authoritative outcomes on one Gateway path
without inventing list/stream endpoints.
"""
