"""Pure Chapter 9.6–9.7 gate evaluators -- no PostgreSQL.

These prove the in-process scanners actually inspect a real diff: a planted
secret, a planted vulnerable dependency, a typosquat, a forbidden path,
and a missing licence header each fail closed, and a clean diff plus a
justified new dependency pass. Persistence and merge-queue wiring live in
`test_diff_gates_postgres.py`.
"""

from __future__ import annotations

from engine.core.hashing import canonical_json, sha256_hex
from engine.integration.gates import (
    evaluate_diff,
    generate_sbom,
    scan_forbidden_paths,
    scan_licence_headers,
    scan_secrets,
    scan_static,
)

PLANTED_SECRET = "-----BEGIN RSA PRIVATE KEY-----"  # noqa: S105


def test_secret_detection_blocks_a_planted_private_key() -> None:
    diff = (
        "diff --git a/x.txt b/x.txt\n"
        "--- a/x.txt\n"
        "+++ b/x.txt\n"
        "@@ -0,0 +1 @@\n"
        f"+{PLANTED_SECRET}\n"
    )
    finding = scan_secrets(diff)
    assert finding.passed is False
    assert finding.blocking is True
    assert finding.gate == "secret_detection"


def test_secret_detection_passes_a_clean_diff() -> None:
    diff = (
        "diff --git a/x.txt b/x.txt\n"
        "--- a/x.txt\n"
        "+++ b/x.txt\n"
        "@@ -0,0 +1 @@\n"
        "+hello world\n"
    )
    assert scan_secrets(diff).passed is True


def test_secret_detection_blob_backstop_when_diff_has_no_plus_lines() -> None:
    """Regression: git 'Binary files differ' hunks carry no '+' lines;
    proposed blob contents must still fail closed."""
    binary_style_diff = (
        "diff --git a/engine/routing/dde021-secret.txt "
        "b/engine/routing/dde021-secret.txt\n"
        "new file mode 100644\n"
        "index 0000000..abc1234\n"
        "Binary files /dev/null and b/engine/routing/dde021-secret.txt differ\n"
    )
    assert scan_secrets(binary_style_diff).passed is True
    finding = scan_secrets(
        binary_style_diff,
        proposed_blobs={
            "engine/routing/dde021-secret.txt": f"{PLANTED_SECRET}\n",
        },
    )
    assert finding.passed is False
    assert finding.blocking is True
    assert "private_key_pem" in str(finding.details.get("hit_classes"))


def test_forbidden_path_blocks_github_workflows() -> None:
    finding = scan_forbidden_paths([".github/workflows/evil.yml"])
    assert finding.passed is False
    assert finding.gate == "forbidden_path"


def test_licence_header_blocks_new_python_without_spdx() -> None:
    finding = scan_licence_headers(
        ["engine/routing/new_mod.py"],
        {"engine/routing/new_mod.py": "def f() -> None:\n    return None\n"},
    )
    assert finding.passed is False


def test_licence_header_passes_spdx_header() -> None:
    finding = scan_licence_headers(
        ["engine/routing/new_mod.py"],
        {
            "engine/routing/new_mod.py": (
                "# SPDX-License-Identifier: Apache-2.0\n\ndef f() -> None:\n    pass\n"
            )
        },
    )
    assert finding.passed is True


def test_static_analysis_blocks_subprocess_shell() -> None:
    diff = (
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -0,0 +1 @@\n"
        "+subprocess.run(cmd, shell=True)\n"
    )
    assert scan_static(diff).passed is False


def test_planted_vulnerable_dependency_is_rejected() -> None:
    outcome = evaluate_diff(
        changed_paths=["engine/routing/requirements.txt"],
        unified_diff=(
            "diff --git a/engine/routing/requirements.txt "
            "b/engine/routing/requirements.txt\n"
            "--- /dev/null\n"
            "+++ b/engine/routing/requirements.txt\n"
            "@@ -0,0 +1 @@\n"
            "+dde-planted-vulnerable==0.0.1\n"
        ),
        proposed_blobs={
            "engine/routing/requirements.txt": "dde-planted-vulnerable==0.0.1\n"
        },
        base_manifest_blobs={"engine/routing/requirements.txt": None},
        proposed_manifest_blobs={
            "engine/routing/requirements.txt": "dde-planted-vulnerable==0.0.1\n"
        },
        new_paths=["engine/routing/requirements.txt"],
    )
    assert outcome.passed is False
    assert outcome.admissions
    assert outcome.admissions[0].status == "REJECTED"
    assert outcome.admissions[0].vulnerability_ids == ("DDE-PLANTED-001",)
    assert "dde-planted-vulnerable" in str(outcome.sbom_document)


def test_new_top_level_without_justification_is_rejected() -> None:
    outcome = evaluate_diff(
        changed_paths=["engine/routing/requirements.txt"],
        unified_diff=(
            "diff --git a/engine/routing/requirements.txt "
            "b/engine/routing/requirements.txt\n"
            "--- /dev/null\n"
            "+++ b/engine/routing/requirements.txt\n"
            "@@ -0,0 +1 @@\n"
            "+httpx==0.27.0\n"
        ),
        proposed_blobs={"engine/routing/requirements.txt": "httpx==0.27.0\n"},
        base_manifest_blobs={"engine/routing/requirements.txt": None},
        proposed_manifest_blobs={"engine/routing/requirements.txt": "httpx==0.27.0\n"},
        new_paths=["engine/routing/requirements.txt"],
    )
    assert outcome.passed is False
    assert outcome.admissions[0].blocking_reason is not None
    assert "justification" in outcome.admissions[0].blocking_reason


def test_justified_new_dependency_is_admitted() -> None:
    justification = (
        "# httpx\n"
        "licence: BSD-3-Clause\n"
        "maintenance: actively maintained\n"
        "stdlib_insufficient: HTTP/2 and timeout control urllib lacks\n"
    )
    outcome = evaluate_diff(
        changed_paths=[
            "engine/routing/requirements.txt",
            "engine/routing/DEPENDENCY_JUSTIFICATION.md",
        ],
        unified_diff=(
            "diff --git a/engine/routing/requirements.txt "
            "b/engine/routing/requirements.txt\n"
            "--- /dev/null\n"
            "+++ b/engine/routing/requirements.txt\n"
            "@@ -0,0 +1 @@\n"
            "+httpx==0.27.0\n"
        ),
        proposed_blobs={
            "engine/routing/requirements.txt": "httpx==0.27.0\n",
            "engine/routing/DEPENDENCY_JUSTIFICATION.md": justification,
        },
        base_manifest_blobs={"engine/routing/requirements.txt": None},
        proposed_manifest_blobs={"engine/routing/requirements.txt": "httpx==0.27.0\n"},
        new_paths=[
            "engine/routing/requirements.txt",
            "engine/routing/DEPENDENCY_JUSTIFICATION.md",
        ],
    )
    assert outcome.passed is True
    assert outcome.admissions[0].status == "ADMITTED"


def test_typosquat_is_rejected() -> None:
    outcome = evaluate_diff(
        changed_paths=["engine/routing/requirements.txt"],
        unified_diff="",
        proposed_blobs={"engine/routing/requirements.txt": "reqeusts==2.0.0\n"},
        base_manifest_blobs={"engine/routing/requirements.txt": None},
        proposed_manifest_blobs={
            "engine/routing/requirements.txt": "reqeusts==2.0.0\n"
        },
        new_paths=["engine/routing/requirements.txt"],
    )
    assert outcome.passed is False
    assert outcome.admissions[0].typosquat_of == "requests"


def test_sbom_round_trips_through_content_hash() -> None:
    document, digest = generate_sbom(
        {"pyproject.toml": '[project]\ndependencies = ["fastapi>=0.1"]\n'}
    )
    assert document["bomFormat"] == "CycloneDX"
    assert document["specVersion"] == "1.5"
    components = document["components"]
    assert isinstance(components, list)
    assert any(
        isinstance(item, dict) and item.get("name") == "fastapi" for item in components
    )
    assert sha256_hex(canonical_json(document)) == digest
