"""Typed write workflows and bounded, resumable provider pages."""
import hashlib
import json
import re
from urllib.parse import urlencode, urlsplit, parse_qs
from app.apps.power_apps.integrations.contracts import IntegrationFailure

TARGETS={'facebook_lead_ads':('crm','leads'),'linkedin_lead_forms':('crm','leads'),
 'mailchimp':('crm','contacts'),'activecampaign':('crm','contacts'),'klaviyo':('crm','contacts'),
 'apollo':('crm','contacts'),'cloudtalk':('crm','contacts'),'surfe':('crm','contacts'),
 'trello':('pms','tasks'),'zendesk':('crm','activities'),'docusign':('crm','activities')}


def extend(profiles,a):
    pages={
      'facebook_lead_ads':('/v24.0/{resource_id}/leads','resource_id cursor'),
      'mailchimp':('/3.0/lists/{resource_id}/members','resource_id cursor'),
      'docusign':('/restapi/v2.1/accounts/{resource_id}/envelopes','resource_id cursor from_date'),
      'trello':('/1/boards/{resource_id}/cards','resource_id cursor'),
      'zendesk':('/api/v2/tickets.json','cursor'),
      'activecampaign':('/api/3/contacts','cursor'),
      'linkedin_lead_forms':('/rest/leadFormResponses','owner lead_type cursor'),
      'klaviyo':('/api/profiles','cursor'),
      'surfe':('/v2/people/enrich/{resource_id}','resource_id cursor'),
      'apollo':('/api/v1/contacts/search','cursor'),
      'cloudtalk':('/api/contacts/index.json','cursor'),
    }
    for key,(path,fields) in pages.items():
        profiles[key]['actions'].append(a('sync_page','Sync provider records','POST' if key=='apollo' else 'GET',path,fields,
            defaults={'cursor':'0'},transform='marketplace_page',read_only=True,force_write=key=='surfe'))
    writes={
      'mailchimp':a('upsert_contact','Sync contact to audience','PUT','/3.0/lists/{list_id}/members/{subscriber_hash}','list_id email first_name last_name',transform='marketplace_mailchimp'),
      'activecampaign':a('upsert_contact','Sync contact','POST','/api/3/contact/sync','email first_name last_name',transform='marketplace_activecampaign'),
      'klaviyo':a('upsert_contact','Sync profile','POST','/api/profile-import','email first_name last_name',transform='marketplace_klaviyo'),
      'trello':a('create_card','Create project card','POST','/1/cards','list_id title text',body={'idList':'list_id','name':'title','desc':'text'}),
      'zendesk':a('create_ticket','Create support ticket','POST','/api/v2/tickets.json','title text',transform='marketplace_zendesk'),
      'docusign':a('create_draft','Create contract draft from template','POST','/restapi/v2.1/accounts/{account_id}/envelopes','account_id template_id email name role_name',transform='marketplace_docusign'),
      'apollo':a('upsert_contact','Sync contact with deduplication','POST','/api/v1/contacts','email first_name last_name',transform='marketplace_apollo'),
      'cloudtalk':a('create_contact','Create call-centre contact','POST','/api/contacts/add.json','name email',transform='marketplace_cloudtalk'),
      'surfe':a('enrich_person','Enrich CRM contact (uses credits)','POST','/v2/people/enrich','first_name last_name company_domain',transform='marketplace_surfe'),
    }
    for key,action in writes.items(): profiles[key]['actions'].append(action)
    for key in ('mailchimp','activecampaign','klaviyo','apollo'):
        writes[key]['defaults']['last_name']=''
    writes['trello']['defaults']['text']=''


def build(conn,action,data,path,body):
    key=conn.connector_id
    if action=='sync_page':
        cursor=data.get('cursor','0')
        if len(cursor)>1000: raise IntegrationFailure('schema','Provider cursor is too long')
        query={}
        if key in {'mailchimp','activecampaign','linkedin_lead_forms','zendesk','cloudtalk','docusign','apollo'}:
            if not cursor.isdigit() or int(cursor)>10000000: raise IntegrationFailure('schema','Invalid numeric sync cursor')
            offset=int(cursor)
        if key=='facebook_lead_ads': query={'limit':50,**({'after':cursor} if cursor!='0' else {})}
        elif key=='mailchimp': query={'count':50,'offset':offset}
        elif key=='activecampaign': query={'limit':50,'offset':offset}
        elif key=='linkedin_lead_forms':
            if data['lead_type'] not in {'SPONSORED','EVENT','COMPANY','ORGANIZATION_PRODUCT'} or not re.fullmatch(r'\((organization|sponsoredAccount):urn:li:(organization|sponsoredAccount):[0-9]+\)',data['owner']):
                raise IntegrationFailure('schema','Choose a valid LinkedIn owner and lead type')
            query={'q':'owner','owner':data['owner'],'leadType':'(leadType:'+data['lead_type']+')','count':50,'start':offset}
        elif key=='zendesk': query={'per_page':50,'page':offset+1}
        elif key=='cloudtalk': query={'limit':50,'page':offset+1}
        elif key=='docusign':
            from datetime import date
            try: date.fromisoformat(data['from_date'])
            except ValueError: raise IntegrationFailure('schema','Enter an ISO envelope start date')
            query={'count':50,'start_position':offset,'from_date':data['from_date']}
        elif key=='trello': query={'limit':50,**({'before':cursor} if cursor!='0' else {})}
        elif key=='klaviyo': query={'page[size]':50,**({'page[cursor]':cursor} if cursor!='0' else {})}
        elif key=='apollo': body={'page':offset+1,'per_page':50}
        if query: path+='?'+urlencode(query)
    elif key=='mailchimp':
        path=path.replace('{subscriber_hash}',hashlib.md5(data['email'].strip().lower().encode()).hexdigest())
        body={'email_address':data['email'],'status_if_new':'unsubscribed','merge_fields':{'FNAME':data['first_name'],'LNAME':data['last_name']}}
    elif key=='activecampaign': body={'contact':{'email':data['email'],'firstName':data['first_name'],'lastName':data['last_name']}}
    elif key=='klaviyo': body={'data':{'type':'profile','attributes':{k:data[k] for k in ('email','first_name','last_name')}}}
    elif key=='zendesk': body={'ticket':{'subject':data['title'],'comment':{'body':data['text'],'public':False}}}
    elif key=='docusign': body={'templateId':data['template_id'],'templateRoles':[{'email':data['email'],'name':data['name'],'roleName':data['role_name']}],'status':'created'}
    elif key=='apollo': body={**{k:data[k] for k in ('email','first_name','last_name')},'run_dedupe':True}
    elif key=='cloudtalk': body={'name':data['name'],'emails':[{'email':data['email']}]}
    elif key=='surfe': body={'people':[{'firstName':data['first_name'],'lastName':data['last_name'],'companyDomain':data['company_domain'],'externalID':hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()}],'include':{'email':True,'mobile':False}}
    return path,body


def origin(conn,action):
    from app.apps.power_apps.integrations.marketplace_providers import DYNAMIC,validate_host
    if conn.connector_id=='docusign' and action!='test':
        return api_host(conn.config)
    return validate_host(conn.connector_id,conn.config) if conn.connector_id in DYNAMIC else None


def api_host(config):
    host=config.get('api_host','demo.docusign.net')
    if not isinstance(host,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,40}\.docusign\.net',host):
        raise IntegrationFailure('schema','Choose a verified DocuSign API hostname')
    return host


def page_result(conn,args,result):
    key=conn.connector_id;cursor=args.get('cursor','0');next_cursor=None
    if not isinstance(result,(dict,list)): raise IntegrationFailure('response','Invalid provider page')
    expected={'facebook_lead_ads':'data','mailchimp':'members','activecampaign':'contacts','linkedin_lead_forms':'elements','zendesk':'tickets','cloudtalk':'responseData','apollo':'contacts','docusign':'envelopes','klaviyo':'data'}
    if key in expected and (not isinstance(result,dict) or expected[key] not in result):
        raise IntegrationFailure('response','Provider response does not contain the requested record collection')
    if key=='trello' and not isinstance(result,list):
        raise IntegrationFailure('response','Expected a Trello card collection')
    if key=='surfe' and (not isinstance(result,dict) or not any(field in result for field in ('people','data','status'))):
        raise IntegrationFailure('response','Invalid enrichment response')
    if key=='facebook_lead_ads':
        rows=result.get('data',[])
        if result.get('paging',{}).get('next'): next_cursor=result.get('paging',{}).get('cursors',{}).get('after')
    elif key=='mailchimp':
        rows=result.get('members',[])
        if int(cursor)+len(rows)<int(result.get('total_items',0)): next_cursor=str(int(cursor)+len(rows))
    elif key=='activecampaign':
        rows=result.get('contacts',[])
        if int(cursor)+len(rows)<int(result.get('meta',{}).get('total',0)): next_cursor=str(int(cursor)+len(rows))
    elif key=='linkedin_lead_forms':
        rows=result.get('elements',[])
        if len(rows)==50: next_cursor=str(int(cursor)+len(rows))
    elif key=='zendesk':
        rows=result.get('tickets',[])
        if result.get('next_page'): next_cursor=str(int(cursor)+1)
    elif key=='cloudtalk':
        rows=result.get('responseData',{}).get('data',[])
        if len(rows)==50: next_cursor=str(int(cursor)+1)
    elif key=='apollo':
        rows=result.get('contacts',[])
        if int(cursor)+1<int(result.get('pagination',{}).get('total_pages',1)): next_cursor=str(int(cursor)+1)
    elif key=='docusign':
        rows=result.get('envelopes',[])
        if result.get('nextUri'): next_cursor=str(int(cursor)+len(rows))
    elif key=='trello':
        rows=result if isinstance(result,list) else result.get('cards',[])
        if len(rows)==50: next_cursor=str(rows[-1]['id'])
    elif key=='klaviyo':
        rows=result.get('data',[]);link=result.get('links',{}).get('next')
        if link:
            parsed=urlsplit(link)
            if parsed.hostname!='a.klaviyo.com' or parsed.path.rstrip('/')!='/api/profiles': raise IntegrationFailure('response','Unexpected Klaviyo pagination destination')
            next_cursor=parse_qs(parsed.query).get('page[cursor]',[None])[0]
    else:
        if str(result.get('status','')).upper() in {'PENDING','PROCESSING','IN_PROGRESS'}: raise IntegrationFailure('pending','Enrichment is still processing; retry later',retryable=True,retry_after=30)
        rows=result.get('people',result.get('data',[]))
    if not isinstance(rows,list) or len(rows)>1000: raise IntegrationFailure('response','Invalid or oversized provider page')
    if next_cursor is not None and (not rows or next_cursor==cursor): raise IntegrationFailure('response','Provider pagination did not advance')
    normalized=[normalize(key,row) for row in rows]
    return {'records':normalized,'next_cursor':next_cursor}


def normalize(key,row):
    if not isinstance(row,dict): raise IntegrationFailure('response','Invalid provider record')
    if key=='cloudtalk': row=row.get('Contact',row.get('contact',row))
    identity=row.get('id') or row.get('envelopeId') or row.get('externalID') or row.get('versionedLeadGenFormUrn')
    if not identity and key=='surfe': identity=row.get('linkedInUrl') or row.get('email')
    if not identity: raise IntegrationFailure('response','Provider record has no stable identity')
    result={'external_id':str(identity)}
    if key=='trello':
        result.update(task_key='TRELLO-'+str(identity),title=row.get('name',''),description=row.get('desc',''))
    elif key in {'docusign','zendesk'}:
        result.update(subject=(key+' #'+str(identity)+' '+str(row.get('emailSubject',row.get('subject',''))))[:180],activity_type='Note',body=str(row.get('description',row.get('status',''))))
    else:
        data=row.get('attributes',row)
        if key=='facebook_lead_ads': data={f.get('name'): (f.get('values') or [''])[0] for f in row.get('field_data',[])}
        if key=='linkedin_lead_forms':
            answers=row.get('formResponse',{}).get('answers',[])
            data={str(a.get('questionId')):a.get('answerDetails',{}).get('textQuestionAnswer',{}).get('answer','') for a in answers}
            data.update(row.get('leadMetadata',{}))
        first=data.get('first_name',data.get('firstName',data.get('merge_fields',{}).get('FNAME','')))
        last=data.get('last_name',data.get('lastName',data.get('merge_fields',{}).get('LNAME','')))
        name=data.get('full_name') or data.get('name') or ' '.join(v for v in [first,last] if v)
        email=data.get('email_address',data.get('email',''))
        if isinstance(email,list): email=(email[0].get('email','') if email and isinstance(email[0],dict) else '')
        if not email and data.get('emails'): email=data['emails'][0].get('email','') if isinstance(data['emails'][0],dict) else data['emails'][0]
        result.update(full_name=name,first_name=first or (name.split(' ')[0] if name else ''),last_name=last,email=email,phone=data.get('phone',data.get('phone_number','')),source=key)
        # Keep unmapped LinkedIn answers available for the existing mapping review.
        if key=='linkedin_lead_forms': result.update({k:str(v) for k,v in data.items() if k.isdigit()})
    return {k:str(v)[:16000] if v is not None else '' for k,v in result.items()}
