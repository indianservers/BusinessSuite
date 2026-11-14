"""Product/service audience contract, analytics and visibility regressions."""
import json
from datetime import datetime, timedelta, timezone
from tests.test_crm_associations_merge import superuser_headers, post, offering, line, contact
from tests.test_crm_growth import get
from app.apps.crm.models import CRMContact, CRMLead


def test_multi_offering_any_all_unique_analytics_and_clear(client,db,superuser_headers):
    h=superuser_headers
    p=offering(client,h,'product','AUD-P');s=offering(client,h,'service','AUD-S')
    both=contact(client,h,full_name='Both offerings',email='both@example.com',lifecycle_stage='Customer',catalog_lines=[line(p),line(s)])
    single=contact(client,h,full_name='Only product',email='one@example.com',catalog_lines=[line(p)])
    contact(client,h,full_name='Unassigned',email='none@example.com')
    filters=json.dumps([{'kind':'product','id':p['id']},{'kind':'service','id':s['id']}])
    result=get(client,h,'/records',entity='contacts',offerings=filters,match='any',include_analytics=True,trend_days=7)
    assert result['total']==2
    assert result['analytics']['counts']=={'contacts':2}
    assert result['analytics']['customers']==1
    assert len(result['analytics']['trends'])==7
    assert len(result['analytics']['top_offerings'])==2
    assert sum(x['relationships'] for x in result['analytics']['top_offerings'])==3
    result=get(client,h,'/records',entity='contacts',offerings=filters,match='all',include_analytics=True)
    assert result['total']==1 and result['items'][0]['id']==both['id']
    assert len(result['items'][0]['offerings'])==2
    assert get(client,h,'/records',entity='contacts',audience=True)['total']==3
    assert get(client,h,'/records',entity='customers',audience=True)['total']==1
    assert get(client,h,'/records',entity='contacts',audience=True,search='AUD-S')['total']==1
    assert get(client,h,'/records',entity='contacts',audience=True,unassigned=True)['total']==1
    note=post(client,h,'crm/notes',{'body':'New relationship context','contact_id':both['id']})
    with_note=get(client,h,'/records',entity='contacts',audience=True,search='Both offerings')
    assert with_note['items'][0]['last_contact'] is not None
    assert note['body']=='New relationship context'
    due=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    for item in [p,s]:
        post(client,h,'crm/growth/follow-up',{'entity':'contacts','record_id':both['id'],'due_at':due,'offering_kind':item['kind'],'offering_id':item['id']})
    pending=get(client,h,f"/pending/contacts/{both['id']}")['items']
    assert {(row['metadata']['offering_kind'],row['metadata']['offering_id']) for row in pending}=={('product',p['id']),('service',s['id'])}
    assert get(client,h,'/records',entity='contacts',audience=True)['total']==3
    db.add(CRMContact(organization_id=2,first_name='Secret',full_name='Secret',email='secret@example.com'));db.commit()
    assert get(client,h,'/records',entity='contacts',include_analytics=True)['total']==3
    for invalid in ['not-json','{}','[{"kind":"sql","id":1}]','[{"kind":"product","id":true}]']:
        assert client.get('/api/v1/crm/growth/records',headers=h,params={'offerings':invalid}).status_code==422


def test_inherited_products_all_record_types_pagination_and_metrics(client,db,superuser_headers):
    h=superuser_headers;p=offering(client,h,'product','INHERIT-P');s=offering(client,h,'service','INHERIT-S')
    person=contact(client,h,full_name='Shared buyer',email='buyer@example.com')
    company=post(client,h,'crm/companies',{'name':'Shared account','account_type':'Customer'})
    lead=post(client,h,'crm/leads',{'first_name':'Shared','full_name':'Shared prospect','catalog_lines':[line(p),line(s)]})
    pipeline=post(client,h,'crm/pipelines',{'name':'Audience pipeline'})
    stage=post(client,h,f"crm/pipelines/{pipeline['id']}/stages",{'name':'Discovery'})
    deal=post(client,h,'crm/deals',{'name':'Multi offering deal','pipeline_id':pipeline['id'],'stage_id':stage['id'],'contact_id':person['id'],'company_id':company['id'],'catalog_items':[line(p),line(s)]})
    offers=json.dumps([{'kind':'product','id':p['id']},{'kind':'service','id':s['id']}])
    result=get(client,h,'/records',offerings=offers,match='all',include_analytics=True,per_page=2,page=2)
    assert result['total']==4 and len(result['items'])==2
    assert result['analytics']['counts']=={'leads':1,'contacts':1,'companies':1,'deals':1}
    assert result['analytics']['active_deals']==1
    assert float(result['analytics']['pipeline_values'][0]['value'])==200
    converted=db.get(CRMLead,lead['id']);converted.is_converted=True;converted.converted_at=datetime.now(timezone.utc);db.commit()
    converted_metrics=get(client,h,'/records',entity='leads',offerings=offers,match='all',include_analytics=True,trend_days=7)
    assert converted_metrics['analytics']['conversion_rate']==100
    assert sum(day['converted'] for day in converted_metrics['analytics']['trends'])==1
    converted_state={'filters':{'logic':'and','rules':[{'field':'converted','operator':'equals','value':1}]},'page':1,'pageSize':10}
    assert get(client,h,'/records',entity='leads',audience=True,state=json.dumps(converted_state))['total']==1
    for entity in ['leads','contacts','companies','deals']:
        found=get(client,h,'/records',entity=entity,offerings=offers,match='all',include_analytics=True)
        assert found['total']==1 and found['analytics']['counts']=={entity:1}
    changed=client.put(f"/api/v1/catalog/links/deal/{deal['id']}?source=crm",headers=h,json={'lines':[line(p)]})
    assert changed.status_code==200,changed.text
    assert get(client,h,'/records',offerings=offers,match='all',include_analytics=True)['total']==1
    state={'search':'','page':1,'pageSize':1,'sorting':[{'id':'name','desc':True}]}
    found=get(client,h,'/records',offerings=offers,match='any',audience=True,state=json.dumps(state))
    assert len(found['items'])==1 and found['total']==4


def test_audience_permissions_hide_records_and_catalog_and_reject_writes(client,db,superuser_headers):
    from tests.test_shared_catalog import scoped_headers
    from app.models.user import User
    from app.branches.models import BranchGrant
    h=superuser_headers;p=offering(client,h,'product','PRIVATE-OFFERING')
    hidden=contact(client,h,full_name='Hidden owner',email='hidden-owner@example.com',catalog_lines=[line(p)])
    own=contact(client,h,full_name='Visible owner',email='visible-owner@example.com')
    viewer=scoped_headers(client,db,'audience_viewer',['crm_view'])
    actor=db.query(User).filter_by(email='audience_viewer@example.com').one()
    grant = db.query(BranchGrant).filter_by(user_id=actor.id,company_id=1,branch_id=int(h['X-Suite-Branch'])).one_or_none()
    if grant is None:
        grant = BranchGrant(user_id=actor.id,company_id=1,branch_id=int(h['X-Suite-Branch']))
        db.add(grant)
    grant.can_write = False
    db.get(CRMContact,own['id']).owner_user_id=actor.id;db.commit()
    viewer['X-Suite-Branch']=h['X-Suite-Branch']
    result=get(client,viewer,'/records',entity='contacts',include_analytics=True)
    assert result['total']==1 and result['items'][0]['id']==own['id']
    assert result['analytics']['counts']=={'contacts':1}
    assert not result['items'][0]['can_edit'] and not any(result['can_create'].values())
    assert client.get(f"/api/v1/crm/contacts/{hidden['id']}/related",headers=viewer).status_code in (403,404)
    assert client.put(f"/api/v1/catalog/links/contact/{own['id']}?source=crm",headers=viewer,json={'lines':[line(p)]}).status_code==403
    assert client.get('/api/v1/crm/growth/records',params={'audience':True}).status_code in (401,403)


def test_shared_catalog_name_changes_refresh_audience_and_postgres_sql_compiles(client,db,superuser_headers):
    from types import SimpleNamespace
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql
    from app.apps.crm.growth_audience import offering_relations
    from app.models.user import User
    h=superuser_headers;p=offering(client,h,'product','SHARED-AUDIENCE')
    contact(client,h,full_name='One shared buyer',catalog_lines=[line(p)])
    response=client.put(f"/api/v1/catalog/items/product/{p['id']}?source=crm",headers=h,json={'kind':'product','name':'Updated shared offering','code':p['code'],'price':150,'currency':'INR','tax':0,'version':p['version']})
    assert response.status_code==200,response.text
    for source in ['crm','srm','pms']:
        same=client.get(f"/api/v1/catalog/items/product/{p['id']}?source={source}",headers=h)
        assert same.status_code==200,same.text
        assert same.json()['name']=='Updated shared offering' and same.json()['id']==p['id']
    result=get(client,h,'/records',entity='contacts',audience=True,include_analytics=True,search='Updated shared offering')
    assert result['total']==1 and result['items'][0]['offerings'][0]['name']=='Updated shared offering'
    class PostgreSQLProjection:
        bind=SimpleNamespace(dialect=postgresql.dialect())
        def __getattr__(self,key):return getattr(db,key)
    sql=str(select(offering_relations(PostgreSQLProjection(),db.query(User).filter_by(email='testadmin@test.com').one(),'all')).compile(dialect=postgresql.dialect()))
    assert 'LATERAL' in sql and 'jsonb_array_elements' in sql


import pytest

@pytest.mark.parametrize('needle',['%','_',chr(92),'/',chr(92)+'%',chr(92)+'_'])
def test_audit_growth_search_is_literal_for_people_and_offerings(client,superuser_headers,needle):
    h=superuser_headers
    matching=contact(client,h,full_name='QA'+needle+'Literal',email='literal@example.com')
    contact(client,h,full_name='QAplainLiteral',email='ordinary@example.com')
    for audience in [False,True]:
        result=get(client,h,'/records',entity='contacts',audience=audience,search=needle,per_page=1)
        assert result['total']==1
        assert [row['id'] for row in result['items']]==[matching['id']]
    product=post(client,h,'catalog/items?source=crm',{'kind':'product','name':'Offering'+needle+'Literal','code':'SEARCH-OFFERING','price':10,'currency':'INR'})
    linked=contact(client,h,full_name='Offering customer',email='offering@example.com',catalog_lines=[line(product)])
    result=get(client,h,'/records',entity='contacts',audience=True,search=needle)
    assert result['total']==2
    assert {row['id'] for row in result['items']}=={matching['id'],linked['id']}
