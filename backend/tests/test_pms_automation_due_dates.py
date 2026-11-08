from tests.test_pms_workspaces import middleware_database,BASE
from tests.test_pms_automations import setup_workspace
from tests.test_pms_advanced_scheduling import task
import os
import pytest


def test_due_action_logs_success_and_skips_inverted_dates(client,db):
    wid,pid,_,oh,_,_,_,_,gh=setup_workspace(client,db)
    path=f"{BASE}/workspaces/{wid}"
    rule=client.post(path+"/automations",headers=oh,json={"name":"Fixed delivery date","project_id":pid,"trigger":"task.created","action":"set_due_date","due_date":"2026-11-15"})
    assert rule.status_code==201,rule.text
    task(client,pid,oh,"AUTO-DUE-1","2026-11-09","2026-11-10")
    task(client,pid,oh,"AUTO-DUE-2","2026-11-20","2026-11-21")
    report=client.get(path+"/automation-runs/report?limit=1",headers=oh)
    assert report.status_code==200,report.text
    assert report.json()["counts"]=={"executed":1,"skipped":1}
    assert report.json()["items"][0]["metadata"]["reason"]=="Due date would be before task start"
    cursor=report.json()["next_cursor"]
    assert cursor
    older=client.get(path+f"/automation-runs/report?before_id={cursor}",headers=oh).json()
    assert older["items"][0]["metadata"]["after"]["due_date"]=="2026-11-15"
    assert client.get(path+"/automation-runs/report?outcome=skipped",headers=oh).json()["counts"]=={"executed":0,"skipped":1}
    assert client.get(path+"/automation-runs/report",headers=gh).status_code==403
    assert client.get(path+"/automation-runs/report?since=2026-12-01&until=2026-11-01",headers=oh).status_code==422
    assert client.post(path+"/automations",headers=oh,json={"name":"Invalid","project_id":pid,"trigger":"task.created","action":"set_due_date"}).status_code==422


@pytest.mark.skipif(os.environ.get("RUN_CRM_PMS_FUNCTIONALITY_BROWSER")!="1",reason="Explicit disposable browser integration")
def test_automation_browser_with_disposable_api(client,db):
    from tests.workflow_browser_utils import run_browser
    wid,pid,_,oh,_,_,_,_,_=setup_workspace(client,db)
    run_browser(client,db,"test-reporting-automation.cjs",{"WORKFLOW_TEST_TOKEN":oh["Authorization"].split(" ",1)[1],"WORKFLOW_TEST_WORKSPACE":str(wid),"WORKFLOW_TEST_PROJECT":str(pid),"FUNCTIONALITY_UI_MODE":"automation"})


def test_clock_due_date_action_reuses_replay_protection(client,db):
    from tests.test_pms_automation_schedules import fixture,task as clock_task,NOW
    from app.apps.project_management.automation_schedules import dispatch_due
    from app.apps.project_management.models import PMSTask
    from datetime import date
    wid,pid,owner,oh,member,mh,rule=fixture(client,db,action="set_due_date",due_date="2030-01-10")
    tid=clock_task(client,pid,mh,start_date="2030-01-01",due_date="2030-01-02")
    result=dispatch_due(db,now=NOW)
    assert result["failed_rule_ids"]==[],result
    assert result["processed"]==1
    assert db.get(PMSTask,tid).due_date==date(2030,1,10)
    assert dispatch_due(db,now=NOW)["processed"]==0


def test_due_date_action_does_not_reschedule_completed_work(client,db):
    wid,pid,_,oh,_,_,_,_,_=setup_workspace(client,db)
    r=client.post(f"{BASE}/workspaces/{wid}/automations",headers=oh,json={"name":"Do not move completed work","project_id":pid,"trigger":"task.status_changed","action":"set_due_date","due_date":"2030-03-15"})
    assert r.status_code==201,r.text
    tid=task(client,pid,oh,"DONE-DUE","2030-01-01","2030-01-02")
    complete=client.patch(f"{BASE}/tasks/{tid}",headers=oh,json={"status":"Done"})
    assert complete.status_code==200,complete.text
    assert complete.json()["due_date"]=="2030-01-02"
    report=client.get(f"{BASE}/workspaces/{wid}/automation-runs/report",headers=oh).json()
    assert report["counts"]["skipped"]==1
    assert report["items"][0]["metadata"]["reason"]=="Completed/cancelled task is not rescheduled"
