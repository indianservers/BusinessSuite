import asyncio
import json
from datetime import timedelta
from urllib.parse import unquote

from app.ai_operator.suite_models import SuiteRun
from app.apps.crm.models import CRMTask
from app.apps.power_apps import telegram_approvals
from app.apps.power_apps.models import PowerExecution
from app.apps.power_apps.runtime import now
from app.apps.power_apps.runtime_models import AutomationJob, AutomationRun
from app.apps.power_apps.integrations.transport import Response
from tests.test_power_runtime import db, publish, run as start_run
from tests.test_power_apps import actors
from tests.test_telegram_operations import bot
from tests.test_telegram_experience import deliver
from tests.test_telegram_action_approvals import proposed


def test_telegram_worker_claims_only_telegram_and_skips_other_schedulers(client, db, actors, bot, monkeypatch):
    from app.apps.power_apps import worker
    manual = publish(client, actors[0])
    manual_id = start_run(client, actors[0], manual)
    unrelated_suite = SuiteRun(user_id=bot[2].id, scope_key='company:1',
        request_key='manual-suite-before-telegram', request_hash='b' * 64,
        command='Unrelated queued agent request', status='queued', result={})
    db.add(unrelated_suite)
    db.commit()
    bot[4]('/start')
    telegram_ids = [ident for ident, in db.query(AutomationRun.id).filter_by(trigger_kind='telegram').all()]
    assert telegram_ids

    def unrelated(*args, **kwargs):
        raise AssertionError('Telegram-only mode invoked an unrelated scheduler')

    async def no_ai(*args, **kwargs):
        assert args[1] is application
        return 0

    monkeypatch.setattr(worker, 'tick', unrelated)
    monkeypatch.setattr(worker, 'scheduler_tick', unrelated)
    monkeypatch.setattr('app.apps.power_apps.integrations.automation_triggers.poll_tick', unrelated)
    monkeypatch.setattr('app.apps.power_apps.integrations.marketplace_sync.dispatch_due', unrelated)
    monkeypatch.setattr('app.apps.power_apps.integrations.google_leads.dispatch_due', unrelated)
    monkeypatch.setattr('app.apps.power_apps.integrations.health_alerts.dispatch', unrelated)
    monkeypatch.setattr('app.apps.power_apps.runtime_retention.purge_payloads', unrelated)
    monkeypatch.setattr('app.apps.power_apps.integrations.native_runtime.tick', unrelated)
    monkeypatch.setattr('app.apps.power_apps.telegram.poll_tick', lambda *args: 0)
    monkeypatch.setattr('app.apps.power_apps.telegram_ai.dispatch', no_ai)
    from fastapi import FastAPI
    application = FastAPI()
    sent = []

    class Transport:
        def __init__(self, policy):
            pass

        def request(self, method, url, **kwargs):
            assert unquote(url).endswith('/sendMessage')
            sent.append(json.loads(kwargs['body']))
            return Response(200, {}, b'{"ok":true,"result":{"message_id":100}}', 1)

    monkeypatch.setattr('app.apps.power_apps.integrations.adapters.HTTP_FACTORY', Transport)
    for _ in range(10):
        if not worker.worker_tick(db, 'telegram-scoped-test', telegram_only=True, application=application):
            break
    assert sent and all(str(message['chat_id']) == '42' for message in sent)
    assert all(db.get(PowerExecution, ident).status == 'completed' for ident in telegram_ids)
    assert db.get(PowerExecution, manual_id).status == 'queued'
    assert db.query(AutomationJob).filter_by(run_id=manual_id, status='queued').count() == 1
    db.refresh(unrelated_suite)
    assert unrelated_suite.status == 'queued' and not unrelated_suite.error_code


def test_telegram_suite_filter_leaves_other_queued_waiting_and_expired_runs_untouched(client, db, actors, bot, proposed):
    from app.ai_operator.suite import process_suite_batch
    _, _, telegram_run, button = proposed
    others = []
    for index, status in enumerate(['queued', 'waiting_pms', 'executing']):
        other = SuiteRun(user_id=telegram_run.user_id, scope_key=telegram_run.scope_key,
            request_key=f'non-telegram-{index}', request_hash='a' * 64, command='Unrelated authorized work',
            status=status, result={}, lease_until=now() - timedelta(minutes=10))
        db.add(other)
        others.append(other)
    db.commit()
    deliver(db, bot, 3, callback=button, sender_id=77)
    asyncio.run(telegram_approvals.dispatch(db, client.app))
    assert asyncio.run(process_suite_batch(db, client.app, telegram_only=True)) == 1
    db.refresh(telegram_run)
    assert telegram_run.status == 'succeeded'
    assert db.query(CRMTask).one().title == 'Telegram reviewed action'
    for other, expected in zip(others, ['queued', 'waiting_pms', 'executing']):
        db.refresh(other)
        assert other.status == expected and not other.error_code
    assert asyncio.run(process_suite_batch(db, client.app, telegram_only=True)) == 0
