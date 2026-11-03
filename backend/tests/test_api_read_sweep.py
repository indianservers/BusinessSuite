"""Schema-driven read smoke over every fixed API path without required inputs."""
import json
from pathlib import Path


def test_fixed_api_reads_do_not_crash(client, db, superuser_headers):
    from app.main import app
    from app.models.user import User
    from test_identity_utils import attach_test_identity, attach_workflow_branch
    actor = db.query(User).filter_by(email="testadmin@test.com").one()
    attach_test_identity(db, actor)
    branch = attach_workflow_branch(db, actor)
    db.commit()
    headers = {**superuser_headers, "X-Suite-Branch": str(branch.id)}
    schema = app.openapi()
    results = []
    target = Path(__file__).resolve().parents[2] / ".local" / "api-read-sweep.json"
    # No optional external systems are configured by conftest. No writes or
    # outbound messages are issued by this read-only contract sweep.
    for path, operations in sorted(schema["paths"].items()):
        operation = operations.get("get")
        if not operation or "{" in path or not path.startswith("/api/v1/"):
            continue
        if any(p.get("required") for p in operation.get("parameters", [])):
            continue
        if any(segment in path for segment in ("/realtime/events", "/stream", "/websocket", "/sse")):
            continue
        if path.endswith(("/export", ".pdf", ".xlsx", ".csv")):
            continue
        target.write_text(json.dumps({"current":path,"results":results,"complete":False},indent=2),encoding="utf-8")
        try:
            response = client.get(path, headers=headers)
            expected_unconfigured = path == "/api/v1/integrations/whatsapp/webhook" and response.status_code == 503 and "configured" in response.text.lower()
            results.append({"path":path,"status":response.status_code, "expectedUnconfigured":expected_unconfigured})
        except Exception as exc:
            results.append({"path":path,"status":500,"error":type(exc).__name__+": "+str(exc)[:300]})
            db.rollback()
    target = Path(__file__).resolve().parents[2] / ".local" / "api-read-sweep.json"
    target.write_text(json.dumps({"results":results,"complete":True},indent=2),encoding="utf-8")
    failures = [x for x in results if x["status"] >= 500 and not x.get("expectedUnconfigured")]
    assert not failures, json.dumps(failures,indent=2)
