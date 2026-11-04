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

    def upload_profile_jpeg(self, content):
        """Meta's resumable upload is separate from ordinary JSON Graph requests."""
        if not settings.CRM_WHATSAPP_APP_ID.isdecimal():
            raise MetaError('Configure the Meta app ID before uploading a profile photo')
        result = self.request('POST', settings.CRM_WHATSAPP_APP_ID+'/uploads', params={
            'file_name':'whatsapp-profile.jpg','file_length':len(content),'file_type':'image/jpeg'})
        session = result.get('id','')
        # The provider may append a signed query. Accept only its upload ID/signature
        # grammar and always pin the host; never treat it as an arbitrary URL.
        if not isinstance(session,str) or not re.fullmatch(r'upload:[A-Za-z0-9_+=%/.-]+(?:\?sig=[A-Za-z0-9_+=%/.-]+)?',session):
            raise MetaError('Meta did not return a valid upload session')
        try:
            response = httpx.post('https://graph.facebook.com/'+settings.CRM_WHATSAPP_API_VERSION+'/'+session,
                headers={'Authorization':'OAuth '+self.token,'file_offset':'0','Content-Type':'application/octet-stream'},content=content,timeout=30)
            data = response.json()
        except httpx.TransportError:
            raise MetaError('Profile photo upload could not be confirmed; refresh the profile before retrying',uncertain=True) from None
        except ValueError:
            raise MetaError('Meta returned an unreadable upload response') from None
        if response.is_error or not isinstance(data,dict) or not isinstance(data.get('h'),str):
            raise MetaError('Meta rejected the profile photo upload')
        return data['h']


class MetaWhatsAppProvider:
    name = 'meta'

    def __init__(self, token=None, phone_number_id=None):
        self.token, self.phone_number_id = token, phone_number_id

    def send(self, *, channel='whatsapp', to, body='', template=None, media=None, reply_to=None):
        if channel != 'whatsapp': raise MetaError('Meta transport supports WhatsApp only')
        token = self.token if self.token is not None else settings.CRM_WHATSAPP_ACCESS_TOKEN
        phone = self.phone_number_id or settings.CRM_WHATSAPP_PHONE_NUMBER_ID
        if not token or not phone: raise MetaError('WhatsApp access token and phone number ID are not configured')
        if not phone.isdecimal(): raise MetaError('Invalid WhatsApp sender ID')
        number = re.sub(r'[\s()+-]', '', to)
        if not re.fullmatch(r'[1-9]\d{6,14}', number): raise MetaError('Use an international recipient number including country code')
        payload = {'messaging_product':'whatsapp','to':number}
        if reply_to:
            payload['context']={'message_id':reply_to}
        if media:
            kind = media['kind']
            if kind not in {'image','document','audio','video','sticker'} or not str(media.get('id','')).isdecimal():
                raise MetaError('Invalid WhatsApp media')
            item = {'id':media['id']}
            if kind in {'image','document','video'} and body:
                if len(body)>1024: raise MetaError('Media captions may contain at most 1024 characters')
                item['caption']=body
            if kind=='document': item['filename']=media.get('filename','attachment')
            payload.update(type=kind, **{kind:item})
        elif template:
            payload.update(type='template', template=template)
        else:
            if not body.strip() or len(body)>4096: raise MetaError('WhatsApp text must contain 1–4096 characters')
            payload.update(type='text', text={'body':body,'preview_url':False})
        result = WhatsAppGraph(token).request('POST',phone+'/messages',payload=payload)
        messages = result.get('messages') or []
        if not messages or not messages[0].get('id'):
            raise MetaError('WhatsApp acceptance is uncertain; reconcile before retrying', uncertain=True)
        return 'accepted', messages[0]['id']
