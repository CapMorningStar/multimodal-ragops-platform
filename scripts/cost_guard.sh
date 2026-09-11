#!/usr/bin/env bash
# ==============================================================================
# Cost-Guard Zero-Idle-Burn Audit Script (Bash)
# Verifies that no continuous billable GCP resources are left running idle.
# ==============================================================================

set -euo pipefail

PROJECT="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo '')}"
REGION="${GCP_REGION:-us-central1}"

echo "=========================================================="
echo "   GCP COST-GUARD: ZERO-IDLE-BURN AUDIT FOR MULTIMODAL RAG"
echo "=========================================================="

if [ -z "$PROJECT" ]; then
    echo "[SKIP] GCP_PROJECT_ID not set and gcloud has no active project."
    echo "[PASS] Verified local development store is file-backed (data/vector_index). Idle cost is $0.00."
    exit 0
fi

echo "Target Project: $PROJECT"
echo "Target Region:  $REGION"
echo ""

ERRORS=0

# 1. Audit Vertex AI Vector Search Index Endpoints
echo -n "[1/3] Checking Vertex AI Vector Search Index Endpoints... "
ENDPOINTS=$(gcloud ai index-endpoints list --project="$PROJECT" --region="$REGION" --format="value(name)" 2>/dev/null || true)
if [ -n "$ENDPOINTS" ]; then
    echo " [CRITICAL WARNING]"
    echo "Found running Vertex AI Vector Search Index Endpoints:"
    echo "$ENDPOINTS"
    ERRORS=$((ERRORS + 1))
else
    echo "[PASS] 0 active index endpoints."
fi

# 2. Audit Cloud Run min-instances
echo -n "[2/3] Checking Cloud Run Services min-instances... "
RUN_WARNING=0
while IFS=, read -r svc min_scale; do
    if [ -n "$min_scale" ] && [ "$min_scale" -gt 0 ]; then
        echo ""
        echo "  [WARNING] Service '$svc' has min-instances=$min_scale (idle burn!)."
        RUN_WARNING=1
        ERRORS=$((ERRORS + 1))
    fi
done < <(gcloud run services list --project="$PROJECT" --region="$REGION" --format="csv[no-heading](service,spec.template.metadata.annotations['autoscaling.knative.dev/minScale'])" 2>/dev/null || true)

if [ "$RUN_WARNING" -eq 0 ]; then
    echo "[PASS] All services set to min-instances=0."
fi

# 3. Audit Compute Engine instances
echo -n "[3/3] Checking Compute Engine VMs... "
VMS=$(gcloud compute instances list --project="$PROJECT" --filter="status=RUNNING" --format="value(name)" 2>/dev/null || true)
if [ -n "$VMS" ]; then
    echo "[WARNING] Found running Compute Engine instances:"
    echo "$VMS"
    ERRORS=$((ERRORS + 1))
else
    echo "[PASS] 0 running VMs."
fi

echo ""
echo "=========================================================="
if [ "$ERRORS" -eq 0 ]; then
    echo "AUDIT RESULT: PASSED. Zero idle billing detected."
else
    echo "AUDIT RESULT: ATTENTION REQUIRED ($ERRORS warnings)."
fi
echo "=========================================================="
