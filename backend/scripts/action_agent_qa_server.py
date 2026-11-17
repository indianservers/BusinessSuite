"""Disposable live action-agent API with a worker; never uses the app database.

Reuses the navigation QA users and isolated storage. Bind only to loopback.
External providers are deliberately disabled by the underlying QA environment.
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import runpy
import os

qa = runpy.run_path(str(Path(__file__).with_name('suite_navigation_qa_server.py')))
app = qa['app']
SessionLocal = qa['SessionLocal']

# Complete only this disposable company's workflow prerequisites.
from datetime import date
from app.models.user import User
from app.models.employee import Employee
from app.apps.business_os.models import BOSEnabledModule
from test_identity_utils import attach_workflow_branch, provision_workflow_workspace, own_workflow_records
from tests.srm_test_utils import seed_invoice_parties
with SessionLocal() as db:
    actor = db.query(User).filter_by(email='admin@suiteqa.example.com').one()
    attach_workflow_branch(db, actor)
    provision_workflow_workspace(db, actor)
    employee = Employee(employee_id='ACTION-QA', first_name='Action', last_name='QA',
                        user_id=actor.id, date_of_joining=date.today())
    db.add(employee)
    own_workflow_records(db, employee)
    seed_invoice_parties(db)
    db.query(BOSEnabledModule).filter_by(company_id=1).update({'enabled': True})
    db.commit()


@asynccontextmanager
async def lifespan(application):
    from app.ai_operator.suite import process_suite_batch

    async def worker():
        while True:
            # SQLite permits one writer. Match the QA request serialization,
            # including the context marker used by nested canonical ASGI calls.
            async with qa['request_lock']:
                token = qa['inside_qa_request'].set(True)
                try:
                    with SessionLocal() as db:
                        await process_suite_batch(db, application, limit=12)
                finally:
                    qa['inside_qa_request'].reset(token)
            await asyncio.sleep(.25)

    task = asyncio.create_task(worker())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app.router.lifespan_context = lifespan

if __name__ == '__main__':
    import uvicorn
    try:
        uvicorn.run(app, host='127.0.0.1', port=int(os.environ.get('SUITE_QA_PORT', '1558')), log_level='warning')
    finally:
        qa['engine'].dispose()
        qa['temporary'].cleanup()
