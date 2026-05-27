import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union
from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)


def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: Union[str, Any]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    return jwt.encode(to_encode, settings.REFRESH_SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str, secret_key: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, secret_key, algorithms=[settings.ALGORITHM])
        return payload
    except ExpiredSignatureError:
        return None
    except JWTError as exc:
        logger.warning("Token verification failed: %s", exc.__class__.__name__)
        return None


def verify_access_token(token: str) -> Optional[dict]:
    for secret_key in [settings.SECRET_KEY, settings.SECRET_KEY_PREVIOUS]:
        if not secret_key:
            continue
        payload = verify_token(token, secret_key)
        if payload and payload.get("type") == "access":
            return payload
    return None


def verify_refresh_token(token: str) -> Optional[dict]:
    for secret_key in [settings.REFRESH_SECRET_KEY, settings.REFRESH_SECRET_KEY_PREVIOUS]:
        if not secret_key:
            continue
        payload = verify_token(token, secret_key)
        if payload and payload.get("type") == "refresh":
            return payload
    return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
