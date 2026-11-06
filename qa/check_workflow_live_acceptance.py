"""Explicit live acceptance using isolated QA records and no invitations or mail."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
from urllib.parse import urlsplit
from uuid import uuid4
import httpx

ROOT = Path(__file__).resolve().parents[1]
PMS = "/api/v1/project-management"


def run(base, credentials_file, destination):
    assert urlsplit(base).hostname in {"app.dsbchartered.com", "app.indianservers.com", "127.0.0.1", "localhost"}
    credentials = json.loads(Path(credentials_file).read_text())
    run_id = uuid4().hex[:10]
    report = {"site": base, "run_id": run_id, "checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "checks": [], "cleanup": [], "fixture": {"user_ids": [], "member_ids": []}}
    fixture = report["fixture"]
    admin = {}; company = None
    def record(label, response, statuses=(200,)):
        report["checks"].append({"check": label, "status": response.status_code, "passed": response.status_code in statuses})
        destination.write_text(json.dumps(report, indent=2))
        if response.status_code not in statuses:
            detail = response.json().get("detail", "") if response.headers.get("content-type", "").startswith("application/json") else ""
            raise RuntimeError(f"{label}: HTTP {response.status_code}: {detail}")
        return response.json() if response.content else {}
    with httpx.Client(base_url=base, timeout=40) as client:
        try:
            login = record("administrator login", client.post("/api/v1/auth/login", json={"email": credentials["email"], "password": credentials["password"]}))
            admin = {"Authorization": "Bearer " + login["access_token"]}
            profile = record("administrator profile", client.get("/api/v1/auth/me", headers=admin))
            assert profile["is_superuser"]
            step = record("administrator reauthentication", client.post("/api/v1/access/step-up", headers=admin, json={"password": credentials["password"]}))
            admin["X-Access-Step-Up"] = step["token"]
            context = record("branch context", client.get("/api/v1/branches/context", headers=admin))
            company = context["company_id"]
            qa_branch = record("create isolated QA branch", client.post("/api/v1/branches", headers=admin,
                json={"name": "Workflow QA "+run_id, "code": "WQA"+run_id.upper(), "reason": "Isolated workflow acceptance "+run_id}), (201,))
            fixture["branch_id"] = branch = qa_branch["id"]
            destination.write_text(json.dumps(report, indent=2))
            admin.update({"X-Suite-Branch": str(branch), "X-Suite-Organization": str(company)})
            actors = []
            for name in ["requester", "reviewer", "final-reviewer"]:
                password = "Qa7!"+secrets.token_urlsafe(24)
                email = f"workflow-acceptance-{run_id}-{name}@example.com"
                created = record("create QA "+name, client.post("/api/v1/access/users", headers=admin, json={
                    "companyId": company, "name": "Workflow acceptance "+name+" "+run_id,
                    "email": email, "password": password, "invite": False, "reason": "Isolated workflow production acceptance "+run_id}), (201,))
                user = created["user"]; uid = user["id"]; fixture["user_ids"].append(uid)
                destination.write_text(json.dumps(report, indent=2))
                grants = {"project_management": {"enabled": True, "role": "Workflow acceptance tester", "scope": "organization",
                    "permissions": ["pms_view", "pms_manage_tasks"], "actions": ["view", "create", "edit", "approve"]}}
                record("grant PMS-only access "+name, client.post("/api/v1/access/changes/apply", headers=admin, json={
                    "companyId": company, "changes": [{"userId": uid, "version": user["version"], "grants": grants}],
                    "reason": "PMS-only workflow acceptance "+run_id}))
                policy = record("read QA branch policy "+name, client.get(f"/api/v1/branches/access/{uid}", headers=admin))
                record("grant QA branch "+name, client.put(f"/api/v1/branches/access/{uid}", headers=admin, json={
                    "expected_version": policy["version"], "all_branches": False, "manage_access": False, "use_home_branch": False,
                    "grants": [{"branch_id": branch, "can_write": True}], "reason": "Isolated workflow acceptance branch "+run_id}))
                session = record("QA login "+name, client.post("/api/v1/auth/login", json={"email": email, "password": password}))
                actors.append({"id": uid, "headers": {"Authorization": "Bearer "+session["access_token"],
                    "X-Suite-Branch": str(branch), "X-Suite-Organization": str(company)}})
            requester, reviewer, final_reviewer = actors
            workspace = record("create QA workspace", client.post(PMS+"/workspaces", headers=admin,
                json={"name": "Workflow acceptance "+run_id+" (QA only)"}), (201,))
            fixture["workspace_id"] = wid = workspace["id"]
            for actor in actors:
                member = record("add QA member", client.post(f"{PMS}/workspaces/{wid}/members", headers=admin,
                    json={"user_id": actor["id"], "role": "Member"}), (201,))
                fixture["member_ids"].append(member["id"])
            project = record("create QA project", client.post(PMS+"/projects", headers=admin,
                json={"name": "Workflow acceptance "+run_id, "project_key": "WQA"+run_id.upper(), "workspace_id": wid}))
            fixture["project_id"] = pid = project["id"]
            destination.write_text(json.dumps(report, indent=2))
            route = {"revision": 0, "enabled": True, "transitions": [
                {"source": "To Do", "target": "Done", "approval_user_ids": [reviewer["id"], final_reviewer["id"]]},
                {"source": "Done", "target": "To Do"}], "work_type_transitions": {"Bug": [
                {"source": "To Do", "target": "In Review", "approval_user_ids": [final_reviewer["id"]]}]}}
            record("publish type-aware approval routes", client.put(f"{PMS}/projects/{pid}/workflow-scheme", headers=admin, json=route))
            normal = record("create QA task", client.post(f"{PMS}/projects/{pid}/tasks", headers=requester["headers"],
                json={"title": "Workflow acceptance "+run_id, "task_key": "WQA-"+run_id}))
            tid = normal["id"]; fixture["task_id"] = tid
            url = f"{PMS}/tasks/{tid}"
            record("unreviewed transition blocked", client.patch(url, headers=requester["headers"], json={"status": "Done"}), (409,))
            def ask(): return record("request transition", client.post(url+"/transition-approvals", headers=requester["headers"], json={"target": "Done"}), (201,))
            def decision(approval, actor, value, *, step_id=None, task_url=url):
                review_id = step_id or approval["steps"][0]["id"]
                return client.put(f"{task_url}/transition-approvals/{approval['id']}/steps/{review_id}/decision", headers=actor, json={"decision": value, "reason": "Workflow acceptance "+run_id})
            first = ask(); duplicate = ask(); assert first["id"] == duplicate["id"]
            record("self review denied", decision(first, requester["headers"], "approve"), (403,))
            record("reviewer rejection", decision(first, reviewer["headers"], "reject"))
            second = ask(); assert second["id"] != first["id"]
            record("first ordered review", decision(second, reviewer["headers"], "approve"))
            record("partial review cannot apply", client.patch(url, headers=requester["headers"], json={"status": "Done"}), (409,))
            current = record("read ordered reviews", client.get(url+"/transition-approvals", headers=admin))["requests"][0]
            pending = next(s for s in current["steps"] if s["status"] == "Pending")
            record("final ordered review", decision(current, final_reviewer["headers"], "approve", step_id=pending["id"]))
            record("apply approved transition", client.patch(url, headers=requester["headers"], json={"status": "Done"}))
            record("cycle task back", client.patch(url, headers=requester["headers"], json={"status": "To Do"}))
            record("approval replay denied", client.patch(url, headers=requester["headers"], json={"status": "Done"}), (409,))
            stale = ask()
            record("edit saved task", client.patch(url, headers=requester["headers"], json={"description": "New acceptance revision"}))
            record("stale review denied", decision(stale, reviewer["headers"], "approve"), (409,))
            bug = record("create QA Bug", client.post(f"{PMS}/projects/{pid}/tasks", headers=requester["headers"],
                json={"title": "Workflow Bug acceptance "+run_id, "task_key": "WQAB-"+run_id, "work_type": "Bug"}))
            bug_url = f"{PMS}/tasks/{bug['id']}"
            record("Bug override blocks default edge", client.patch(bug_url, headers=requester["headers"], json={"status": "Done"}), (409,))
            bug_review = record("request Bug review", client.post(bug_url+"/transition-approvals", headers=requester["headers"], json={"target": "In Review"}), (201,))
            record("approve Bug route", decision(bug_review, final_reviewer["headers"], "approve", task_url=bug_url))
            record("apply Bug route", client.patch(bug_url, headers=requester["headers"], json={"status": "In Review"}))
            report["passed"] = True
        except Exception as exc:
            report["passed"] = False; report["failure"] = str(exc) or type(exc).__name__
        finally:
            def cleanup(label, call):
                try:
                    response = call(); report["cleanup"].append({"action": label, "status": response.status_code, "passed": response.status_code == 200})
                except Exception as exc: report["cleanup"].append({"action": label, "error": type(exc).__name__, "passed": False})
            for uid in fixture["user_ids"]:
                def suspend(uid=uid):
                    snapshot = client.get(f"/api/v1/access/users/{uid}", headers=admin, params={"companyId": company}).json()
                    return client.post("/api/v1/access/changes/apply", headers=admin, json={"companyId": company,
                        "changes": [{"userId": uid, "version": snapshot["version"], "grants": {}, "status": "suspended"}],
                        "reason": "Clean up workflow acceptance "+run_id})
                cleanup("suspend QA user "+str(uid), suspend)
            for mid in fixture["member_ids"]:
                cleanup("remove QA workspace member "+str(mid), lambda mid=mid: client.delete(f"{PMS}/workspaces/{fixture['workspace_id']}/members/{mid}", headers=admin))
            if fixture.get("project_id"):
                cleanup("trash QA project", lambda: client.delete(f"{PMS}/projects/{fixture['project_id']}", headers=admin))
            if fixture.get("branch_id"):
                cleanup("trash isolated QA branch", lambda: client.post(f"/api/v1/branches/{fixture['branch_id']}/trash", headers=admin,
                    json={"expected_version": 0, "reason": "Clean up isolated workflow acceptance "+run_id}))
            report["cleanup_note"] = "Created QA accounts are suspended and the QA project/branch are in Trash. Workspace and audit history are retained. No invitations or mail were sent."
            destination.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0 if report.get("passed") and all(c["passed"] for c in report["cleanup"]) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--credentials-file", required=True)
    parser.add_argument("--output", default=str(ROOT / "outputs/workflow-live-acceptance.json"))
    args = parser.parse_args()
    raise SystemExit(run(args.base_url.rstrip("/"), args.credentials_file, Path(args.output)))
