import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _get_fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY
    if key:
        return Fernet(key.encode())
    key_bytes = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def encrypt(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _get_fernet().decrypt(value.encode()).decode()


def safe_decrypt(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return decrypt(value)
    except (InvalidToken, Exception):
        return None
