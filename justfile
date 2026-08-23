set dotenv-load := false

# Windows hosts have no `sh`; every recipe below is a single argv-style
# invocation, so powershell works as the shell there. CI/Linux keep sh.
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

export UV_PYTHON := "3.12"

dev:
    uv run uvicorn interfaces.api:app --host 0.0.0.0 --port 8000 --reload

test:
    uv run pytest tests/unit tests/contract tests/recovery --cov --cov-report=term-missing

# Pure unit tests only: no PostgreSQL, no Redis. Runs on any dev host
# (Windows included) without the devcontainer services.
test-unit:
    uv run pytest tests/unit -m "not integration"

contract-test:
    uv run python -m scripts.generate_contracts --check
    uv run python -m scripts.generate_design_tokens --check
    uv run pytest tests/contract

db-upgrade:
    uv run alembic upgrade head

db-revision message:
    uv run alembic revision --autogenerate -m "{{message}}"

lint:
    uv run ruff check .
    uv run ruff format --check .

typecheck:
    uv run mypy

check: lint typecheck test contract-test design-lints studio-check

design-lints:
    uv run python -m scripts.design_lints --baseline

studio-check:
    npm --prefix interfaces/dde-studio ci
    npm --prefix interfaces/dde-studio run check
    npm --prefix interfaces/dde-studio test
    npm --prefix interfaces/dde-studio/desktop ci
    npm --prefix interfaces/dde-studio/desktop run check

fmt:
    uv run ruff check --fix .
    uv run ruff format .

contracts:
    uv run python -m scripts.generate_contracts
