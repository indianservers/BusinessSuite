"""Media adapter for the existing WhatsApp connection and durable message store."""
import json
import re
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.shared.integrations import protect, reveal
from app.services.whatsapp import MetaError, WhatsAppGraph


# Application caps are deliberately bounded; audio/video codecs are checked by Meta.
MEDIA_TYPES = {
    'image/jpeg': ('image', 5), 'image/png': ('image', 5),
    'audio/aac': ('audio', 16), 'audio/mp4': ('audio', 16),
    'audio/mpeg': ('audio', 16), 'audio/amr': ('audio', 16), 'audio/ogg': ('audio', 16),
    'video/mp4': ('video', 16), 'video/3gpp': ('video', 16),
    'application/pdf': ('document', 16), 'text/plain': ('document', 16),
    'application/msword': ('document', 16), 'application/vnd.ms-excel': ('document', 16),
    'application/vnd.ms-powerpoint': ('document', 16),
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ('document', 16),
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ('document', 16),
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': ('document', 16),
    'image/webp': ('sticker', .5),
}
MAX_DOWNLOAD = 100 * 1024 * 1024


def filename(value):
    return re.sub(r'[^\w. ()-]', '_', str(value or 'attachment').replace('\\', '/').split('/')[-1])[:180] or 'attachment'


def metadata(message):
    payload=message.template_json
    value = payload.get('media') if message.kind != 'template' and isinstance(payload,dict) else None
    return value if isinstance(value, dict) else None


def upload(connection, token, content, mime, name):
    if mime not in MEDIA_TYPES:
        raise HTTPException(422, 'Choose a supported image, PDF, document, audio or video file')
    kind, limit = MEDIA_TYPES[mime]
    if not content or len(content) > limit * 1024 * 1024:
        raise HTTPException(422, f'This file type must contain data and be no larger than {limit:g} MB')
    # Reject a renamed active document/image before uploading it to the provider.
    signatures = {'image/png': b'\x89PNG\r\n\x1a\n', 'image/jpeg': b'\xff\xd8\xff', 'application/pdf': b'%PDF-'}
    if mime in signatures and not content.startswith(signatures[mime]):
        raise HTTPException(422, 'The file content does not match its media type')
    if not connection.phone_number_id.isdecimal() or not re.fullmatch(r'v\d+\.\d+', settings.CRM_WHATSAPP_API_VERSION):
        raise MetaError('Invalid WhatsApp sender configuration')
    try:
        response = httpx.post(f'https://graph.facebook.com/{settings.CRM_WHATSAPP_API_VERSION}/{connection.phone_number_id}/media',
            headers={'Authorization': 'Bearer '+token}, data={'messaging_product': 'whatsapp', 'type': mime},
            files={'file': (filename(name), content, mime)}, timeout=30)
        result = response.json()
    except (httpx.TransportError, ValueError):
        raise MetaError('Media upload could not be confirmed. No WhatsApp message was sent.') from None
    media_id = result.get('id') if isinstance(result, dict) else None
    if response.is_error or not isinstance(media_id, str) or not media_id.isdecimal():
        raise MetaError('Meta rejected this media upload. Check the file format and codec.')
    return {'id': media_id, 'kind': kind, 'mimeType': mime, 'filename': filename(name), 'size': len(content)}


def upload_token(user, contact, connection, media):
    from app.services import whatsapp_workspace as wa
    return protect(json.dumps({'user': user.id, 'organization': contact.organization_id, 'contact': contact.id,
        'connection': connection.id, 'expires': wa.now().timestamp()+86400, 'media': media}))


def verify_upload(value, user, contact, connection):
    from app.services import whatsapp_workspace as wa
    try:
        data = json.loads(reveal(value))
        if (data['user'], data['organization'], data['contact'], data['connection']) != (user.id, contact.organization_id, contact.id, connection.id) or data['expires'] < wa.now().timestamp():
            raise ValueError()
        return data['media']
    except Exception:
        raise HTTPException(422, 'Attachment expired or belongs to another conversation. Attach the file again.') from None


def download(connection, token, media):
    """Return a bounded provider response. Never accept a URL supplied by the caller."""
    media_id = str(media.get('id', ''))
    if not media_id.isdecimal():
        raise HTTPException(404, 'This message has no downloadable media')
    result = WhatsAppGraph(token).request('GET', media_id, params={'phone_number_id': connection.phone_number_id})
    url = result.get('url', '')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443) or not (parsed.hostname == 'lookaside.fbsbx.com' or (parsed.hostname or '').endswith('.fbcdn.net')):
        raise MetaError('Meta returned an unsupported media download location')
    mime = str(result.get('mime_type') or media.get('mimeType') or '')
    if mime not in MEDIA_TYPES:
        raise HTTPException(415, 'This media type is not supported for preview or download')
    try:
        with httpx.stream('GET', url, headers={'Authorization': 'Bearer '+token}, timeout=30, follow_redirects=False) as response:
            if response.status_code != 200:
                raise MetaError('This media is unavailable or has expired at Meta')
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_DOWNLOAD:
                    raise HTTPException(413, 'This media exceeds the 100 MB download limit')
                chunks.append(chunk)
            return b''.join(chunks), mime
    except httpx.TransportError:
        raise MetaError('Media download interrupted. Try loading the attachment again.') from None
