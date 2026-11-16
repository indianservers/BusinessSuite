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
    assert run.status == 'awaiting_approval', run.plan
    approval = db.query(TelegramActionApproval).one()
    return resource, approval, run, review_button(db)


def test_telegram_approval_executes_canonical_action_once(client, db, actors, bot, proposed):
    _, approval, run, button = proposed
    assert db.query(CRMTask).count() == 0
    deliver(db, bot, 3, callback=button, sender_id=77)
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    from app.ai_operator.suite import process_suite_batch
    assert asyncio.run(process_suite_batch(db, client.app)) == 1
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    db.refresh(run)
    assert run.status == 'succeeded', str((run.status, run.error_code, run.result))
    assert db.query(CRMTask).one().title == 'Telegram reviewed action'
    db.refresh(approval); db.refresh(run)
    assert approval.status == 'approved' and run.status == 'succeeded'
    assert approval.result['receipts']
    deliver(db, bot, 4, callback=button, sender_id=77)
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    assert asyncio.run(process_suite_batch(db, client.app)) == 0
    assert db.query(CRMTask).count() == 1


@pytest.mark.parametrize('change', ['expired', 'tampered', 'other_sender', 'rejected'])
def test_review_expiry_tampering_wrong_identity_and_rejection_block_execution(client, db, bot, proposed, change):
    _, approval, run, button = proposed
    sender = 77
    if change == 'expired':
        approval.expires_at = now() - timedelta(seconds=1); db.commit()
    elif change == 'tampered':
        approval.operation = {**approval.operation, 'plan_hash': '0' * 64}; db.commit()
    elif change == 'other_sender':
        sender = 88
    else:
        button = review_button(db, 'Reject')
    deliver(db, bot, 3, callback=button, sender_id=sender)
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    from app.ai_operator.suite import process_suite_batch
    assert asyncio.run(process_suite_batch(db, client.app)) == 0
    assert db.query(CRMTask).count() == 0
    db.refresh(run)
    assert run.status == ('cancelled' if change == 'rejected' else 'awaiting_approval')


def test_revoked_telegram_identity_blocks_already_approved_execution(client, db, actors, bot, proposed):
    resource, approval, run, button = proposed
    deliver(db, bot, 3, callback=button, sender_id=77)
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    assert client.delete(f'{ROOT}/{resource.id}/identities/{approval.identity_id}', headers=actors[0]).status_code == 200
    from app.ai_operator.suite import process_suite_batch
    asyncio.run(process_suite_batch(db, client.app))
    db.refresh(run)
    assert run.status == 'paused' and run.error_code == 'CANONICAL_STEP_403'
    assert db.query(CRMTask).count() == 0


def test_expiry_after_queue_does_not_claim_a_known_failed_outcome(client, db, bot, proposed):
    _, approval, _, button = proposed
    deliver(db, bot, 3, callback=button, sender_id=77)
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    approval.expires_at = now() - timedelta(seconds=1)
    db.commit()
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    db.refresh(approval)
    assert approval.status == 'needs_reconciliation'
    assert 'receipts before retrying' in approval.result['error']
    assert db.query(CRMTask).count() == 0
