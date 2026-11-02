from __future__ import annotations

import hashlib
import secrets
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings

ALLOWED_JOB_HOSTS = {
    "www.fl.ru",
    "fl.ru",
    "freelancehunt.com",
    "www.freelancehunt.com",
}


def get_fernet(settings: Settings) -> Fernet:
    key = settings.encryption_key.strip()
    if not key:
        key = Fernet.generate_key().decode()
        settings.encryption_key = key
    if len(key) != 44:
        digest = hashlib.sha256(key.encode()).digest()
        import base64

        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(value: str, settings: Settings) -> str:
    if not value:
        return ""
    return get_fernet(settings).encrypt(value.encode()).decode()


def decrypt_secret(value: str, settings: Settings) -> str:
    if not value:
        return ""
    try:
        return get_fernet(settings).decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt stored credential") from exc


def canonical_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = (parsed.netloc or "").lower()
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme.lower()}://{host}{path}"


def is_allowed_job_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    return host in ALLOWED_JOB_HOSTS and parsed.scheme in {"http", "https"}


def content_hash(*parts: str | None) -> str:
    blob = "\n".join((part or "").strip().lower() for part in parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def new_correlation_id() -> str:
    return secrets.token_hex(8)
