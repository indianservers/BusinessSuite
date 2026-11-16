import asyncio
import json
from datetime import timedelta

import pytest

from app.apps.crm.models import CRMTask
from app.apps.power_apps import telegram_approvals
from app.apps.power_apps.runtime import now, utc
from app.models.user import UserSession
from tests.test_power_runtime import db
from tests.test_power_apps import actors
from tests.test_telegram_operations import bot
from tests.test_telegram_experience import deliver
from tests.test_telegram_action_approvals import proposed


def test_distinct_employee_channel_session_executes_as_employee(client, db, actors, bot):
    from tests.test_telegram_ai import test_company_model_uses_distinct_employees_ai_identity
    from tests.test_telegram_booking_flow import review_button
    from app.ai_operator.suite_models import SuiteRun
    from app.ai_operator.suite import process_suite_batch
    test_company_model_uses_distinct_employees_ai_identity(client, db, actors, bot)
    run = db.query(SuiteRun).one()
    session = db.get(UserSession, run.session_id)
    assert session.user_id == run.user_id != bot[2].id
    deliver(db, bot, 10, callback=review_button(db), sender_id=123)
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    assert asyncio.run(process_suite_batch(db, client.app)) == 1
    db.refresh(run)
    assert run.status == 'succeeded', (run.status, run.error_code)
    assert db.query(CRMTask).one().created_by_user_id == run.user_id


@pytest.mark.parametrize('change', ['none', 'revoked', 'expired'])
def test_short_lived_channel_session_is_bound_and_native_execution_rechecks_it(client, db, actors, bot, proposed, change):
    resource, approval, run, button = proposed
    session = db.get(UserSession, run.session_id)
    assert session and session.user_id == run.user_id
    assert session.device_name == 'Telegram AI agent' and not session.trusted_device
    provenance = json.loads(session.user_agent)
    assert provenance['identity_id'] == approval.identity_id
    assert provenance['resource_id'] == resource.id
    assert utc(session.expires_at) <= now() + timedelta(minutes=20)
    assert run.security_context['session_id'] == session.id
    deliver(db, bot, 3, callback=button, sender_id=77)
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    if change == 'revoked':
        session.status = 'Revoked'
    elif change == 'expired':
        session.expires_at = now() - timedelta(seconds=1)
    db.commit()
    from app.ai_operator.suite import process_suite_batch
    asyncio.run(process_suite_batch(db, client.app))
    db.refresh(run)
    if change == 'none':
        assert run.status == 'succeeded', (run.status, run.error_code)
        assert db.query(CRMTask).one().title == 'Telegram reviewed action'
    else:
        assert run.status == 'paused' and run.error_code == 'CANONICAL_STEP_401'
        assert db.query(CRMTask).count() == 0
