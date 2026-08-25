#!/usr/bin/env bash
# Deploy Preflight to Google Cloud.
#
# Idempotent: safe to re-run. Each step either creates what is missing or
# updates what exists, so a partial failure is fixed by running it again
# rather than by unpicking state by hand.
set -euo pipefail

PROJECT="${GOOGLE_CLOUD_PROJECT:-preflight-505021}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
TAG="${TAG:-v1}"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT}/preflight"
SA="preflight-api@${PROJECT}.iam.gserviceaccount.com"
BUCKET="${PROJECT}-media"

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

say "building images"
gcloud builds submit --config=infra/cloudbuild-api.yaml \
  --substitutions=_TAG="${TAG}" --project="${PROJECT}" .
gcloud builds submit --config=infra/cloudbuild-worker.yaml \
  --substitutions=_TAG="${TAG}" --project="${PROJECT}" .

say "deploying worker"
# Private: only Cloud Tasks may reach it, authenticated as the runtime service
# account. The worker holds other people's unreleased films and has no reason
# to be addressable from the internet.
gcloud run deploy preflight-worker \
  --image="${REGISTRY}/worker:${TAG}" \
  --region="${REGION}" --project="${PROJECT}" \
  --service-account="${SA}" \
  --no-allow-unauthenticated \
  --memory=4Gi --cpu=2 \
  --timeout=900 \
  --concurrency=1 \
  --max-instances=5 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT},GCS_BUCKET=${BUCKET},GOOGLE_CLOUD_LOCATION=${REGION}"

WORKER_URL=$(gcloud run services describe preflight-worker \
  --region="${REGION}" --project="${PROJECT}" --format='value(status.url)')
say "worker at ${WORKER_URL}"

say "deploying api"
gcloud run deploy preflight-api \
  --image="${REGISTRY}/api:${TAG}" \
  --region="${REGION}" --project="${PROJECT}" \
  --service-account="${SA}" \
  --allow-unauthenticated \
  --memory=1Gi --cpu=1 \
  --timeout=120 \
  --max-instances=10 \
  --add-cloudsql-instances="${PROJECT}:${REGION}:preflight-db" \
  --set-secrets="DATABASE_URL=database-url:latest,PARALLEL_API_KEY=parallel-api-key:latest" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT},GCS_BUCKET=${BUCKET},GOOGLE_CLOUD_LOCATION=${REGION},WORKER_BASE_URL=${WORKER_URL},ENVIRONMENT=production"

API_URL=$(gcloud run services describe preflight-api \
  --region="${REGION}" --project="${PROJECT}" --format='value(status.url)')

say "verifying"
# A deploy that returns a URL is not a deploy that works. Readiness crosses the
# real database boundary, so this fails loudly if migrations have not been run
# or the connector is misconfigured.
code=$(curl -s -o /dev/null -w '%{http_code}' "${API_URL}/health/ready")
if [ "${code}" != "200" ]; then
  echo "readiness returned ${code}" >&2
  curl -s "${API_URL}/health/ready" >&2
  exit 1
fi

say "deployed"
echo "  api:    ${API_URL}"
echo "  worker: ${WORKER_URL}"
