"""Google Calendar transport. Credentials never leave the backend."""
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

SCOPE = "https://www.googleapis.com/auth/calendar.events"


def cipher():
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest()))


def configured():
    if not all((settings.CRM_GOOGLE_CALENDAR_CLIENT_ID, settings.CRM_GOOGLE_CALENDAR_CLIENT_SECRET,
                settings.CRM_GOOGLE_CALENDAR_REDIRECT_URI)):
        raise HTTPException(503, "Configure Google Calendar client ID, client secret and redirect URI on the server first.")


def authorize(user_id, organization_id):
    configured()
    verifier = secrets.token_urlsafe(48)
    state = cipher().encrypt(json.dumps({"user": user_id, "organization": organization_id,
                                        "verifier": verifier}).encode()).decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return {"state": state, "url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": settings.CRM_GOOGLE_CALENDAR_CLIENT_ID,
        "redirect_uri": settings.CRM_GOOGLE_CALENDAR_REDIRECT_URI,
        "response_type": "code", "scope": SCOPE, "access_type": "offline", "prompt": "consent",
        "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
    })}


def token_request(data):
    configured()
    try:
        response = httpx.post("https://oauth2.googleapis.com/token", data={
            "client_id": settings.CRM_GOOGLE_CALENDAR_CLIENT_ID,
            "client_secret": settings.CRM_GOOGLE_CALENDAR_CLIENT_SECRET, **data,
        }, timeout=20)
    except httpx.RequestError:
        raise HTTPException(502, "Google Calendar could not be reached. Try again.") from None
    if response.status_code != 200:
        raise HTTPException(400, "Google authorization expired or was revoked. Reconnect Google Calendar.")
    result = response.json()
    if not result.get("access_token"):
        raise HTTPException(502, "Google did not return an access token.")
    return result


def exchange(code, state, user_id, organization_id):
    try:
        payload = json.loads(cipher().decrypt(state.encode(), ttl=600))
    except (InvalidToken, ValueError, TypeError):
        raise HTTPException(400, "Invalid or expired calendar authorization. Start again.") from None
    if payload.get("user") != user_id or payload.get("organization") != organization_id:
        raise HTTPException(403, "Calendar authorization belongs to another user or organization.")
    result = token_request({"grant_type": "authorization_code", "code": code,
                            "redirect_uri": settings.CRM_GOOGLE_CALENDAR_REDIRECT_URI,
                            "code_verifier": payload["verifier"]})
    if SCOPE not in result.get("scope", "").split():
        raise HTTPException(400, "Google Calendar event permission was not granted.")
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
            raise RuntimeError("Reconnect Google Calendar to renew access.")
        refresh = cipher().decrypt(integration.refresh_token_encrypted.encode()).decode()
        store_tokens(integration, token_request({"grant_type": "refresh_token", "refresh_token": refresh}))
    token = cipher().decrypt(integration.access_token_encrypted.encode()).decode()
    # Include the connection ID so separate users' calendars cannot share an event mapping.
    event_id = hashlib.sha256(f"business-suite:{integration.organization_id}:{integration.id}:{meeting.id}".encode()).hexdigest()
    def iso(value):
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()
    body = {"summary": meeting.title, "description": meeting.description or "",
            "location": meeting.location or "", "start": {"dateTime": iso(meeting.start_time)},
            "end": {"dateTime": iso(meeting.end_time)},
            "status": "cancelled" if str(meeting.status).lower() in {"cancelled", "canceled"} else "confirmed"}
    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        with httpx.Client(timeout=20) as client:
            response = client.post(url, headers=headers, json={"id": event_id, **body})
            if response.status_code == 409:
                response = client.patch(f"{url}/{quote(event_id, safe='')}", headers=headers, json=body)
    except httpx.RequestError:
        raise RuntimeError("Google Calendar could not be reached. Retry sync.") from None
    if response.status_code not in (200, 201):
        raise RuntimeError(f"Google Calendar rejected event sync (HTTP {response.status_code}). Reconnect if access expired.")
    return response.json()["id"]
