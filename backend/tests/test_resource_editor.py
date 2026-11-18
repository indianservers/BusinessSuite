from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.apps.srm.industry_api import ResourceInput, ResourceUpdate, resource, update_resource
from app.apps.srm.industry_models import IndustryRecord
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer


def draft(**values):
    return dict(request_id=uuid4(), title='Treatment Room 01', resource_type='room',
                timezone='Asia/Kolkata', weekdays=[0, 1, 2, 3, 4], opens='09:00', closes='19:00',
                capacity=1, location='First floor', **values)


def test_editor_saves_color_location_and_status_and_checks_revision(db, scenario):
    user, branch, _, _ = scenario
    with native_writer(db, user, branch):
        row = resource(ResourceInput(**draft()), db, user)
        updated = update_resource(row['id'], ResourceUpdate(**draft(assigned_color='Mint'), expected_revision=1, status='inactive'), db, user)
        assert updated['revision'] == 2
        assert updated['status'] == 'inactive'
        assert updated['data']['assigned_color'] == 'Mint'
        assert updated['data']['location'] == 'First floor'
        with pytest.raises(HTTPException) as stale:
            update_resource(row['id'], ResourceUpdate(**draft(), expected_revision=1), db, user)
        assert stale.value.status_code == 409
        archived = update_resource(row['id'], ResourceUpdate(**draft(), expected_revision=2, status='archived'), db, user)
        assert archived['status'] == 'archived'


def test_editor_rejects_rules_or_deletion_that_break_upcoming_bookings(db, scenario):
    user, branch, _, _ = scenario
    with native_writer(db, user, branch):
        row = resource(ResourceInput(**draft()), db, user)
        start = datetime.now(timezone.utc) + timedelta(days=2)
        appointment = IndustryRecord(organization_id=1, branch_id=branch, kind='appointment', title='Reserved visit', status='booked', revision=1, request_id=str(uuid4()), created_by=user.id, starts_at=start, ends_at=start + timedelta(hours=1), data={'resource_ids': [row['id']]})
        db.add(appointment); db.commit()
        for changes in [{'capacity': 2}, {'status': 'archived'}]:
            data = {**draft(), **changes, 'expected_revision': 1}
            with pytest.raises(HTTPException) as conflict:
                update_resource(row['id'], ResourceUpdate(**data), db, user)
            assert conflict.value.status_code == 409
        # Cosmetic edits and disabling new reservations preserve the existing appointment.
        saved = update_resource(row['id'], ResourceUpdate(**draft(assigned_color='Rose'), expected_revision=1, status='inactive'), db, user)
        assert saved['revision'] == 2
        assert db.get(IndustryRecord, appointment.id).status == 'booked'


def test_editor_does_not_cross_branch_or_overwrite_employee_identity(db, scenario):
    user, branch, _, _ = scenario
    with native_writer(db, user, branch):
        row = resource(ResourceInput(**draft()), db, user)
        with pytest.raises(HTTPException) as identity:
            update_resource(row['id'], ResourceUpdate(**draft(employee_id=999), expected_revision=1), db, user)
        assert identity.value.status_code == 409
        with pytest.raises(HTTPException) as missing:
            update_resource(999999, ResourceUpdate(**draft(), expected_revision=1), db, user)
        assert missing.value.status_code == 404


@pytest.mark.parametrize('change', [{'weekdays': []}, {'weekdays': [0, 0]}, {'opens': '20:00', 'closes': '09:00'}, {'capacity': 0}, {'timezone': 'Invalid/Zone'}])
def test_editor_validates_days_hours_capacity_and_timezone(change):
    with pytest.raises(ValidationError):
        ResourceUpdate(**{**draft(), **change}, expected_revision=1)


def test_resource_update_http_endpoint_and_stale_revision(client, db, scenario):
    user, branch, catalog, _ = scenario
    with native_writer(db, user, branch):
        row = resource(ResourceInput(**draft()), db, user)
    body = ResourceUpdate(**draft(assigned_color='Blue'), expected_revision=1).model_dump(mode='json')
    response = client.put(f"/api/v1/srm/industry/resources/{row['id']}", headers=catalog[0], json=body)
    assert response.status_code == 200, response.text
    assert response.json()['data']['assigned_color'] == 'Blue'
    assert client.put(f"/api/v1/srm/industry/resources/{row['id']}", headers=catalog[0], json=body).status_code == 409
