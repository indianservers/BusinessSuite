from tests.rich_text_test_utils import organization_context
import csv
import io
import os
import pytest
from tests.test_crm_deal_workspace import create
from tests.test_pms_workspaces import account

BASE="/api/v1/crm/report-builder"


def test_saved_report_group_currency_paging_revision_and_exports(client,db,superuser_headers):
    first=create(client,db,superuser_headers,name="=Unsafe spreadsheet cell",amount=100,currency="INR",status="Open")
    second=client.post("/api/v1/crm/deals",headers=superuser_headers,json={"name":"US opportunity","amount":20,"currency":"USD","status":"Open","pipeline_id":first["pipeline_id"],"stage_id":first["stage_id"],"company_id":first.get("company_id")})
    assert second.status_code==201,second.text
    definition={"name":"Open sales","columns":["name","amount","currency","status"],"group_by":"status","status":"Open"}
    saved=client.post(BASE,headers=superuser_headers,json=definition)
    assert saved.status_code==201,saved.text
    report=saved.json();identity=report["id"]
    result=client.get(f"{BASE}/{identity}/run?page_size=1",headers=superuser_headers)
    assert result.status_code==200,result.text
    assert result.json()["total"]==2
    assert len(result.json()["items"])==1
    page2=client.get(f"{BASE}/{identity}/run?page=2&page_size=1",headers=superuser_headers).json()
    currencies={result.json()["items"][0]["currency"],page2["items"][0]["currency"]}
    assert currencies=={"INR","USD"}
    export=client.get(f"{BASE}/{identity}/export?format=csv",headers=superuser_headers)
    assert export.status_code==200,export.text
    data=list(csv.DictReader(io.StringIO(export.content.decode("utf-8-sig"))))
    assert {r["currency"]:float(r["total_amount"]) for r in data}=={"INR":100,"USD":20}
    updated=client.put(f"{BASE}/{identity}",headers=superuser_headers,json={**definition,"group_by":"","expected_revision":report["revision"]})
    assert updated.status_code==200,updated.text
    assert client.put(f"{BASE}/{identity}",headers=superuser_headers,json={**definition,"expected_revision":report["revision"]}).status_code==409
    assert client.get(f"{BASE}/{identity}/export?expected_revision={report['revision']}",headers=superuser_headers).status_code==409
    export=client.get(f"{BASE}/{identity}/export?format=csv",headers=superuser_headers)
    assert "'=Unsafe spreadsheet cell" in export.content.decode("utf-8-sig")
    excel=client.get(f"{BASE}/{identity}/export?format=xlsx",headers=superuser_headers)
    assert excel.status_code==200 and excel.content.startswith(b"PK")
    from zipfile import ZipFile
    from xml.etree import ElementTree as ET
    with ZipFile(io.BytesIO(excel.content)) as archive:
        workbook=ET.fromstring(archive.read("xl/workbook.xml"))
        sheet=ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        assert workbook.find(".//{*}sheet").attrib["name"]=="Deal report"
        assert sheet.find(".//{*}f") is None
        assert "=Unsafe spreadsheet cell" in [n.text for n in sheet.findall(".//{*}t")]
    assert client.get(f"/api/v1/analytics/reports/{identity}",headers=superuser_headers).status_code==404
    listed=client.get("/api/v1/analytics/reports",headers=superuser_headers).json()
    assert identity not in [r["id"] for r in listed["items"]]


def test_private_definition_and_column_validation(client,db,superuser_headers):
    create(client,db,superuser_headers)
    saved=client.post(BASE,headers=superuser_headers,json={"name":"Private pipeline"}).json()
    outsider,headers=account(db,"private-report-viewer@test.com",True)
    assert client.get(BASE,headers=headers).json()==[]
    assert client.get(f"{BASE}/{saved['id']}/run",headers=headers).status_code==404
    assert client.get(f"{BASE}/{saved['id']}/export",headers=headers).status_code==404
    assert client.delete(f"{BASE}/{saved['id']}",headers=headers).status_code==404
    assert client.post(BASE,headers=superuser_headers,json={"name":"Unsafe fields","columns":["organization_id"]}).status_code==422
    assert client.post(BASE,headers=superuser_headers,json={"name":"Invalid grouping","group_by":"organization_id"}).status_code==422
    assert client.delete(f"{BASE}/{saved['id']}",headers=superuser_headers).status_code==204
    assert client.get(f"{BASE}/{saved['id']}/run",headers=superuser_headers).status_code==404


@pytest.mark.skipif(os.environ.get("RUN_CRM_PMS_FUNCTIONALITY_BROWSER")!="1",reason="Explicit disposable browser integration")
def test_crm_reporting_browser_with_disposable_api(client,db,superuser_headers):
    from tests.workflow_browser_utils import run_browser
    first=create(client,db,superuser_headers,name="UI INR opportunity",amount=100,currency="INR")
    result=client.post("/api/v1/crm/deals",headers=superuser_headers,json={"name":"UI USD opportunity","amount":20,"currency":"USD","pipeline_id":first["pipeline_id"],"stage_id":first["stage_id"]})
    assert result.status_code==201,result.text
    run_browser(client,db,"test-reporting-automation.cjs",{"WORKFLOW_TEST_TOKEN":superuser_headers["Authorization"].split(" ",1)[1],"FUNCTIONALITY_UI_MODE":"crm"})


def test_readonly_report_retains_deal_visibility(client,db,superuser_headers):
    from app.models.user import User
    from app.apps.crm.models import CRMDeal
    from tests.test_crm_phase_1_core_foundation import _headers_for_permissions
    first=create(client,db,superuser_headers,name="Reader-owned deal")
    second=client.post("/api/v1/crm/deals",headers=superuser_headers,json={"name":"Another rep's deal","pipeline_id":first["pipeline_id"],"stage_id":first["stage_id"]})
    assert second.status_code==201,second.text
    headers=_headers_for_permissions(client,db,"report-reader@example.com",["crm_deals_view"])
    reader=db.query(User).filter_by(email="report-reader@example.com").one()
    db.get(CRMDeal,first["id"]).owner_user_id=reader.id;db.commit()
    saved=client.post(BASE,headers=headers,json={"name":"My visible deals","columns":["name","currency"]})
    assert saved.status_code==201,saved.text
    result=client.get(f"{BASE}/{saved.json()['id']}/run",headers=headers)
    assert result.status_code==200,result.text
    assert [r["name"] for r in result.json()["items"]]==["Reader-owned deal"]
    assert client.delete(f"{BASE}/{saved.json()['id']}",headers=headers).status_code==204
    assert db.get(CRMDeal,first["id"]) is not None
