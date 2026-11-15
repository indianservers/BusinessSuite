"""Desktop/mobile Accounts delivery through real native HTTP and persisted sources."""
from copy import deepcopy
from decimal import Decimal
import json

from sqlalchemy import select
from app.access.models import AccessPolicy
from app.apps.project_management.models import PMSProjectMember, PMSTimeLog, PMSFileAsset, PMSProject, PMSTask
from app.apps.srm.models import SRMInvoice, SRMReceipt, SRMEngagement
from app.apps.crm.models import CRMCompany
from app.models.employee import Employee
from app.business_packs.models import PackContext
from app.business_packs.accounting_firm.models import AccountsPeriod, AccountsEngagementCommand
from tests.test_accounts_periods import accounts, scenario, catalog, directory_identity
from tests.test_accounts_actual_time import delivery
from tests.test_pms_attachment_operation import attachment_source
from tests.test_accounts_binary_uploads import binary_task
from tests.test_business_pack_http_integration import native_actor, grant


def test_native_accounts_delivery_all_workflows_desktop_mobile(client, db, accounts, binary_task, delivery, monkeypatch):
    from tests.test_control_browser import test_control_center_real_browser

    case = accounts
    for role in ('preparer', 'reviewer'):
        policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=case[role]['user'].id).one()
        values = deepcopy(policy.grants)
        values['project_management'] = {'enabled': True, 'permissions': ['pms_view'], 'actions': ['view'], 'scope': 'own'}
        if 'export' not in values['srm']['actions']:
            values['srm']['actions'].append('export')
        policy.grants = values
    reviewer_membership = db.query(PMSProjectMember).filter_by(
        project_id=delivery, user_id=case['reviewer']['user'].id).one_or_none()
    if reviewer_membership is None:
        db.add(PMSProjectMember(project_id=delivery, user_id=case['reviewer']['user'].id, role='Viewer'))
    else:
        assert reviewer_membership.role == 'Viewer'
    billing_headers, billing_actor = native_actor(db, case['branch'])
    grant(db, billing_actor, case['branch'], 'accounting_firm', 'billing_officer', db.get(PackContext, case['context']))
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=billing_actor.id).one()
    policy.grants = policy.grants | {'project_management': {
        'enabled': True, 'permissions': ['pms_view'], 'actions': ['view'], 'scope': 'own'}}
    db.add(PMSProjectMember(project_id=delivery, user_id=billing_actor.id, role='Viewer'))
    db.commit()
    masters_before = {model: db.query(model).count() for model in (PMSProject, PMSTask, CRMCompany, Employee)}
    engagements_before = db.query(SRMEngagement).count()

    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT', 'accounts-delivery-native.cjs')
    monkeypatch.setenv('VITE_CACHE_DIR', '../.local/vite-accounts-delivery-browser')
    monkeypatch.setenv('SUITE_QA_AUTH', json.dumps({
        'branch': str(case['branch']), 'context': str(case['context']),
        'manager': case['headers']['Authorization'].split(' ', 1)[1],
        'preparer': case['preparer']['headers']['Authorization'].split(' ', 1)[1],
        'reviewer': case['reviewer']['headers']['Authorization'].split(' ', 1)[1],
        'billing': billing_headers['Authorization'].split(' ', 1)[1],
        'client': 101, 'project': delivery, 'task': binary_task[0],
        'preparer_employee': case['preparer']['employee'], 'reviewer_employee': case['reviewer']['employee'],
    }))
    test_control_center_real_browser(client, db, None, case['headers'])

    periods = db.connection().execute(select(AccountsPeriod.__table__).order_by(AccountsPeriod.__table__.c.id)).mappings().all()
    assert len(periods) == 2
    assert [(row['starts_on'].isoformat(), row['ends_on'].isoformat(), row['due_on'].isoformat()) for row in periods] == [
        ('2026-01-01', '2026-01-31', '2026-02-10'), ('2026-02-01', '2026-02-28', '2026-03-10')]
    assert periods[0]['state'] == 'approved' and periods[0]['approved_work_revision'] == 2
    assert periods[1]['state'] == 'draft'
    assert db.query(AccountsEngagementCommand).count() == 1
    assert db.query(SRMEngagement).count() == engagements_before + 1
    assert {model: db.query(model).count() for model in masters_before} == masters_before
    assert db.query(PMSTimeLog).count() == 1
    time = db.query(PMSTimeLog).one()
    assert time.project_id == delivery and time.duration_minutes == 75
    assert time.user_id == case['preparer']['user'].id and time.approval_status == 'Pending' and time.timesheet_id is None
    assert db.query(PMSFileAsset).count() == 1
    file = db.query(PMSFileAsset).one()
    assert file.project_id == delivery and file.task_id == binary_task[0] and file.uploaded_by_user_id == case['preparer']['user'].id
    assert db.query(SRMInvoice).count() == 1 and db.query(SRMReceipt).count() == 2
    invoice = db.query(SRMInvoice).one()
    assert invoice.engagement_id == periods[0]['engagement_id'] and invoice.customer_id == 101
    assert invoice.total_amount == Decimal('1500.00') and invoice.paid_amount == Decimal('1500.00') and invoice.balance_amount == 0
