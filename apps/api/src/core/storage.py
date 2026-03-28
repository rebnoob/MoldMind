"""Storage abstraction: local filesystem (dev) or S3-compatible (prod)."""

import os
from pathlib import Path
from io import BytesIO

from .config import get_settings

settings = get_settings()

LOCAL_STORAGE_DIR = Path("./storage")


def _ensure_local_dir():
    LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def get_s3_client():
    import boto3
    from botocore.config import Config as BotoConfig
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=BotoConfig(signature_version="s3v4"),
    )


def ensure_bucket():
    """Create the bucket if it doesn't exist (S3 mode only)."""
    if settings.use_local_storage:
        _ensure_local_dir()
        return
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except client.exceptions.ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)


def upload_file(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to storage. Returns the key."""
    if settings.use_local_storage:
        _ensure_local_dir()
        filepath = LOCAL_STORAGE_DIR / key
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(data)
        return key

    client = get_s3_client()
    client.upload_fileobj(
        BytesIO(data),
        settings.s3_bucket,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return key


def download_file(key: str) -> bytes:
    """Download file from storage."""
    if settings.use_local_storage:
        filepath = LOCAL_STORAGE_DIR / key
        return filepath.read_bytes()

    client = get_s3_client()
    response = client.get_object(Bucket=settings.s3_bucket, Key=key)
    return response["Body"].read()


def generate_presigned_url(key: str, expiry: int = 3600) -> str:
    """Generate a URL for direct browser access."""
    if settings.use_local_storage:
        # In local mode, serve via API endpoint
        return f"/api/files/{key}"

    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expiry,
    )
