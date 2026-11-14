"""Literal Access audit search, including exported result selection."""
import pytest
from app.access.models import AccessAudit
from app.models.user import User
from app.models.company import Company
from tests.test_import_workspace import import_headers

@pytest.mark.parametrize('needle',['%','_',chr(92),'/',chr(92)+'%',chr(92)+'_'])
def test_access_audit_search_is_literal(client,db,import_headers,needle):
    actor=db.query(User).filter_by(email='testadmin@test.com').one()
    if not db.get(Company,2):db.add(Company(id=2,name='Foreign audit company'))
    db.flush()
    matching=AccessAudit(actor_id=actor.id,company_id=1,operation='Search',reason='QA'+needle+'Literal')
    ordinary=AccessAudit(actor_id=actor.id,company_id=1,operation='Search',reason='Plain request')
    foreign=AccessAudit(actor_id=actor.id,company_id=2,operation='Search',reason='QA'+needle+'Literal')
    db.add_all([matching,ordinary,foreign]);db.commit()
    response=client.get('/api/v1/access/audit',headers=import_headers,params={'companyId':1,'search':needle})
    assert response.status_code==200,response.text
    assert response.json()['total']==1
    assert [row['id'] for row in response.json()['items']]==[matching.id]

    import csv,io
    exported=client.get('/api/v1/access/audit',headers=import_headers,params={'companyId':1,'search':needle,'export':True})
    assert exported.status_code==200,exported.text
    assert [int(row['id']) for row in csv.DictReader(io.StringIO(exported.text))]==[matching.id]
    normal=client.get('/api/v1/access/audit',headers=import_headers,params={'companyId':1,'search':'PLAIN'})
    assert normal.status_code==200,normal.text
    assert [row['id'] for row in normal.json()['items']]==[ordinary.id]
