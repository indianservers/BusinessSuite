import base64
import hashlib
import io
import secrets
import pyotp
import qrcode
from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings


APP_NAME = "Business Suite"


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def generate_totp_secret() -> str:
    """Generate a new random TOTP secret."""
    return pyotp.random_base32()


def protect_totp_secret(secret: str) -> str:
    """Encrypt a TOTP secret before storing it."""
    return _fernet().encrypt(secret.encode("utf-8")).decode("utf-8")


def reveal_totp_secret(secret_ref: str) -> str:
    """Decrypt a stored TOTP secret. Plain legacy values are accepted for migration compatibility."""
    if not secret_ref:
        return ""
    try:
        return _fernet().decrypt(secret_ref.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return secret_ref


def get_totp_uri(secret: str, user_email: str, issuer: str = APP_NAME) -> str:
    """Build the otpauth URI consumed by authenticator apps."""
    return pyotp.totp.TOTP(secret).provisioning_uri(name=user_email, issuer_name=issuer)


def generate_totp_qr_base64(secret: str, user_email: str) -> str:
    """Returns a base64-encoded PNG QR code image."""
    uri = get_totp_uri(secret, user_email)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    """Verify a 6-digit TOTP code with a small clock drift window."""
    try:
        return pyotp.TOTP(secret).verify(str(code).strip(), valid_window=window)
    except Exception:
        return False


def generate_recovery_codes(count: int = 10) -> list[str]:
    """Generate one-time recovery codes in XXXX-XXXX-XXXX format."""
    codes = []
    for _ in range(count):
        raw = secrets.token_hex(6).upper()
        codes.append(f"{raw[:4]}-{raw[4:8]}-{raw[8:]}")
    return codes


def hash_recovery_code(code: str) -> str:
    """Hash a recovery code for secure storage."""
    normalized = code.replace("-", "").upper().strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


def verify_recovery_code(plain: str, hashed: str) -> bool:
    """Verify a plain recovery code against its stored hash."""
    return hash_recovery_code(plain) == hashed
