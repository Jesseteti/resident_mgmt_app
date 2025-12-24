import os
from dotenv import load_dotenv
load_dotenv()

import hashlib
import requests
from urllib.parse import quote

SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SERVICE_ROLE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")

STORAGE_BASE = f"{SUPABASE_URL.rstrip('/')}/storage/v1"

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def upload_bytes(bucket: str, object_path: str, data: bytes, content_type: str = "application/octet-stream") -> dict:
    """
    Upload bytes to Supabase Storage (private bucket OK) using service role key.
    Returns metadata dict (sha256, size_bytes).
    """
    # Storage object endpoint wants URL-encoded path pieces
    encoded_path = quote(object_path, safe="/")
    url = f"{STORAGE_BASE}/object/{bucket}/{encoded_path}"

    headers = {
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "apikey": SERVICE_ROLE_KEY,
        "Content-Type": content_type,
        "x-upsert": "true",  # overwrite if exists
    }

    resp = requests.post(url, headers=headers, data=data, timeout=30)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Storage upload failed ({resp.status_code}): {resp.text}")

    return {
        "sha256": sha256_bytes(data),
        "size_bytes": len(data),
    }

def create_signed_url(bucket: str, object_path: str, expires_in_seconds: int = 300) -> str:
    """
    Create a time-limited signed URL for a private object.
    """
    encoded_path = quote(object_path, safe="/")
    url = f"{STORAGE_BASE}/object/sign/{bucket}/{encoded_path}"

    headers = {
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "apikey": SERVICE_ROLE_KEY,
        "Content-Type": "application/json",
    }

    payload = {"expiresIn": expires_in_seconds}
    resp = requests.post(url, headers=headers, json=payload, timeout=30)

    if resp.status_code != 200:
        raise RuntimeError(f"Signed URL failed ({resp.status_code}): {resp.text}")

    # Supabase returns {"signedURL": "..."} (or "signedUrl" depending on version)
    data = resp.json()
    signed = data.get("signedURL") or data.get("signedUrl")
    if not signed:
        raise RuntimeError(f"Signed URL response missing signedURL: {data}")

    # signedURL might be a full URL or a path.
    # We must ensure final URL includes /storage/v1 prefix.
    if signed.startswith("http"):
        return signed

    if not signed.startswith("/"):
        signed = "/" + signed

    # If Supabase returns "/object/sign/..." (missing "/storage/v1"),
    # prepend "/storage/v1" ourselves.
    if not signed.startswith("/storage/v1/"):
        signed = "/storage/v1" + signed

    return f"{SUPABASE_URL.rstrip('/')}{signed}"

