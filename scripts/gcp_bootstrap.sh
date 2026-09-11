#!/usr/bin/env bash
# ==============================================================================
# GCP API & Resource Bootstrap Script (Bash)
# Enables required APIs and sets up service identity for Multimodal RAG.
# ==============================================================================

set -euo pipefail

PROJECT="${1:-${GCP_PROJECT_ID:-}}"
REGION="${2:-${GCP_REGION:-us-central1}}"

if [ -z "$PROJECT" ]; then
    echo "Usage: ./gcp_bootstrap.sh <GCP_PROJECT_ID> [GCP_REGION]"
    exit 1
fi

echo "=========================================================="
echo "   BOOTSTRAPPING GCP ENVIRONMENT FOR MULTIMODAL RAG"
echo "=========================================================="
echo "Target Project: $PROJECT"
echo "Target Region:  $REGION"

gcloud config set project "$PROJECT"

APIS=(
    "documentai.googleapis.com"
    "aiplatform.googleapis.com"
    "run.googleapis.com"
    "storage.googleapis.com"
    "cloudbuild.googleapis.com"
    "artifactregistry.googleapis.com"
)

echo ""
echo "Enabling GCP APIs (this may take 1-2 minutes)..."
for api in "${APIS[@]}"; do
    echo -n " - Enabling $api... "
    gcloud services enable "$api" --project="$PROJECT"
    echo "[DONE]"
done

echo ""
echo "GCP APIs enabled successfully!"
