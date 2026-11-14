"""Bounded media transport, not an API or an authorization boundary.

Callers must resolve the current scoped provider, verify media capability grants
and exact reviewed input, and journal execution before calling this adapter.
Only supplied bytes are processed; no URL retrieval, tools or automatic retries.
Artifact persistence and sharing remain the existing artifact service's job.
"""
import base64
import binascii
from dataclasses import dataclass
import io
import json
import wave
import httpx
from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field,FiniteFloat,model_validator

IMAGE_MODELS={'gemini-3.1-flash-image','gemini-3.1-flash-lite-image','gemini-3-pro-image'}
DEFAULT_IMAGE_MODEL='gemini-3.1-flash-image'
IMAGE_MIMES={'PNG':'image/png','JPEG':'image/jpeg','WEBP':'image/webp'}
MAX_INPUT=5_000_000
MAX_OUTPUT=8_000_000


class MediaProviderError(HTTPException):
    def __init__(self,status,quota_limit=None,retry_after=None):
        super().__init__(502,'MEDIA_PROVIDER_HTTP_'+str(status))
        self.provider_status=status;self.quota_limit=quota_limit;self.retry_after=retry_after


def provider_error(response):
    """Keep only bounded quota numbers; never retain provider error text/keys."""
    quota=[];retry=None
    try:
        value=response.headers.get('Retry-After','')
        if value.isdigit() and int(value)<=3600:retry=int(value)
        raw=bytearray()
        for chunk in response.iter_bytes():
            raw.extend(chunk)
            if len(raw)>32768:break
        if len(raw)<=32768:
            error=json.loads(raw).get('error',{})
            for detail in error.get('details',[])[:10]:
                for violation in detail.get('violations',[])[:10]:
                    value=violation.get('quotaValue')
                    if isinstance(value,str) and value.isdigit() and int(value)<=1_000_000_000:quota.append(int(value))
                value=detail.get('retryDelay','')
                if isinstance(value,str) and value.endswith('s'):
                    number=float(value[:-1])
                    if 0<=number<=3600:retry=max(1,int(number)+1)
    except (ValueError,TypeError,KeyError,AttributeError):pass
    return MediaProviderError(response.status_code,min(quota) if quota else None,retry)


@dataclass(frozen=True)
class ImageResult:
    content:bytes
    mime_type:str
    width:int
    height:int
    caption:str
    model:str
    usage:dict


class Segment(BaseModel):
    model_config=ConfigDict(extra='forbid')
    start_seconds:FiniteFloat=Field(ge=0,le=300)
    end_seconds:FiniteFloat=Field(ge=0,le=300)
    text:str=Field(min_length=1,max_length=2000)

    @model_validator(mode='after')
    def order(self):
        if self.end_seconds<self.start_seconds or not self.text.strip():raise ValueError('Invalid transcript segment')
        return self


class Transcript(BaseModel):
    model_config=ConfigDict(extra='forbid')
    text:str=Field(max_length=20000)
    language:str=Field(min_length=1,max_length=60)
    segments:list[Segment]=Field(max_length=200)
    notes:list[str]=Field(max_length=10)

    @model_validator(mode='after')
    def bounded(self):
        if any(len(value)>500 for value in self.notes):raise ValueError('Transcript notes too long')
        if self.segments and not self.text.strip():raise ValueError('Missing transcript text')
        if any(a.start_seconds>b.start_seconds for a,b in zip(self.segments,self.segments[1:])):raise ValueError('Unordered transcript')
        return self


def image_bytes(content,mime=None):
    """Validate pixels before decoding, then strip ancillary image metadata."""
    from PIL import Image,ImageOps,UnidentifiedImageError
    if not isinstance(content,bytes) or not content or len(content)>MAX_OUTPUT:raise HTTPException(413,'MEDIA_IMAGE_SIZE_LIMIT')
    try:
        with Image.open(io.BytesIO(content)) as source:
            actual=IMAGE_MIMES.get(source.format)
            if not actual or mime is not None and mime!=actual:raise ValueError('Unsupported image encoding')
            width,height=source.size
            if min(width,height)<1 or max(width,height)>4096 or width*height>16_777_216:raise ValueError('Image pixel limit')
            source.load();oriented=ImageOps.exif_transpose(source).convert('RGBA')
            # A fresh raster prevents Pillow from carrying EXIF/ICC/private PNG
            # metadata through conversion. Preserve the displayed orientation.
            clean=Image.new('RGBA',oriented.size);clean.paste(oriented);width,height=clean.size
            output=io.BytesIO();clean.save(output,format='PNG')
            value=output.getvalue()
            if len(value)>MAX_OUTPUT:raise HTTPException(413,'MEDIA_IMAGE_SIZE_LIMIT')
            return value,width,height
    except (ValueError,OSError,UnidentifiedImageError,Image.DecompressionBombError):raise HTTPException(422,'MEDIA_INVALID_IMAGE') from None


def wav_duration(content):
    if not isinstance(content,bytes) or not content or len(content)>MAX_INPUT:raise HTTPException(413,'MEDIA_AUDIO_SIZE_LIMIT')
    try:
        with wave.open(io.BytesIO(content),'rb') as audio:
            rate=audio.getframerate();frames=audio.getnframes();channels=audio.getnchannels();width=audio.getsampwidth()
            if audio.getcomptype()!='NONE' or channels not in (1,2) or width not in (1,2,3,4) or not 8000<=rate<=48000 or not frames or frames/rate>300:raise ValueError('Unsupported PCM audio')
            if len(audio.readframes(frames))!=frames*channels*width:raise ValueError('Truncated audio')
            return frames/rate
    except (wave.Error,EOFError,ValueError):raise HTTPException(422,'MEDIA_INVALID_WAV') from None


def _post(config,model,body,seconds):
    if config.provider!='gemini' or not config.enabled or not config.data_sharing_allowed:raise HTTPException(409,'MEDIA_PROVIDER_UNAVAILABLE')
    if not isinstance(model,str) or not model.startswith('gemini-') or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-.' for c in model):raise HTTPException(422,'MEDIA_UNSUPPORTED_MODEL')
    raw=json.dumps(body,ensure_ascii=False).encode('utf-8')
    if len(raw)>16_000_000:raise HTTPException(413,'MEDIA_REQUEST_SIZE_LIMIT')
    from app.ai_operator.providers import cipher
    try:
        key=cipher().decrypt(config.encrypted_key.encode()).decode()
        with httpx.Client(timeout=max(1,min(45,seconds)),follow_redirects=False) as client:
            with client.stream('POST',f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                headers={'x-goog-api-key':key,'Content-Type':'application/json'},content=raw) as response:
                if response.status_code!=200:raise provider_error(response)
                content=bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content)>12_000_000:raise HTTPException(502,'MEDIA_RESPONSE_SIZE_LIMIT')
                data=json.loads(content)
        if data.get('promptFeedback',{}).get('blockReason'):raise HTTPException(422,'MEDIA_OUTPUT_BLOCKED')
        candidates=data.get('candidates',[])
        if len(candidates)!=1 or candidates[0].get('finishReason')!='STOP':raise HTTPException(502,'MEDIA_INCOMPLETE_OUTPUT')
        parts=candidates[0]['content']['parts']
        if not isinstance(parts,list) or not parts or len(parts)>20 or any(not isinstance(part,dict) or any(key in part for key in ('fileData','functionCall','executableCode','codeExecutionResult')) for part in parts):raise ValueError('Unsupported response parts')
        usage={key:value for key,value in data.get('usageMetadata',{}).items() if key in {'promptTokenCount','candidatesTokenCount','thoughtsTokenCount'} and type(value) is int and 0<=value<=10_000_000}
        return parts,usage
    except InvalidToken:raise HTTPException(409,'MEDIA_PROVIDER_UNAVAILABLE') from None
    except httpx.TimeoutException:raise HTTPException(504,'MEDIA_PROVIDER_TIMEOUT') from None
    except httpx.RequestError:raise HTTPException(502,'MEDIA_PROVIDER_CONNECTION_ERROR') from None
    except (ValueError,KeyError,TypeError,AttributeError):raise HTTPException(502,'MEDIA_INVALID_OUTPUT') from None


def generate_image(config,prompt,*,model=DEFAULT_IMAGE_MODEL,references=(),aspect_ratio='1:1',seconds=45):
    if model not in IMAGE_MODELS:raise HTTPException(422,'MEDIA_UNSUPPORTED_IMAGE_MODEL')
    if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>4000:raise HTTPException(422,'MEDIA_INVALID_PROMPT')
    if len(references)>3 or aspect_ratio not in {'1:1','16:9','9:16','4:3','3:4'}:raise HTTPException(422,'MEDIA_IMAGE_LIMIT')
    from app.ai_agents.services.advanced_security import AiDataRedactionService
    parts=[{'text':AiDataRedactionService().redact_text(prompt)}]
    for content,mime in references:
        if len(content)>MAX_INPUT:raise HTTPException(413,'MEDIA_IMAGE_SIZE_LIMIT')
        validated,_,_=image_bytes(content,mime)
        parts.append({'inlineData':{'mimeType':'image/png','data':base64.b64encode(validated).decode('ascii')}})
    body={'contents':[{'role':'user','parts':parts}], 'generationConfig':{'candidateCount':1,'responseModalities':['IMAGE'],
        'maxOutputTokens':min(config.max_tokens,8192),'imageConfig':{'aspectRatio':aspect_ratio,'imageSize':'1K'}}}
    result,usage=_post(config,model,body,seconds)
    images=[p['inlineData'] for p in result if p.get('inlineData') and not p.get('thought')]
    if len(images)!=1:raise HTTPException(502,'MEDIA_EXPECTED_ONE_IMAGE')
    try:content=base64.b64decode(images[0]['data'],validate=True)
    except (ValueError,KeyError,TypeError,binascii.Error):raise HTTPException(502,'MEDIA_INVALID_IMAGE_OUTPUT') from None
    try:content,width,height=image_bytes(content,images[0].get('mimeType'))
    except HTTPException:raise HTTPException(502,'MEDIA_INVALID_IMAGE_OUTPUT') from None
    caption='\n'.join(p['text'] for p in result if isinstance(p.get('text'),str) and not p.get('thought'))[:2000]
    return ImageResult(content,'image/png',width,height,caption,model,usage)


def transcribe_wav(config,content,*,seconds=45):
    duration=wav_duration(content)
    from app.ai_operator.prompt_registry import render
    instruction,_=render('media_transcription',Transcript.model_json_schema())
    body={'contents':[{'role':'user','parts':[{'text':instruction},
        {'inlineData':{'mimeType':'audio/wav','data':base64.b64encode(content).decode('ascii')}}]}],
        # The account's 3.5 Flash Lite audio path rejects this full JSON Schema
        # in responseJsonSchema (HTTP 400). Keep the schema in the versioned
        # instruction, request JSON mode once, and validate strictly server-side.
        'generationConfig':{'responseMimeType':'application/json','maxOutputTokens':min(config.max_tokens,8192)}}
    parts,usage=_post(config,config.model,body,seconds)
    if any(p.get('inlineData') for p in parts):raise HTTPException(502,'MEDIA_INVALID_TRANSCRIPT')
    try:result=Transcript.model_validate(json.loads(''.join(p['text'] for p in parts if isinstance(p.get('text'),str) and not p.get('thought'))))
    except (ValueError,TypeError):raise HTTPException(502,'MEDIA_INVALID_TRANSCRIPT') from None
    if any(s.end_seconds>duration+.5 for s in result.segments):raise HTTPException(502,'MEDIA_INVALID_TRANSCRIPT_TIMESTAMPS')
    return result,usage
