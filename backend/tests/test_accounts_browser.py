import json
from sqlalchemy import select
from app.business_packs.accounting_firm.models import AccountsPeriod
from tests.test_accounts_periods import accounts,scenario,catalog,directory_identity


def test_native_accounts_manager_preparer_reviewer_desktop_mobile(client,db,accounts,monkeypatch):
    from tests.test_control_browser import test_control_center_real_browser
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT','accounts-native.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH',json.dumps({'branch':str(accounts['branch']),'context':str(accounts['context']),
        'manager':accounts['headers']['Authorization'].split(' ',1)[1],
        'preparer':accounts['preparer']['headers']['Authorization'].split(' ',1)[1],
        'reviewer':accounts['reviewer']['headers']['Authorization'].split(' ',1)[1],
        'engagement':accounts['engagement'],'preparer_employee':accounts['preparer']['employee'],'reviewer_employee':accounts['reviewer']['employee']}))
    test_control_center_real_browser(client,db,None,accounts['headers'])
    row=db.connection().execute(select(AccountsPeriod.__table__)).mappings().one()
    assert row['state']=='approved' and row['approved_work_revision']==1
