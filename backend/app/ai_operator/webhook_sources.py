"""Reviewed agent bindings to the existing signed, native-record webhook ingress."""
from fastapi import HTTPException
from app.apps.automation.models import AutomationWebhookEndpoint
from app.models.user import User
from app.ai_agents.security import company
from app.shared import webhook_receipts
from app.shared.contracts import RECORDS,service_identity

MODULES={'CRM':'crm','PMS':'project_management','HRMS':'hrms','SRM':'srm','FAM':'fam'}
EVENTS={name.lower()+'.webhook_received':name for name in MODULES}


def endpoint(db,user,ident,module,event=None,expected=None):
    from app.access.api import admin,company_access
    admin(user,db);company_access(db,user,company(user))
    row=db.query(AutomationWebhookEndpoint).filter_by(id=ident,organization_id=company(user),is_active=True).populate_existing().first()
    if not row:raise HTTPException(404,'Signed webhook endpoint is unavailable')
    config=row.event_types_json;native=MODULES[module]
    if not isinstance(config,dict) or type(config.get('runAsUserId')) is not int or config['runAsUserId']<1:
        raise HTTPException(422,'Webhook execution identity is not configured')
    names=config.get('events')
    if not isinstance(names,list) or not 1<=len(names)<=20 or any(not isinstance(n,str) or not 1<=len(n)<=120 for n in names):
        raise HTTPException(422,'Configure bounded webhook event names first')
    if row.target_url!='internal:'+native or config.get('module')!=native or (native,config.get('entity')) not in RECORDS:
        raise HTTPException(422,'Choose a registered record webhook for this agent module')
    if not row.secret_ref:raise HTTPException(409,'Configure signed webhook credentials first')
    if event is not None and event not in config.get('events',[]):raise HTTPException(422,'The webhook does not admit this event name')
    service_identity(db,db.get(User,config.get('runAsUserId')),company(user),native)
    value={**webhook_receipts.binding(row),'module':native,'entity':config['entity'],'run_as_user_id':config['runAsUserId']}
    if expected is not None and value!=expected:raise HTTPException(409,'Webhook identity or configuration changed; prepare a fresh event review')
    return row,value


def record_reference(db,user,data,source):
    module=EVENTS[data['spec']['event']]
    row,_=endpoint(db,user,data['spec']['webhook_endpoint_id'],module,data['spec']['webhook_event'],data['source_binding'])
    if not webhook_receipts.verified(row,source):raise HTTPException(409,'Signed webhook admission proof is unavailable or changed')
    if source.organization_id!=data['company_id'] or source.actor_id!=row.event_types_json['runAsUserId'] or source.event_type!=data['spec']['webhook_event']:
        raise HTTPException(409,'Webhook event identity changed')
    from app.shared.gateway import read_record
    record=read_record(db,user,data['company_id'],source.module_key,source.entity_type,source.entity_id)
    if module=='PMS':
        project=source.entity_id if source.entity_type=='project' else record.get('project_id')
        from app.apps.project_management.models import PMSProject
        parent=db.get(PMSProject,project) if project else None
        if not parent or parent.workspace_id!=data['snapshot']['workspace_id'] or data['snapshot']['project_id'] and project!=data['snapshot']['project_id']:
            raise HTTPException(404,'Webhook record is outside the reviewed project/workspace')
    return [(source.entity_type,source.entity_id)]
