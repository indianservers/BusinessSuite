"""Use the real worker implementation, restricted to this audit's tagged approval."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import settings
from sqlalchemy.engine import make_url

url = make_url(settings.SQLALCHEMY_DATABASE_URI)
assert url.host in {"localhost", "127.0.0.1"} and url.database == "business_suite"
from app.db.base import Base
from app.db.session import SessionLocal
from app.apps.power_apps.approvals.models import RequestState
from app.models.approval_os import ApprovalRequest
from app.apps.power_apps.runtime import claim, process

state = json.loads((ROOT / ".tmp/workflow-board-live-records.json").read_text())
record = state["records"]["approval"]
with SessionLocal() as db:
    request = db.get(ApprovalRequest, record["id"])
    request_state = db.get(RequestState, record["id"])
    assert request.title == record["title"]
    assert request.requester_user_id == state["qaActors"]["requester"]["id"]
    run_id = request_state.run_id
    for _ in range(12):
        work = claim(db, "workflow-board-live-verification", run_ids=[run_id])
        if not work:
            break
        process(db, *work)
    db.expire_all()
    print(json.dumps({"request": record["id"], "run": run_id, "status": db.get(ApprovalRequest, record["id"]).status}))
