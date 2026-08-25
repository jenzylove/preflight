# Preflight API.
#
# No ffmpeg here. The API never touches media — it issues signed URLs, records
# evidence and dispatches jobs. Keeping the media toolchain out of this image
# keeps its attack surface small and its cold starts short; the worker is a
# separate image for exactly that reason.

FROM python:3.12-slim

RUN useradd --create-home --uid 10001 preflight

WORKDIR /app

COPY pyproject.toml ./
COPY packages/contracts/ ./packages/contracts/
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
    "firebase-admin>=6.5"

ENV PYTHONPATH=/app/packages/contracts:/app/apps/api \
    PYTHONUNBUFFERED=1

USER preflight

EXPOSE 8080

CMD ["sh", "-c", "uvicorn preflight_api.main:app --host 0.0.0.0 --port ${PORT:-8080} --timeout-graceful-shutdown 30"]
