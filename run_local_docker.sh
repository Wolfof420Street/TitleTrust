#!/bin/bash

# Configuration
PROJECT_ID="titletrust-f5bf6"
IMAGE_NAME="titletrust-backend-local"
SERVICE_ACCOUNT_FILE="titletrust-f5bf6-firebase-adminsdk-fbsvc-99c61f4bf4.json"

# Check if Map API Key is set
if [ -z "$MAPS_API_KEY" ]; then
    echo "⚠️  WARNING: MAPS_API_KEY environment variable is not set."
    echo "   Please run: export MAPS_API_KEY='your_api_key'"
    exit 1
fi

echo "🚀 Building Docker Image..."
# Build from backend directory context
docker build -t $IMAGE_NAME -f backend/Dockerfile backend/

if [ $? -eq 0 ]; then
    echo "✅ Build Successful."
    echo "🏃 Running Container on port 8080..."

    # Run with:
    # - Port mapping 8080:8080
    # - Env vars for Config
    # - Volume mount for Service Account Key (mapped to /app/service-account.json)
    # - GOOGLE_APPLICATION_CREDENTIALS pointing to the mounted file
    # - PORT=8080 explicitly
    
    docker run --rm -p 8080:8080 \
        -e PORT=8080 \
        -e GCP_PROJECT_ID=$PROJECT_ID \
        -e MAPS_API_KEY=$MAPS_API_KEY \
        -e VERTEX_AI_LOCATION="us-central1" \
        -e GOOGLE_APPLICATION_CREDENTIALS="/app/service-account.json" \
        -v "$(pwd)/$SERVICE_ACCOUNT_FILE:/app/service-account.json" \
        $IMAGE_NAME
else
    echo "❌ Build Failed."
    exit 1
fi
