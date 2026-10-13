# syntax=docker/dockerfile:1

# Pin uv exactly so dependency resolution/build tooling is repeatable.
FROM ghcr.io/astral-sh/uv:0.13.0 AS uv

FROM python:3.12-slim AS dependency-builder
COPY --from=uv /uv /uvx /bin/
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# A separate virtualenv includes development dependencies only in the test image.
FROM dependency-builder AS test-dependency-builder
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --group dev --no-install-project

FROM python:3.12-slim AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN groupadd --system app \
    && useradd --system --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=dependency-builder /opt/venv /opt/venv
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
COPY seeds ./seeds
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"]
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

# Development tool image for changing/checking uv.lock; it is not deployed.
FROM python:3.12-slim AS uv-tools
COPY --from=uv /uv /uvx /bin/
ENV UV_CACHE_DIR=/tmp/uv-cache \
    UV_PROJECT_ENVIRONMENT=/tmp/appointments-venv
WORKDIR /app
ENTRYPOINT ["uv"]

# Test image: uv is used only at build time; the test runtime contains no uv binary.
FROM python:3.12-slim AS test
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=test-dependency-builder /opt/venv /opt/venv
COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
COPY seeds ./seeds
COPY tests ./tests
CMD ["pytest"]
