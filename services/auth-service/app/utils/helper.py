import hashlib
import json
import uuid


def generate_user_id() -> str:
    return f"usr_{uuid.uuid4().hex[:10]}"


def build_request_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()