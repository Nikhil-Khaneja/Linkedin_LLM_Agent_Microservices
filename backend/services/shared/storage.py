from __future__ import annotations

import os
from datetime import timedelta
from io import BytesIO
from urllib.parse import urlsplit, urlunsplit
from minio import Minio

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_PUBLIC_ENDPOINT = os.environ.get("MINIO_PUBLIC_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin")
MINIO_BUCKET_PROFILE = os.environ.get("MINIO_BUCKET_PROFILE", "profile-media")
MINIO_BUCKET_RESUME = os.environ.get("MINIO_BUCKET_RESUME", "resume-media")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"
MINIO_PUBLIC_SECURE = os.environ.get("MINIO_PUBLIC_SECURE", os.environ.get("MINIO_SECURE", "false")).lower() == "true"


def _client(endpoint: str, secure: bool):
    return Minio(endpoint, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=secure)


def client():
    return _client(MINIO_ENDPOINT, MINIO_SECURE)


def public_client():
    return _client(MINIO_PUBLIC_ENDPOINT, MINIO_PUBLIC_SECURE)


def _rewrite_public_url(url: str) -> str:
    if not url:
        return url
    public_scheme = 'https' if MINIO_PUBLIC_SECURE else 'http'
    internal_scheme = 'https' if MINIO_SECURE else 'http'
    public_endpoint = (MINIO_PUBLIC_ENDPOINT or '').strip()
    internal_endpoint = (MINIO_ENDPOINT or '').strip()
    if not public_endpoint:
        return url
    try:
        parsed = urlsplit(url)
        netloc = parsed.netloc or parsed.path
        if netloc == public_endpoint and parsed.scheme == public_scheme:
            return url
        if netloc == internal_endpoint or parsed.scheme == internal_scheme:
            path = parsed.path if parsed.netloc else ''
            query = parsed.query if parsed.netloc else parsed.query
            fragment = parsed.fragment if parsed.netloc else ''
            return urlunsplit((public_scheme, public_endpoint, path, query, fragment))
        return url
    except Exception:
        return url.replace(f'{internal_scheme}://{internal_endpoint}', f'{public_scheme}://{public_endpoint}')


def ensure_bucket(name: str) -> None:
    c = client()
    found = c.bucket_exists(name)
    if not found:
        c.make_bucket(name)


def presigned_put(bucket: str, object_name: str, expiry_seconds: int = 3600) -> str:
    ensure_bucket(bucket)
    signed = client().get_presigned_url('PUT', bucket, object_name, expires=timedelta(seconds=expiry_seconds))
    return _rewrite_public_url(signed)


def presigned_get(bucket: str, object_name: str, expiry_seconds: int = 3600) -> str:
    ensure_bucket(bucket)
    signed = client().get_presigned_url('GET', bucket, object_name, expires=timedelta(seconds=expiry_seconds))
    return _rewrite_public_url(signed)


def upload_bytes(bucket: str, object_name: str, data: bytes, content_type: str = 'application/octet-stream') -> str:
    ensure_bucket(bucket)
    client().put_object(bucket, object_name, BytesIO(data), length=len(data), content_type=content_type)
    return presigned_get(bucket, object_name)


def download_bytes(bucket: str, object_name: str) -> bytes:
    ensure_bucket(bucket)
    response = client().get_object(bucket, object_name)
    try:
        return response.read()
    finally:
        try:
            response.close()
        except Exception:
            pass
        try:
            response.release_conn()
        except Exception:
            pass
