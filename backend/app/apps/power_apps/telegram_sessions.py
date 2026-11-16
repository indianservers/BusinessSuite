"""Short-lived initiating sessions for code-owned Telegram AI requests.

These sessions never reuse browser credentials or expose a refresh/access secret
to Telegram. Normal session expiry/revocation and AI delegation checks still apply.
"""
import hashlib
import json
import secrets
from datetime import timedelta

from fastapi import HTTPException

from app.apps.power_apps.runtime import now, utc
from app.models.user import UserSession


def initiate(db, user, resource, thread, linked):
    if (not linked or linked.interface != 'company' or linked.user_id != user.id
            or linked.resource_id != resource.id or linked.revoked_at or not linked.verified_at
            or thread.identity_id != linked.id or thread.interface != 'company'
            or resource.organization_id != user.organization_id):
        raise HTTPException(403, 'A current verified employee link is required')
    instant = now()
    session = UserSession(user_id=user.id,
        session_token_hash=hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
        device_name='Telegram AI agent', ip_address=None, trusted_device=False,
        user_agent=json.dumps({'channel': 'telegram', 'resource_id': resource.id,
            'conversation_id': thread.id, 'identity_id': linked.id,
            'verified_at': utc(linked.verified_at).isoformat()}, separators=(',', ':')),
        status='Active', last_seen_at=instant, expires_at=instant + timedelta(minutes=20))
    db.add(session)
    db.flush()
    user._suite_session_id = session.id
    return session
