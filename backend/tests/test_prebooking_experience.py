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


def test_discovery_time_window_and_notes_metadata(db, scenario):
    from datetime import time
    from app.apps.srm.industry_api import ResourceInput, resource
    user, branch, _, basket = scenario
    draft = selection(basket)
    with native_writer(db,user,branch):
        result=find_choices(db,user,draft.service_id,draft.starts_at.date(),draft.duration_minutes,
            starts_at=draft.starts_at,window_from=time(13),window_until=time(15),priority='same_employee',preferred_employee_id=draft.booking.employee_id)
        assert result['choices']
        for choice in result['choices']:
            at=__import__('datetime').datetime.fromisoformat(choice['starts_at'])
            assert time(13)<=at.time().replace(tzinfo=None)
            assert (at+timedelta(minutes=draft.duration_minutes)).time().replace(tzinfo=None)<=time(15)
        empty=find_choices(db,user,draft.service_id,draft.starts_at.date(),draft.duration_minutes,
            window_from=time(13),window_until=time(13,5))
        assert empty['choices']==[]
        with pytest.raises(HTTPException) as error:
            find_choices(db,user,draft.service_id,draft.starts_at.date(),draft.duration_minutes,window_from=time(15),window_until=time(13))
        assert error.value.status_code==422
        from app.apps.srm.service_checkout_options import service_options
        exact=service_options(db,user,draft.service_id,employee_id=draft.booking.employee_id)
        assert [p['employee_id'] for p in exact['specialists']]==[draft.booking.employee_id]
        assert service_options(db,user,draft.service_id,employee_id=999999)['specialists']==[]
        draft.notes='Private staff instruction'
        draft.customer_notes='Please arrive ten minutes early.'
        saved=appointment_operation(draft,db,user)
        assert saved['data']['notes']==draft.notes
        assert saved['data']['customer_notes']==draft.customer_notes
        # Resource metadata uses the existing authorized resource writer and options.
        from app.apps.srm.service_checkout_options import service_options
        new_room=resource(ResourceInput(request_id=uuid4(),title='Accessible room',resource_type='room',
            location='Ground floor',accessibility='Step-free',facilities='Projector',timezone='UTC'),db,user)
        metadata=next(r for r in service_options(db,user,draft.service_id)['resources'] if r['id']==new_room['id'])
        assert metadata['accessibility']=='Step-free'
        assert metadata['location']=='Ground floor'
        assert metadata['facilities']=='Projector'


def test_discovery_priority_and_least_resource_change(monkeypatch):
    from datetime import datetime, timezone
    import app.apps.srm.service_checkout_options as source
    day=(datetime.now(timezone.utc)+timedelta(days=2)).date()
    people=[dict(eligibility_id=i,employee_id=i+20,employee_name=str(i),timezone='UTC',provider_resource_id=i+10,eligibility_revision=1) for i in [2,3]]
    resources=[dict(id=i,name=str(i),resource_type='room') for i in [30,31]]
    options=dict(policy=dict(id=1,active=True,required_resource_types=['room']),specialists=people,resources=resources,has_more=False)
    monkeypatch.setattr(source,'_authority',lambda *a:(1,1,None))
    monkeypatch.setattr(source,'service_options',lambda *a,**kw:options)
    def available(db,actor,service,eligibility,date,minutes,**kw):
        at=datetime.combine(day,__import__('datetime').time(10 if eligibility==2 else 11),timezone.utc)
        return dict(selection_available=True,slots=[dict(starts_at=at.isoformat())])
    monkeypatch.setattr(source,'scheduling_availability',available)
    first=find_choices(None,None,9,day,30,auto_resources=True,resource_ids=[31],priority='earliest',preferred_employee_id=23)
    assert first['choices'][0]['employee_id']==22
    assert first['choices'][0]['resource_ids']==[31]
    preferred=find_choices(None,None,9,day,30,auto_resources=True,resource_ids=[31],priority='same_employee',preferred_employee_id=23)
    assert preferred['choices'][0]['employee_id']==23
    minimal=find_choices(None,None,9,day,30,auto_resources=True,resource_ids=[31],priority='fewest_changes')
    assert minimal['choices'][0]['changed_resources']==0
