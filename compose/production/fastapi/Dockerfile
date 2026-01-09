FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS python-build-stage

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_CACHE_DIR=/root/.cache/uv UV_FROZEN=1  UV_REQUIRE_HASHES=1 UV_VERIFY_HASHES=1
ARG APP_HOME=/app
WORKDIR ${APP_HOME}

# Copy Python requirements and install dependencies first
COPY . ${APP_HOME}

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-group dev --group prod --no-install-project --no-editable

FROM docker.io/python:3.14-slim-bookworm AS python-run-stage

ARG APP_HOME=/app
WORKDIR ${APP_HOME}

# Install apt packages
RUN apt-get update && apt-get install --no-install-recommends -y curl

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY --from=python-build-stage --chown=appuser:appgroup ${APP_HOME} ${APP_HOME}

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

USER appuser

CMD ["fastapi", "run", "app/main.py", "--port", "80"]
