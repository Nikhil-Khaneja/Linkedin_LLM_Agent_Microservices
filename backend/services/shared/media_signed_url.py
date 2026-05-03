"""Signed, time-limited URLs for member media served via the member API (avoids broken S3 SigV4 when
rewriting presigned MinIO URLs from internal host to localhost)."""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from urllib.parse import quote, urlencode


def media_sig_secret() -> bytes:
    s = os.environ.get("MEDIA_SIG_SECRET") or os.environ.get("JWT_SECRET_KEY") or "dev-media-sig-change-me"
    return s.encode("utf-8")


def sign_media_params(member_id: str, bucket: str, object_name: str, expires_at: int) -> str:
    msg = f"{member_id}|{bucket}|{object_name}|{expires_at}".encode("utf-8")
    return hmac.new(media_sig_secret(), msg, hashlib.sha256).hexdigest()


def verify_media_params(member_id: str, bucket: str, object_name: str, expires_at: int, sig: str) -> bool:
    if expires_at < int(time.time()):
        return False
    expect = sign_media_params(member_id, bucket, object_name, expires_at)
    return hmac.compare_digest(expect, sig)


def default_member_public_url() -> str:
    return (os.environ.get("MEMBER_PUBLIC_URL") or "http://localhost:8002").rstrip("/")


def member_media_proxy_url(public_base: str, member_id: str, bucket: str, object_name: str, ttl_seconds: int = 3600) -> str:
    public_base = (public_base or "").strip().rstrip("/")
    if not public_base or not object_name.strip() or not (member_id or "").strip():
        return ""
    exp = int(time.time()) + max(60, int(ttl_seconds))
    sig = sign_media_params(member_id, bucket, object_name, exp)
    q = urlencode(
        {"member_id": member_id, "bucket": bucket, "object": object_name, "e": str(exp), "s": sig},
        quote_via=quote,
    )
    return f"{public_base}/members/media?{q}"


def sanitize_media_public_base(raw: str | None) -> str | None:
    if not raw or not isinstance(raw, str):
        return None
    t = raw.strip().rstrip("/")
    if len(t) > 256 or any(c in t for c in "\r\n\t"):
        return None
    if not (t.startswith("http://") or t.startswith("https://")):
        return None
    return t
