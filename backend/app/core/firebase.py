"""Verify Google identities issued by the installation's Firebase project."""
import time
from functools import lru_cache
import httpx
import jwt
from cryptography import x509
from fastapi import HTTPException
from pydantic import EmailStr, TypeAdapter

CERT_URL = 'https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com'


@lru_cache(maxsize=2)
def _certificates(bucket):
    # Short cache bounds key rotation while avoiding a Google request per signup.
    response = httpx.get(CERT_URL, timeout=15)
    response.raise_for_status()
    return response.json()


def verify_google_identity(token, project):
    if not project:
        raise HTTPException(503, 'Google sign-in is not configured yet')
    header = jwt.get_unverified_header(token)
    if header.get('alg') != 'RS256' or not isinstance(header.get('kid'), str):
        raise ValueError('Unexpected identity signing key')
    certificates = _certificates(int(time.monotonic() // 300))
    certificate = certificates.get(header['kid'])
    if not certificate:
        raise ValueError('Unknown Firebase signing key')
    key = x509.load_pem_x509_certificate(certificate.encode()).public_key()
    claims = jwt.decode(token, key, algorithms=['RS256'], audience=project,
        issuer=f'https://securetoken.google.com/{project}',
        options={'require':['exp','iat','auth_time','sub','aud','iss']})
    if (not isinstance(claims['sub'], str) or not 1 <= len(claims['sub']) <= 128
            or type(claims['auth_time']) is not int or claims['auth_time'] > time.time()):
        raise ValueError('Invalid Firebase subject or authentication time')
    provider = claims.get('firebase', {}).get('sign_in_provider')
    if provider not in {'google.com'}:
        raise ValueError('Unsupported signup identity provider')
    if provider == 'google.com' and claims.get('email_verified') is not True:
        raise ValueError('Google email must be verified')
    email = str(TypeAdapter(EmailStr).validate_python(claims.get('email')))
    if len(email) > 254:
        raise ValueError('Email exceeds account limit')
    name = claims.get('name') or ''
    if not isinstance(name, str):
        raise ValueError('Invalid display name')
    return {'email':email, 'full_name':name.strip()[:160], 'provider':'google', 'subject':claims['sub']}

