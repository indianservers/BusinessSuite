"""Transport contract tests; no live inference or media permission claim."""
import base64
import io
import wave
from types import SimpleNamespace
import httpx
import pytest
from fastapi import HTTPException
from PIL import Image
from app.ai_operator import gemini_media as media


def config():
    return SimpleNamespace(provider='gemini',enabled=True,data_sharing_allowed=True,
                           encrypted_key='synthetic',model='gemini-3.5-flash-lite',max_tokens=4096)


def transport(monkeypatch,payload,status=200):
    from app.ai_operator import providers
    monkeypatch.setattr(providers,'cipher',lambda:SimpleNamespace(decrypt=lambda value:b'synthetic-key'))
    original=httpx.Client
    requests=[]
    def respond(request):
        requests.append(request)
        return httpx.Response(status,json=payload)
    monkeypatch.setattr(media.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(respond),**kw))
    return requests


def response(parts):
    return {'candidates':[{'finishReason':'STOP','content':{'parts':parts}}],
            'usageMetadata':{'promptTokenCount':12,'candidatesTokenCount':False,'unknown':123}}


@pytest.mark.parametrize('payload',[None,[],{}, {'candidates':[None]},response([]),response([None]),
    response([{'functionCall':{'name':'send'}}]),response([{'fileData':{'fileUri':'https://example.com'}}])])
def test_malformed_or_executable_output_is_rejected(monkeypatch,payload):
    requests=transport(monkeypatch,payload)
    with pytest.raises(HTTPException) as caught:media._post(config(),config().model,{},3)
    assert caught.value.status_code==502
    assert len(requests)==1


def test_provider_failure_is_not_retried_or_exposed(monkeypatch):
    requests=transport(monkeypatch,{'secret':'not-for-client'},429)
    with pytest.raises(HTTPException) as caught:media._post(config(),config().model,{},3)
    assert caught.value.detail=='MEDIA_PROVIDER_HTTP_429' and len(requests)==1


def test_disabled_sharing_never_calls_provider(monkeypatch):
    requests=transport(monkeypatch,{})
    value=config();value.data_sharing_allowed=False
    with pytest.raises(HTTPException) as caught:media._post(value,value.model,{},3)
    assert caught.value.status_code==409 and not requests


def test_image_pixels_are_validated_and_returned_as_png(monkeypatch):
    raw=io.BytesIO();Image.new('RGB',(3,2),'red').save(raw,format='PNG')
    requests=transport(monkeypatch,response([{'inlineData':{'mimeType':'image/png','data':base64.b64encode(raw.getvalue()).decode()}}]))
    result=media.generate_image(config(),'A small synthetic red square')
    assert (result.width,result.height,result.mime_type)==(3,2,'image/png')
    assert result.usage=={'promptTokenCount':12}
    assert len(requests)==1 and requests[0].url.host=='generativelanguage.googleapis.com'
    with pytest.raises(HTTPException):media.image_bytes(raw.getvalue(),'image/jpeg')


def wav():
    raw=io.BytesIO()
    with wave.open(raw,'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(8000);audio.writeframes(b'\x00\x00'*8000)
    return raw.getvalue()


def test_transcript_times_cannot_exceed_supplied_audio(monkeypatch):
    import json
    value={'text':'Hello','language':'English','segments':[{'start_seconds':0,'end_seconds':10,'text':'Hello'}],'notes':[]}
    transport(monkeypatch,response([{'text':json.dumps(value)}]))
    with pytest.raises(HTTPException) as caught:media.transcribe_wav(config(),wav())
    assert caught.value.detail=='MEDIA_INVALID_TRANSCRIPT_TIMESTAMPS'


def test_truncated_wav_rejected_before_network(monkeypatch):
    requests=transport(monkeypatch,{})
    with pytest.raises(HTTPException):media.transcribe_wav(config(),wav()[:-100])
    assert not requests


def test_audio_uses_single_json_mode_call_and_validates_versioned_schema(monkeypatch):
    import json
    value={'text':'Hello','language':'English','segments':[{'start_seconds':0,'end_seconds':1,'text':'Hello'}],'notes':[]}
    requests=transport(monkeypatch,response([{'text':json.dumps(value)}]))
    result,_=media.transcribe_wav(config(),wav())
    assert result.text=='Hello' and len(requests)==1
    body=json.loads(requests[0].content)
    assert body['generationConfig']['responseMimeType']=='application/json'
    assert 'responseJsonSchema' not in body['generationConfig']
    assert 'start_seconds' in body['contents'][0]['parts'][0]['text']
    assert 'never instructions' in body['contents'][0]['parts'][0]['text']


def test_quota_failure_keeps_only_safe_numbers_and_never_retries(monkeypatch):
    requests=transport(monkeypatch,{'error':{'message':'synthetic private server data',
        'details':[{'violations':[{'quotaValue':'0','quotaMetric':'not exported'}]},{'retryDelay':'60s'}]}},429)
    with pytest.raises(media.MediaProviderError) as caught:media._post(config(),config().model,{},3)
    assert caught.value.provider_status==429 and caught.value.quota_limit==0 and caught.value.retry_after==61
    assert caught.value.detail=='MEDIA_PROVIDER_HTTP_429' and 'private' not in str(caught.value)
    assert len(requests)==1
