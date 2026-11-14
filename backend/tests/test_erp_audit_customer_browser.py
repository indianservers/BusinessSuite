"""Actual customer creation must survive list refreshes with its selected entity kind."""
import os
import pytest
from tests.test_contact_directory import directory_identity


@pytest.mark.skipif(os.environ.get('RUN_CUSTOMER_BROWSER')!='1',reason='Explicit disposable customer browser integration')
def test_customer_creation_real_browser_and_sql_directories(client,db,superuser_headers,directory_identity):
    if db.get_bind().dialect.name!='sqlite':
        pytest.skip('Disposable browser profile copies an isolated SQLite fixture')
    from app.apps.crm.models import CRMCompany
    from tests.workflow_browser_utils import run_browser
    before=db.query(CRMCompany).count()
    run_browser(client,db,'test-customer-live-workflow.cjs',{
        'CUSTOMER_TOKEN':superuser_headers['Authorization'].split(' ',1)[1],
        'CUSTOMER_COMPANY':'1','CUSTOMER_BRANCH':str(directory_identity.id)},timeout_seconds=300)
    db.expire_all()
    assert db.query(CRMCompany).count()==before
