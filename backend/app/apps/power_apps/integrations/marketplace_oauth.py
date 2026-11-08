"""Provider-specific OAuth parameters; state, ownership and refresh live in oauth.py."""
import base64
import json
from urllib.parse import urlencode, urlsplit
from fastapi import HTTPException
from app.core.config import settings
from app.apps.power_apps.integrations.contracts import IntegrationFailure
from app.apps.power_apps.integrations.transport import HttpTransport, EgressPolicy

# Read and write scopes are separate so a read connection never requests write access.
PROVIDERS = {
 'facebook_lead_ads':dict(name='facebook',authorize='https://www.facebook.com/v24.0/dialog/oauth',token='https://graph.facebook.com/v24.0/oauth/access_token',pkce=False,separator=',',read=['pages_show_list','pages_read_engagement','leads_retrieval'],write=[]),
 'mailchimp':dict(name='mailchimp',authorize='https://login.mailchimp.com/oauth2/authorize',token='https://login.mailchimp.com/oauth2/token',pkce=False,read=[],write=[]),
 'docusign':dict(name='docusign',authorize='/oauth/auth',token='/oauth/token',pkce=True,basic=True,read=['signature'],write=[]),
 'trello':dict(name='trello',authorize='https://auth.atlassian.com/authorize',token='https://auth.atlassian.com/oauth/token',pkce=True,json=True,read=['read:member:trello','read:board:trello','read:card:trello','offline_access'],write=['write:card:trello']),
 'zendesk':dict(name='zendesk',authorize='/oauth/authorizations/new',token='/oauth/tokens',pkce=True,read=['read'],write=['write']),
 'linkedin_lead_forms':dict(name='linkedin',authorize='https://www.linkedin.com/oauth/v2/authorization',token='https://www.linkedin.com/oauth/v2/accessToken',pkce=False,read=['r_marketing_leadgen_automation'],write=[]),
 'klaviyo':dict(name='klaviyo',authorize='https://www.klaviyo.com/oauth/authorize',token='https://a.klaviyo.com/oauth/token',pkce=True,basic=True,read=['accounts:read','profiles:read','lists:read'],write=['profiles:write']),
 'apollo':dict(name='apollo',authorize='https://app.apollo.io/#/oauth/authorize',token='https://app.apollo.io/api/v1/oauth/token',pkce=False,read=['users_list','contacts_search','read_user_profile'],write=['contacts_write']),
}


def config(key, connection=None):
    spec=PROVIDERS[key]
    client=getattr(settings,'POWER_'+spec['name'].upper()+'_CLIENT_ID','')
    secret=getattr(settings,'POWER_'+spec['name'].upper()+'_CLIENT_SECRET','')
    redirect=settings.POWER_OAUTH_REDIRECT_URI
    expected=settings.BACKEND_PUBLIC_URL.rstrip('/')+'/api/v1/power-apps/integrations/oauth/callback'
    if not client or not secret or redirect!=expected or (urlsplit(redirect).scheme!='https' and settings.ENVIRONMENT!='test'):
        raise HTTPException(503,'Configure this provider OAuth application and exact secure callback URI first')
    result={**spec,'client_id':client,'secret':secret,'redirect':redirect,'revoke':None,'connector_id':key}
    if key in {'docusign','zendesk'}:
        from app.apps.power_apps.integrations.marketplace_providers import validate_host
        host=validate_host(key,connection.config) if connection else ('account-d.docusign.com' if key=='docusign' else 'example.zendesk.com')
        result['authorize']='https://'+host+spec['authorize'];result['token']='https://'+host+spec['token']
    return result


def request_token(config, fields):
    fields=dict(fields)
    if not config.get('pkce'): fields.pop('code_verifier',None)
    headers={'Content-Type':'application/x-www-form-urlencoded'}
    if config.get('basic'):
        headers['Authorization']='Basic '+base64.b64encode((config['client_id']+':'+config['secret']).encode()).decode()
        fields.pop('client_secret',None)
        if config['connector_id']=='klaviyo': fields.pop('client_id',None)
    if config['connector_id'] in {'mailchimp','facebook_lead_ads'}: fields.pop('scope',None)
    if config.get('json'):
        headers['Content-Type']='application/json'; body=json.dumps(fields).encode()
    else: body=urlencode(fields).encode()
    response=HttpTransport(EgressPolicy([urlsplit(config['token']).hostname])).request('POST',config['token'],headers,body,timeout=10)
    if response.status!=200:
        raise IntegrationFailure('oauth','Provider authorization failed; reconnect before retrying',http_status=response.status)
    try:
        tokens=json.loads(response.body)
        if not isinstance(tokens.get('access_token'),str) or not tokens['access_token'] or tokens.get('error'): raise ValueError()
        return tokens
    except (ValueError,TypeError,KeyError):
        raise IntegrationFailure('oauth','Provider returned an invalid token response') from None


def bind_account(conn,credential,tokens):
    if conn.connector_id=='docusign':
        host=conn.config['provider_host']
        response=HttpTransport(EgressPolicy([host])).request('GET','https://'+host+'/oauth/userinfo',{'Authorization':'Bearer '+tokens['access_token']},timeout=10)
        try:
            info=json.loads(response.body)
            accounts=info['accounts']
            selected=next((a for a in accounts if a['account_id']==conn.config.get('account_id')),None)
            selected=selected or next((a for a in accounts if a.get('is_default')),None) or (accounts[0] if len(accounts)==1 else None)
            if response.status!=200 or not selected: raise ValueError()
            api_host=urlsplit(selected['base_uri']).hostname
            from app.apps.power_apps.integrations.marketplace_actions import api_host as validate_api
            validate_api({'api_host':api_host})
            conn.config={**conn.config,'api_host':api_host,'account_id':selected['account_id']};credential.hosts=[host,api_host]
        except (ValueError,KeyError,TypeError,IntegrationFailure):
            raise IntegrationFailure('oauth','Select an accessible DocuSign account before authorizing') from None
        return
    if conn.connector_id!='mailchimp': return
    response=HttpTransport(EgressPolicy(['login.mailchimp.com'])).request('GET','https://login.mailchimp.com/oauth2/metadata',{'Authorization':'OAuth '+tokens['access_token']},timeout=10)
    try:
        value=json.loads(response.body)
        if response.status!=200: raise ValueError()
        host=str(value['dc'])+'.api.mailchimp.com'
        from app.apps.power_apps.integrations.marketplace_providers import validate_host
        validate_host('mailchimp',{'provider_host':host})
        conn.config={**conn.config,'provider_host':host};credential.hosts=[host]
    except (ValueError,KeyError,TypeError,HTTPException):
        raise IntegrationFailure('oauth','Mailchimp account data centre could not be verified') from None


def install(registry):
    for key,spec in PROVIDERS.items():
        manifest=registry[key]
        manifest.authentication=['oauth2',*manifest.authentication]
        manifest.oauth_scopes=spec['read'];manifest.oauth_write_scopes=spec['write']
