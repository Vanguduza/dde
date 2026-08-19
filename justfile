set dotenv-load := false

export UV_PYTHON := "3.12"

dev:
    uv run uvicorn interfaces.api:app --host 0.0.0.0 --port 8000 --reload

test:
    uv run pytest tests/unit tests/contract --cov --cov-report=term-missing

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

fmt:
    uv run ruff check --fix .
    uv run ruff format .

contracts:
    uv run python -m scripts.generate_contracts
