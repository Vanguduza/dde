"""Worker self-grading guardrails (Chapter 11.4 independence, mechanically).

SWE-bench's documented harness-gaming attacks are this codebase's exact
threat model: a generator worker that edits its own tests, or adds a file at
a path where the oracle expects to FIND tests, can manufacture a false
"resolved" without the product ever working. The comparable-systems research
(§4, item 1) adopts SWE-bench issue #538's lesson for DDE: these checks
belong in the verification chain itself, before oracle evaluation -- cheap,
deterministic, and recorded as evidence rather than asserted in prose.

**What is wired here.** `assess_diff_independence()` inspects the real diff
under verification (computed from `workspace.base_revision` via
`WorkspaceService.diff_name_only` -- committed and uncommitted changes) at
the production call site `VerificationRunnerService.run`
(`engine.verification.runner`) before any oracle outcome executes. Two
mechanical findings:

- `undeclared_test_edits`: the diff touches a test-owned path the Task does
  not authorise (`Task.expected_write_scope` carries no matching entry).
- `shadowed_test_layout`: an ADDED file sits at a path matching the oracle's
  expected-test layout (paths its bindings reference), which could shadow or
  displace the real suite.

Findings travel on the existing `Evidence.independence_flags` map (free-form
`dict[str, object]`, schema `additionalProperties: true`) under the keys
`test_scope_findings` / `test_scope_violation`; the per-evidence
`independent` flag stays True -- these checks judge *what changed*, they do
not by themselves overturn a verdict.

The runner records findings, refuses to certify a clean pass over a
violating diff (`runner._evaluate`: PARTIAL), and classifies the run as
SCOPE_VIOLATION on the recovery surface this codebase already consumes:
its `TaskAttempt` is durably FAILED with that failure class, so
`RecoveryService.assert_clear_to_retry` maps it onto Chapter 12.3's
reject/requires-human/never-retry row.

**Honest limits.** Stage 1 has no declared test-file manifest: "test-owned"
is inferred from conventional test-path patterns plus whatever paths the
oracle's own bindings name; `expected_write_scope` entries are prefix-
matched. The runner still does not quarantine the workspace or compute a
context-attribution for the violation; the PARTIAL `VerificationRun`
carries no `routing_decision_outcomes` telemetry row (Chapter 6.5's
outcome enum admits only PASSED/FAILED).
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.contracts.acceptance_oracle import AcceptanceOracle
from engine.contracts.task import Task

TEST_OWNED_SUFFIXES: tuple[str, ...] = (
    "test_",
    "_test.py",
    ".spec.ts",
    ".test.ts",
    ".spec.js",
    ".test.js",
)
TEST_DIRECTORY_SEGMENTS: tuple[str, ...] = ("tests", "test")
ORACLE_LAYOUT_SEGMENT = "/tests/"

INDEPENDENCE_FLAG_KEY = "test_scope_findings"
VIOLATION_FLAG_KEY = "test_scope_violation"


def _is_test_owned(path: str) -> bool:
    """Filename-level ownership: the file itself IS a test module (or
    spec), by conventional naming -- `test_*.py`, `*_test.py`, `*.spec.*`.
    Deliberately does NOT look at directories and deliberately does NOT
    claim `conftest`/fixtures: those live inside test directories but are
    injection vectors rather than gradable tests, so they belong to the
    shadowing rule below."""
    normalised = path.replace("\\", "/")
    name = normalised.rsplit("/", 1)[-1]
    return name.startswith(TEST_OWNED_SUFFIXES) or name.endswith(TEST_OWNED_SUFFIXES)


def _authorises(task: Task, path: str) -> bool:
    normalised = path.replace("\\", "/")
    return any(
        scope_entry
        and (
            normalised == scope_entry
            or normalised.startswith(scope_entry.rstrip("/") + "/")
        )
        for scope_entry in task.expected_write_scope
    )


def _oracle_declared_paths(oracle: AcceptanceOracle) -> set[str]:
    paths: set[str] = set()
    for outcome in [*oracle.observable_outcomes, *oracle.negative_cases]:
        ref = outcome.evidence_binding.ref
        if ref and _is_test_owned(ref):
            paths.add(ref.replace("\\", "/"))
    return paths


@dataclass(frozen=True)
class TestScopeFinding:
    """One mechanical anti-gaming observation about the diff under
    verification. `violation` marks findings that make a clean PASSED
    certification dishonest."""

    kind: str
    path: str
    detail: str
    violation: bool


@dataclass(frozen=True)
class TestScopeAssessment:
    """Result of the pre-oracle guardrail sweep. `violations` non-empty
    means the diff games the harness; `findings` may still carry
    informational entries when `violations` is empty."""

    findings: tuple[TestScopeFinding, ...]

    @property
    def violations(self) -> tuple[TestScopeFinding, ...]:
        return tuple(item for item in self.findings if item.violation)

    def as_flags(self) -> dict[str, object]:
        """The exact `Evidence.independence_flags` additions for one
        evidence row: always the full finding list; plus a boolean marker
        key only when a violation exists."""
        flags: dict[str, object] = {
            INDEPENDENCE_FLAG_KEY: [
                {
                    "kind": item.kind,
                    "path": item.path,
                    "detail": item.detail,
                    "violation": item.violation,
                }
                for item in self.findings
            ]
        }
        violations = self.violations
        if violations:
            flags[VIOLATION_FLAG_KEY] = True
        else:
            flags[VIOLATION_FLAG_KEY] = False
        return flags


def assess_diff_independence(
    *,
    task: Task,
    oracle: AcceptanceOracle,
    changed_files: list[str],
) -> TestScopeAssessment:
    """Pure policy over the already-computed changed-file list: no I/O, so
    the runner can call it inside the verification transaction and unit
    tests can drive it without PostgreSQL. Findings are deterministic for
    a given `(task, oracle, changed_files)` triple and mutually exclusive
    per path: a test-module FILENAME (`test_*.py`/`*_test.py`/`*.spec.*`)
    outside the task's write scope counts as an undeclared test EDIT; any
    other file sitting INSIDE a conventional test directory tree
    (`conftest`, fixtures, data, plugins) counts as potential layout
    shadowing."""

    oracle_paths = _oracle_declared_paths(oracle)
    findings: list[TestScopeFinding] = []

    for path in sorted(dict.fromkeys(changed_files)):
        normalised = path.replace("\\", "/")
        if _authorises(task, normalised):
            continue
        if _is_test_owned(normalised):
            findings.append(
                TestScopeFinding(
                    kind="undeclared_test_edit",
                    path=normalised,
                    detail=(
                        "diff touches a test-owned path outside the task's "
                        "declared write scope"
                    ),
                    violation=True,
                )
            )
            continue
        if not _in_test_directory(normalised):
            continue
        shadow_targets = sorted(
            target
            for target in oracle_paths
            if target == normalised
            or target.rsplit("/", 1)[0] == normalised.rsplit("/", 1)[0]
        )
        findings.append(
            TestScopeFinding(
                kind="added_file_shadows_expected_test_layout",
                path=normalised,
                detail=(
                    "file added inside a test directory overlapping the "
                    "oracle's expected-test layout (" + ", ".join(shadow_targets) + ")"
                    if shadow_targets
                    else "file added inside a conventional test directory "
                    "where an expected test could be displaced"
                ),
                violation=True,
            )
        )

    return TestScopeAssessment(findings=tuple(findings))


def _in_test_directory(path: str) -> bool:
    """A file whose LOCATION could inject or displace expected tests: any
    parent segment naming a conventional test directory. Without an
    added/renamed marker from git, every such path is treated as a
    potential injection (disclosed conservative limitation)."""
    segments = path.split("/")
    return any(
        segment in TEST_DIRECTORY_SEGMENTS or segment.startswith("test_")
        for segment in segments[:-1]
    )


def merge_flags(
    base: dict[str, object], assessment: TestScopeAssessment
) -> dict[str, object]:
    """Return the evidence independence-flags dict with the guardrail
    findings merged in. `base` keeps the runner's generator/verifier
    separation record; guardrail keys never overwrite it."""
    merged: dict[str, object] = dict(base)
    merged.update(assessment.as_flags())
    return merged
