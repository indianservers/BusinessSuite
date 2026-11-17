"""Capacity-aware shared rooms keep employee exclusivity and atomic cart checks."""
from datetime import datetime
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.service_checkout import checkout, save_eligibility
from app.apps.srm.service_checkout_options import scheduling_availability
from app.apps.srm.service_checkout_schemas import EligibilityInput
from app.models.employee import Employee
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer


def provider(db, user, branch, policy):
    employee=Employee(employee_id='CAPACITY-'+uuid4().hex,first_name='Capacity',last_name='Employee',branch_id=branch,status='Active',date_of_joining=datetime.now().date())
    db.add(employee);db.flush()
    resource=IndustryRecord(organization_id=1,branch_id=branch,kind='resource',title='Capacity provider '+uuid4().hex,status='active',request_id=str(uuid4()),created_by=user.id,
        data={'resource_type':'employee','employee_id':employee.id,'timezone':'UTC','weekdays':list(range(7)),'opens':'00:00:00','closes':'23:59:00'})
    db.add(resource);db.commit()
    eligibility=save_eligibility(EligibilityInput(policy_id=policy.policy_id,expected_policy_revision=policy.expected_policy_revision,provider_resource_id=resource.id,employee_id=employee.id),db,user)
    return employee, resource, eligibility


def test_capacity_two_accepts_two_employees_then_blocks_third_and_releases(db, scenario):
    user, branch, _, basket=scenario
    with native_writer(db,user,branch):
        first=basket(False);first.lines=[first.lines[1]]
        room=IndustryRecord(organization_id=1,branch_id=branch,kind='resource',title='Shared capacity room',status='active',request_id=str(uuid4()),created_by=user.id,
            data={'resource_type':'room','capacity':2,'timezone':'UTC','weekdays':list(range(7)),'opens':'00:00:00','closes':'23:59:00'})
        db.add(room);db.commit()
        first.lines[0].booking.additional_resource_ids=[room.id]
        second=basket(False);second.lines=[second.lines[1]]
        employee,resource,eligibility=provider(db,user,branch,first.lines[0].booking)
        b=second.lines[0].booking
        b.employee_id=employee.id;b.provider_resource_id=resource.id;b.eligibility_id=eligibility['id'];b.expected_eligibility_revision=eligibility['revision'];b.additional_resource_ids=[room.id]
        checkout(first,db,user)
        availability=scheduling_availability(db,user,second.lines[0].product_id,b.eligibility_id,b.starts_at.date(),b.duration_minutes,starts_at=b.starts_at,resource_ids=[room.id])
        assert availability['selection_available'] is True
        room_state=next(r for r in availability['resources'] if r['id']==room.id)
        assert room_state['capacity']==2 and room_state['remaining_capacity']==1
        second_result=checkout(second,db,user)
        third=basket(False);third.lines=[third.lines[1]]
        employee,resource,eligibility=provider(db,user,branch,b)
        c=third.lines[0].booking
        c.employee_id=employee.id;c.provider_resource_id=resource.id;c.eligibility_id=eligibility['id'];c.expected_eligibility_revision=eligibility['revision'];c.additional_resource_ids=[room.id]
        availability=scheduling_availability(db,user,third.lines[0].product_id,c.eligibility_id,c.starts_at.date(),c.duration_minutes,starts_at=c.starts_at,resource_ids=[room.id])
        assert availability['selection_available'] is False
        assert next(r for r in availability['resources'] if r['id']==room.id)['remaining_capacity']==0
        with pytest.raises(HTTPException) as rejected:checkout(third,db,user)
        assert rejected.value.status_code==409
        appointment=db.get(IndustryRecord,second_result['lines'][0]['appointment_id']);appointment.status='cancelled';db.commit()
        assert checkout(third,db,user)['state']=='committed'


def test_capacity_one_rejects_two_unsaved_cart_bookings_atomically(db,scenario):
    user,branch,_,basket=scenario
    with native_writer(db,user,branch):
        data=basket(False);data.lines=data.lines[1:]
        room=IndustryRecord(organization_id=1,branch_id=branch,kind='resource',title='Exclusive room',status='active',request_id=str(uuid4()),created_by=user.id,
            data={'resource_type':'room','capacity':1,'timezone':'UTC','weekdays':list(range(7)),'opens':'00:00:00','closes':'23:59:00'})
        db.add(room);db.commit()
        employee,resource,eligibility=provider(db,user,branch,data.lines[0].booking)
        b=data.lines[1].booking
        b.starts_at=data.lines[0].booking.starts_at;b.employee_id=employee.id;b.provider_resource_id=resource.id;b.eligibility_id=eligibility['id'];b.expected_eligibility_revision=eligibility['revision']
        for line in data.lines:line.booking.additional_resource_ids=[room.id]
        with pytest.raises(HTTPException) as rejected:checkout(data,db,user)
        assert rejected.value.status_code==409
        assert db.query(IndustryRecord).filter_by(kind='appointment').count()==0
