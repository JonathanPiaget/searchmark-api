FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ARG APP_HOME=/app

WORKDIR ${APP_HOME}

# we need to move the virtualenv outside of the $APP_HOME directory because it will be overriden by the docker compose mount
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_CACHE_DIR=/root/.cache/uv

COPY ./pyproject.toml ./uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --no-group prod --no-install-project --no-editable

ENV PATH="/${APP_HOME}/.venv/bin:$PATH"

CMD ["fastapi", "run", "app/main.py", "--port", "80"]
