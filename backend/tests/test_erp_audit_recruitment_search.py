"""Literal recruitment candidate searches retain job/status filters."""
from uuid import uuid4
import pytest
from app.models.recruitment import Job,Candidate
from tests.test_import_workspace import import_headers
from tests.rich_text_test_utils import organization_context

@pytest.mark.parametrize('needle',['%','_',chr(92),'/'])
def test_candidate_search_is_literal(client,db,import_headers,needle):
    jobs=[Job(title=name,branch_id=int(import_headers['X-Suite-Branch'])) for name in ['Selected job','Other job']]
    db.add_all(jobs);db.flush()
    rows=[]
    for name,job,status in [('QA'+needle+'Literal',jobs[0],'Applied'),('QAplainLiteral',jobs[0],'Applied'),('QA'+needle+'Literal',jobs[1],'Applied'),('QA'+needle+'Literal',jobs[0],'Rejected')]:
        row=Candidate(job_id=job.id,first_name=name,last_name='Person',email=uuid4().hex+'@example.com',status=status)
        db.add(row);rows.append(row)
    db.commit()
    params={'job_id':jobs[0].id,'status':'Applied','search':needle}
    response=client.get('/api/v1/recruitment/candidates',headers=import_headers,params=params)
    assert response.status_code==200,response.text
    assert [row['id'] for row in response.json()]==[rows[0].id]
    normal=client.get('/api/v1/recruitment/candidates',headers=import_headers,params={**params,'search':'qaplain','per_page':1})
    assert normal.status_code==200,normal.text
    assert [row['id'] for row in normal.json()]==[rows[1].id]
