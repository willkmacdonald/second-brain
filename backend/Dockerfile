# syntax=docker/dockerfile:1

# ============ Build Stage ============
FROM python:3.12-slim-bookworm AS builder

# Copy uv binary from official image (pinned version for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app

# uv environment variables for Docker builds
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Install dependencies FIRST for better layer caching
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy source code and install the project itself
COPY src/ ./src/
RUN uv sync --frozen --no-dev --no-editable

# ============ Runtime Stage ============
FROM python:3.12-slim-bookworm AS runtime

# Security: non-root user
RUN groupadd -g 1001 app && \
    useradd -u 1001 -g app -m -d /app -s /bin/false app

WORKDIR /app

# Production environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy only the virtual environment and source from builder
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src

USER app

EXPOSE 8000

# Run with uvicorn (port 8000 in container; local dev uses 8003)
CMD ["uvicorn", "second_brain.main:app", "--host", "0.0.0.0", "--port", "8000"]
