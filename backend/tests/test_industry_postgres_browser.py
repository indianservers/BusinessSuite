"""Full browser money workflow on an explicitly disposable migrated PostgreSQL DB."""
import os
import pytest
from sqlalchemy.orm import Session
from tests.test_industry_operations import business
from tests.test_contact_directory import directory_identity

pytestmark = pytest.mark.skipif(
    os.environ.get('RUN_INDUSTRY_POSTGRES_BROWSER') != '1',
    reason='Explicit disposable PostgreSQL browser profile only',
)


@pytest.fixture
def db(db_engine):
    url = db_engine.url
    if (os.environ.get('INDUSTRY_DISPOSABLE_BROWSER') != '1'
            or url.get_backend_name() != 'postgresql'
            or url.host not in {'localhost', '127.0.0.1', '::1'}
            or not (url.database or '').startswith('business_suite_qa_')
            or not url.database.endswith('_test')):
        pytest.fail('This committed-session browser profile requires its own guarded disposable runner')
    # Unlike rollback-only API fixtures, committed seeds must be visible to the
    # independent HTTP sessions used by real browsers. The runner owns the DB.
    with Session(db_engine, autoflush=False) as session:
        yield session


def test_salon_and_construction_postgres_browser_money_lifecycle(client, db, business):
    from app.apps.project_management.models import PMSProject, PMSTask
    from app.apps.srm.models import SRMInvoice, SRMReceipt
    from app.apps.srm.industry_models import IndustryRecord
    from test_identity_utils import own_workflow_records
    from tests.workflow_browser_utils import run_browser
    h, _, project, _ = business
    salon = PMSProject(organization_id=1, name='Salon delivery project', project_key='SALONDEL', manager_user_id=project.manager_user_id)
    db.add(salon); db.flush(); own_workflow_records(db, salon); db.commit()
    run_browser(client, db, 'test-industry-live-workflow.cjs', {
        'INDUSTRY_TOKEN': h['Authorization'].split(' ', 1)[1],
        'INDUSTRY_BRANCH': h['X-Suite-Branch'], 'INDUSTRY_PROJECT': str(project.id),
        'INDUSTRY_SALON_PROJECT': str(salon.id),
    }, timeout_seconds=360)
    db.expire_all()
    invoices = db.query(SRMInvoice).all()
    assert len(invoices) == 4 and all(i.balance_amount == 0 for i in invoices)
    assert db.query(SRMReceipt).count() == 4
    assert db.query(PMSTask).filter(PMSTask.task_key.like('SALON-%')).count() == 2
    assert db.query(IndustryRecord).filter_by(kind='appointment', status='completed').count() == 2
    assert db.query(IndustryRecord).filter_by(kind='measurement', status='approved').count() == 2
