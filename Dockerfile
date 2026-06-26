# syntax=docker/dockerfile:1

# ── build stage: install dependencies + project into /app/.venv ──────────
FROM python:3.14-slim AS build

# bring in the uv binary from the distroless image (pinned, not :latest)
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

# copy packages across the layer boundary (not hardlink), and precompile to
# .pyc so the runtime container starts a little faster
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# 1) dependencies only — this layer is cached unless the lockfile changes
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# 2) now the source, then install the project itself on top
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ── runtime stage: slim image with only the venv + source ────────────────
FROM python:3.14-slim AS runtime

# run as a non-root user
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

# the venv references /usr/local/bin/python — same base image, so it resolves.
# the editable install points at /app/src, so the source must live there too.
COPY --from=build --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=build --chown=appuser:appuser /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER appuser
EXPOSE 8000

# production server (NOT `fastapi dev`); 0.0.0.0 so the container is reachable
CMD ["fastapi", "run", "src/app/main.py", "--host", "0.0.0.0", "--port", "8000"]
