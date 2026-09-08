"""Deterministic target-workspace stack observation for Production VEKL.

The observer reads DDE-owned Workspace state and repository/runtime files only.
It has no model/provider input and performs no network access. Every observed file
fact is content-hash backed so StackFingerprint is reproducible and invalidatable.
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from engine.contracts.workspace import Workspace
from engine.core.errors import DdeError

_SKIP_DIRS = frozenset(
    {".git", ".dde", ".venv", "node_modules", "dist", "build", "__pycache__"}
)
_STACK_NAMES = frozenset(
    {
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "pnpm-lock.yml",
        "yarn.lock",
        "bun.lock",
        "bun.lockb",
        "pyproject.toml",
        "uv.lock",
        "poetry.lock",
        "Pipfile.lock",
        "requirements.txt",
        "Cargo.toml",
        "Cargo.lock",
        "go.mod",
        "go.sum",
        "pubspec.yaml",
        "pubspec.lock",
        "gradle.lockfile",
        "pom.xml",
        ".python-version",
        ".nvmrc",
        ".node-version",
    }
)
_MAX_FILES = 256
_MAX_FILE_BYTES = 4_000_000
_EXACT_SEMVER = re.compile(r"^(?:v)?\d+(?:\.\d+){0,3}(?:[-+][0-9A-Za-z.-]+)?$")
_PEP508_EXACT = re.compile(r"^\s*([A-Za-z0-9_.-]+)(?:\[[^]]+\])?\s*==\s*([^;\s]+)")


@dataclass(frozen=True)
class StackObservation:
    facts: dict[str, object]
    evidence_refs: tuple[str, ...]


def _hash_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _safe_stack_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [name for name in dirnames if name not in _SKIP_DIRS]
        base = Path(directory)
        for name in filenames:
            if name not in _STACK_NAMES and not (
                name.startswith("requirements-") and name.endswith(".txt")
            ):
                continue
            path = base / name
            if path.is_symlink():
                continue
            try:
                path.relative_to(root)
            except ValueError as exc:
                raise DdeError(
                    "POLICY_DENIED", "workspace stack path escaped its root"
                ) from exc
            found.append(path)
            if len(found) > _MAX_FILES:
                raise DdeError(
                    "CONTEXT_INCOMPLETE",
                    "workspace stack observation exceeded the bounded "
                    "manifest-file limit",
                    details={"max_files": _MAX_FILES},
                )
    return sorted(found, key=lambda item: item.relative_to(root).as_posix())


def _exact_version(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return (
        stripped[1:]
        if stripped.startswith("v") and _EXACT_SEMVER.fullmatch(stripped)
        else (stripped if _EXACT_SEMVER.fullmatch(stripped) else None)
    )


def _package_json_versions(
    payload: bytes,
) -> tuple[dict[str, str], str | None, dict[str, object]]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}, None, {}
    if not isinstance(value, dict):
        return {}, None, {}
    versions: dict[str, str] = {}
    for bucket in (
        "dependencies",
        "devDependencies",
        "peerDependencies",
        "optionalDependencies",
    ):
        entries = value.get(bucket)
        if not isinstance(entries, dict):
            continue
        for name, raw in entries.items():
            if isinstance(name, str) and (exact := _exact_version(raw)) is not None:
                versions[name] = exact
    manager = value.get("packageManager")
    package_manager = (
        manager.split("@", 1)[0]
        if isinstance(manager, str) and "@" in manager
        else None
    )
    raw_engines = value.get("engines")
    engines: dict[str, object] = {}
    if isinstance(raw_engines, dict):
        engines = {str(key): item for key, item in raw_engines.items()}
    return versions, package_manager, engines


def _package_lock_versions(payload: bytes) -> dict[str, str]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(value, dict):
        return {}
    versions: dict[str, str] = {}
    packages = value.get("packages")
    if isinstance(packages, dict):
        for path, metadata in packages.items():
            if (
                not isinstance(path, str)
                or not path.startswith("node_modules/")
                or not isinstance(metadata, dict)
            ):
                continue
            name = path.removeprefix("node_modules/")
            raw = metadata.get("version")
            if (exact := _exact_version(raw)) is not None:
                versions[name] = exact
    return versions


def _pyproject_versions(payload: bytes) -> tuple[dict[str, str], dict[str, object]]:
    try:
        value = tomllib.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        return {}, {}
    project = value.get("project")
    if not isinstance(project, dict):
        return {}, {}
    versions: dict[str, str] = {}
    dependencies = project.get("dependencies")
    if isinstance(dependencies, list):
        for item in dependencies:
            if (
                isinstance(item, str)
                and (match := _PEP508_EXACT.match(item)) is not None
            ):
                versions[match.group(1)] = match.group(2)
    runtime: dict[str, object] = {}
    if isinstance(project.get("requires-python"), str):
        runtime["requires_python"] = project["requires-python"]
    return versions, runtime


def _requirements_versions(payload: bytes) -> dict[str, str]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return {}
    versions: dict[str, str] = {}
    for line in text.splitlines():
        if match := _PEP508_EXACT.match(line):
            versions[match.group(1)] = match.group(2)
    return versions


def observe_workspace_stack(workspace: Workspace) -> StackObservation:
    """Observe a DDE-owned Workspace without trusting caller/model-declared facts."""
    if workspace.status not in {"READY", "IN_USE"} or workspace.workspace_path is None:
        raise DdeError(
            "CONTEXT_INCOMPLETE",
            "VEKL stack observation requires a READY/IN_USE workspace with a path",
            details={
                "workspace_id": str(workspace.workspace_id),
                "status": workspace.status,
            },
        )
    root = Path(workspace.workspace_path).resolve()
    if not root.is_dir():
        raise DdeError(
            "CONTEXT_INCOMPLETE",
            "VEKL workspace path is unavailable",
            details={"workspace_id": str(workspace.workspace_id)},
        )
    versions: dict[str, str] = {}
    package_managers: set[str] = set()
    languages: set[str] = set()
    runtimes: dict[str, object] = {}
    lockfiles: list[str] = []
    evidence_refs: list[str] = []
    manifest_hashes: dict[str, str] = {}
    for path in _safe_stack_files(root):
        relative = path.relative_to(root).as_posix()
        payload = path.read_bytes()
        if len(payload) > _MAX_FILE_BYTES:
            raise DdeError(
                "CONTEXT_INCOMPLETE",
                "workspace stack manifest exceeds the bounded read size",
                details={"path": relative, "max_bytes": _MAX_FILE_BYTES},
            )
        digest = _hash_bytes(payload)
        manifest_hashes[relative] = digest
        evidence_refs.append(
            f"workspace:{workspace.workspace_id}:{relative}#sha256:{digest}"
        )
        name = path.name
        if name == "package.json":
            observed, manager, engines = _package_json_versions(payload)
            versions.update(observed)
            if manager:
                package_managers.add(manager)
            runtimes.update(
                {f"node_engine:{key}": value for key, value in engines.items()}
            )
            languages.add("javascript/typescript")
        elif name == "package-lock.json":
            versions.update(_package_lock_versions(payload))
            package_managers.add("npm")
            lockfiles.append(relative)
            languages.add("javascript/typescript")
        elif name.startswith("pnpm-lock"):
            package_managers.add("pnpm")
            lockfiles.append(relative)
            languages.add("javascript/typescript")
        elif name == "yarn.lock":
            package_managers.add("yarn")
            lockfiles.append(relative)
            languages.add("javascript/typescript")
        elif name in {"bun.lock", "bun.lockb"}:
            package_managers.add("bun")
            lockfiles.append(relative)
            languages.add("javascript/typescript")
        elif name == "pyproject.toml":
            observed, runtime = _pyproject_versions(payload)
            versions.update(observed)
            runtimes.update(runtime)
            languages.add("python")
        elif name.startswith("requirements") and name.endswith(".txt"):
            versions.update(_requirements_versions(payload))
            package_managers.add("pip")
            languages.add("python")
        elif name == "uv.lock":
            package_managers.add("uv")
            lockfiles.append(relative)
            languages.add("python")
        elif name == "poetry.lock":
            package_managers.add("poetry")
            lockfiles.append(relative)
            languages.add("python")
        elif name == "Pipfile.lock":
            package_managers.add("pipenv")
            lockfiles.append(relative)
            languages.add("python")
        elif name == "Cargo.toml":
            package_managers.add("cargo")
            languages.add("rust")
        elif name == "Cargo.lock":
            package_managers.add("cargo")
            lockfiles.append(relative)
            languages.add("rust")
        elif name == "go.mod":
            package_managers.add("go")
            languages.add("go")
        elif name == "go.sum":
            package_managers.add("go")
            lockfiles.append(relative)
            languages.add("go")
        elif name == "pubspec.yaml":
            package_managers.add("pub")
            languages.add("dart")
        elif name == "pubspec.lock":
            package_managers.add("pub")
            lockfiles.append(relative)
            languages.add("dart")
        elif name in {"gradle.lockfile", "pom.xml"}:
            package_managers.add("gradle" if name == "gradle.lockfile" else "maven")
            if name == "gradle.lockfile":
                lockfiles.append(relative)
            languages.add("java/kotlin")
        elif name in {".python-version", ".nvmrc", ".node-version"}:
            try:
                runtimes[name] = payload.decode("utf-8").strip()
            except UnicodeDecodeError:
                pass
    facts: dict[str, object] = {
        "workspace_id": str(workspace.workspace_id),
        "workspace_revision": workspace.current_revision,
        "base_revision": workspace.base_revision,
        "versions": dict(sorted(versions.items())),
        "package_managers": sorted(package_managers),
        "languages": sorted(languages),
        "lockfiles": sorted(lockfiles),
        "runtimes": dict(sorted(runtimes.items())),
        "manifest_hashes": manifest_hashes,
    }
    if len(package_managers) == 1:
        facts["package_manager"] = next(iter(package_managers))
    revision = workspace.current_revision or workspace.base_revision or "UNRESOLVED"
    evidence_refs.append(f"workspace:{workspace.workspace_id}:revision:{revision}")
    return StackObservation(facts=facts, evidence_refs=tuple(sorted(evidence_refs)))
