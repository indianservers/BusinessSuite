import base64
import hashlib
import json
import secrets
from urllib.parse import urlencode, urlsplit
import jwt
from starlette.concurrency import run_in_threadpool
from app.apps.power_apps.integrations.transport import EgressPolicy, HttpTransport
from app.core.config import settings
from app.models.sso import SSOProvider


FRONTEND_ORIGIN = settings.FRONTEND_PUBLIC_URL
GOOGLE_OIDC_ENDPOINTS = {
    "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_url": "https://oauth2.googleapis.com/token",
    "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
}
OIDC_RESPONSE_LIMIT = 256 * 1024


def oidc_target_host(url: str) -> str:
    if (not isinstance(url, str) or len(url) > 2048 or "\\" in url
        or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in url)):
        raise ValueError("Invalid OIDC endpoint")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https" or not parsed.hostname or parsed.port not in {None, 443}
        or parsed.username is not None or parsed.password is not None or parsed.fragment
    ):
        raise ValueError("Use an HTTPS endpoint without credentials or a fragment")
    return parsed.hostname.encode("idna").decode("ascii").rstrip(".")


async def request_oidc_endpoint(method, url, *, headers=None, data=None, probe=False):
    transport = HttpTransport(EgressPolicy([oidc_target_host(url)]))
    body = urlencode(data).encode() if data is not None else None
    if data is not None:
        headers = {**(headers or {}), "Content-Type": "application/x-www-form-urlencoded"}
    return await run_in_threadpool(
        transport.request, method, url, headers, body,
        timeout=10, return_redirect=probe, max_response_bytes=OIDC_RESPONSE_LIMIT,
    )


def oidc_json(response):
    if not 200 <= response.status < 300:
        raise ValueError("Identity provider rejected the request")
    data = json.loads(response.body)
    if not isinstance(data, dict):
        raise ValueError("Identity provider returned an invalid response")
    return data


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
    url = GOOGLE_OIDC_ENDPOINTS["authorization_url"] if provider.provider_type.lower() == "google" else provider.authorization_url
    oidc_target_host(url)
    return f"{url}{'&' if urlsplit(url).query else '?'}{urlencode(params)}"


def validate_google_identity(id_token: str, jwks: dict, provider: SSOProvider, nonce: str, access_token: str | None = None) -> dict:
    """Accept only signed, current, audience-bound Google Workspace identities."""
    if not nonce or not provider.domain_hint:
        raise ValueError("Google Workspace domain and nonce are required")
    header=jwt.get_unverified_header(id_token)
    keys=[key for key in jwks.get('keys',[]) if key.get('kid')==header.get('kid') and key.get('kty')=='RSA' and key.get('use','sig')=='sig']
    if len(keys)!=1 or header.get('alg')!='RS256':
        raise ValueError('Unexpected identity signing key')
    key=jwt.PyJWK.from_dict(keys[0],algorithm='RS256').key
    claims = jwt.decode(id_token, key, algorithms=["RS256"], audience=provider.client_id,
        issuer=["https://accounts.google.com", "accounts.google.com"],
        options={"require": ["exp","iat","sub","aud","iss"]})
    if claims.get('at_hash'):
        expected=base64.urlsafe_b64encode(hashlib.sha256((access_token or '').encode()).digest()[:16]).rstrip(b'=').decode()
        if not access_token or not isinstance(claims['at_hash'],str) or not secrets.compare_digest(claims['at_hash'],expected):
            raise ValueError('Identity access token hash mismatch')
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
    google = provider.provider_type.lower() == "google"
    token_url = GOOGLE_OIDC_ENDPOINTS["token_url"] if google else provider.token_url
    response = await request_oidc_endpoint("POST", token_url, data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": provider.redirect_uri or f"{settings.BACKEND_PUBLIC_URL}/api/v1/auth/sso/callback/oidc/{provider.id}",
        "client_id": provider.client_id,
        "client_secret": provider.client_secret,
        "code_verifier": code_verifier,
    })
    tokens = oidc_json(response)
    if google:
        keys = oidc_json(await request_oidc_endpoint("GET", "https://www.googleapis.com/oauth2/v3/certs"))
        return validate_google_identity(tokens.get("id_token", ""), keys, provider, nonce or "", tokens.get("access_token"))
    access_token = tokens.get("access_token")
    if not isinstance(access_token, str) or not access_token or len(access_token) > 8192:
        raise ValueError("Identity provider returned an invalid access token")
    return oidc_json(await request_oidc_endpoint(
        "GET", provider.userinfo_url, headers={"Authorization": f"Bearer {access_token}"},
    ))


def extract_user_attributes(userinfo: dict, provider: SSOProvider) -> dict:
    """Map IdP claims to AI HRMS user fields."""
    email = userinfo.get("email")
    if not isinstance(email, str) or not email or len(email) > 320:
        raise ValueError("Identity provider did not return an email")
    if provider.provider_type.lower() != "google" and userinfo.get("email_verified") is not True:
        raise ValueError("Identity provider did not verify the email")
    mapped_email = userinfo.get(provider.attr_email or "email")
    if not isinstance(mapped_email, str) or mapped_email.casefold() != email.casefold():
        raise ValueError("Configured email must match the provider's verified email")
    return {
        "email": email,
        "first_name": userinfo.get(provider.attr_first_name or "given_name", ""),
        "last_name": userinfo.get(provider.attr_last_name or "family_name", ""),
        "role_hint": userinfo.get(provider.attr_role) if provider.attr_role else None,
    }
