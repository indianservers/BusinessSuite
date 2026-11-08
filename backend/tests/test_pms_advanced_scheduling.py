from datetime import date
from types import SimpleNamespace as Obj
import os
import pytest
from tests.test_pms_automations import setup_workspace
from tests.test_pms_workspaces import middleware_database, BASE, account
from app.apps.project_management.models import PMSTask, PMSTaskDependency
from app.apps.project_management.scheduling import calculate, CalendarSpec


def task(client, pid, headers, key, start, end):
    r = client.post(f"{BASE}/projects/{pid}/tasks", headers=headers, json={"task_key": key, "title": key, "start_date": start, "due_date": end})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_baseline_preview_cascade_apply_variance_and_stale_plan(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    a = task(client, pid, oh, "PLAN-A", "2026-11-09", "2026-11-10")
    b = task(client, pid, oh, "PLAN-B", "2026-11-11", "2026-11-12")
    r = client.post(BASE + "/task-dependencies", headers=oh, json={"source_task_id": a, "target_task_id": b, "dependency_type": "Finish To Start", "lag_days": 0})
    assert r.status_code == 201, r.text
    path = f"{BASE}/projects/{pid}"
    initial = client.get(path + "/schedule-analysis", headers=oh).json()
    assert initial["complete"] and set(initial["critical_task_ids"]) == {a, b}
    base = client.post(path + "/schedule-baselines", headers=oh, json={"name": "Approved plan", "expected_revision": initial["revision"]})
    assert base.status_code == 201, base.text
    payload = {"task_id": a, "start_date": "2026-11-12", "due_date": "2026-11-13", "calendar": {"weekdays": [0,1,2,3,4], "holidays": ["2026-11-16"]}}
    preview = client.post(path + "/schedule-preview", headers=oh, json=payload)
    assert preview.status_code == 200, preview.text
    plan = preview.json()
    assert {c["id"]: c["start_date"] for c in plan["changes"]} == {a: "2026-11-12", b: "2026-11-17"}
    assert db.get(PMSTask, b).start_date == date(2026,11,11), "Preview must not mutate"
    applied = client.post(path + "/schedule-apply", headers=oh, json={**payload, "expected_revision": plan["revision"]})
    assert applied.status_code == 200, applied.text
    assert applied.json()["updated"] == 2
    again = client.post(path + "/schedule-apply", headers=oh, json={**payload, "expected_revision": plan["revision"]})
    assert again.status_code == 409
    result = client.get(path + "/schedule-analysis", headers=oh).json()
    assert result["calendar"]["holidays"] == ["2026-11-16"]
    assert next(t for t in result["variance"] if t["id"] == b)["due_variance_days"] == 6
    assert result["baselines"][0]["id"] == base.json()["id"]
    csv_export=client.get(path+"/schedule-variance/export?format=csv",headers=oh)
    assert csv_export.status_code==200 and "PLAN-B" in csv_export.text
    xlsx=client.get(path+"/schedule-variance/export?format=xlsx",headers=oh)
    assert xlsx.status_code==200 and xlsx.content.startswith(b"PK")
    from zipfile import ZipFile
    from io import BytesIO
    from xml.etree import ElementTree as ET
    with ZipFile(BytesIO(xlsx.content)) as archive:
        sheet=ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        assert "6" in [n.text for n in sheet.findall(".//{*}v")]
        assert ET.fromstring(archive.read("xl/workbook.xml")).find(".//{*}sheet").attrib["name"]=="Schedule variance"
    assert client.post(path + "/schedule-apply", headers=gh, json={**payload,"expected_revision":result["revision"]}).status_code == 403
    outsider, xh = account(db, "schedule-outsider@test.com")
    assert client.get(path + "/schedule-analysis", headers=xh).status_code in (403,404)
    assert client.get(path + "/schedule-analysis?baseline_id=another-project", headers=oh).status_code == 404


def test_critical_path_and_float_on_parallel_branches():
    dates=[(9,10),(11,11),(11,13),(9,9)]
    tasks=[Obj(id=i+1,task_key=str(i+1),title=str(i+1),start_date=date(2026,11,s),due_date=date(2026,11,e)) for i,(s,e) in enumerate(dates)]
    edges=[(1,2),(1,3),(2,4),(3,4)]
    deps=[Obj(depends_on_task_id=a,task_id=b,dependency_type="Finish To Start",lag_days=0) for a,b in edges]
    result=calculate(tasks,deps,CalendarSpec())
    assert result["critical_task_ids"]==[1,3,4]
    assert next(r for r in result["tasks"] if r["id"]==2)["slack_workdays"]==2
    assert result["finish_date"]=="2026-11-16"


@pytest.mark.parametrize("kind,lag,expected", [
    ("Finish To Start",0,"2026-11-11"), ("Finish To Start",1,"2026-11-12"),
    ("Start To Start",1,"2026-11-10"), ("Finish To Finish",1,"2026-11-11"),
    ("Start To Finish",2,"2026-11-11"), ("Start To Start",-1,"2026-11-09"),
])
def test_generalized_precedence(kind,lag,expected):
    tasks=[Obj(id=1,task_key="A",title="A",start_date=date(2026,11,9),due_date=date(2026,11,10)),Obj(id=2,task_key="B",title="B",start_date=date(2026,11,9),due_date=date(2026,11,9))]
    dep=Obj(depends_on_task_id=1,task_id=2,dependency_type=kind,lag_days=lag)
    result=calculate(tasks,[dep],CalendarSpec())
    assert result["tasks"][1]["start_date"]==expected


def test_stale_edit_incomplete_plan_and_terminal_task_are_atomic(client, db):
    _,pid,_,oh,_,_,_,_,_=setup_workspace(client, db)
    a=task(client,pid,oh,"SAFE-A","2026-11-09","2026-11-09")
    b=task(client,pid,oh,"SAFE-B","2026-11-10","2026-11-10")
    dep=client.post(BASE+"/task-dependencies",headers=oh,json={"source_task_id":a,"target_task_id":b,"dependency_type":"Finish To Start","lag_days":0})
    assert dep.status_code==201,dep.text
    path=f"{BASE}/projects/{pid}"
    payload={"task_id":a,"start_date":"2026-11-12","due_date":"2026-11-12"}
    plan=client.post(path+"/schedule-preview",headers=oh,json=payload).json()
    db.get(PMSTask,b).status="Done"; db.commit()
    assert client.post(path+"/schedule-apply",headers=oh,json={**payload,"expected_revision":plan["revision"]}).status_code==409
    # Set up the terminal-task case independently of stale-write rejection.
    db.get(PMSTask,b).status="Done"; db.commit()
    plan=client.post(path+"/schedule-preview",headers=oh,json=payload).json()
    assert b in [c["id"] for c in plan["changes"]], plan
    assert client.post(path+"/schedule-apply",headers=oh,json={**payload,"expected_revision":plan["revision"]}).status_code==409
    db.expire_all(); assert db.get(PMSTask,a).start_date==date(2026,11,9)
    task(client,pid,oh,"UNSCHEDULED",None,None)
    plan=client.post(path+"/schedule-preview",headers=oh,json={}).json()
    assert plan["complete"] is False
    assert client.post(path+"/schedule-apply",headers=oh,json={"expected_revision":plan["revision"]}).status_code==409


def test_cycle_and_invalid_calendar_rejected(client, db):
    _,pid,_,oh,_,_,_,_,_=setup_workspace(client, db)
    a=task(client,pid,oh,"CYCLE-A","2026-11-09","2026-11-09")
    b=task(client,pid,oh,"CYCLE-B","2026-11-10","2026-11-10")
    tasks=[Obj(id=t,task_key=str(t),title=str(t),start_date=date(2026,11,9),due_date=date(2026,11,10)) for t in (a,b)]
    deps=[Obj(task_id=y,depends_on_task_id=x,dependency_type="Finish To Start",lag_days=0) for x,y in [(a,b),(b,a)]]
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc: calculate(tasks,deps,CalendarSpec())
    assert exc.value.status_code==409
    path=f"{BASE}/projects/{pid}/schedule-preview"
    assert client.post(path,headers=oh,json={"calendar":{"weekdays":[]}}).status_code==422


@pytest.mark.skipif(os.environ.get("RUN_PMS_SCHEDULING_BROWSER")!="1",reason="Explicit disposable browser integration")
def test_scheduling_browser_with_disposable_api(client,db):
    from tests.workflow_browser_utils import run_browser
    _,pid,_,oh,_,_,_,_,_=setup_workspace(client,db)
    a=task(client,pid,oh,"UI-A","2026-11-09","2026-11-10")
    b=task(client,pid,oh,"UI-B","2026-11-11","2026-11-12")
    r=client.post(BASE+"/task-dependencies",headers=oh,json={"source_task_id":a,"target_task_id":b,"dependency_type":"Finish To Start","lag_days":0})
    assert r.status_code==201,r.text
    run_browser(client,db,"test-advanced-scheduling.cjs",{"WORKFLOW_TEST_TOKEN":oh["Authorization"].split(" ",1)[1],"WORKFLOW_TEST_PROJECT":str(pid),"WORKFLOW_TEST_TASK":str(a)})
