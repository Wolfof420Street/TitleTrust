from __future__ import annotations

import mimetypes
import os
import time
import uuid
from datetime import timedelta
from typing import BinaryIO
from urllib.parse import urlparse

try:
    from google.cloud import storage
except ImportError:
    storage = None

try:
    from backend.config import settings
except ModuleNotFoundError:
    from config import settings


class CloudStorageService:
    def __init__(self) -> None:
        self._client = None

    def create_signed_upload(
        self,
        *,
        filename: str,
        content_type: str | None,
        user_id: str,
        organization_id: str,
        purpose: str,
    ) -> dict[str, object]:
        bucket_name = settings.UPLOAD_BUCKET_NAME
        if not bucket_name:
            raise ValueError("UPLOAD_BUCKET_NAME is not configured")
        client = self._get_client()

        sanitized_name = os.path.basename(filename) or "upload.bin"
        object_name = (
            f"{settings.STORAGE_UPLOAD_PREFIX.rstrip('/')}/"
            f"{organization_id}/{user_id}/{purpose}/{uuid.uuid4()}-{sanitized_name}"
        )
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        resolved_content_type = content_type or mimetypes.guess_type(sanitized_name)[0] or "application/octet-stream"
        expires_in = settings.SIGNED_UPLOAD_URL_TTL_SECONDS
        upload_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expires_in),
            method="PUT",
            content_type=resolved_content_type,
        )
        return {
            "upload_url": upload_url,
            "object_path": f"gs://{bucket_name}/{object_name}",
            "method": "PUT",
            "headers": {"Content-Type": resolved_content_type},
            "expires_in_seconds": expires_in,
        }

    def upload_fileobj(
        self,
        *,
        file_obj: BinaryIO,
        filename: str,
        content_type: str | None,
        user_id: str,
        organization_id: str,
        purpose: str,
    ) -> dict[str, object]:
        bucket_name = settings.UPLOAD_BUCKET_NAME
        if not bucket_name:
            raise ValueError("UPLOAD_BUCKET_NAME is not configured")
        client = self._get_client()

        sanitized_name = os.path.basename(filename) or "upload.bin"
        object_name = (
            f"{settings.STORAGE_UPLOAD_PREFIX.rstrip('/')}/"
            f"{organization_id}/{user_id}/{purpose}/{uuid.uuid4()}-{sanitized_name}"
        )
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        resolved_content_type = content_type or mimetypes.guess_type(sanitized_name)[0] or "application/octet-stream"
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        blob.upload_from_file(file_obj, rewind=True, content_type=resolved_content_type)
        return {
            "object_path": f"gs://{bucket_name}/{object_name}",
            "content_type": resolved_content_type,
        }

    def stat_object(self, object_path: str) -> dict[str, object]:
        started = time.perf_counter()
        client = self._get_client()
        bucket_name, blob_name = self._parse_gcs_path(object_path)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.reload()
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "bucket": bucket_name,
            "name": blob_name,
            "size": blob.size,
            "content_type": blob.content_type or mimetypes.guess_type(blob_name)[0] or "application/octet-stream",
            "latency_ms": latency_ms,
        }

    def _get_client(self):
        if storage is None:
            raise RuntimeError("google-cloud-storage is not installed")
        if self._client is None:
            self._client = storage.Client(project=settings.GCP_PROJECT_ID)
        return self._client

    @staticmethod
    def _parse_gcs_path(object_path: str) -> tuple[str, str]:
        parsed = urlparse(object_path)
        if parsed.scheme != "gs" or not parsed.netloc or not parsed.path:
            raise ValueError("object_path must use the gs://bucket/object format")
        object_name = parsed.path.lstrip("/")
        if not object_name:
            raise ValueError("object_path must include a non-empty object name")
        return parsed.netloc, object_name


cloud_storage_service = CloudStorageService()
