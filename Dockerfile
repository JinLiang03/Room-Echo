# syntax=docker/dockerfile:1.7

FROM node:22.18.0-bookworm-slim AS web-build
WORKDIR /src
COPY apps/web/package.json apps/web/package-lock.json ./apps/web/
RUN npm ci --prefix apps/web
COPY apps/web/ ./apps/web/
RUN npm --prefix apps/web run build

# Use an official derived image tag. The versioned bookworm composite tag
# (0.10.10-python3.11-bookworm-slim) is not published in GHCR and fails on
# hosted builders such as Render; this stable Python 3.11/trixie image ships
# uv preinstalled and keeps the Python ABI explicit.
FROM ghcr.io/astral-sh/uv:python3.11-trixie-slim AS runtime
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    SERVE_WEB=1 \
    PUBLIC_REPLAY=1 \
    APP_MODE=replay \
    SCENARIO=demo_2min \
    DEMO_AUTOSTART=1 \
    DEMO_LOOP=1

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
COPY --from=web-build /src/apps/web/dist ./apps/web/dist
RUN uv sync --frozen --no-dev \
    && mkdir -p data/derived/stream data/raw \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000

# One process owns the singleton Replay session and WebSocket ring buffer.
CMD ["sh", "-c", "exec uvicorn wifi_api.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
