# Preflight API.
#
# No ffmpeg here, deliberately. The API never opens a media file — it issues
# signed URLs, records evidence, and asks the worker to measure what was
# uploaded. A service that cannot read a master cannot leak one, and keeping
# the media toolchain out also keeps this image small and its cold starts short.

FROM python:3.12-slim

RUN useradd --create-home --uid 10001 preflight

WORKDIR /app

COPY pyproject.toml ./
COPY packages/contracts/ ./packages/contracts/
# The agent is how a destination gets researched at runtime: Parallel finds
# and reads the pages, Gemini structures only what passed the trust check.
COPY apps/agent/ ./apps/agent/
COPY apps/api/ ./apps/api/

RUN pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.32" \
    "pydantic>=2.9" \
    "pydantic-settings>=2.6" \
    "sqlalchemy>=2.0" \
    "psycopg[binary]>=3.2" \
    "alembic>=1.14" \
    "pillow>=11.0" \
    "google-cloud-storage>=2.18" \
    "google-cloud-tasks>=2.16" \
    "firebase-admin>=6.5" \
    "httpx>=0.28" \
    "google-genai>=1.0"

ENV PYTHONPATH=/app/packages/contracts:/app/apps/agent:/app/apps/api \
    PYTHONUNBUFFERED=1

USER preflight

EXPOSE 8080

CMD ["sh", "-c", "uvicorn preflight_api.main:app --host 0.0.0.0 --port ${PORT:-8080} --timeout-graceful-shutdown 30"]
