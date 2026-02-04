from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from jose import jwt
from passlib.context import CryptContext

from app.core.config import get_settings


# Use PBKDF2-SHA256 for password hashing.
# This avoids the bcrypt 72-byte password limit and sidesteps
# platform-specific bcrypt backend issues.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def create_access_token(subject: str | int, expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "exp": datetime.now(timezone.utc) + expires_delta,
    }
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def get_fernet() -> Fernet | None:
    key = get_settings().encryption_key
    if not key:
        return None
    return Fernet(key)


def encrypt_sensitive(data: bytes) -> bytes:
    """
    Encrypt sensitive financial data for storage at rest.
    If no encryption key is configured, returns the data unchanged.
    """
    f = get_fernet()
    if f is None:
        return data
    return f.encrypt(data)


def decrypt_sensitive(token: bytes) -> bytes:
    """
    Decrypt sensitive financial data for processing.
    If no encryption key is configured or decryption fails, returns the original token.
    """
    f = get_fernet()
    if f is None:
        return token
    try:
        return f.decrypt(token)
    except InvalidToken:
        return token

