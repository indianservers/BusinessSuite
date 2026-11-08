import pytest
from tests.test_power_apps import actors

@pytest.mark.parametrize('kind',['forms','tables','app-builder','notifications'])
def test_workspace_crud_scope_and_stale_writes(client,actors,kind):
    root='/api/v1/power-apps/workspaces/'+kind
    definition={'fields':['Subject'] if kind in ['forms','tables'] else [],'entries':[],'content':'Internal content','acknowledged':False,'table_id':None}
    payload={'name':'Acceptance '+kind,'description':'Scoped definition','definition':definition}
    assert client.post(root,headers=actors[2],json=payload).status_code==403
    created=client.post(root,headers=actors[0],json=payload);assert created.status_code==201,created.text
    row=created.json();url=root+'/'+str(row['id'])
    assert client.get(url,headers=actors[1]).status_code==404
    assert client.get(url,headers=actors[0],params={'environment':'testing'}).status_code==404
    updated=client.put(url,headers=actors[0],json={**payload,'name':'Renamed','expected_version':1});assert updated.status_code==200,updated.text
    assert client.put(url,headers=actors[0],json={**payload,'expected_version':1}).status_code==409
    assert client.delete(url,headers=actors[2],params={'expected_version':2}).status_code==403
    assert client.delete(url,headers=actors[0],params={'expected_version':1}).status_code==409
    assert client.delete(url,headers=actors[0],params={'expected_version':2}).status_code==204
    assert client.get(url,headers=actors[0]).status_code==404

@pytest.mark.parametrize('kind,payload',[
 ('kanban',{'module_name':'acceptance','name':'Board','group_by_field':'name'}),
 ('validation-rules',{'module_name':'acceptance','name':'Rule','condition_json':{'field':'amount','operator':'less_than','value':0},'error_message':'Positive amount required'}),
 ('related-lists',{'module_name':'acceptance','related_module_name':'acceptance','lookup_field':'parent','label':'Children'}),
 ('buttons',{'module_name':'acceptance','label':'Review','action_type':'timeline_event','action_config_json':{'title':'Reviewed'}}),
 ('layouts',{'module_name':'acceptance','name':'Layout'}),
 ('picklists',{'api_name':'acceptance_values','label':'Values','values':[{'value':'Open'}]})])
def test_missing_customization_update_delete(client,superuser_headers,kind,payload):
    root='/api/v1/customization/'+kind
    response=client.post(root,headers=superuser_headers,json=payload);assert response.status_code==201,response.text
    row=response.json();url=root+'/'+str(row['id']);field='label' if kind in ['buttons','related-lists','picklists'] else 'name'
    changed=client.put(url,headers=superuser_headers,json={**payload,field:'Updated'});assert changed.status_code==200,changed.text
    assert changed.json()[field]=='Updated'
    assert client.delete(url).status_code in [401,403]
    assert client.delete(url,headers=superuser_headers).status_code==204
    assert not any(r['id']==row['id'] for r in client.get(root,headers=superuser_headers).json()['items'])


def test_table_references_and_form_values_are_protected(client,actors):
    headers=actors[0];root='/api/v1/power-apps/workspaces'
    table=client.post(root+'/tables',headers=headers,json={'name':'Protected table','definition':{'fields':['Subject']}}).json()
    app=client.post(root+'/app-builder',headers=headers,json={'name':'Table app','definition':{'content':'Connected page','table_id':table['id']}})
    assert app.status_code==201,app.text
    assert client.delete(root+'/tables/'+str(table['id']),headers=headers,params={'expected_version':1}).status_code==409
    invalid=client.put(root+'/tables/'+str(table['id']),headers=headers,json={'name':'Protected table','expected_version':1,'definition':{'fields':['Subject'],'entries':[{'id':'one','values':{'Unknown':'No'}}]}})
    assert invalid.status_code==422
    other=client.post(root+'/app-builder',headers=actors[1],json={'name':'Cross tenant app','definition':{'table_id':table['id']}})
    assert other.status_code==404


@pytest.mark.parametrize('root,payload,name_field',[
 ('/fam/inventory/stock-groups',{'group_code':'NEWG','group_name':'New group'},'group_name'),
 ('/fam/inventory/units',{'unit_code':'NEWU','unit_name':'New unit'},'unit_name'),
 ('/srm/inventory/warehouses',{'warehouse_code':'NEWW','warehouse_name':'New warehouse'},'warehouse_name'),
 ('/timesheets/projects',{'code':'NEWT','name':'New project'},'name'),
 ('/assets/',{'asset_tag':'NEWA','name':'New asset'},'name')])
def test_new_master_updates_and_deletes(client,superuser_headers,root,payload,name_field):
    h=superuser_headers;c=client.post('/api/v1'+root,headers=h,json=payload);assert c.status_code==201,c.text
    row=c.json();url='/api/v1'+root.rstrip('/')+'/'+str(row['id'])
    assert client.put(url,headers=h,json={**payload,name_field:'Updated resource'}).status_code==200
    assert client.delete(url).status_code in [401,403]
    assert client.delete(url,headers=h).status_code in [200,204]
    items=client.get('/api/v1'+root,headers=h).json()
    if isinstance(items,dict):items=items['items']
    assert not any(item['id']==row['id'] and item.get('active',True) for item in items)


def test_unused_campaign_and_schedule_have_complete_actions(client,superuser_headers):
    h=superuser_headers;root='/api/v1'
    t=client.post(root+'/communication/email-templates',headers=h,json={'name':'Draft template','subject':'Acceptance','body_text':'No delivery'});assert t.status_code==201,t.text
    body={'name':'Draft campaign','template_id':t.json()['id'],'type':'email','status':'draft'}
    c=client.post(root+'/communication/campaigns',headers=h,json=body);assert c.status_code==201,c.text
    url=root+'/communication/campaigns/'+str(c.json()['id'])
    assert client.put(url,headers=h,json={**body,'name':'Updated campaign'}).status_code==200
    assert client.delete(url,headers=h).status_code==204
    report=client.post(root+'/analytics/reports',headers=h,json={'name':'Schedule test','module_name':'crm_deals','report_type':'table','visibility':'public','fields_json':['name']});assert report.status_code==201,report.text
    body={'name':'Own schedule','report_id':report.json()['id'],'frequency':'weekly','recipients_json':['acceptance@example.com']}
    c=client.post(root+'/analytics/schedules',headers=h,json=body);assert c.status_code==201,c.text
    url=root+'/analytics/schedules/'+str(c.json()['id'])
    assert client.put(url,headers=h,json={**body,'frequency':'monthly'}).status_code==200
    assert client.delete(url,headers=h).status_code==204
