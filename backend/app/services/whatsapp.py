"""Meta Cloud API transport with server-only deployment or customer credentials."""
import logging
import re
import httpx
from app.core.config import settings


class GraphLogFilter(logging.Filter):
    def filter(self, record):
        # OAuth code exchange has provider-required secrets in query parameters.
        if isinstance(record.args, tuple):
            record.args = tuple(str(v).partition('?')[0] if str(v).startswith('https://graph.facebook.com/') else v for v in record.args)
        return True


if not any(isinstance(f, GraphLogFilter) for f in logging.getLogger('httpx').filters):
    logging.getLogger('httpx').addFilter(GraphLogFilter())


class MetaError(RuntimeError):
    def __init__(self, message, code=None, uncertain=False):
        super().__init__(message)
        self.code, self.uncertain = code, uncertain


class WhatsAppGraph:
    def __init__(self, token):
        self.token = token

    def request(self, method, path, *, params=None, payload=None):
        if not re.fullmatch(r'v\d+\.\d+', settings.CRM_WHATSAPP_API_VERSION):
            raise MetaError('Invalid WhatsApp API version')
        if not re.fullmatch(r'[A-Za-z0-9_/-]+', path):
            raise MetaError('Invalid Meta resource')
        kwargs = {'headers': {'Authorization': 'Bearer '+self.token}, 'timeout': 20}
        if params is not None: kwargs['params'] = params
        if payload is not None: kwargs['json'] = payload
        try:
            response = getattr(httpx, method.lower())('https://graph.facebook.com/'+settings.CRM_WHATSAPP_API_VERSION+'/'+path, **kwargs)
        except httpx.TransportError:
            raise MetaError('Meta response is uncertain; reconcile before retrying', uncertain=True) from None
        try:
            result = response.json()
            if not isinstance(result, dict): raise ValueError()
        except ValueError:
            raise MetaError('Meta response is unreadable; reconcile before retrying', uncertain=True) from None
        if response.is_error or result.get('error'):
            code = str(result.get('error', {}).get('code', 'unknown'))[:20]
            raise MetaError(f'Meta rejected request (HTTP {response.status_code}, code {code})', code=code, uncertain=response.status_code>=500)
        return result


class MetaWhatsAppProvider:
    name = 'meta'

    def __init__(self, token=None, phone_number_id=None):
        self.token, self.phone_number_id = token, phone_number_id

    def send(self, *, channel='whatsapp', to, body='', template=None):
        if channel != 'whatsapp': raise MetaError('Meta transport supports WhatsApp only')
        token = self.token if self.token is not None else settings.CRM_WHATSAPP_ACCESS_TOKEN
        phone = self.phone_number_id or settings.CRM_WHATSAPP_PHONE_NUMBER_ID
        if not token or not phone: raise MetaError('WhatsApp access token and phone number ID are not configured')
        if not phone.isdecimal(): raise MetaError('Invalid WhatsApp sender ID')
        number = re.sub(r'[\s()+-]', '', to)
        if not re.fullmatch(r'[1-9]\d{6,14}', number): raise MetaError('Use an international recipient number including country code')
        payload = {'messaging_product':'whatsapp','to':number}
        if template:
            payload.update(type='template', template=template)
        else:
            if not body.strip() or len(body)>4096: raise MetaError('WhatsApp text must contain 1–4096 characters')
            payload.update(type='text', text={'body':body,'preview_url':False})
        result = WhatsAppGraph(token).request('POST',phone+'/messages',payload=payload)
        messages = result.get('messages') or []
        if not messages or not messages[0].get('id'):
            raise MetaError('WhatsApp acceptance is uncertain; reconcile before retrying', uncertain=True)
        return 'accepted', messages[0]['id']
