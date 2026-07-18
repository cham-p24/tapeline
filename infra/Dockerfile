FROM python:3.12-slim

# Build context is the project root (set by fly.toml [build] section).
# The actual app code lives in backend/, so install deps from backend/pyproject.toml
# then copy the backend dir, and run from there.

# System deps for psycopg + pandas + curl (healthcheck)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first — caches between code changes
WORKDIR /app/backend
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

# Copy the backend source
COPY backend/ ./

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend

# Run as an unprivileged user. Until now both the API and the worker ran as
# root, so any RCE-class bug (or a malicious transitive dependency) executed
# with full container privileges.
#
# The application code stays root-owned and is therefore READ-ONLY to the
# runtime user — deliberate, so a write-primitive can't rewrite the code that
# executes on the next boot. Only the two paths that are genuinely written at
# runtime are handed over:
#   - /app/backend/.cache   — finnhub_feed + fred_feed response caches, which
#                             resolve to <backend>/.cache via __file__
#   - $HOME/.cache          — historical_bars bar cache, default
#                             ~/.cache/tapeline/historical_bars/
# HOME is set explicitly rather than relying on Docker to derive it from
# /etc/passwd; without it those writes land in / and fail as non-root.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/backend/.cache \
    && chown appuser:appuser /app/backend/.cache

ENV HOME=/home/appuser
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

EXPOSE 8000
