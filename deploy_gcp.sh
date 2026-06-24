#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ASBA Google Cloud Run Deployment Script
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Automates the provisioning, building, and deploying of the ASBA
# fullstack agent on Google Cloud Serverless infrastructure.
#
# Prerequisite:
#   1. Make sure you have installed Google Cloud CLI (gcloud).
#   2. Run `gcloud auth login` to authenticate.
#
# Run this script:
#   chmod +x deploy_gcp.sh
#   ./deploy_gcp.sh

set -e # Exit immediately if a command exits with a non-zero status

# ──────────────────────────────────────────────────────────────
# 1. Configuration
# ──────────────────────────────────────────────────────────────
PROJECT_ID="adroit-gravity-500216-r4"
REGION="us-central1"
REPO_NAME="asba-repo"
SERVICE_NAME="asba-service"

echo "=========================================================="
echo "🚀 ASBA GCP Deployment Tool"
echo "=========================================================="
echo "Project ID:      $PROJECT_ID"
echo "Target Region:   $REGION"
echo "Repository:      $REPO_NAME"
echo "Service Name:    $SERVICE_NAME"
echo "=========================================================="
echo ""

# Ensure gcloud is pointing to the correct project
echo "Step 1: Setting active project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# ──────────────────────────────────────────────────────────────
# 2. Enable Required APIs
# ──────────────────────────────────────────────────────────────
echo ""
echo "Step 2: Enabling required Google Cloud APIs..."
echo "(This might take a moment if they are not already enabled)"
gcloud services enable \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    aiplatform.googleapis.com

# ──────────────────────────────────────────────────────────────
# 3. Create Artifact Registry Repository
# ──────────────────────────────────────────────────────────────
echo ""
echo "Step 3: Creating Artifact Registry Docker repository..."
if gcloud artifacts repositories describe $REPO_NAME --location=$REGION &>/dev/null; then
    echo "  [OK] Repository '$REPO_NAME' already exists."
else
    gcloud artifacts repositories create $REPO_NAME \
        --repository-format=docker \
        --location=$REGION \
        --description="Docker repository for ASBA app"
    echo "  [OK] Repository '$REPO_NAME' created successfully."
fi

# ──────────────────────────────────────────────────────────────
# 4. Build and Push Container Image via Google Cloud Build
# ──────────────────────────────────────────────────────────────
echo ""
echo "Step 4: Compiling image on the cloud using Google Cloud Build..."
echo "(This uploads your codebase, compiles the React assets, and installs dependencies)"
IMAGE_TAG="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$SERVICE_NAME:latest"

gcloud builds submit --tag $IMAGE_TAG .

echo "  [OK] Container image pushed to Artifact Registry: $IMAGE_TAG"

# ──────────────────────────────────────────────────────────────
# 5. Deploy to Google Cloud Run
# ──────────────────────────────────────────────────────────────
echo ""
echo "Step 5: Deploying service to Google Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_TAG \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars="USE_VERTEX_AI=true,GCP_PROJECT=$PROJECT_ID" \
    --port 8080

# Retrieve deployed URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format="value(status.url)")

# ──────────────────────────────────────────────────────────────
# 6. Secure IAM bindings for Vertex AI (Keyless Mode)
# ──────────────────────────────────────────────────────────────
echo ""
echo "Step 6: Granting Vertex AI User permissions to the Cloud Run Service Account..."
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
# Default compute service account used by Cloud Run
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/aiplatform.user"

echo ""
echo "=========================================================="
echo "🎉 DEPLOYMENT COMPLETE!"
echo "=========================================================="
echo "Your supply chain agent is now running securely on GCP!"
echo "Dashboard Web URL:   $SERVICE_URL"
echo ""
echo "Notice: The agent has been configured with 'USE_VERTEX_AI=true'."
echo "It will automatically authenticate with Vertex AI using the Cloud"
echo "Run identity. No raw API keys are stored in the environment!"
echo "=========================================================="
