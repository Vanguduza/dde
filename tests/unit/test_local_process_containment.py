"""Chapter 7.2 T2 rule 1 ("Zero ambient credentials") and Chapter 18.2's S2
exit-gate fixture ("no ambient credential reachable from an environment"),
proven against the one real `EnvironmentBackend` this repository has
(`LocalProcessBackend`, DDE-010).

**Scoping note (DDE-018).** Chapter 7.2 ties full T2 containment (egress
proxy, seccomp, non-privileged user, container/microVM isolation) to
"third-party agent harnesses with their own tool planes" -- a caller class
that does not exist yet in this codebase (the only certified worker,
`engine.workers.scripted_adapter.ScriptedWorkerAdapter`, is DDE-native and
already T1-brokered; see `engine.capabilities.seed.SEED_CAPABILITIES`, all
three of which are correctly declared `enforcement_tier="T1"`). Real
container-level egress control and full credential isolation are
therefore out of this mission's honest reach on this platform without the
container backend DDE-010 explicitly deferred (see
`engine.environments.backends.local_process`'s module docstring).

What genuinely IS buildable and provable today, independent of any
container: `LocalProcessBackend.run()` no longer hands a worker-controlled
subprocess a verbatim copy of the Core process's own environment (which,
per this repository's own `DDE_DATABASE_URL`/`DDE_REDIS_URL` convention,
is exactly where real credential material lives today). This suite plants
a fake ambient secret in the *test* process's own environment -- exactly
mirroring a real credential -- and proves a real spawned subprocess
cannot read it back."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from engine.environments.backends.local_process import LocalProcessBackend

AMBIENT_SECRET_ENV_VAR = "DDE_TEST_AMBIENT_SECRET_TOKEN"  # noqa: S105 -- fixture name, not a secret
AMBIENT_SECRET_VALUE = "sk-fake-ambient-credential-should-never-leak"  # noqa: S105 -- fake planted value


def _read_env_var_probe(name: str) -> list[str]:
    return [
        sys.executable,
        "-c",
        f"import os, sys; sys.stdout.write(os.environ.get({name!r}, '<ABSENT>'))",
    ]


def test_spawned_subprocess_cannot_read_planted_ambient_credential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The negative test (Chapter 19.1's Security suite: "credential
    exfiltration attempt"; Chapter 18.2's S2 exit gate: "no ambient
    credential reachable from an environment"). Plants a real fake secret
    in the *test process's own* environment -- the same mechanism a real
    provider token or `DDE_DATABASE_URL` would use -- and proves a real
    subprocess spawned by `LocalProcessBackend.run()` genuinely cannot read
    it. This test would fail today if `run()` reverted to `env=None`
    (verbatim ambient inheritance)."""
    monkeypatch.setenv(AMBIENT_SECRET_ENV_VAR, AMBIENT_SECRET_VALUE)

    backend = LocalProcessBackend()
    result = backend.run(
        cwd=tmp_path,
        command=_read_env_var_probe(AMBIENT_SECRET_ENV_VAR),
        timeout_seconds=10.0,
    )

    assert result.exit_code == 0
    assert AMBIENT_SECRET_VALUE not in result.stdout
    assert result.stdout == "<ABSENT>"


def test_spawned_subprocess_still_gets_a_functional_minimal_environment(
    tmp_path: Path,
) -> None:
    """The positive control for the test above: containment must not be a
    placebo that merely breaks every subprocess. A real interpreter must
    still be able to start, run and exit cleanly with the filtered
    environment `run()` now passes."""
    backend = LocalProcessBackend()
    result = backend.run(
        cwd=tmp_path,
        command=[sys.executable, "-c", "print('dde-containment-proof')"],
        timeout_seconds=10.0,
    )

    assert result.exit_code == 0
    assert not result.timed_out
    assert "dde-containment-proof" in result.stdout


def test_non_allowlisted_ambient_variable_is_absent_even_when_populated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second, differently-named ambient variable (not the first test's
    `DDE_`-prefixed name) is also absent -- proves the mechanism is a real
    allowlist, not a name-specific special case for one variable."""
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-aws-secret")

    backend = LocalProcessBackend()
    result = backend.run(
        cwd=tmp_path,
        command=_read_env_var_probe("AWS_SECRET_ACCESS_KEY"),
        timeout_seconds=10.0,
    )

    assert result.exit_code == 0
    assert result.stdout == "<ABSENT>"
