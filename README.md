# Tom's Fuel Finder

A learning project: a FastAPI service that wraps the UK Government
[Fuel Finder API](https://www.gov.uk/guidance/access-the-latest-fuel-prices-and-forecourt-data-via-api-or-email).
Given a postcode, fuel type and sort order, it fetches fuel prices from the
government service, then filters and sorts them.

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) for dependency management

## Setup

```bash
# Install all dependencies (runtime + dev) into the project venv
uv sync

# Install the git pre-commit hooks (one-time)
uv run pre-commit install
```

All commands below use `uv run`, which executes inside the project's
environment — no manual venv activation needed.

## Common commands

| Task | Command                              |
|------|--------------------------------------|
| Run the API (with auto-reload) | `uv run fastapi dev src/app/main.py` |
| Run the tests | `uv run pytest`                      |
| Format the code | `uv run black .`                     |
| Lint (and autofix) | `uv run ruff check --fix .`          |
| Type check | `uv run mypy .`                      |
| Run all pre-commit hooks manually | `uv run pre-commit run --all-files`  |

Once the API is running, the interactive docs are at:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Raw OpenAPI: <http://localhost:8000/openapi.json>

## Tooling

- **black** — code formatter (owns layout/line length).
- **ruff** — linter and import sorter (formatting is left to black).
- **mypy** — static type checker (strict mode).
- **pytest** / **pytest-asyncio** — test runner with async support.
- **respx** — mocks `httpx` calls so tests don't hit the real gov API.
- **pre-commit** — runs black, ruff, mypy and file-hygiene checks on every commit.

Tool settings live in `pyproject.toml`; hook config lives in
`.pre-commit-config.yaml`.

## Configuration

Runtime settings (gov API credentials, base URLs) are read from environment
variables via `pydantic-settings`. For local development, place them in a
`.env` file (which is git-ignored):

```
# .env
GOV_CLIENT_ID=...
GOV_CLIENT_SECRET=...
GOV_BASE_URL=https://...
```
