"""Full Helpdesk UI against an isolated SQL copy, with only defaults fault-injected."""
import os
from datetime import date
import pytest
from ai_test_utils import auth_headers
from tests.test_ticket_actions import seed
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit


@pytest.mark.skipif(os.environ.get('RUN_HELPDESK_BROWSER')!='1',reason='Explicit disposable Helpdesk browser integration')
def test_helpdesk_browser_requester_and_manager_during_defaults_outage(client,db):
    if db.get_bind().dialect.name!='sqlite':
        pytest.skip('Disposable browser profile uses a copied SQLite fixture')
    from app.models.employee import Employee
    from app.models.helpdesk import HelpdeskCategory,HelpdeskTicket
    from tests.workflow_browser_utils import run_browser
    manager,actor,_=seed(client,db)
    requester,user=auth_headers(client,db,'helpdesk-browser-requester@example.com',permissions=['helpdesk_view'])
    branch=int(requester['X-Suite-Branch'])
    employee=Employee(employee_id='QA-HELPDESK-BROWSER',first_name='Helpdesk',last_name='Requester',user_id=user.id,branch_id=branch,date_of_joining=date(2026,1,1))
    category=HelpdeskCategory(name='QA browser support',sla_hours=8,is_active=True)
    db.add_all([employee,category]);db.commit();db.expire(user,['employee'])
    before=db.query(HelpdeskTicket).count()
    run_browser(client,db,'test-helpdesk-live-workflow.cjs',{
        'HD_MANAGER_TOKEN':manager['Authorization'].split(' ',1)[1],
        'HD_REQUESTER_TOKEN':requester['Authorization'].split(' ',1)[1],
        'HD_BRANCH':str(branch),'HD_COMPANY':'1','HD_CATEGORY':str(category.id)},timeout_seconds=300)
    db.expire_all()
    assert db.query(HelpdeskTicket).count()==before
