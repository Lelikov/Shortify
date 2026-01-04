import datetime
import hashlib
import secrets
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from shortify.app.core.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Algorithm used to generate the JWT token
ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a hashed password and a plain password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password for storing."""
    return pwd_context.hash(password)


def create_access_token(
    subject: str | Any,
    expires_delta: datetime.timedelta | None = None,
) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.datetime.now(datetime.UTC) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
            settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        )
    payload = {
        "exp": expire,
        "sub": str(subject),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_api_key() -> str:
    """Create a random API key."""
    return hashlib.sha256(secrets.token_bytes(32)).hexdigest()
