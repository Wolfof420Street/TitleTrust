# Cloud Build Troubleshooting Guide

## Issues Resolved

### ✅ Issue 1: Dockerfile Not Found
**Error:** `Invalid value for [source]: Dockerfile required when specifying --tag`

**Cause:** The Dockerfile was in `backend/` subdirectory, but the script was looking in the root directory.

**Fix:** Updated `deploy.sh` to specify `backend/` as the source directory:
```bash
gcloud builds submit --tag="${IMAGE_NAME}" --project="${PROJECT_ID}" backend/
```

---

### ✅ Issue 2: NOT_FOUND Error
**Error:** `NOT_FOUND: Requested entity was not found`

**Cause:** Missing API enablement and insufficient Cloud Build service account permissions.

**Fixes Applied:**

1. **Enabled Required APIs:**
   ```bash
   gcloud services enable run.googleapis.com
   gcloud services enable containerregistry.googleapis.com
   # Optional: Enable Artifact Registry if migrating from Container Registry
   # gcloud services enable artifactregistry.googleapis.com
   ```

2. **Granted Cloud Build Permissions:**
   ```bash
   # Define variables
   export PROJECT_ID="your-project-id"
   export CLOUD_BUILD_SA="[PROJECT_NUMBER]@cloudbuild.gserviceaccount.com"

   # Permission to deploy to Cloud Run
   gcloud projects add-iam-policy-binding ${PROJECT_ID} \
     --member="serviceAccount:${CLOUD_BUILD_SA}" \
     --role="roles/run.admin"
   
   # Permission to act as service account
   gcloud projects add-iam-policy-binding ${PROJECT_ID} \
     --member="serviceAccount:${CLOUD_BUILD_SA}" \
     --role="roles/iam.serviceAccountUser"
   ```

---

## Current Service Account Permissions

The Cloud Build service account now has:

- ✅ `roles/cloudbuild.builds.builder` - Build containers
- ✅ `roles/run.admin` - Deploy to Cloud Run
- ✅ `roles/iam.serviceAccountUser` - Act as Cloud Run service account

---

## Ready to Deploy

All prerequisites are now configured. Retry the deployment:

```bash
./deploy.sh
```

This should now:
1. ✅ Build the container image successfully
2. ✅ Push to Google Container Registry (or Artifact Registry if configured)
3. ✅ Deploy to Cloud Run with environment variables
4. ✅ Return a public URL for your API
