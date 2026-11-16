import asyncio
from datetime import timedelta

import pytest
from app.apps.crm.models import CRMTask
from app.apps.power_apps.models import TelegramActionApproval
from app.ai_operator.suite_models import SuiteRun
from app.apps.power_apps import telegram_ai, telegram_approvals
from app.apps.power_apps.runtime import now
from tests.test_power_runtime import db
from tests.test_power_apps import actors
from tests.test_telegram_operations import bot, ROOT
from tests.test_telegram_experience import deliver
from tests.test_telegram_ai import ai_permission
from tests.test_telegram_booking_flow import review_button


@pytest.fixture
def proposed(client, db, actors, bot):
    resource, _, owner, _, _ = bot
    ai_permission(db, owner)
    response = client.post(f'{ROOT}/{resource.id}/link-code', headers=actors[0], json={'interface': 'company'})
    assert response.status_code == 200
    deliver(db, bot, 1, text=response.json()['command'], sender_id=77)
    deliver(db, bot, 2, text='Create a CRM task called "Telegram reviewed action"', sender_id=77)
    asyncio.run(telegram_ai.dispatch(db, client.app))
    run = db.query(SuiteRun).one()
    # Reconstruct an old, pre-view-only review to exercise persisted queue fences.
    import hashlib
    from app.apps.power_apps.models import TelegramConversation, TelegramIdentity
    thread = db.query(TelegramConversation).filter_by(interface='company').one()
    linked = db.get(TelegramIdentity, thread.identity_id)
    token = 'a' * 32
    operation = {'suite_run_id': run.id, 'plan_hash': run.plan_hash,
        '_binding': telegram_approvals.binding(linked), '_preview': ['Legacy company action']}
    approval = TelegramActionApproval(resource_id=resource.id, organization_id=resource.organization_id,
        environment=resource.environment, conversation_id=thread.id, identity_id=linked.id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(), kind='suite', operation=operation,
        operation_hash=telegram_approvals.digest(operation), status='pending', result={'viewed_page': 0},
        expires_at=now() + timedelta(minutes=15))
    db.add(approval); db.commit()
    return resource, approval, run, 'approve:' + token


def test_company_action_is_cancelled_and_legacy_review_cannot_execute(client, db, actors, bot, proposed):
    _, approval, run, button = proposed
    assert run.status == 'cancelled'
    deliver(db, bot, 3, callback=button, sender_id=77)
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    from app.ai_operator.suite import process_suite_batch
    assert asyncio.run(process_suite_batch(db, client.app)) == 0
    assert db.query(CRMTask).count() == 0


@pytest.mark.parametrize('status', ['approve_requested', 'executing'])
def test_persisted_company_queue_cannot_bypass_view_only(client, db, bot, proposed, status):
    _, approval, _, _ = proposed
    approval.status = status
    db.commit()
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    db.refresh(approval)
    assert approval.status == ('needs_reconciliation' if status == 'executing' else 'failed')
    assert db.query(CRMTask).count() == 0


def test_non_telegram_origins_unchanged_but_legacy_company_origin_denied():
    from types import SimpleNamespace
    from fastapi import HTTPException
    assert telegram_approvals.validate_origin(None, None, SimpleNamespace(result={})) is None
    with pytest.raises(HTTPException) as error:
        telegram_approvals.validate_origin(None, None, SimpleNamespace(result={'telegram_origin': {'resource_id': 1}}))
    assert error.value.status_code == 403
