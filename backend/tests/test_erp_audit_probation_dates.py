from datetime import date
import pytest
from app.models.employee import ProbationAction
from tests.rich_text_test_utils import organization_context
from tests.test_erp_audit_probation_letters import employee


@pytest.mark.parametrize('kind', ['confirm', 'extend', 'terminate'])
def test_probation_action_cannot_precede_joining(client, db, superuser_headers, kind):
    person = employee(db)
    original = (person.status, person.probation_status, person.date_of_confirmation, person.date_of_exit, person.probation_end_date)
    response = client.post(f'/api/v1/hrms/probation/{person.id}/{kind}', headers=superuser_headers,
        json={'effectiveDate':'2025-12-31', 'extendedUntil':'2026-09-30' if kind == 'extend' else None})
    assert response.status_code == 422, response.text
    db.refresh(person)
    assert (person.status, person.probation_status, person.date_of_confirmation, person.date_of_exit, person.probation_end_date) == original
    assert db.query(ProbationAction).filter_by(employee_id=person.id).count() == 0


@pytest.mark.parametrize('effective,end', [('2026-06-30','2026-06-29'),
    ('2026-06-30','2026-06-30'), ('2026-06-30','2026-07-01'),
    ('2026-09-30','2026-09-29')])
def test_extension_must_extend_current_probation_and_follow_effective_date(client, db, superuser_headers, effective, end):
    person = employee(db)
    response = client.post(f'/api/v1/hrms/probation/{person.id}/extend', headers=superuser_headers,
        json={'effectiveDate':effective, 'extendedUntil':end})
    assert response.status_code == 422, response.text
    db.refresh(person)
    assert person.probation_status == 'on_probation' and person.probation_end_date is None
    assert db.query(ProbationAction).filter_by(employee_id=person.id).count() == 0


def test_valid_extension_persists_and_next_extension_cannot_shorten_it(client, db, superuser_headers):
    person = employee(db)
    endpoint = f'/api/v1/hrms/probation/{person.id}/extend'
    response = client.post(endpoint, headers=superuser_headers,
        json={'effectiveDate':'2026-06-30', 'extendedUntil':'2026-09-30', 'remarks':'Synthetic approved extension'})
    assert response.status_code == 200, response.text
    db.refresh(person)
    assert person.probation_end_date == date(2026,9,30)
    assert person.probation_status == 'extended'
    response = client.post(endpoint, headers=superuser_headers,
        json={'effectiveDate':'2026-07-01', 'extendedUntil':'2026-08-31'})
    assert response.status_code == 422, response.text
    db.refresh(person)
    assert person.probation_end_date == date(2026,9,30)
    assert db.query(ProbationAction).filter_by(employee_id=person.id).count() == 1
