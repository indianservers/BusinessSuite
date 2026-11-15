from uuid import uuid4
from sqlalchemy import select, func
import pytest

from app.business_packs.accounting_firm.models import AccountsPeriod, AccountsCommand
from tests.test_accounts_periods import accounts, scenario, catalog, directory_identity, body, send


def counts(db):
    return tuple(db.connection().scalar(select(func.count()).select_from(model.__table__))
                 for model in (AccountsPeriod, AccountsCommand))


def test_recurring_calendar_due_dates_and_exact_retry(client, db, accounts):
    payload = body(accounts) | {'occurrences': 3}
    result = send(client, accounts['headers'], '', payload, status=201)
    assert [(p['starts_on'], p['ends_on'], p['due_on']) for p in result['periods']] == [
        ('2026-01-01', '2026-01-31', '2026-02-10'),
        ('2026-02-01', '2026-02-28', '2026-03-10'),
        ('2026-03-01', '2026-03-31', '2026-04-10')]
    assert counts(db) == (3, 4)
    assert send(client, accounts['headers'], '', payload, status=201) == result
    assert counts(db) == (3, 4)
    send(client, accounts['headers'], '', payload | {'occurrences': 4}, status=409)
    assert counts(db) == (3, 4)


def test_recurring_late_collision_rolls_back_all_new_periods_and_retry(client, db, accounts):
    # The second occurrence collides after the first has already flushed.
    existing = body(accounts) | {'starts_on': '2026-02-01', 'ends_on': '2026-02-28', 'due_on': '2026-03-10'}
    send(client, accounts['headers'], '', existing, status=201)
    before = counts(db)
    payload = body(accounts) | {'occurrences': 3}
    send(client, accounts['headers'], '', payload, status=409)
    assert counts(db) == before
    # Reuse the failed UUID with a corrected explicit schedule: no phantom command.
    result = send(client, accounts['headers'], '', payload | {
        'starts_on': '2026-03-01', 'ends_on': '2026-03-31', 'due_on': '2026-04-10'}, status=201)
    assert len(result['periods']) == 3
    assert counts(db) == (4, 5)


@pytest.mark.parametrize('extra', [{'occurrences': 0}, {'occurrences': 37}, {'occurrences': True},
    {'interval_months': 0}, {'interval_months': 13}, {'occurrences': 3, 'starts_on': '9999-11-01',
    'ends_on': '9999-11-30', 'due_on': '9999-12-10'}])
def test_recurrence_bounds_fail_without_writes(client, db, accounts, extra):
    before = counts(db)
    send(client, accounts['headers'], '', body(accounts) | extra, status=422)
    assert counts(db) == before


def test_recurrence_is_never_a_preparer_grant(client, db, accounts):
    send(client, accounts['preparer']['headers'], '', body(accounts) | {'occurrences': 3}, status=403)
    assert counts(db) == (0, 0)


def test_quarterly_leap_year_anchors():
    from datetime import date
    from app.business_packs.accounting_firm.recurrence import shift_month
    assert shift_month(date(2028, 1, 31), 1) == date(2028, 2, 29)
    assert shift_month(date(2028, 1, 31), 2) == date(2028, 3, 31)
    assert shift_month(date(2028, 1, 15), 3) == date(2028, 4, 15)
