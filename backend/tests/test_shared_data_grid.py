from tests.rich_text_test_utils import organization_context
import csv
import io
import json
from datetime import date
import pytest
from openpyxl import load_workbook
from app.models.user import User
from app.apps.crm.models import CRMDeal, CRMPipelineStage
from test_identity_utils import attach_test_identity
from tests.test_crm_deal_catalog import seed
from tests.test_shared_catalog import scoped_headers
from tests.test_suite_access import access_account, secure, grant, apply, login

ROOT = "/api/v1/crm/deal-workspace/grid"


@pytest.fixture
def headers(db, superuser_headers):
    attach_test_identity(db, db.query(User).filter_by(email="testadmin@test.com").one())
    db.commit()
    return superuser_headers


@pytest.fixture
def deals(client, db, headers):
    payload, _, _ = seed(client, db, headers)
    owner = db.query(User).filter_by(email="testadmin@test.com").one()
    for index in range(125):
        db.add(CRMDeal(name=f"Opportunity {index:03}", organization_id=1, pipeline_id=payload["pipeline_id"], stage_id=payload["stage_id"], owner_user_id=owner.id, amount=100+index, probability=50, currency="USD" if index%2 else "INR", status="Open", priority="High" if index%3 else "Low", expected_close_date=date(2026,11,15)))
    db.add(CRMDeal(name="Foreign secret",organization_id=99,pipeline_id=payload["pipeline_id"],stage_id=payload["stage_id"],amount=999999,currency="USD",status="Open"))
    db.commit()
    return payload


def query(client, headers, state=None, **extra):
    return client.get(ROOT+"/query", headers=headers, params={"state":json.dumps(state or {}),**extra})


def test_full_filtered_statistics_and_stable_server_pagination(client, db, headers, deals):
    result=query(client,headers,{"pageSize":25,"page":2,"sorting":[{"id":"amount","desc":True},{"id":"name","desc":False}]})
    assert result.status_code==200,result.text
    body=result.json();assert len(body["rows"])==25 and body["total"]==125
    assert body["rows"][0]["amount"]==199
    assert all(r["organization_id"]==1 and r["owner_name"] for r in body["rows"])
    cohorts={r["currency"]:r for r in body["aggregates"]}
    assert cohorts["INR"]["count"]==63 and cohorts["USD"]["count"]==62
    assert cohorts["INR"]["sum"]==sum(100+i for i in range(125) if i%2==0)
    assert body["context"]["summary"]["counts"]["open"]==125
    assert query(client,headers,{"pageSize":201}).status_code==422


def test_nested_and_or_filters_ranges_nulls_and_validation(client,db,headers,deals):
    state={"filters":{"logic":"and","rules":[{"field":"amount","operator":"between","value":110,"value2":120},{"logic":"or","rules":[{"field":"currency","operator":"equals","value":"USD"},{"field":"priority","operator":"equals","value":"Low"}]}]}}
    result=query(client,headers,state);assert result.status_code==200,result.text
    expected=[i for i in range(10,21) if i%2 or i%3==0]
    assert result.json()["total"]==len(expected)
    assert sum(c["sum"] for c in result.json()["aggregates"])==sum(100+i for i in expected)
    for rule in [{"field":"amount);DROP TABLE crm_deals","operator":"equals","value":1},{"field":"amount","operator":"contains","value":"1"},{"field":"amount","operator":"gt","value":"NaN"},{"field":"expected_close_date","operator":"between","value":"2026-12-01","value2":"2026-11-01"}]:
        assert query(client,headers,{"filters":{"logic":"and","rules":[rule]}}).status_code==422
    empty=query(client,headers,{"filters":{"logic":"and","rules":[{"field":"next_follow_up_at","operator":"empty"}]}})
    assert empty.json()["total"]==125
    literal=query(client,headers,{"filters":{"logic":"and","rules":[{"field":"name","operator":"contains","value":"%"}]}})
    assert literal.json()["total"]==0


def test_paginated_server_grouping_and_nested_aggregations(client,db,headers,deals):
    state={"grouping":["priority","currency"],"pageSize":25}
    result=query(client,headers,state);assert result.status_code==200,result.text
    body=result.json();assert len(body["groups"])==2 and not body["rows"]
    assert sum(g["count"] for g in body["groups"])==125
    high=next(g for g in body["groups"] if g["value"]=="High")
    assert sum(a["sum"] for a in high["aggregates"])==sum(100+i for i in range(125) if i%3)
    child=query(client,headers,{**state,"path":high["path"]}).json()
    assert len(child["groups"])==2
    leaf=query(client,headers,{**state,"path":child["groups"][0]["path"]}).json()
    assert len(leaf["rows"])<=25 and leaf["pageTotal"]>25
    assert all(r["priority"]=="High" and r["currency"]==child["groups"][0]["value"] for r in leaf["rows"])
    assert query(client,headers,{**state,"path":[{"field":"currency","value":"USD"}]}).status_code==422


def test_facets_and_exports_share_filters_columns_and_permissions(client,db,headers,deals):
    state={"filters":{"logic":"and","rules":[{"field":"currency","operator":"equals","value":"USD"}]},"sorting":[{"id":"amount","desc":True}]}
    facet=client.get(ROOT+"/facets",headers=headers,params={"field":"priority","state":json.dumps(state)});assert facet.status_code==200,facet.text
    assert sum(v["count"] for v in facet.json()["values"])==62
    selected=[r["id"] for r in query(client,headers,state).json()["rows"][:3]]
    params={"state":json.dumps(state),"columns":json.dumps(["name","amount","currency"]),"scope":"selected","ids":json.dumps(selected)}
    exported=client.get(ROOT+"/export",headers=headers,params={**params,"format":"csv"});assert exported.status_code==200,exported.text
    table=list(csv.reader(io.StringIO(exported.content.decode("utf-8-sig"))));assert table[0]==["Deal name","Deal value","Currency"] and len(table)==4
    assert all(row[2]=="USD" for row in table[1:])
    xlsx=client.get(ROOT+"/export",headers=headers,params={**params,"format":"xlsx"});assert xlsx.status_code==200,xlsx.text
    book=load_workbook(io.BytesIO(xlsx.content));assert book.active.max_row==4
    pdf=client.get(ROOT+"/export",headers=headers,params={**params,"format":"pdf"});assert pdf.status_code==200 and pdf.content.startswith(b"%PDF")
    import os
    if os.environ.get("GRID_EXPORT_QA_DIR"):
        from pathlib import Path
        destination=Path(os.environ["GRID_EXPORT_QA_DIR"]);destination.mkdir(parents=True,exist_ok=True)
        wide=client.get(ROOT+"/export",headers=headers,params={**params,"format":"pdf","include_summaries":True,"include_groups":True,"columns":json.dumps(["name","amount","currency","pipeline_id","stage_id","owner_user_id","probability","weighted","expected_close_date","priority","status"]),"state":json.dumps({**state,"grouping":["priority"]})})
        assert wide.status_code==200,wide.text
        (destination/"deals-export.pdf").write_bytes(wide.content)
    invalid=client.get(ROOT+"/export",headers=headers,params={"columns":'["hashed_password"]'});assert invalid.status_code==422
    outsider=scoped_headers(client,db,"grid-foreign-admin",["crm_admin"],2)
    assert query(client,outsider).json()["total"]==0
    exported=client.get(ROOT+"/export",headers=outsider,params={**params,"format":"csv"})
    assert exported.status_code==200 and len(list(csv.reader(io.StringIO(exported.content.decode("utf-8-sig")))))==1


def test_exports_escape_spreadsheet_formulas(client,db,headers,deals):
    row=db.query(CRMDeal).filter_by(organization_id=1).first();row.name="=HYPERLINK(\"https://example.com\")";db.commit()
    response=client.get(ROOT+"/export",headers=headers,params={"scope":"selected","ids":json.dumps([row.id]),"columns":'["name"]'})
    table=list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert table[1][0].startswith("'=")


def test_read_only_managed_grid_cannot_edit_archive_or_export(client,db,headers,deals,access_account):
    admin=secure(client,headers)
    viewer={**grant(client,admin,"crm","viewer"),"scope":"organization"}
    assigned=apply(client,admin,access_account,{"crm":viewer})
    assert assigned.status_code==200,assigned.text
    actor=login(client)
    result=query(client,actor);assert result.status_code==200,result.text
    assert result.json()["total"]==125
    assert not result.json()["permissions"]["edit"] and not result.json()["permissions"]["export"]
    record=result.json()["rows"][0]
    assert client.get(ROOT+"/export",headers=actor).status_code==403
    assert client.post(ROOT+"/archive",headers=actor,json={"records":[{"id":record["id"],"version":record["version"]}]}).status_code==403
    assert client.patch(f"/api/v1/crm/deals/{record['id']}",headers=actor,json={"name":"Denied"}).status_code==403


def test_bulk_archive_preserves_history_and_rejects_stale_versions(client,db,headers,deals):
    selected=query(client,headers).json()["rows"][:2]
    response=client.post(ROOT+"/archive",headers=headers,json={"records":[{"id":selected[0]["id"],"version":selected[0]["version"]},{"id":selected[1]["id"],"version":99}]})
    assert response.status_code==200,response.text
    assert response.json()["items"][0]["saved"] and not response.json()["items"][1]["saved"]
    db.expire_all()
    assert db.get(CRMDeal,selected[0]["id"]).deleted_at is not None
    assert db.get(CRMDeal,selected[1]["id"]).deleted_at is None


def test_large_dataset_stays_paginated_and_facets_are_bounded(client,db,headers,deals):
    db.bulk_insert_mappings(CRMDeal,[{"name":f"Scale record {i}","organization_id":1,"pipeline_id":deals["pipeline_id"],"stage_id":deals["stage_id"],"amount":10,"probability":50,"currency":"INR","status":"Open"} for i in range(10000)])
    db.commit()
    from app.branches.models import BranchOwnership
    from app.models.company import Branch
    branch = db.query(Branch).filter_by(company_id=1).order_by(Branch.id).first()
    ids = db.query(CRMDeal.id).filter(CRMDeal.organization_id==1, CRMDeal.name.like("Scale record %")).all()
    db.execute(BranchOwnership.__table__.insert(), [
        dict(company_id=1, branch_id=branch.id, resource_table="crm_deals", resource_key=str(row.id), source="grid-scale-fixture")
        for row in ids])
    db.commit()
    response=query(client,headers,{"pageSize":200,"page":40});assert response.status_code==200,response.text
    assert response.json()["total"]==10125 and len(response.json()["rows"])==200
    assert len(response.content)<2_000_000
    facets=client.get(ROOT+"/facets",headers=headers,params={"field":"name"})
    assert facets.status_code==200 and len(facets.json()["values"])==200 and facets.json()["hasMore"]
