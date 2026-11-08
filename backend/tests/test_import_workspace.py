import io
import pytest
from app.models.user import User
from app.shared.import_models import ImportBatch
from app.apps.crm.models import CRMLead
from test_identity_utils import attach_test_identity, attach_workflow_branch, own_workflow_records


@pytest.fixture
def import_headers(client, db, superuser_headers):
    actor = db.query(User).filter_by(email="testadmin@test.com").one()
    attach_test_identity(db, actor)
    branch = attach_workflow_branch(db, actor)
    db.commit()
    return {**superuser_headers,"X-Suite-Branch":str(branch.id)}


def upload(client, headers, content, module="crm", entity="leads"):
    response=client.post(f"/api/v1/imports/{module}/upload",headers=headers,data={"entity":entity},files={"file":("sample.csv",content,"text/csv")})
    assert response.status_code==200,response.text
    return response.json()


def preview(client, headers, batch, mapping, **options):
    response=client.post(f"/api/v1/imports/{batch['module']}/batches/{batch['id']}/preview",headers=headers,json={"version":batch["version"],"mapping":mapping,**options})
    assert response.status_code==200,response.text
    return response.json()


def action(client, headers, batch, name):
    return client.post(f"/api/v1/imports/{batch['module']}/batches/{batch['id']}/{name}",headers=headers,json={"version":batch["version"]})


def test_import_catalog_supported_types_and_real_templates(client, import_headers):
    from openpyxl import load_workbook
    for module in ("crm","srm","hrms","pms","fam"):
        response=client.get(f"/api/v1/imports/{module}/catalog",headers=import_headers)
        assert response.status_code==200,response.text
        assert len(response.json())==(5 if module=="crm" else 3)
        for spec in response.json():
            template=client.get(f"/api/v1/imports/{module}/template/{spec['key']}",headers=import_headers)
            assert template.status_code==200,template.text
            book=load_workbook(io.BytesIO(template.content),data_only=False)
            assert list(next(book.worksheets[0].values))==[field["key"] for field in spec["fields"]]


def test_mapping_preview_cleaning_duplicate_commit_and_revoke(client, db, import_headers):
    batch=upload(client,import_headers,"Person,Mail\n  Asha Rao  ,ASHA@example.com\nAsha again,asha@example.com\n")
    assert action(client,import_headers,batch,"commit").status_code==409
    missing=client.post(f"/api/v1/imports/crm/batches/{batch['id']}/preview",headers=import_headers,json={"version":batch["version"],"mapping":{"full_name":"Person"}})
    assert missing.status_code==422
    ready=preview(client,import_headers,batch,{"full_name":"Person","email":"Mail"})
    assert ready["preview"]["counts"]=={"create":1,"skip":1}
    assert ready["preview"]["rows"][0]["values"]["full_name"]=="Asha Rao"
    assert ready["preview"]["rows"][0]["suggestions"]
    response=action(client,import_headers,ready,"commit")
    assert response.status_code==200,response.text
    committed=response.json()
    assert action(client,import_headers,ready,"commit").status_code==409
    assert db.query(CRMLead).filter_by(email="asha@example.com").count()==1
    revoked=action(client,import_headers,committed,"revoke")
    assert revoked.status_code==200,revoked.text
    assert db.query(CRMLead).filter_by(email="asha@example.com").count()==0
    retried=action(client,import_headers,revoked.json(),"retry")
    assert retried.status_code==200,retried.text
    assert retried.json()["status"]=="uploaded"
    history=client.get("/api/v1/imports/crm/history",headers=import_headers).json()
    assert len(history)==2


def test_revoke_restores_update_and_blocks_later_edits(client, db, import_headers):
    actor=db.query(User).filter_by(email="testadmin@test.com").one()
    lead=CRMLead(organization_id=1,branch_id=int(import_headers["X-Suite-Branch"]),owner_user_id=actor.id,full_name="Before",first_name="Before",email="existing@example.com")
    db.add(lead);own_workflow_records(db,lead);db.commit()
    batch=upload(client,import_headers,"Name,Email\nAfter,existing@example.com\n")
    ready=preview(client,import_headers,batch,{"full_name":"Name","email":"Email"},duplicates="update")
    assert ready["preview"]["counts"]=={"update":1}
    committed=action(client,import_headers,ready,"commit")
    assert committed.status_code==200,committed.text
    revoked=action(client,import_headers,committed.json(),"revoke")
    assert revoked.status_code==200,revoked.text
    db.expire_all();assert db.get(CRMLead,lead.id).full_name=="Before"
    new=upload(client,import_headers,"Name,Email\nNew,changed@example.com\n")
    ready=preview(client,import_headers,new,{"full_name":"Name","email":"Email"})
    response=action(client,import_headers,ready,"commit")
    assert response.status_code==200,response.text
    committed=response.json()
    row=db.query(CRMLead).filter_by(email="changed@example.com").one();row.full_name="Edited later";db.commit()
    assert action(client,import_headers,committed,"revoke").status_code==409
    db.expire_all();assert db.get(CRMLead,row.id).full_name=="Edited later"


def test_preview_errors_corrections_and_stale_data(client, db, import_headers):
    batch=upload(client,import_headers,"Name,Email\nBroken,not-email\n")
    invalid=preview(client,import_headers,batch,{"full_name":"Name","email":"Email"})
    assert invalid["preview"]["can_import"] is False
    assert action(client,import_headers,invalid,"commit").status_code==409
    ready=preview(client,import_headers,invalid,{"full_name":"Name","email":"Email"},edits={"0":{"Email":"corrected@example.com"}})
    assert ready["preview"]["can_import"]
    competing=CRMLead(organization_id=1,branch_id=int(import_headers["X-Suite-Branch"]),full_name="Other import",first_name="Other",email="corrected@example.com")
    db.add(competing);own_workflow_records(db,competing);db.commit()
    assert action(client,import_headers,ready,"commit").status_code==409
    assert db.query(CRMLead).filter_by(email="corrected@example.com").count()==1


def test_import_history_and_jobs_are_private(client, db, import_headers):
    from tests.srm_test_utils import auth_headers_for
    batch=upload(client,import_headers,"Name,Email\nPrivate,private@example.com\n")
    other=auth_headers_for(client,db,"other-importer@example.com","srm_admin",permissions=["crm_lead_manage","srm_view"])
    assert client.get(f"/api/v1/imports/crm/batches/{batch['id']}",headers=other).status_code==404
    blocked=auth_headers_for(client,db,"blocked-importer@example.com","srm_viewer",permissions=["crm_lead_view","srm_view"])
    assert client.get("/api/v1/imports/crm/catalog",headers=blocked).json()==[]
    denied=client.post("/api/v1/imports/crm/upload",headers=blocked,data={"entity":"leads"},files={"file":("sample.csv","Name,Email\nBad,bad@example.com\n","text/csv")})
    assert denied.status_code==403
