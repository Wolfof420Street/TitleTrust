#!/bin/bash

# TitleTrust Backend Deployment Script for Google Cloud Run
# Usage: ./deploy.sh

set -euo pipefail  # Exit on error, undefined vars, and pipe failures

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-}"
SERVICE_NAME="titletrust-backend"
REGION="us-central1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}TitleTrust Backend Deployment${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if required environment variables are set
if [ -z "${GCP_PROJECT_ID:-}" ]; then
    echo -e "${RED}Error: GCP_PROJECT_ID environment variable is not set${NC}"
    exit 1
fi

# MAPS_API_KEY is handled via Secrets now, but we verify it's known or prompt user to ensure secret creation
if [ -z "${MAPS_API_KEY:-}" ] && [ -z "${SKIP_SECRET_CHECK:-}" ]; then
    echo -e "${YELLOW}Warning: MAPS_API_KEY env var not found. Ensure secret 'MAPS_API_KEY' exists in Secret Manager.${NC}"
    # We no longer exit here, assuming Secret Manager is used.
fi

if [ -z "${VERTEX_AI_LOCATION:-}" ]; then
    echo -e "${YELLOW}Warning: VERTEX_AI_LOCATION not set, using default: us-central1${NC}"
    VERTEX_AI_LOCATION="us-central1"
fi

echo -e "${GREEN}Project ID:${NC} ${PROJECT_ID}"
echo -e "${GREEN}Service Name:${NC} ${SERVICE_NAME}"
echo -e "${GREEN}Region:${NC} ${REGION}"
echo ""

# Helper to ensure secret exists
ensure_secret() {
    local SECRET_NAME=$1
    local PROMPT_TEXT=$2
    local IS_FILE_PATH=${3:-false}

    if ! gcloud secrets describe "${SECRET_NAME}" --project="${PROJECT_ID}" &>/dev/null; then
        echo -e "${YELLOW}Secret '${SECRET_NAME}' not found.${NC}"
        read -p "${PROMPT_TEXT}: " USER_INPUT
        
        if [ "$IS_FILE_PATH" = "true" ]; then
            if [ ! -f "$USER_INPUT" ]; then
                echo -e "${RED}Error: File '$USER_INPUT' not found.${NC}"
                exit 1
            fi
            gcloud secrets create "${SECRET_NAME}" --data-file="$USER_INPUT" --project="${PROJECT_ID}"
        else
            echo -n "$USER_INPUT" | gcloud secrets create "${SECRET_NAME}" --data-file=- --project="${PROJECT_ID}"
        fi
        echo -e "${GREEN}Secret '${SECRET_NAME}' created.${NC}"
    else
        echo -e "${GREEN}✓ Secret '${SECRET_NAME}' exists${NC}"
    fi
}

# Step 1: Build the container image using Cloud Build
echo -e "${GREEN}Step 1: Building container image...${NC}"
echo "DEBUG: Content of backend/main.py (first 15 lines):"
cat backend/main.py | head -n 15
echo "---------------------------------------------------"

gcloud builds submit \
    --tag="${IMAGE_NAME}" \
    --project="${PROJECT_ID}" \
    backend/

echo -e "${GREEN}✓ Container image built successfully${NC}"
echo ""

# Step 1.5: Ensure Secrets Exist
echo -e "${GREEN}Step 1.5:Verifying Secrets...${NC}"
ensure_secret "GEMINI_API_KEY" "Enter your Gemini API Key"
ensure_secret "FIREBASE_CREDENTIALS" "Enter path to your Firebase Service Account JSON (e.g., ./service-account.json)" "true"
ensure_secret "MAPS_API_KEY" "Enter your Google Maps API Key"

# Step 2: Grant Permissions
echo -e "${GREEN}Step 2: Configuring IAM permissions...${NC}"

# Get Project Number
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "Granting Secret Accessor role to ${SERVICE_ACCOUNT}..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor" > /dev/null

echo "Granting Vertex AI User role to ${SERVICE_ACCOUNT}..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/aiplatform.user" > /dev/null

echo "Granting Token Creator role to ${SERVICE_ACCOUNT} (for Live API)..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/iam.serviceAccountTokenCreator" > /dev/null

echo "Granting Cloud Tasks Enqueuer role to ${SERVICE_ACCOUNT}..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/cloudtasks.enqueuer" > /dev/null

echo -e "${GREEN}✓ IAM permissions granted${NC}"
echo ""

# Step 2.5: Deploy Firestore Rules
echo -e "${GREEN}Step 2.5: Deploying Firestore Rules...${NC}"
if command -v firebase &> /dev/null; then
    firebase deploy --only firestore:rules --project="${PROJECT_ID}"
    echo -e "${GREEN}✓ Firestore Rules deployed${NC}"
else
    echo -e "${YELLOW}Warning: 'firebase' command not found. Skipping Firestore rules deployment.${NC}"
    echo -e "${YELLOW}Install firebase-tools: npm install -g firebase-tools${NC}"
fi
echo ""

# Step 3: Deploy to Cloud Run
echo -e "${GREEN}Step 3: Deploying to Cloud Run...${NC}"
gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_NAME}" \
    --platform=managed \
    --region="${REGION}" \
    --allow-unauthenticated \
    --set-env-vars="GCP_PROJECT_ID=${GCP_PROJECT_ID},VERTEX_AI_LOCATION=${VERTEX_AI_LOCATION},FIREBASE_CREDENTIALS_PATH=/app/secrets/service-account.json,SERVICE_ACCOUNT_EMAIL=${SERVICE_ACCOUNT}" \
    --set-secrets="/app/secrets/service-account.json=FIREBASE_CREDENTIALS:latest,MAPS_API_KEY=MAPS_API_KEY:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest" \
    --project="${PROJECT_ID}" \
    --memory=2Gi \
    --cpu=1 \
    --timeout=600 \
    --max-instances=10 \
    --min-instances=0

echo -e "${GREEN}✓ Deployment completed successfully${NC}"
echo ""

# Get the service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --platform=managed \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --format="value(status.url)")

echo -e "${GREEN}Service URL:${NC} ${SERVICE_URL}"

# Update the service with its own URL (required for Cloud Tasks)
echo -e "${GREEN}Configuring CLOUD_RUN_URL...${NC}"
gcloud run services update "${SERVICE_NAME}" \
    --platform=managed \
    --region="${REGION}" \
    --update-env-vars="CLOUD_RUN_URL=${SERVICE_URL}" \
    --project="${PROJECT_ID}" \
    --quiet

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Service URL:${NC} ${SERVICE_URL}"
echo -e "${GREEN}Health Check:${NC} ${SERVICE_URL}/"
echo ""
echo -e "${YELLOW}Note: You can now access your API at the URL above${NC}"
echo -e "${YELLOW}Update your Flutter app's API endpoint to use this URL${NC}"
