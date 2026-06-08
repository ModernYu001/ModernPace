#!/usr/bin/env bash
# One-command Cloud Run deploy for Pace (the FastAPI web UI).
#
# Prereqs (run once on your machine):
#   gcloud auth login
#   gcloud config set project <YOUR_PROJECT_ID>
#   gcloud services enable run.googleapis.com cloudbuild.googleapis.com
#
# Usage:
#   ./deploy.sh                      # uses current gcloud project, region us-central1
#   PROJECT=my-proj REGION=asia-east1 ./deploy.sh
#
# It reads GOOGLE_API_KEY / PACE_API_KEYS / PACE_MODELS / PACE_LANG from .env and
# passes them to the service as runtime env vars (via a temp, git-ignored file).
set -euo pipefail

SERVICE="${SERVICE:-pace}"
REGION="${REGION:-us-central1}"
PROJECT="${PROJECT:-$(gcloud config get-value project 2>/dev/null)}"

if [[ -z "${PROJECT}" || "${PROJECT}" == "(unset)" ]]; then
  echo "✖ No GCP project. Run: gcloud config set project <YOUR_PROJECT_ID>" >&2
  exit 1
fi
if [[ ! -f .env ]]; then
  echo "✖ .env not found. Copy .env.example to .env and add your key first." >&2
  exit 1
fi

# Load .env so the values are available to this script (does not export to image).
set -a; source .env; set +a

# Build a temp env-vars file (YAML quoting keeps comma-separated lists intact).
ENV_FILE=".env.deploy.yaml"
{
  echo "GOOGLE_API_KEY: \"${GOOGLE_API_KEY:-}\""
  echo "PACE_API_KEYS: \"${PACE_API_KEYS:-${GOOGLE_API_KEY:-}}\""
  echo "PACE_MODELS: \"${PACE_MODELS:-gemini-2.5-flash}\""
  echo "PACE_LANG: \"${PACE_LANG:-zh}\""
} > "${ENV_FILE}"
trap 'rm -f "${ENV_FILE}"' EXIT   # never leave keys on disk

echo "▶ Deploying ${SERVICE} to Cloud Run  (project=${PROJECT}, region=${REGION})"
gcloud run deploy "${SERVICE}" \
  --source . \
  --project "${PROJECT}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --env-vars-file "${ENV_FILE}"

echo "✔ Done. URL above. Open it and walk the full loop for the demo."
