from uuid import uuid4
from datetime import timedelta
import pytest
from fastapi import HTTPException
from app.apps.srm.prebooking_experience import request_status, customer_context
from app.apps.srm.prebooking_choices import find_choices
from app.apps.srm.industry_api import appointment_operation
from tests.test_prebooking_shared_selection import selection
from tests.test_prebooking_resource_requirements import configure, room
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer


def test_recovery_returns_only_original_actor_and_context(db, scenario):
    user, branch, _, basket = scenario
    draft = selection(basket)
    with native_writer(db,user,branch):
        assert request_status(db,user,draft.request_id) == {'state':'not_found'}
        saved = appointment_operation(draft,db,user)
        recovered = request_status(db,user,draft.request_id)
        assert recovered['state'] == 'confirmed'
        assert recovered['appointment']['id'] == saved['id']
        assert request_status(db,user,uuid4()) == {'state':'not_found'}
        assert appointment_operation(draft,db,user)['id'] == saved['id']
        from app.apps.srm.industry_models import IndustryRecord
        row=db.get(IndustryRecord,saved['id'])
        row.created_by=user.id+999
        db.flush()
        assert request_status(db,user,draft.request_id)=={'state':'not_found'}
        db.rollback()


def test_customer_duplicate_context_and_offset_validation(db, scenario):
    user, branch, _, basket = scenario
    draft = selection(basket)
    with native_writer(db,user,branch):
        saved = appointment_operation(draft,db,user)
        result = customer_context(db,user,draft.customer_id,service_id=draft.service_id,starts_at=draft.starts_at)
        assert [r['id'] for r in result['possible_duplicates']] == [saved['id']]
        assert result['upcoming'][0]['id'] == saved['id']
        assert customer_context(db,user,draft.customer_id,service_id=draft.service_id,starts_at=draft.starts_at+timedelta(hours=3))['possible_duplicates'] == []
        with pytest.raises(HTTPException) as error:
            customer_context(db,user,draft.customer_id,starts_at=draft.starts_at.replace(tzinfo=None))
        assert error.value.status_code == 422


def test_discovery_assigns_required_resource_and_rechecks_reserved_slot(db, scenario):
    user, branch, _, basket = scenario
    draft = selection(basket)
    with native_writer(db,user,branch):
        configure(db,user,draft.service_id,draft.booking,['room'])
        resource = room(db,user,branch)
        result = find_choices(db,user,draft.service_id,draft.starts_at.date(),draft.duration_minutes,
            starts_at=draft.starts_at,auto_resources=True)
        assert result['choices']
        choice = result['choices'][0]
        assert choice['employee_id'] == draft.booking.employee_id
        assert resource.id in choice['resource_ids']
        assert result['checked_combinations'] <= 128
        with pytest.raises(HTTPException) as error:
            find_choices(db,user,draft.service_id,draft.starts_at.date(),draft.duration_minutes,resource_ids=[resource.id]*2)
        assert error.value.status_code == 422
