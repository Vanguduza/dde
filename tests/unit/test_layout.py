"""Layout, import-boundary and identity tests."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

from engine.core.ids import uuid7

ROOT = Path(__file__).resolve().parents[2]

ENGINE_PACKAGES = [
    "engine.audit",
    "engine.capabilities",
    "engine.context",
    "engine.core",
    "engine.environments",
    "engine.events",
    "engine.execution",
    "engine.governance",
    "engine.integration",
    "engine.knowledge",
    "engine.learning",
    "engine.missions",
    "engine.planning",
    "engine.projections",
    "engine.recovery",
    "engine.routing",
    "engine.truth",
    "engine.verification",
    "engine.workers",
    "engine.workspaces",
    "engine.dr",
]


def test_uuid7_version_and_variant() -> None:
    value = uuid7()
    assert value.version == 7
    assert ((value.int >> 62) & 0x3) == 2


def test_chapter_36_directories_exist() -> None:
    required = [
        "engine/core",
        "engine/truth",
        "engine/missions",
        "engine/planning",
        "engine/context",
        "engine/routing",
        "engine/execution",
        "engine/environments",
        "engine/workspaces",
        "engine/workers",
        "engine/capabilities",
        "engine/integration",
        "engine/verification",
        "engine/recovery",
        "engine/governance",
        "engine/events",
        "engine/projections",
        "engine/learning",
        "engine/knowledge",
        "engine/audit",
        "engine/contracts",
        "engine/gateway",
        "adapters",
        "interfaces",
        "schemas",
        "migrations",
        "evals",
        "evals/context",
        "evals/routing",
        "evals/security",
        "evals/chaos",
        "evals/golden-mission",
        "tests",
        "infra",
        "docs/blueprint",
        "docs/truth",
    ]
    missing = [item for item in required if not (ROOT / item).exists()]
    assert missing == []


def test_engine_packages_import() -> None:
    for name in ENGINE_PACKAGES:
        imported = importlib.import_module(name)
        assert imported.__doc__


def test_core_does_not_import_adapters_or_vendor_sdks() -> None:
    forbidden_prefixes = ("adapters", "anthropic", "openai", "langfuse")
    for path in (ROOT / "engine" / "core").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            for name in names:
                assert not any(
                    name == prefix or name.startswith(f"{prefix}.")
                    for prefix in forbidden_prefixes
                )


def test_cursor_sdk_is_only_importable_from_adapters_cursor() -> None:
    """AGENTS.md: cursor_sdk / cursor-sdk-bridge may be imported only from
    adapters/cursor/**. DDE-025's Cursor adapter does not import them yet
    (live invocation is fail-closed); this still fences the rest of the
    tree so a later credentialed wiring cannot leak into engine/.
    """
    forbidden = ("cursor_sdk", "cursor-sdk-bridge", "cursor_sdk_bridge")
    scanned = (
        ROOT / "engine",
        ROOT / "adapters",
        ROOT / "scripts",
        ROOT / "tests",
    )
    for root in scanned:
        for path in root.rglob("*.py"):
            if "adapters" in path.parts and "cursor" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names.append(node.module)
                for name in names:
                    assert not any(
                        name == item or name.startswith(f"{item}.")
                        for item in forbidden
                    ), path


def test_adapters_claude_is_not_imported_from_engine() -> None:
    """AGENTS.md boundary, EDR-0001 Path A: `adapters/claude/**` carries
    every Claude/Anthropic-specific name in this repository (mirrors
    `adapters/cursor/**`'s existing boundary). `engine/**` never imports it
    directly -- a concrete `WorkerAdapter` instance is handed to
    `engine.workers.registry.WorkerProfileRegistry` by whatever process
    wiring constructs adapters, never by an import inside `engine/**`
    itself. `engine/core` is additionally covered by
    `test_core_does_not_import_adapters_or_vendor_sdks` (it forbids the
    whole `adapters` prefix, not just `adapters.claude`)."""
    forbidden = ("adapters.claude",)
    for path in (ROOT / "engine").rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            for name in names:
                assert not any(
                    name == item or name.startswith(f"{item}.") for item in forbidden
                ), path
