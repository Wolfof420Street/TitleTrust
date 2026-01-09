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

# Step 1: Build the container image using Cloud Build
echo -e "${GREEN}Step 1: Building container image...${NC}"
gcloud builds submit \
    --tag="${IMAGE_NAME}" \
    --project="${PROJECT_ID}" \
    backend/

echo -e "${GREEN}✓ Container image built successfully${NC}"
echo ""

# Step 2: Deploy to Cloud Run
echo -e "${GREEN}Step 2: Deploying to Cloud Run...${NC}"
# Note: Ensure secret 'MAPS_API_KEY' exists: echo -n "KEY" | gcloud secrets create MAPS_API_KEY --data-file=-
gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_NAME}" \
    --platform=managed \
    --region="${REGION}" \
    --allow-unauthenticated \
    --set-env-vars="GCP_PROJECT_ID=${GCP_PROJECT_ID},VERTEX_AI_LOCATION=${VERTEX_AI_LOCATION}" \
    --set-secrets="MAPS_API_KEY=MAPS_API_KEY:latest" \
    --project="${PROJECT_ID}" \
    --memory=2Gi \
    --cpu=1 \
    --timeout=300 \
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

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Service URL:${NC} ${SERVICE_URL}"
echo -e "${GREEN}Health Check:${NC} ${SERVICE_URL}/"
echo ""
echo -e "${YELLOW}Note: You can now access your API at the URL above${NC}"
echo -e "${YELLOW}Update your Flutter app's API endpoint to use this URL${NC}"
