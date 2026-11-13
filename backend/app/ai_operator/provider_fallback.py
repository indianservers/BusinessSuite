"""Explicit, bounded planning fallback. No business actions execute here."""
import time
from fastapi import HTTPException
from app.ai_operator.provider_scope import resolve_provider
from app.ai_operator.providers import planning_deadline, retry_budget

TRANSIENT = {'PROVIDER_TIMEOUT','PROVIDER_CIRCUIT_OPEN',
             *{f'PROVIDER_HTTP_{status}' for status in (408,429,500,502,503,504)}}


def validate(db,user,primary,provider,workspace_id):
    if primary is None or provider==primary.provider:
        raise HTTPException(422,'Choose a different connected cloud provider for fallback')
    return _identity(_configuration(db,user,provider,workspace_id))


def _configuration(db,user,provider,workspace_id):
    # The resolver executes a fresh, scope-authorized control-plane SELECT and
    # returns a snapshot, not an ORM entity subject to business-record filters.
    config=resolve_provider(db,user,provider,workspace_id)
    if not config or not config.enabled or not config.data_sharing_allowed:
        raise HTTPException(409,'Fallback provider is unavailable or data sharing is disabled in this scope')
    return config


def _identity(config):
    return {'id':config.id,'provider':config.provider,'model':config.model}


def start(db,user,primary,fallback):
    from app.ai_agents.security import company,limits
    seconds=min(45,limits(db,company(user))['max_seconds'])
    return {'deadline':time.monotonic()+seconds,'seconds':seconds,
            'primary':{'provider':primary.provider,'model':primary.model},
            'fallback':fallback,'used':False,'attempts':[]}


def public(state):
    return {'policy':'explicit-fallback-v1','primary':state['primary'],
            'fallback':{k:state['fallback'][k] for k in ('provider','model')},
            'fallback_used':any(a['provider']==state['fallback']['provider'] for a in state['attempts']),
            'attempts':[dict(a) for a in state['attempts']],
            'deadline_seconds':state['seconds'],'planning_only':True}


def generate(db,user,config,*,workspace_id,state,gateway,**kwargs):
    """At most one switch, with scoped configuration revalidated at that switch."""
    while True:
        remaining=state['deadline']-time.monotonic()
        if remaining<=0:raise HTTPException(504,'PROVIDER_TIMEOUT')
        # Reserve time for the explicitly selected alternative. No nested retries.
        deadline=time.monotonic()+remaining/2 if not state['used'] else state['deadline']
        attempt={'provider':config.provider,'model':config.model,'status':'failed'}
        state['attempts'].append(attempt)
        try:
            with planning_deadline(deadline),retry_budget(1):
                value=gateway(db,user,config,**kwargs)
            attempt['status']='success'
            return value,config
        except HTTPException as exc:
            code=exc.detail if isinstance(exc.detail,str) else 'PROVIDER_FAILED'
            attempt['error_code']=code if code in TRANSIENT else 'PROVIDER_FAILED'
            if state['used'] or code not in TRANSIENT:raise
            expected=state['fallback']
            candidate=_configuration(db,user,expected['provider'],workspace_id)
            fresh=_identity(candidate)
            if fresh!=expected:
                raise HTTPException(409,'Fallback configuration changed; prepare a new request')
            config=candidate
            state['used']=True
