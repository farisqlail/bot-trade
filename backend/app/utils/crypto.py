import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_warned_no_encryption_key = False


def _get_fernet() -> Fernet:
    global _warned_no_encryption_key
    key = settings.ENCRYPTION_KEY
    if key:
        return Fernet(key.encode())
    if not _warned_no_encryption_key:
        logger.warning("encryption_key_not_set_falling_back_to_secret_key_derivation_insecure")
        _warned_no_encryption_key = True
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
