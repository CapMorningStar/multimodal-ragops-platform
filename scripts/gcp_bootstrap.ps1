# ==============================================================================
# GCP API & Resource Bootstrap Script (PowerShell)
# Enables required APIs and sets up service identity for Multimodal RAG.
# ==============================================================================

param (
    [Parameter(Mandatory=$true)]
    [string]$Project,
    [string]$Region = "us-central1"
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   BOOTSTRAPPING GCP ENVIRONMENT FOR MULTIMODAL RAG" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Target Project: $Project" -ForegroundColor Yellow
Write-Host "Target Region:  $Region" -ForegroundColor Yellow

# Set gcloud project
gcloud config set project $Project

# Enable Required APIs
$APIs = @(
    "documentai.googleapis.com",
    "aiplatform.googleapis.com",
    "run.googleapis.com",
    "storage.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com"
)

Write-Host "`nEnabling GCP APIs (this may take 1-2 minutes)..." -ForegroundColor Yellow
foreach ($api in $APIs) {
    Write-Host " - Enabling $api..." -NoNewline
    gcloud services enable $api --project=$Project
    Write-Host " [DONE]" -ForegroundColor Green
}

Write-Host "`nGCP APIs enabled successfully!" -ForegroundColor Green
Write-Host "Next Step: Create a Document AI Layout Parser processor via Google Cloud Console or gcloud."
