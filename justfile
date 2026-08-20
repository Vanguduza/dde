set dotenv-load := false

export UV_PYTHON := "3.12"

dev:
    uv run uvicorn interfaces.api:app --host 0.0.0.0 --port 8000 --reload

test:
    uv run pytest tests/unit tests/contract tests/recovery --cov --cov-report=term-missing

contract-test:
    uv run python -m scripts.generate_contracts --check
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

check: lint typecheck test contract-test

studio-check:
    npm --prefix interfaces/dde-studio ci
    npm --prefix interfaces/dde-studio run check
    npm --prefix interfaces/dde-studio/desktop ci
    npm --prefix interfaces/dde-studio/desktop run check

fmt:
    uv run ruff check --fix .
    uv run ruff format .

contracts:
    uv run python -m scripts.generate_contracts
