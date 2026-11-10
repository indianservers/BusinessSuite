from tests.rich_text_test_utils import organization_context
from tests.test_public_signup import platform_store,platform_headers
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import json
import pytest
from fastapi import HTTPException
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite
from app.ai_operator.training import parse_excel,process_training
from app.ai_operator.query_models import NlpDataset
from app.apps.automation.models import AutomationScheduledJob as Job

ROOT='/api/v1/ai-operator/suite/training'


def workbook(rows):
    from openpyxl import Workbook
    book=Workbook();sheet=book.active;sheet.title='Commands';sheet.append(['module','query','intent','split'])
    for row in rows:sheet.append(row)
    out=BytesIO();book.save(out);return out.getvalue()


def upload(client,h,rows=None):
    data=workbook(rows or [['CRM','CRM: fetch prospect roster','leads.list','train']])
    response=client.post(ROOT+'/datasets',headers=h,files={'file':('commands.xlsx',data,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},data={'name':'Local QA commands'})
    assert response.status_code==200,response.text
    return response.json()


@pytest.mark.parametrize('rows',[
 [['CRM','=HYPERLINK("https://example.com")','leads.list','train']],
 [['CRM','Show leads','invented.intent','train']],
 [['CRM','CRM: show all leads','leads.list','test']],
 [['CRM','CRM: display a lead record','leads.list','train'],['CRM','CRM: display a lead record','deals.list','train']],
])
def test_invalid_workbooks_fail_with_row_errors(rows):
    with pytest.raises(HTTPException) as result:parse_excel(workbook(rows))
    assert result.value.status_code==422


def test_expanded_platform_baseline_cannot_be_uploaded_as_unseen_holdout():
    from app.ai_operator.expanded_corpus import examples as expanded
    from app.ai_operator.local_corpus import examples
    from app.ai_operator.training import fingerprint
    base={fingerprint(row) for row in examples()}
    row=next(row for row in expanded(60) if fingerprint(row) not in base)
    with pytest.raises(HTTPException) as error:
        parse_excel(workbook([[row['module'],row['text'],row['intent'],'test']]))
    assert error.value.status_code==422


def test_real_download_template_is_valid_and_has_480_commands(client,db,platform_headers):
    from openpyxl import load_workbook
    response=client.get('/api/v1/platform/nlp-training/template',headers=platform_headers)
    assert response.status_code==200,response.text[:200]
    book=load_workbook(BytesIO(response.content),read_only=True)
    assert book.sheetnames==['Commands','Intents','Instructions']
    assert sum(1 for row in book['Commands'].iter_rows(min_row=2,values_only=True) if row[0])==480
    from collections import Counter
    from app.ai_operator.local_corpus import examples
    rows=list(book['Commands'].iter_rows(min_row=2,values_only=True))
    pairs={(row[0],row[2]) for row in rows if row[0]}
    assert pairs=={(row['module'],row['intent']) for row in examples()}
    assert len(pairs)==80
    assert Counter(row[0] for row in rows if row[0])=={'CRM':120,'PMS':120,'Sales':120,'HRMS':120}
    book.close()
    samples,counts=parse_excel(response.content)
    assert counts['modules'].keys()=={'CRM','PMS','Sales','HRMS'}


def test_legacy_customer_training_routes_are_blocked(client,db):
    h,_,_,_=setup_suite(client,db)
    assert client.get(ROOT+'/datasets',headers=h).status_code==403
    assert client.post(ROOT+'/jobs',headers=h,json={'request_key':str(uuid4()),'dataset_ids':[1]}).status_code==403
    assert client.post(ROOT+'/models/reset',headers=h).status_code==403
