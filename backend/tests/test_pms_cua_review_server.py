"""Opt-in real API bridge for manual CUA review; never launches a browser.

Run with PMS_CUA_REVIEW_DIR pointing inside this checkout's ignored .local.
Create its stop file to finish. A passing bridge lifecycle is not UI acceptance.
"""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_pms_workspaces import middleware_database, BASE
from tests.test_pms_automations import setup_workspace
from app.apps.project_management.models import PMSTask, PMSWorkspaceMember, PMSComment
from app.models.workflow_engine import WorkflowInstance


@pytest.mark.skipif(not os.getenv("PMS_CUA_REVIEW_DIR"), reason="Opt-in manual CUA API bridge")
def test_manual_review_bridge(client, db):
    root=Path(__file__).resolve().parents[2]
    review=Path(os.environ["PMS_CUA_REVIEW_DIR"]).resolve()
    assert review.is_relative_to(root/".local"), "Manual review must use ignored local artifacts"
    review.mkdir(parents=True,exist_ok=True)
    wid,pid,owner,oh,ah,member,mh,guest,gh=setup_workspace(client,db)
    admin_id=db.query(PMSWorkspaceMember).filter_by(workspace_id=wid,role="Admin").one().user_id
    scheme=client.put(f"{BASE}/projects/{pid}/workflow-scheme",headers=oh,json={
        "revision":0,"enabled":True,"transitions":[
            {"source":"To Do","target":"In Review"},
            {"source":"In Review","target":"Done","approval_user_ids":[admin_id]},
            {"source":"Done","target":"To Do"}]})
    assert scheme.status_code==200,scheme.text
    task_ids=[]
    task_count=max(3,min(24,int(os.getenv("PMS_CUA_TASK_COUNT","3"))))
    for index in range(1,task_count+1):
        response=client.post(f"{BASE}/projects/{pid}/tasks",headers=mh,json={
            "task_key":f"CUA-{index}","title":f"Disposable API review task {index}",
            "description":"Local manual review only", "priority":"High"})
        assert response.status_code==200,response.text
        task_ids.append(response.json()["id"])
    roles={}
    for name,headers in {"owner":oh,"reviewer":ah,"member":mh,"guest":gh}.items():
        profile=client.get("/api/v1/auth/me",headers=headers)
        access=client.get("/api/v1/access/me",headers=headers)
        branch=client.get("/api/v1/branches/context",headers=headers)
        assert profile.status_code==access.status_code==branch.status_code==200,(name,profile.status_code,access.status_code,branch.status_code)
        roles[name]={"token":headers["Authorization"].split(" ",1)[1],
            "user":{**profile.json(),"access":access.json()},
            "company":access.json()["companyId"],"branch":branch.json()["selected"],
            "workspace":wid,"project":pid,"tasks":task_ids,"role":name}

    def evidence():
        db.expire_all()
        return {"workspace":wid,"project":pid,"tasks":[{
            "id":row.id,"title":row.title,"status":row.status,
            "comments":db.query(PMSComment).filter_by(task_id=row.id).count(),
        } for row in db.query(PMSTask).filter(PMSTask.id.in_(task_ids)).order_by(PMSTask.id)],
        "approvals":[{"id":row.id,"status":row.status} for row in db.query(WorkflowInstance).all()]}

    class Bridge(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def forward(self):
            parsed=urlsplit(self.path)
            if self.command=="GET" and parsed.path in {"/api/_qa/bootstrap","/api/_qa/evidence"}:
                if parsed.path.endswith("bootstrap"):
                    name=parse_qs(parsed.query).get("role",["member"])[0]
                    data=roles.get(name)
                    if data is None:self.send_error(400,"Unknown disposable role");return
                else:data=evidence()
                body=json.dumps(data).encode()
                self.send_response(200);self.send_header("Content-Type","application/json")
                self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(body)))
                self.end_headers();self.wfile.write(body);return
            headers={key:value for key,value in self.headers.items() if key.lower() not in {"host","content-length","connection","accept-encoding"}}
            payload=self.rfile.read(int(self.headers.get("Content-Length",0)))
            response=client.request(self.command,self.path,content=payload,headers=headers)
            self.send_response(response.status_code)
            for key,value in response.headers.items():
                if key.lower() not in {"content-length","content-encoding","transfer-encoding","connection"}:self.send_header(key,value)
            self.send_header("Content-Length",str(len(response.content)));self.end_headers()
            try:self.wfile.write(response.content)
            except (ConnectionAbortedError,BrokenPipeError,ConnectionResetError):pass
        do_GET=do_POST=do_PUT=do_PATCH=do_DELETE=forward

    class QueuedServer(HTTPServer):request_queue_size=128
    server=QueuedServer(("127.0.0.1",0),Bridge)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    ready={"bridge":f"http://127.0.0.1:{server.server_port}","workspace":wid,"project":pid,"tasks":task_ids}
    (review/"ready.json").write_text(json.dumps(ready),encoding="utf-8")
    print("Disposable PMS API bridge ready",flush=True)
    try:
        deadline=time.monotonic()+2700
        while not (review/"stop").exists() and time.monotonic()<deadline:
            threading.Event().wait(0.5)
        assert (review/"stop").exists(),"Manual review expired without a stop signal"
        (review/"evidence.json").write_text(json.dumps(evidence()),encoding="utf-8")
    finally:server.shutdown();server.server_close();thread.join(timeout=5)
