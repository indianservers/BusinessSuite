"""Failure routing never executes actions or broadens provider data sharing."""
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.ai_operator import provider_fallback as fallback,providers


def environment(monkeypatch):
    primary=SimpleNamespace(id=1,provider='gemini',model='primary',enabled=True,data_sharing_allowed=True)
    alternate=SimpleNamespace(id=2,provider='openai',model='alternate',enabled=True,data_sharing_allowed=True)
    db=object()  # Scope-authorized provider snapshots must never use ORM refresh.
    monkeypatch.setattr(fallback,'resolve_provider',lambda *args:alternate)
    monkeypatch.setattr(fallback.time,'monotonic',lambda:100)
    state={'deadline':130,'seconds':30,'primary':{'provider':'gemini','model':'primary'},
           'fallback':{'id':2,'provider':'openai','model':'alternate'},'used':False,'attempts':[]}
    return db,primary,alternate,state


@pytest.mark.parametrize('code',sorted(fallback.TRANSIENT))
def test_transient_failure_switches_once_with_shared_deadline_and_no_nested_retries(monkeypatch,code):
    db,primary,alternate,state=environment(monkeypatch);calls=[]
    def gateway(db,user,config,**kwargs):
        calls.append((config.provider,providers._request_attempts.get(),providers._request_deadline.get()))
        if config is primary:raise HTTPException(502,code)
        return {'summary':'Proposed only'}
    value,chosen=fallback.generate(db,object(),primary,workspace_id=9,state=state,gateway=gateway)
    assert value=={'summary':'Proposed only'} and chosen is alternate
    assert calls==[('gemini',1,115),('openai',1,130)]
    assert providers._request_attempts.get()==3 and providers._request_deadline.get() is None
    assert fallback.public(state)['fallback_used'] is True
    assert [a['status'] for a in state['attempts']]==['failed','success']
    assert 'id' not in fallback.public(state)['fallback']


@pytest.mark.parametrize('code',['PROVIDER_HTTP_401','PROVIDER_HTTP_403','PROVIDER_INVALID_OUTPUT','PROVIDER_CONNECTION_OR_KEY_ERROR','private raw error'])
def test_authentication_invalid_output_and_unknown_errors_do_not_switch(monkeypatch,code):
    db,primary,alternate,state=environment(monkeypatch);calls=[]
    def gateway(*args,**kwargs):
        calls.append(1);raise HTTPException(502,code)
    with pytest.raises(HTTPException):fallback.generate(db,object(),primary,workspace_id=9,state=state,gateway=gateway)
    assert len(calls)==1 and not state['used']
    assert state['attempts'][0]['error_code']=='PROVIDER_FAILED'


@pytest.mark.parametrize('change',['disabled','sharing','model'])
def test_fallback_is_revalidated_after_primary_failure(monkeypatch,change):
    db,primary,alternate,state=environment(monkeypatch);calls=[]
    def gateway(*args,**kwargs):
        calls.append(1)
        if change=='disabled':alternate.enabled=False
        elif change=='sharing':alternate.data_sharing_allowed=False
        else:alternate.model='changed'
        raise HTTPException(504,'PROVIDER_TIMEOUT')
    with pytest.raises(HTTPException) as exc:
        fallback.generate(db,object(),primary,workspace_id=9,state=state,gateway=gateway)
    assert exc.value.status_code==409 and len(calls)==1


def test_second_failure_is_terminal_and_expired_budget_never_calls_alternate(monkeypatch):
    db,primary,alternate,state=environment(monkeypatch);calls=[]
    def failed(db,user,config,**kwargs):
        calls.append(config.provider);raise HTTPException(504,'PROVIDER_TIMEOUT')
    with pytest.raises(HTTPException):fallback.generate(db,object(),primary,workspace_id=9,state=state,gateway=failed)
    assert calls==['gemini','openai']
    db,primary,alternate,state=environment(monkeypatch);calls=[]
    def expired(db,user,config,**kwargs):
        calls.append(config.provider)
        monkeypatch.setattr(fallback.time,'monotonic',lambda:140)
        raise HTTPException(504,'PROVIDER_TIMEOUT')
    with pytest.raises(HTTPException):fallback.generate(db,object(),primary,workspace_id=9,state=state,gateway=expired)
    assert calls==['gemini'] and fallback.public(state)['fallback_used'] is False
