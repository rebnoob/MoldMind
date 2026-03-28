"""S3-compatible object storage client (MinIO in dev, S3 in prod)."""

import boto3
from botocore.config import Config as BotoConfig
from io import BytesIO

from .config import get_settings

settings = get_settings()


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=BotoConfig(signature_version="s3v4"),
    )


def ensure_bucket():
    """Create the bucket if it doesn't exist."""
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except client.exceptions.ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)


def upload_file(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to object storage. Returns the key."""
    client = get_s3_client()
    client.upload_fileobj(
        BytesIO(data),
        settings.s3_bucket,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return key


def download_file(key: str) -> bytes:
    """Download file from object storage."""
    client = get_s3_client()
    response = client.get_object(Bucket=settings.s3_bucket, Key=key)
    return response["Body"].read()


def generate_presigned_url(key: str, expiry: int = 3600) -> str:
    """Generate a presigned URL for direct browser access."""
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expiry,
    )
