"""Emit Pydantic contracts, SQL, OpenAPI and catalog docs from schemas/."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
OBJECTS = SCHEMAS / "objects"
EVENTS = SCHEMAS / "events"
API = SCHEMAS / "api"
SQL_DIR = SCHEMAS / "sql"
CONTRACTS = ROOT / "engine" / "contracts"
GENERATED_DOCS = ROOT / "docs" / "blueprint" / "generated"

HEADER = "# GENERATED from schemas/. Do not edit.\n"

PYTHON_FIELDS = {"class": "class_", "def": "def_", "from": "from_"}
SQL_QUOTED = {"class", "type", "user", "timestamp", "order"}
MAX_LINE = 88


def _py_field(name: str) -> str:
    return PYTHON_FIELDS.get(name, name)


def _sql_ident(name: str) -> str:
    if name in SQL_QUOTED:
        return f'"{name}"'
    return name


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return data


def _schema_files() -> list[Path]:
    files = (
        sorted(OBJECTS.glob("*.json"))
        + sorted(EVENTS.glob("*.json"))
        + sorted(API.glob("*.json"))
    )
    return [path for path in files if path.name != "openapi.yaml"]


def _class_name(schema: dict[str, Any], path: Path) -> str:
    title = schema.get("title")
    if isinstance(title, str) and title:
        return title
    return "".join(part.capitalize() for part in path.stem.split("_"))


def _py_type(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        ref = schema["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
            raise ValueError(f"unsupported $ref: {ref}")
        return ref.rsplit("/", 1)[-1]
    if "anyOf" in schema:
        return " | ".join(_py_type(part) for part in schema["anyOf"])
    if "const" in schema and schema.get("type") == "string":
        return f"Literal[{json.dumps(schema['const'])}]"
    if schema.get("enum") and schema.get("type") == "string":
        values = ", ".join(json.dumps(item) for item in schema["enum"])
        return f"Literal[{values}]"
    json_type = schema.get("type")
    if json_type == "string":
        fmt = schema.get("format")
        if fmt == "uuid":
            return "UUID"
        if fmt == "date-time":
            return "datetime"
        return "str"
    if json_type == "integer":
        return "int"
    if json_type == "number":
        return "float"
    if json_type == "boolean":
        return "bool"
    if json_type == "null":
        return "None"
    if json_type == "array":
        items = schema.get("items")
        if not isinstance(items, dict):
            raise ValueError("array schema requires items")
        return f"list[{_py_type(items)}]"
    if json_type == "object":
        additional = schema.get("additionalProperties")
        if additional is True:
            return "dict[str, object]"
        if isinstance(additional, dict):
            return f"dict[str, {_py_type(additional)}]"
        return "dict[str, object]"
    raise ValueError(f"unsupported schema type: {schema}")


def _needs(schema: dict[str, Any], token: str) -> bool:
    blob = json.dumps(schema)
    return token in blob


def _docstring_block(docstring: str) -> list[str]:
    single = f'    """{docstring}"""'
    if len(single) <= MAX_LINE:
        return [single]
    wrapped = textwrap.wrap(docstring, width=MAX_LINE - 4)
    return ['    """', *[f"    {line}" for line in wrapped], '    """']


def _optional_annotation(annotation: str) -> str:
    if annotation.endswith(" | None") or annotation == "None":
        return annotation
    return f"{annotation} | None"


def _split_literal_items(inner: str) -> list[str]:
    return [item.strip() for item in inner.split(",") if item.strip()]


def _field_lines(py_name: str, annotation: str, assignment: str) -> list[str]:
    line = f"    {py_name}: {annotation}{assignment}"
    if len(line) <= MAX_LINE:
        return [line]
    if annotation.startswith("Literal[") and annotation.endswith("]"):
        items = _split_literal_items(annotation[len("Literal[") : -1])
        lines = [f"    {py_name}: Literal["]
        lines.extend(f"        {item}," for item in items)
        lines.append(f"    ]{assignment}")
        return lines
    return [line]


def _model_source(
    name: str, schema: dict[str, Any], docstring: str
) -> tuple[str, bool]:
    required = set(schema.get("required") or [])
    properties = schema.get("properties") or {}
    lines = [
        f"class {name}(BaseModel):",
        *_docstring_block(docstring),
        "",
        '    model_config = ConfigDict(extra="forbid")',
        "",
    ]
    if not properties:
        lines.append("    pass")
        return "\n".join(lines), False
    uses_field_alias = False
    for field, field_schema in properties.items():
        annotation = _py_type(field_schema)
        py_name = _py_field(field)
        if py_name != field:
            uses_field_alias = True
            if field in required:
                lines.extend(
                    _field_lines(py_name, annotation, f' = Field(alias="{field}")')
                )
            else:
                optional = _optional_annotation(annotation)
                lines.extend(
                    _field_lines(
                        py_name,
                        optional,
                        f' = Field(default=None, alias="{field}")',
                    )
                )
        elif field in required:
            lines.extend(_field_lines(field, annotation, ""))
        else:
            optional = _optional_annotation(annotation)
            lines.extend(_field_lines(field, optional, " = None"))
    if uses_field_alias:
        lines[lines.index('    model_config = ConfigDict(extra="forbid")')] = (
            '    model_config = ConfigDict(extra="forbid", populate_by_name=True)'
        )
    return "\n".join(lines), uses_field_alias


def _format_python(source: str) -> str:
    formatted = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--stdin-filename",
            "engine/contracts/_generated.py",
            "-",
        ],
        input=source,
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    ).stdout
    linted = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--fix",
            "--stdin-filename",
            "engine/contracts/_generated.py",
            "-",
        ],
        input=formatted,
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    if linted.returncode not in (0, 1):
        raise RuntimeError(linted.stderr or "ruff check --fix failed")
    return linted.stdout if linted.stdout else formatted


def _file_source(path: Path, schema: dict[str, Any]) -> str:
    class_name = _class_name(schema, path)
    docstring = schema.get("description") or f"{class_name} wire contract."
    models: list[str] = []
    uses_field = False
    defs = schema.get("$defs") or {}
    for def_name, def_schema in defs.items():
        source, aliased = _model_source(
            def_name, def_schema, f"{def_name} nested contract."
        )
        models.append(source)
        uses_field = uses_field or aliased
    source, aliased = _model_source(class_name, schema, docstring)
    models.append(source)
    uses_field = uses_field or aliased
    extra: list[str] = []
    if _needs(schema, "date-time"):
        extra.append("from datetime import datetime")
    if _needs(schema, '"format": "uuid"') or _needs(schema, '"format":"uuid"'):
        extra.append("from uuid import UUID")
    if any("Literal[" in model for model in models):
        extra.append("from typing import Literal")
    extra.sort()
    pydantic_names = (
        "BaseModel, ConfigDict, Field" if uses_field else "BaseModel, ConfigDict"
    )
    imports = ["from __future__ import annotations", ""]
    if extra:
        imports.extend(extra)
        imports.append("")
    imports.append(f"from pydantic import {pydantic_names}")
    return _format_python(
        HEADER + "\n" + "\n".join(imports) + "\n\n\n" + "\n\n\n".join(models) + "\n"
    )


def _sql_type(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return "jsonb"
    if schema.get("type") == "array" or schema.get("type") == "object":
        return "jsonb"
    if schema.get("type") == "string":
        fmt = schema.get("format")
        if fmt == "uuid":
            return "uuid"
        if fmt == "date-time":
            return "timestamptz"
        return "text"
    if schema.get("type") == "integer":
        return "integer"
    if schema.get("type") == "number":
        return "numeric"
    if schema.get("type") == "boolean":
        return "boolean"
    if "anyOf" in schema:
        non_null = [part for part in schema["anyOf"] if part.get("type") != "null"]
        if len(non_null) == 1:
            return _sql_type(non_null[0])
    raise ValueError(f"unsupported SQL mapping for {schema}")


def _render_column(name: str, schema: dict[str, Any], required: set[str]) -> str:
    sql_type = _sql_type(schema)
    ident = _sql_ident(name)
    null_sql = " NOT NULL" if name in required else ""
    default = ""
    if sql_type == "jsonb" and name in required:
        if schema.get("type") == "array":
            default = " DEFAULT '[]'::jsonb"
        elif schema.get("type") == "object":
            default = " DEFAULT '{}'::jsonb"
    if name == "lock_version" and name in required:
        default = " DEFAULT 1"
    return f"    {ident} {sql_type}{null_sql}{default}"


def _create_table_sql(schema: dict[str, Any]) -> str:
    storage = schema["x-dde-storage"]
    table = storage["table"]
    required = set(schema.get("required") or [])
    properties: dict[str, Any] = schema["properties"]
    columns = [
        _render_column(name, field, required) for name, field in properties.items()
    ]
    pk_cols = ", ".join(_sql_ident(col) for col in storage["pk"])
    columns.append(f"    PRIMARY KEY ({pk_cols})")
    for unique in storage.get("uniques") or []:
        unique_cols = ", ".join(_sql_ident(col) for col in unique)
        columns.append(f"    UNIQUE ({unique_cols})")
    body = ",\n".join(columns)
    partition = storage.get("partition_range")
    if partition:
        return (
            f"CREATE TABLE {table} (\n{body}\n) PARTITION BY RANGE ({partition});\n"
            f"CREATE TABLE {table}_default PARTITION OF {table} DEFAULT;"
        )
    return f"CREATE TABLE {table} (\n{body}\n);"


def _fk_sql(schema: dict[str, Any]) -> list[str]:
    storage = schema["x-dde-storage"]
    table = storage["table"]
    statements: list[str] = []
    for fk in storage.get("foreign_keys") or []:
        cols = ", ".join(_sql_ident(col) for col in fk["columns"])
        ref_table = fk["ref_table"]
        ref_cols = ", ".join(_sql_ident(col) for col in fk["ref_columns"])
        name = fk.get("name") or f"{table}_{fk['columns'][0]}_fkey"
        statements.append(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} "
            f"FOREIGN KEY ({cols}) REFERENCES {ref_table} ({ref_cols});"
        )
    return statements


def _rls_sql(schema: dict[str, Any]) -> list[str]:
    storage = schema["x-dde-storage"]
    if not storage.get("tenant_scoped"):
        return []
    table = storage["table"]
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;",
        (
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            "USING (tenant_id = CAST(current_setting('dde.tenant_id', true) AS uuid));"
        ),
    ]


def _sql_bundle(
    object_schemas: list[tuple[Path, dict[str, Any]]],
) -> tuple[str, str]:
    stored = [
        (path, schema) for path, schema in object_schemas if "x-dde-storage" in schema
    ]
    stored.sort(key=lambda item: int(item[1]["x-dde-storage"]["order"]))
    up: list[str] = ["-- GENERATED from schemas/objects. Do not edit.", ""]
    for _, schema in stored:
        up.append(_create_table_sql(schema))
        up.append("")
    for _, schema in stored:
        fks = _fk_sql(schema)
        if fks:
            up.extend(fks)
            up.append("")
    for _, schema in stored:
        rls = _rls_sql(schema)
        if rls:
            up.extend(rls)
            up.append("")
    down_tables: list[str] = []
    for _, schema in reversed(stored):
        table = schema["x-dde-storage"]["table"]
        down_tables.append(f"DROP TABLE IF EXISTS {table} CASCADE;")
    down = (
        "-- GENERATED from schemas/objects. Do not edit.\n\n"
        + "\n".join(down_tables)
        + "\n"
    )
    return "\n".join(up).rstrip() + "\n", down


def _openapi(api_schemas: list[tuple[Path, dict[str, Any]]]) -> str:
    by_stem = {path.stem: schema for path, schema in api_schemas}
    healthz = by_stem["healthz"]
    readyz = by_stem["readyz"]
    error = by_stem["error"]
    return (
        "openapi: 3.1.0\n"
        "info:\n"
        "  title: DDE Core\n"
        "  version: 0.1.0\n"
        "paths:\n"
        "  /healthz:\n"
        "    get:\n"
        "      operationId: healthz\n"
        "      responses:\n"
        "        '200':\n"
        "          description: Process is alive.\n"
        "          content:\n"
        "            application/json:\n"
        "              schema:\n"
        "                $ref: './healthz.json'\n"
        "  /readyz:\n"
        "    get:\n"
        "      operationId: readyz\n"
        "      responses:\n"
        "        '200':\n"
        "          description: Safe to accept work.\n"
        "          content:\n"
        "            application/json:\n"
        "              schema:\n"
        "                $ref: './readyz.json'\n"
        "        '503':\n"
        "          description: Database, Redis or migrations are not ready.\n"
        "          content:\n"
        "            application/json:\n"
        "              schema:\n"
        "                $ref: './readyz.json'\n"
        "components:\n"
        "  schemas:\n"
        f"    Healthz: {{ $ref: './healthz.json' }}\n"
        f"    Readyz: {{ $ref: './readyz.json' }}\n"
        f"    Error: {{ $ref: './error.json' }}\n"
        "# source-titles: "
        f"{healthz.get('title')}, {readyz.get('title')}, {error.get('title')}\n"
    )


def _docs(object_schemas: list[tuple[Path, dict[str, Any]]]) -> str:
    lines = [
        "# Generated object catalog",
        "",
        "Generated from `schemas/objects`. Do not edit.",
        "",
    ]
    stored = [
        (path, schema) for path, schema in object_schemas if "x-dde-storage" in schema
    ]
    stored.sort(key=lambda item: int(item[1]["x-dde-storage"]["order"]))
    for path, schema in stored:
        storage = schema["x-dde-storage"]
        lines.append(f"## {schema.get('title', path.stem)}")
        lines.append("")
        lines.append(f"- table: `{storage['table']}`")
        lines.append(f"- primary key: {', '.join(storage['pk'])}")
        tenant_scoped = json.dumps(bool(storage.get("tenant_scoped", False)))
        project_scoped = json.dumps(bool(storage.get("project_scoped", False)))
        lock_version = json.dumps(bool(storage.get("lock_version", False)))
        lines.append(f"- tenant scoped: {tenant_scoped}")
        lines.append(f"- project scoped: {project_scoped}")
        lines.append(f"- lock_version: {lock_version}")
        lines.append("")
    return "\n".join(lines)


def _init_source(exports: list[tuple[str, str]]) -> str:
    lines = [HEADER, "from __future__ import annotations", ""]
    for module, name in exports:
        lines.append(f"from engine.contracts.{module} import {name}")
    lines.append("")
    lines.append("__all__ = [")
    for _, name in exports:
        lines.append(f'    "{name}",')
    lines.append("]")
    lines.append("")
    return _format_python("\n".join(lines))


def render() -> dict[Path, str]:
    files: dict[Path, str] = {}
    exports: list[tuple[str, str]] = []
    object_schemas: list[tuple[Path, dict[str, Any]]] = []
    api_schemas: list[tuple[Path, dict[str, Any]]] = []
    for path in _schema_files():
        schema = _load_json(path)
        declared = schema.get("$schema")
        if declared != "https://json-schema.org/draft/2020-12/schema":
            raise ValueError(f"{path} must declare JSON Schema 2020-12")
        source = _file_source(path, schema)
        dest = CONTRACTS / f"{path.stem}.py"
        files[dest] = source
        exports.append((path.stem, _class_name(schema, path)))
        if path.parent == OBJECTS:
            object_schemas.append((path, schema))
        if path.parent == API:
            api_schemas.append((path, schema))
    exports.sort(key=lambda item: item[0])
    files[CONTRACTS / "__init__.py"] = _init_source(exports)
    up_sql, down_sql = _sql_bundle(object_schemas)
    files[SQL_DIR / "0001_stage1.sql"] = up_sql
    files[SQL_DIR / "0001_stage1_down.sql"] = down_sql
    files[API / "openapi.yaml"] = _openapi(api_schemas)
    files[GENERATED_DOCS / "objects.md"] = _docs(object_schemas)
    return files


def write(files: dict[Path, str]) -> None:
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


def check(files: dict[Path, str]) -> int:
    failed = False
    for path, expected in files.items():
        if not path.exists():
            print(f"missing generated file: {path}", file=sys.stderr)
            failed = True
            continue
        actual = path.read_text(encoding="utf-8")
        if actual.replace("\r\n", "\n") != expected:
            print(f"generated drift: {path}", file=sys.stderr)
            failed = True
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    files = render()
    if args.check:
        return check(files)
    write(files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
