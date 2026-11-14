from tests.rich_text_test_utils import organization_context
from tests.test_shared_services import shared_setup, access_account
from tests.test_erp_audit_dashboard_roles import payload
from app.shared.models import ServicePolicy
from app.access.models import AccessAudit

ROOT='/api/v1/access/enterprise/policies'


def test_exact_dashboard_create_and_edit_replays_return_existing_receipt(client,db,shared_setup):
    headers,_,_=shared_setup
    data=payload(db,[])
    first=client.put(ROOT,headers=headers,json=data)
    assert first.status_code==200,first.text
    ident=first.json()['id'];version=first.json()['version']
    audit_count=db.query(AccessAudit).filter_by(operation='enterprise.policy.saved').count()
    retry=client.put(ROOT,headers=headers,json=data)
    assert retry.status_code==200,retry.text
    assert retry.json()['id']==ident and retry.json()['version']==version
    assert db.query(ServicePolicy).filter_by(kind='dashboard').count()==1
    assert db.query(AccessAudit).filter_by(operation='enterprise.policy.saved').count()==audit_count
    edit={**data,'version':version,'values':{**data['values'],'name':'Updated synthetic layout'}}
    updated=client.put(ROOT,headers=headers,json=edit)
    assert updated.status_code==200,updated.text
    replay=client.put(ROOT,headers=headers,json=edit)
    assert replay.status_code==200,replay.text
    assert replay.json()['id']==ident and replay.json()['version']==version+1
    assert db.query(AccessAudit).filter_by(operation='enterprise.policy.saved').count()==audit_count+1
    # Matching values alone cannot erase a distinct reason or recover an older request.
    for invalid in [{**edit,'reason':'A different administrative intent'},
                    {**edit,'values':{**edit['values'],'name':'Conflicting stale change'}},data]:
        rejected=client.put(ROOT,headers=headers,json=invalid)
        assert rejected.status_code==409,rejected.text
    db.expire_all()
    assert db.get(ServicePolicy,ident).values_json['name']=='Updated synthetic layout'
    assert db.get(ServicePolicy,ident).version==version+1
