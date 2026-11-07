"""Outlook Calendar transport. Credentials never leave the backend."""
import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, quote

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from app.core.config import settings

SCOPE = "Calendars.ReadWrite"


def cipher():
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest()))


def configured():
    if not all((settings.CRM_OUTLOOK_CALENDAR_CLIENT_ID, settings.CRM_OUTLOOK_CALENDAR_CLIENT_SECRET,
                settings.CRM_OUTLOOK_CALENDAR_REDIRECT_URI)):
        raise HTTPException(503, "Configure Outlook Calendar client ID, client secret and redirect URI on the server first.")


def authorize(user_id, organization_id):
    configured()
    verifier = secrets.token_urlsafe(48)
    state = cipher().encrypt(json.dumps({"provider": "outlook", "user": user_id, "organization": organization_id,
                                        "verifier": verifier}).encode()).decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return {"state": state, "url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?" + urlencode({
        "client_id": settings.CRM_OUTLOOK_CALENDAR_CLIENT_ID,
        "redirect_uri": settings.CRM_OUTLOOK_CALENDAR_REDIRECT_URI,
        "response_type": "code", "scope": SCOPE + " offline_access User.Read", "prompt": "consent",
        "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
    })}


def token_request(data):
    configured()
    try:
        response = httpx.post("https://login.microsoftonline.com/common/oauth2/v2.0/token", data={
            "client_id": settings.CRM_OUTLOOK_CALENDAR_CLIENT_ID,
            "client_secret": settings.CRM_OUTLOOK_CALENDAR_CLIENT_SECRET, **data,
        }, timeout=20)
    except httpx.RequestError:
        raise HTTPException(502, "Outlook Calendar could not be reached. Try again.") from None
    if response.status_code != 200:
        raise HTTPException(400, "Outlook authorization expired or was revoked. Reconnect Outlook Calendar.")
    result = response.json()
    if not result.get("access_token"):
        raise HTTPException(502, "Outlook did not return an access token.")
    return result


def exchange(code, state, user_id, organization_id):
    try:
        payload = json.loads(cipher().decrypt(state.encode(), ttl=600))
    except (InvalidToken, ValueError, TypeError):
        raise HTTPException(400, "Invalid or expired calendar authorization. Start again.") from None
    if payload.get("provider") != "outlook" or payload.get("user") != user_id or payload.get("organization") != organization_id:
        raise HTTPException(403, "Calendar authorization belongs to another user or organization.")
    result = token_request({"grant_type": "authorization_code", "code": code,
                            "redirect_uri": settings.CRM_OUTLOOK_CALENDAR_REDIRECT_URI,
                            "code_verifier": payload["verifier"]})
    if SCOPE not in result.get("scope", "").split():
        raise HTTPException(400, "Outlook Calendar event permission was not granted.")
    return result


def store_tokens(integration, tokens):
    integration.access_token_encrypted = cipher().encrypt(tokens["access_token"].encode()).decode()
    if tokens.get("refresh_token"):
        integration.refresh_token_encrypted = cipher().encrypt(tokens["refresh_token"].encode()).decode()
    integration.expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(tokens.get("expires_in", 3600)))


def sync_meeting(integration, meeting):
    expires = integration.expires_at
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if not expires or expires <= datetime.now(timezone.utc) + timedelta(seconds=60):
        if not integration.refresh_token_encrypted:
            raise RuntimeError("Reconnect Outlook Calendar to renew access.")
        refresh = cipher().decrypt(integration.refresh_token_encrypted.encode()).decode()
        store_tokens(integration, token_request({"grant_type": "refresh_token", "refresh_token": refresh}))
    token = cipher().decrypt(integration.access_token_encrypted.encode()).decode()
    from .calendar_transport import PROPERTY
    identity = hashlib.sha256(f"business-suite:{integration.organization_id}:{integration.id}:{meeting.id}".encode()).hexdigest()
    url = "https://graph.microsoft.com/v1.0/me/events"
    headers = {"Authorization": f"Bearer {token}"}
    def stamp(value):
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).replace(tzinfo=None).isoformat()
    body = {"subject": meeting.title, "body": {"contentType": "text", "content": meeting.description or ""},
            "location": {"displayName": meeting.location or ""},
            "start": {"dateTime": stamp(meeting.start_time), "timeZone": "UTC"},
            "end": {"dateTime": stamp(meeting.end_time), "timeZone": "UTC"}}
    try:
        with httpx.Client(timeout=20) as client:
            found = client.get(url, headers=headers, params={"$filter": f"singleValueExtendedProperties/Any(ep: ep/id eq '{PROPERTY}' and ep/value eq '{identity}')", "$select": "id"})
            if found.status_code != 200:
                raise RuntimeError(f"Outlook Calendar lookup failed (HTTP {found.status_code}).")
            events = found.json().get("value", [])
            event_id = events[0]["id"] if events else None
            cancelled = str(meeting.status).lower() in {"cancelled", "canceled"}
            if cancelled:
                if event_id:
                    response = client.delete(f"{url}/{quote(event_id, safe='')}", headers=headers)
                    if response.status_code not in (204, 404):
                        raise RuntimeError(f"Outlook Calendar cancellation failed (HTTP {response.status_code}).")
                return event_id or identity
            if event_id:
                response = client.patch(f"{url}/{quote(event_id, safe='')}", headers=headers, json=body)
            else:
                response = client.post(url, headers=headers, json={**body, "transactionId": identity, "singleValueExtendedProperties": [{"id": PROPERTY, "value": identity}]})
    except httpx.RequestError:
        raise RuntimeError("Outlook Calendar could not be reached. Retry sync.") from None
    if response.status_code not in (200, 201):
        raise RuntimeError(f"Outlook Calendar rejected event sync (HTTP {response.status_code}). Reconnect if access expired.")
    return response.json()["id"]
