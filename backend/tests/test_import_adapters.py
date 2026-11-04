import csv
import io
from datetime import date
import pytest
from app.shared.import_catalog import SPECS
from tests.test_import_workspace import import_headers, upload, preview, action
from test_identity_utils import own_workflow_records


@pytest.mark.parametrize("module,entity",[(s.module,s.key) for s in SPECS])
def test_each_priority_import_writes_native_records(client,db,import_headers,module,entity):
    from app.models.employee import Employee
    from app.models.user import User
    from app.apps.crm.models import CRMCompany,CRMPipeline,CRMPipelineStage
    from app.apps.srm.models import SRMProduct,SRMWarehouse
    from app.apps.project_management.models import PMSWorkspace,PMSProject,PMSTask
    from app.apps.fam.models import FAMLedgerGroup,FAMLedger,FAMParty,FAMBankStatement,FAMBankAccount
    branch=int(import_headers["X-Suite-Branch"])
    user=db.query(User).filter_by(email="testadmin@test.com").one()
    company=CRMCompany(organization_id=1,branch_id=branch,name="Example Customer")
    employee=Employee(employee_id="EMP-DEMO-001",first_name="Example",last_name="Employee",date_of_joining=date(2026,1,1),branch_id=branch)
    pipeline=CRMPipeline(organization_id=1,name="Test pipeline")
    warehouse=SRMWarehouse(organization_id=1,warehouse_name="Test warehouse",warehouse_code="TEST")
    product=SRMProduct(organization_id=1,sku="DEMO-001",item_name="Test product")
    workspace=PMSWorkspace(organization_id=1,name="Import workspace")
    group=FAMLedgerGroup(company_id=1,group_code="DEMO",group_name="Assets",nature="asset")
    db.add_all([company,employee,pipeline,warehouse,product,workspace,group]);db.flush()
    stage=CRMPipelineStage(organization_id=1,pipeline_id=pipeline.id,name="New",position=1)
    project=PMSProject(organization_id=1,branch_id=branch,workspace_id=workspace.id,project_key="DEMO",name="Existing project")
    ledger=FAMLedger(company_id=1,ledger_code="DEMO-CASH",ledger_name="Existing ledger",ledger_group_id=group.id,nature="asset")
    db.add_all([stage,project,ledger]);db.flush()
    party=FAMParty(company_id=1,party_type="customer",party_code="CUST-DEMO",legal_name="Example Customer",ledger_id=ledger.id)
    account=FAMBankAccount(company_id=1,ledger_id=ledger.id,bank_name="Example bank",account_number_masked="XXXX7890")
    task=PMSTask(project_id=project.id,task_key="DEMO-1",title="Existing task")
    db.add_all([party,account,task]);db.flush()
    statement=FAMBankStatement(company_id=1,bank_account_id=account.id,imported_file_name="sample.csv",imported_file_hash="seed",statement_period_start=date(2026,1,1),statement_period_end=date(2026,12,31))
    db.add(statement);db.flush()
    own_workflow_records(db,company,employee,pipeline,stage,warehouse,product,workspace,project,task,group,ledger,party,account,statement)
    db.commit()
    spec=next(s for s in SPECS if (s.module,s.key)==(module,entity))
    source={field["key"]:field["sample"] for field in spec.fields}
    refs={"pipeline_id":pipeline.id,"stage_id":stage.id,"product_id":product.id,"warehouse_id":warehouse.id,"customer_id":company.id,"workspace_id":workspace.id,"project_id":project.id,"ledger_group_id":group.id,"party_id":party.id,"ledger_id":ledger.id,"statement_id":statement.id}
    source.update({key:value for key,value in refs.items() if key in source})
    # New identities for master types whose referenced sample already exists.
    if entity=="products":source["sku"]="IMPORTED-001"
    if entity=="employees":source["employee_id"]="EMP-IMPORTED-001"
    if entity=="companies":source["name"]="Imported company"
    if entity=="projects":source["project_key"]="IMPORTED"
    if entity=="tasks":source["task_key"]="DEMO-IMPORTED"
    if entity=="ledgers":source["ledger_code"]="IMPORTED-CASH"
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=list(source));writer.writeheader();writer.writerow(source);writer.writerow(source)
    batch=upload(client,import_headers,output.getvalue(),module,entity)
    assert action(client,import_headers,batch,"commit").status_code==409
    mapping={key:key for key in source}
    required=next(field["key"] for field in spec.fields if field.get("required"))
    missing=client.post(f"/api/v1/imports/{module}/batches/{batch['id']}/preview",headers=import_headers,json={"version":batch["version"],"mapping":{key:value for key,value in mapping.items() if key!=required}})
    assert missing.status_code==422,missing.text
    ready=preview(client,import_headers,batch,mapping)
    assert ready["preview"]["can_import"],ready["preview"]
    assert ready["preview"]["counts"]=={"create":1,"skip":1}
    committed=action(client,import_headers,ready,"commit")
    assert committed.status_code==200,committed.text
    assert committed.json()["status"]=="imported"
    if entity=="deals":
        from app.apps.crm.models import CRMDeal
        deal=db.query(CRMDeal).filter_by(name=source["name"],pipeline_id=pipeline.id).one()
        assert deal.company_id is None, "Tenant ID must never become a CRM customer ID"


    duplicate=upload(client,import_headers,output.getvalue(),module,entity)
    duplicate=preview(client,import_headers,duplicate,mapping,duplicates="error")
    assert not duplicate["preview"]["can_import"]
    assert action(client,import_headers,duplicate,"commit").status_code==409
    duplicate=preview(client,import_headers,duplicate,mapping,duplicates="skip")
    assert duplicate["preview"]["counts"]=={"skip":2}
    assert all(row["match_id"] is not None or "Duplicate within" in " ".join(row["suggestions"]) for row in duplicate["preview"]["rows"])
    revoked=action(client,import_headers,committed.json(),"revoke")
    assert revoked.status_code==200,revoked.text
    assert revoked.json()["status"]=="revoked"
    assert action(client,import_headers,revoked.json(),"revoke").status_code==409
    # A fresh preview after revoke must see a new record, including stock/payroll types.
    duplicate=preview(client,import_headers,duplicate,mapping)
    assert duplicate["preview"]["counts"]=={"create":1,"skip":1},duplicate["preview"]
