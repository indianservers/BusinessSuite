from uuid import uuid4
from tests.test_pms_automations import setup_workspace
from tests.test_pms_workspaces import middleware_database
from tests.test_shared_forms import definition
from app.forms.models import FormReply


def test_internal_form_submission_through_full_branch_middleware(client, db):
    _,_,owner,headers,*_ = setup_workspace(client,db)
    draft = definition(public=False)
    created = client.post('/api/v1/forms',headers=headers,json={'module_key':'pms','definition':draft})
    assert created.status_code == 201, created.text
    form = created.json()
    published = client.put(f"/api/v1/forms/{form['id']}",headers=headers,json={'revision':form['revision'],'definition':draft,'publish':True})
    assert published.status_code == 200, published.text
    record = published.json()
    body = {'version':record['version'],'request_id':str(uuid4()),'answers':{'title':'Verified intake','email':'audit@example.com'}}
    path = f"/api/v1/forms/{form['id']}/internal/submit"
    response = client.post(path,headers=headers,json=body)
    assert response.status_code == 201, response.text
    assert response.json()['ok']
    repeated = client.post(path,headers=headers,json=body)
    assert repeated.status_code == 201, repeated.text
    assert db.query(FormReply).filter_by(form_id=form['id']).count() == 1
    closed = client.put(f"/api/v1/forms/{form['id']}",headers=headers,json={'revision':record['revision'],'definition':draft,'close':True})
    assert closed.status_code == 200, closed.text
    assert client.post(path,headers=headers,json={**body,'request_id':str(uuid4())}).status_code == 410
