"""Real HTTP/browser acceptance fixture using a disposable database and no mail/AI."""
import suite_navigation_qa_server as qa
from app.models.company import Branch
from app.branches.models import BranchGrant

with qa.SessionLocal() as db:
    branch = Branch(name="UX acceptance branch", company_id=1, code="UXQA")
    db.add(branch)
    db.flush()
    for user in db.query(qa.User).all():
        db.add(BranchGrant(user_id=user.id, company_id=1, branch_id=branch.id, can_write=True))
    db.commit()

if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run(qa.app, host="127.0.0.1", port=1562, log_level="warning")
    finally:
        qa.engine.dispose()
        qa.temporary.cleanup()
