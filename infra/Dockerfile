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

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

EXPOSE 8000
