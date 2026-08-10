# Isolated media worker.
#
# This container handles other people's unreleased films. It runs as a
# non-root user, holds no long-lived credentials of its own (Cloud Run supplies
# a runtime identity), and keeps every working file under a temporary directory
# that is removed when a job ends — including when it ends badly.

FROM python:3.12-slim

# ffmpeg is the reason this is a separate image from the API. Everything
# Preflight measures and every repair it performs depends on it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 preflight

WORKDIR /app

COPY pyproject.toml ./
COPY packages/contracts/ ./packages/contracts/
COPY apps/worker/ ./apps/worker/

RUN pip install --no-cache-dir \
    "pillow>=11.0" \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.32" \
    "sqlalchemy>=2.0" \
    "psycopg[binary]>=3.2" \
    "pydantic-settings>=2.6" \
    "google-cloud-storage>=2.18"

ENV PYTHONPATH=/app/packages/contracts:/app/apps/worker \
    PYTHONUNBUFFERED=1 \
    TMPDIR=/tmp/preflight

RUN mkdir -p /tmp/preflight && chown preflight:preflight /tmp/preflight

USER preflight

EXPOSE 8080

# Cloud Run sends SIGTERM before stopping an instance; uvicorn drains in-flight
# work rather than abandoning a half-written package.
CMD ["uvicorn", "preflight_worker.server:app", "--host", "0.0.0.0", "--port", "8080", "--timeout-graceful-shutdown", "60"]
