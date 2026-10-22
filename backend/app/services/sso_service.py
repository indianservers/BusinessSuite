import base64
import hashlib
import secrets
from urllib.parse import urlencode
import httpx
from jose import jwt
from app.core.config import settings
from app.models.sso import SSOProvider


FRONTEND_ORIGIN = settings.FRONTEND_PUBLIC_URL


def generate_pkce_pair() -> tuple[str, str]:
    """Returns a PKCE verifier and S256 challenge."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


async def get_oidc_authorization_url(
    provider: SSOProvider,
    state: str,
    nonce: str,
    code_challenge: str,
) -> str:
    """Build the provider authorization redirect URL."""
    params = {
        "response_type": "code",
        "client_id": provider.client_id,
        "redirect_uri": provider.redirect_uri or f"{settings.BACKEND_PUBLIC_URL}/api/v1/auth/sso/callback/oidc/{provider.id}",
        "scope": provider.scope or "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    if provider.provider_type.lower() == "google" and provider.domain_hint:
        params["hd"] = provider.domain_hint.strip().lower()
    return f"{provider.authorization_url}?{urlencode(params)}"


def validate_google_identity(id_token: str, jwks: dict, provider: SSOProvider, nonce: str, access_token: str | None = None) -> dict:
    """Accept only signed, current, audience-bound Google Workspace identities."""
    if not nonce or not provider.domain_hint:
        raise ValueError("Google Workspace domain and nonce are required")
    claims = jwt.decode(id_token, jwks, algorithms=["RS256"], audience=provider.client_id, access_token=access_token,
        issuer=["https://accounts.google.com", "accounts.google.com"],
        options={"require_exp": True, "require_iat": True, "require_sub": True, "require_aud": True, "require_iss": True})
    if not isinstance(claims.get("nonce"), str) or not secrets.compare_digest(claims["nonce"], nonce):
        raise ValueError("Google login nonce mismatch")
    if claims.get("azp") and claims["azp"] != provider.client_id:
        raise ValueError("Unexpected authorized client")
    domain = provider.domain_hint.strip().lower()
    email = claims.get("email", "")
    if claims.get("email_verified") is not True or not isinstance(email, str) or not email.lower().endswith("@" + domain):
        raise ValueError("A verified Workspace email is required")
    if str(claims.get("hd", "")).lower() != domain:
        raise ValueError("Account does not belong to the allowed Google Workspace")
    return claims


async def exchange_oidc_code(
    provider: SSOProvider,
    code: str,
    state: str,
    code_verifier: str,
    nonce: str | None = None,
) -> dict:
    """Exchange the OIDC authorization code and return userinfo claims."""
    async with httpx.AsyncClient(timeout=20) as client:
        token_resp = await client.post(provider.token_url, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": provider.redirect_uri or f"{settings.BACKEND_PUBLIC_URL}/api/v1/auth/sso/callback/oidc/{provider.id}",
            "client_id": provider.client_id,
            "client_secret": provider.client_secret,
            "code_verifier": code_verifier,
        })
        token_resp.raise_for_status()
        tokens = token_resp.json()
        if provider.provider_type.lower() == "google":
            keys = await client.get("https://www.googleapis.com/oauth2/v3/certs")
            keys.raise_for_status()
            return validate_google_identity(tokens.get("id_token", ""), keys.json(), provider, nonce or "", tokens.get("access_token"))
        userinfo_resp = await client.get(
            provider.userinfo_url,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        userinfo_resp.raise_for_status()
        return userinfo_resp.json()


def extract_user_attributes(userinfo: dict, provider: SSOProvider) -> dict:
    """Map IdP claims to AI HRMS user fields."""
    return {
        "email": userinfo.get(provider.attr_email or "email"),
        "first_name": userinfo.get(provider.attr_first_name or "given_name", ""),
        "last_name": userinfo.get(provider.attr_last_name or "family_name", ""),
        "role_hint": userinfo.get(provider.attr_role) if provider.attr_role else None,
    }
