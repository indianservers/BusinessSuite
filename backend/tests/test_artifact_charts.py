import io
import json
from decimal import Decimal
from uuid import uuid4
import pytest
from pypdf import PdfReader
from openpyxl import load_workbook
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,ROOT
from tests.test_bot_artifacts import command,execute,A
from app.ai_operator.artifacts import Body
from app.ai_operator import artifact_charts as charts
from ai_test_utils import auth_headers


def body(**extra):
    return {'title':'Delivery amounts','kind':'table','content':'Illustrative reviewed snapshot.','columns':['Region','Amount','Currency','Team'],
        'rows':[['North','1,000.25','INR','A'],['North','250.5','INR','A'],['South','10','USD','B'],
            ['North','=2+2','INR','B'],['South','','USD','A']],
        'chart':{'kind':'bar','category_column':0,'value_column':1,'series_column':3,'aggregation':'sum'},**extra}


@pytest.mark.parametrize('text,value',[('1,234.56','1234.56'),('1,23,456.78','123456.78'),('12,34,567','1234567'),('-.5','-0.5'),('0.000001','0.000001'),
    ('=1+1',None),('1,00',None),('NaN',None),('Infinity',None),('1e9',None),('$20',None),('1.0000001',None),('1000000000000001',None)])
def test_numbers_are_bounded_plain_decimals_never_formulas(text,value):
    assert charts.number(text)==(Decimal(value) if value is not None else None)


def test_aggregation_keeps_currency_units_and_missing_values_separate():
    result=charts.analyze(body());assert len(result['panels'])==2
    inr,usd=result['panels'];assert inr['unit']=='INR' and usd['unit']=='USD'
    assert inr['series'][0]['values']==['1250.75']
    assert inr['statistics']['sum']=='1250.75' and usd['statistics']['sum']=='10'
    assert result['invalid_numeric_rows']==1 and result['blank_numeric_rows']==1
    assert result['valid_rows']==3 and result['profiles'][1]['numeric']==3
    wrong=body(chart={**body()['chart'],'unit_column':3})
    with pytest.raises(ValueError):Body.model_validate(wrong)
    quantities=body(columns=['Project','Hours','Invoice Currency','Unit'],rows=[['A','2','USD','hours'],['A','3','INR','hours']],
        chart={'category_column':0,'value_column':1,'monetary':False,'unit_column':3})
    assert charts.analyze(quantities)['panels'][0]['statistics']['sum']=='5'
    assert charts.analyze({**quantities,'chart':{'category_column':0,'value_column':1}})['panels'][0]['unit']=='USD'


def test_count_mean_sort_filters_and_missing_series_do_not_impute_values():
    raw=body(rows=[['North','10','USD','A'],['South','20','USD','B'],['North','30','USD','A']])
    result=charts.analyze(raw);panel=result['panels'][0]
    assert panel['series'][0]['values']==['40',None] and panel['series'][1]['values']==[None,'20']
    mean=charts.analyze({**raw,'chart':{**raw['chart'],'aggregation':'mean'}})
    assert mean['panels'][0]['series'][0]['values'][0]=='20'
    key=result['available_series'][1]['key'];filtered=charts.analyze(raw,series_key=key)
    assert filtered['valid_rows']==1 and filtered['panels'][0]['statistics']['sum']=='20'
    assert charts.analyze(raw,category_query='south')['valid_rows']==1
    count=charts.analyze({**raw,'chart':{'category_column':0,'value_column':None,'aggregation':'count'}})
    assert count['panels'][0]['series'][0]['values']==['2','1']
    ranked=charts.analyze(raw,order='value_desc',limit=1)['panels'][0]
    assert ranked['categories']==['North'] and ranked['omitted_categories']==1


def test_chart_shape_pie_limits_and_old_hash_shape_are_enforced():
    legacy=Body(title='Legacy table',kind='table',columns=['A'],rows=[['x']]).model_dump()
    assert 'chart' not in legacy
    for value in [body(chart={'value_column':9}),body(chart={'kind':'pie','value_column':1,'series_column':3}),
        body(chart={'kind':'pie','value_column':1},rows=[['N','-1','USD','A']]),
        body(chart={'kind':'pie','value_column':1,'category_limit':1},rows=[['N','1','USD','A'],['S','2','USD','A']])]:
        with pytest.raises(ValueError):Body.model_validate(value)
    with pytest.raises(ValueError):Body(title='Wrong kind',content='Document',chart={'value_column':0})
    zeros=charts.analyze(body(chart={'kind':'pie','value_column':1},rows=[['N','0','USD','A']]))
    assert zeros['panels'][0]['series'][0]['values']==['0']


def test_response_budget_reports_plot_omissions_without_changing_statistics():
    raw=body(columns=['Region','Amount'],rows=[['Category '+str(i)+'x'*200,str(i+1)] for i in range(40)],
        chart={'category_column':0,'value_column':1,'category_limit':40})
    result=charts.bounded(charts.analyze(raw),5000);panel=result['panels'][0]
    assert len(json.dumps(result,ensure_ascii=False).encode())<=5000 and result['disclosure_limited']
    assert panel['omitted_categories']>0 and panel['statistics']['sum']=='820'
    assert len(panel['categories'])==len(panel['series'][0]['values'])


@pytest.mark.parametrize('module',['CRM','PMS','HRMS'])
def test_reviewed_charts_versions_analysis_exports_and_private_access(client,db,module):
    h,_,_,_=setup_suite(client,db)
    prepared=command(client,h,module,'Prepare a chart',local_plan={'summary':'Review this chart table','steps':[{'tool':f'{module.lower()}.create_artifact','payload':body()}]})
    assert prepared['status']=='awaiting_approval',prepared
    preview=client.post(A+'/analyze-preview',headers=h,json={'module':module,'body':body()})
    assert preview.status_code==200 and preview.json()['snapshot']['state']=='unsaved',preview.text
    assert client.get(A,headers=h,params={'module':module}).json()['items']==[]
    made=execute(client,db,h,prepared);ident=made['receipts'][0]['artifact_id']
    found=client.get(A+f'/{ident}/analysis',headers=h)
    assert found.status_code==200 and found.json()['snapshot']['revision']==1,found.text
    assert found.json()['panels'][0]['statistics']['sum']=='1250.75'
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','crm_view','hrms_view','pms_manage_tasks'])
    assert client.get(A+f'/{ident}/analysis',headers=other).status_code==404
    pdf=client.get(A+f'/{ident}/download',headers=h,params={'format':'pdf'})
    assert pdf.status_code==200,pdf.text
    text=' '.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert '1250.75' in text and 'Original table snapshot' in text
    excel=client.get(A+f'/{ident}/download',headers=h,params={'format':'xlsx'});assert excel.status_code==200,excel.text
    book=load_workbook(io.BytesIO(excel.content));assert book.sheetnames[0]=='Chart analysis' and len(book['Chart analysis']._charts)==2
    assert 'A1:G1' in book['Chart analysis'].merged_cells
    assert len(book['Chart analysis'].row_breaks.brk)==2
    assert book['Artifact']['B5'].value=='=2+2' and book['Artifact']['B5'].data_type=='s'
    assert not any(cell.data_type=='f' for row in book['Chart analysis'] for cell in row)
    line=command(client,h,module,f'Edit artifact #{ident}: change chart to line')
    execute(client,db,h,line)
    assert client.get(A+f'/{ident}/analysis',headers=h,params={'revision':1}).json()['panels'][0]['kind']=='bar'
    assert client.get(A+f'/{ident}/analysis',headers=h).json()['panels'][0]['kind']=='line'


def test_local_chart_followups_and_cited_analysis_use_server_arithmetic(client,db):
    h,_,_,_=setup_suite(client,db);chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Chart conversation'}).json()['id']
    first=command(client,h,'CRM','Create bar chart called Sales with columns Region, Amount',conversation_id=chat)
    assert first['status']=='awaiting_approval' and first['plan']['steps'][0]['payload']['chart']['kind']=='bar',first
    command(client,h,'CRM','Add row: North, 100',conversation_id=chat)
    third=command(client,h,'CRM','Add row: South, 200',conversation_id=chat)
    made=execute(client,db,h,third);ident=made['receipts'][0]['artifact_id']
    analyzed=command(client,h,'CRM','Analyze this table',conversation_id=chat)
    assert analyzed['status']=='answered' and 'sum 300' in analyzed['plan']['summary'],analyzed
    assert analyzed['result']['citations'][0]['id']==f'artifact:{ident}:v1'
    edited=command(client,h,'CRM','Replace row 2: South, 250',conversation_id=chat)
    execute(client,db,h,edited)
    assert client.get(A+f'/{ident}/analysis',headers=h).json()['panels'][0]['statistics']['sum']=='350'
    count=command(client,h,'CRM','Chart count by Region',conversation_id=chat)
    assert count['status']=='awaiting_approval' and count['plan']['steps'][0]['payload']['chart']['aggregation']=='count',count


def test_inline_chart_configuration_remains_a_new_review_and_source_citations_reauthorize(client,db):
    h,_,_,_=setup_suite(client,db);chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Inline chart'}).json()['id']
    first=command(client,h,'CRM','Create table called Tracker with columns Region, Amount',conversation_id=chat)
    changed=client.post(ROOT+f'/runs/{first["id"]}/revise',headers=h,json={'request_key':str(uuid4()),'plan_hash':first['plan_hash'],
        'changes':[{'step':1,'field':'chart','value':{'kind':'line','category_column':0,'value_column':1}}]})
    assert changed.status_code==200 and changed.json()['status']=='awaiting_approval',changed.text
    made=execute(client,db,h,changed.json());ident=made['receipts'][0]['artifact_id']
    assert client.get(A+f'/{ident}',headers=h).json()['chart']['kind']=='line'
    assert client.get(A+f'/{ident}/analysis',headers=h,params={'chart_kind':'pie'}).status_code==200
    from types import SimpleNamespace
    from app.ai_operator import artifacts
    original=client.get(A+f'/{ident}',headers=h).json();source=charts.evidence(original)
    run=SimpleNamespace(result={'citations':[source]})
    assert client.delete(A+f'/{ident}',headers=h).status_code==200
    from fastapi import HTTPException
    from app.models.user import User
    with pytest.raises(HTTPException):charts.enforce_sources(db,db.query(User).filter_by(is_superuser=True).first(),run)


def test_copy_with_artifact_evidence_rechecks_source_before_approval(client,db):
    h,_,_,_=setup_suite(client,db)
    source=execute(client,db,h,command(client,h,'CRM','Prepare source table',local_plan={'summary':'Review source',
        'steps':[{'tool':'crm.create_artifact','payload':body()}]}))['receipts'][0]['artifact_id']
    current=client.get(A+f'/{source}',headers=h).json();evidence=charts.evidence(current)
    copy=command(client,h,'CRM','Prepare sourced copy',artifact_id=source,local_plan={'summary':'Review copied snapshot',
        'source_ids':[evidence['id']],'steps':[{'tool':'crm.create_artifact','payload':body(title='Independent copy')} ]})
    assert copy['status']=='awaiting_approval' and copy['result']['citations'][0]['id']==evidence['id'],copy
    client.delete(A+f'/{source}',headers=h)
    denied=client.post(ROOT+f'/runs/{copy["id"]}/approve',headers=h,json={'plan_hash':copy['plan_hash']})
    assert denied.status_code==404,denied.text
