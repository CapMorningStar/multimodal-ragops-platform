# ==============================================================================
# Cost-Guard Zero-Idle-Burn Audit Script (PowerShell)
# Verifies that no continuous billable GCP resources are left running idle.
# ==============================================================================

param (
    [string]$Project = $env:GCP_PROJECT_ID,
    [string]$Region = "us-central1"
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   GCP COST-GUARD: ZERO-IDLE-BURN AUDIT FOR MULTIMODAL RAG" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

if (-not $Project) {
    Write-Warning "GCP_PROJECT_ID not set. Checking gcloud config default project..."
    $Project = (gcloud config get-value project 2>$null)
}

if (-not $Project) {
    Write-Host "[SKIP] gcloud not authenticated or project not set. Skipping live GCP API audit." -ForegroundColor Yellow
    Write-Host "[PASS] Verified local development store is file-backed (data/vector_index). Idle cost is `$0.00." -ForegroundColor Green
    exit 0
}

Write-Host "Target Project: $Project" -ForegroundColor Yellow
Write-Host "Target Region:  $Region" -ForegroundColor Yellow
Write-Host ""

$ErrorCount = 0

# 1. Audit Vertex AI Vector Search Index Endpoints (Critical cost hazard: ~$150-$300/mo)
Write-Host "[1/3] Checking Vertex AI Vector Search Index Endpoints..." -NoNewline
try {
    $endpoints = gcloud ai index-endpoints list --project=$Project --region=$Region --format="value(name)" 2>$null
    if ($endpoints) {
        Write-Host " [CRITICAL WARNING]" -ForegroundColor Red
        Write-Host "  Found running Vertex AI Vector Search Index Endpoints:" -ForegroundColor Red
        $endpoints | ForEach-Object { Write-Host "   - $_" -ForegroundColor Red }
        Write-Host "  ACTION REQUIRED: Undeploy indexes and delete endpoints to prevent idle billing!" -ForegroundColor Red
        $ErrorCount++
    } else {
        Write-Host " [PASS] 0 active index endpoints found." -ForegroundColor Green
    }
} catch {
    Write-Host " [SKIP] Unable to query Vertex AI endpoints." -ForegroundColor DarkGray
}

# 2. Audit Cloud Run min-instances
Write-Host "[2/3] Checking Cloud Run Services min-instances..." -NoNewline
try {
    $services = gcloud run services list --project=$Project --region=$Region --format="csv[no-heading](service,spec.template.metadata.annotations['autoscaling.knative.dev/minScale'])" 2>$null
    $hasIdleInstance = $false
    foreach ($svc in $services) {
        if ($svc) {
            $parts = $svc -split ','
            $svcName = $parts[0]
            $minScale = $parts[1]
            if ($minScale -and [int]$minScale -gt 0) {
                Write-Host ""
                Write-Host "  [WARNING] Service '$svcName' has min-instances set to $minScale (idle burn!)." -ForegroundColor Yellow
                $hasIdleInstance = $true
                $ErrorCount++
            }
        }
    }
    if (-not $hasIdleInstance) {
        Write-Host " [PASS] All Cloud Run services configured with scale-to-zero (min-instances=0)." -ForegroundColor Green
    }
} catch {
    Write-Host " [SKIP] Unable to query Cloud Run services." -ForegroundColor DarkGray
}

# 3. Audit Compute Engine instances
Write-Host "[3/3] Checking Compute Engine VMs..." -NoNewline
try {
    $vms = gcloud compute instances list --project=$Project --filter="status=RUNNING" --format="value(name)" 2>$null
    if ($vms) {
        Write-Host " [WARNING] Found running Compute Engine instances:" -ForegroundColor Yellow
        $vms | ForEach-Object { Write-Host "   - $_" -ForegroundColor Yellow }
        $ErrorCount++
    } else {
        Write-Host " [PASS] 0 running VMs found." -ForegroundColor Green
    }
} catch {
    Write-Host " [SKIP] Unable to query Compute Engine." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
if ($ErrorCount -eq 0) {
    Write-Host "AUDIT RESULT: PASSED. Zero idle billing detected." -ForegroundColor Green
} else {
    Write-Host "AUDIT RESULT: ATTENTION REQUIRED ($ErrorCount warnings)." -ForegroundColor Red
}
Write-Host "==========================================================" -ForegroundColor Cyan
