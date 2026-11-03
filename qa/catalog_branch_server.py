"""Loopback-only branch catalogue browser fixture, using a temporary database."""
from pathlib import Path
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
qa = runpy.run_path(str(Path(__file__).resolve().parents[1] / "backend/scripts/suite_navigation_qa_server.py"))

from app.models.company import Branch
from app.branches.models import BranchOwnership
from app.shared.catalog import save_item, ItemInput
from app.models.user import User

with qa["SessionLocal"]() as db:
    branches = [Branch(company_id=1, name="QA " + name, code="QA-" + name.upper()) for name in ("Main", "North", "South")]
    db.add_all(branches)
    db.flush()
    for branch in branches:
        db.add(BranchOwnership(resource_table="branches", resource_key=str(branch.id), company_id=1, branch_id=branch.id, source="catalog-browser-qa"))
    admin = db.query(User).filter_by(email="admin@suiteqa.example.com").one()
    admin._suite_branch_id = branches[0].id
    for kind in ("product", "service"):
        save_item(db, admin, "srm", ItemInput(kind=kind, name="QA Branch " + kind.title(), code="QA-BRANCH-" + kind.upper(), description="Reusable branch offering for browser verification", price=1200, tax=18, track_inventory=False, custom_fields={"Edition": "QA"}, pricing_options=[{"id": "annual", "name": "Annual", "amount": 10000, "currency": "INR", "interval": "year"}]))
    db.commit()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(qa["app"], host="127.0.0.1", port=1592, log_level="warning")
