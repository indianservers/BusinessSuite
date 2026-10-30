from datetime import date, datetime, timedelta, timezone
from tests.rich_text_test_utils import organization_context
from app.models.employee import Employee
from app.models.user import User
from app.models.attendance import Attendance
from app.models.expense import ExpenseClaim
from app.models.timesheet import Project, Timesheet
from app.models.exit import ExitChecklistItem
from app.core.security import get_password_hash

ROOT = "/api/v1/employees/workbench"


def make_employee(db, code="HR-WORK", **values):
    row=Employee(employee_id=code,first_name="Daily",last_name="Work",date_of_joining=date.today(),**values)
    db.add(row);db.commit();return row


def test_quick_add_duplicates_and_profile_completion(client,db,superuser_headers):
    payload={"first_name":"Quick","date_of_joining":str(date.today()),"personal_email":"quick-work@example.com"}
    response=client.post(ROOT+"/quick-add",headers=superuser_headers,json=payload)
    assert response.status_code==201,response.text
    ident=response.json()["id"]
    panel=client.get(ROOT+f"/people/{ident}",headers=superuser_headers).json()
    assert panel["login_status"]=="No login account" and panel["employment_status"]=="Active"
    assert any(not i["complete"] for i in panel["completion"])
    assert client.post(ROOT+"/quick-add",headers=superuser_headers,json=payload).status_code==409
    assert client.get(ROOT+"/search?q=Quick",headers=superuser_headers).json()["items"][0]["id"]==ident


def test_suspend_access_does_not_terminate_employment_and_stale_guard(client,db,superuser_headers):
    account=User(email="hr-work-login@example.com",hashed_password=get_password_hash("Password@12345"),is_active=True)
    db.add(account);db.commit();person=make_employee(db,user_id=account.id)
    panel=client.get(ROOT+f"/people/{person.id}",headers=superuser_headers).json()
    suspended=client.post(ROOT+f"/people/{person.id}/actions",headers=superuser_headers,json={"action":"suspend_access","version":panel["version"],"reason":"Temporary investigation"})
    assert suspended.status_code==200,suspended.text
    assert suspended.json()["employment_status"]=="Active" and suspended.json()["login_status"]=="Suspended"
    stale=client.post(ROOT+f"/people/{person.id}/actions",headers=superuser_headers,json={"action":"reactivate_access","version":panel["version"],"reason":"Review completed"})
    assert stale.status_code==409
    restored=client.post(ROOT+f"/people/{person.id}/actions",headers=superuser_headers,json={"action":"reactivate_access","version":suspended.json()["version"],"reason":"Review completed"})
    assert restored.status_code==200 and restored.json()["login_status"]=="Active"
    terminated=client.post(ROOT+f"/people/{person.id}/actions",headers=superuser_headers,json={"action":"terminate_employment","version":restored.json()["version"],"reason":"Employment ended"})
    assert terminated.status_code==200,terminated.text
    assert terminated.json()["employment_status"]=="Terminated" and terminated.json()["login_status"]!="Active"


def test_attendance_exceptions_do_not_assume_missing_dates_absent(client,db,superuser_headers):
    person=make_employee(db)
    today=date.today()
    db.add(Attendance(employee_id=person.id,attendance_date=today,check_in=datetime.now(timezone.utc)-timedelta(hours=24),late_minutes=15,total_hours=2))
    current_person=make_employee(db,"HR-CURRENT-SHIFT")
    db.add(Attendance(employee_id=current_person.id,attendance_date=today,check_in=datetime.now(timezone.utc),late_minutes=0,total_hours=0))
    db.commit()
    response=client.get(ROOT+"/attendance-exceptions",params={"month":today.month,"year":today.year},headers=superuser_headers)
    assert response.status_code==200,response.text
    items=response.json()["items"]
    assert len(items)==1 and "Missed punch" in items[0]["issues"]
    assert "Late arrival: 15 minutes" in items[0]["issues"]


def test_exit_checklist_reuses_employee_and_does_not_terminate_implicitly(client,db,superuser_headers):
    person=make_employee(db)
    started=client.post(ROOT+f"/people/{person.id}/start-exit",headers=superuser_headers,json={"last_working_date":str(date.today()+timedelta(days=30)),"reason":"Resignation received"})
    assert started.status_code==201,started.text
    assert db.query(ExitChecklistItem).filter_by(exit_record_id=started.json()["id"]).count()==5
    db.refresh(person);assert person.status=="Active"
    checklist=client.get(ROOT+f"/people/{person.id}/lifecycle-checklist",headers=superuser_headers)
    assert checklist.status_code==200,checklist.text
    assert len(checklist.json()["offboarding"])==5
    assert client.post(ROOT+f"/people/{person.id}/start-exit",headers=superuser_headers,json={"last_working_date":str(date.today()),"reason":"Repeated"}).status_code==409


def test_unified_inbox_has_real_sources_waiting_time_and_bulk_failures(client,db,superuser_headers):
    person=make_employee(db)
    db.add(ExpenseClaim(employee_id=person.id,claim_number="HR-CLAIM",claim_type="Travel",expense_date=date.today(),amount=100,status="submitted",created_at=datetime.now(timezone.utc)-timedelta(days=2)))
    project=Project(code="HR-TS",name="HR project");db.add(project);db.flush()
    db.add(Timesheet(employee_id=person.id,project_id=project.id,period_start=date.today(),period_end=date.today(),status="Submitted",submitted_at=datetime.now(timezone.utc)-timedelta(hours=5)))
    db.commit()
    response=client.get(ROOT+"/approvals",headers=superuser_headers)
    assert response.status_code==200,response.text
    items=response.json()["items"]
    assert {i["kind"] for i in items}=={"expense","timesheet"}
    assert next(i for i in items if i["kind"]=="expense")["waiting_hours"]>=47
    decision=client.post(ROOT+"/approvals/decide",headers=superuser_headers,json={"keys":[items[0]["key"],"expense:999999"],"decision":"approve","reason":"Verified supporting evidence"})
    assert decision.status_code==200,decision.text
    assert [r["ok"] for r in decision.json()["results"]]==[True,False]


def test_scope_and_field_masking_do_not_leak_another_company(client,db):
    from app.models.company import Company, Branch
    from app.models.user import Permission, Role
    from app.core.security import create_access_token
    companies=[Company(name="HR scope A"),Company(name="HR scope B")];db.add_all(companies);db.flush()
    branches=[Branch(name="HR branch",company_id=c.id) for c in companies];db.add_all(branches);db.flush()
    role=Role(name="hr_work_scope",permissions=[Permission(name="employee_view"),Permission(name="employee_update")])
    account=User(email="hr-scope@example.com",hashed_password="unused",role=role,is_active=True);db.add(account);db.flush()
    own=make_employee(db,"HR-OWN",branch_id=branches[0].id,user_id=account.id)
    colleague=make_employee(db,"HR-COLLEAGUE",branch_id=branches[0].id,personal_email="sensitive@example.com",phone_number="9876543210",account_number="123456789012")
    foreign=make_employee(db,"HR-FOREIGN",branch_id=branches[1].id)
    headers={"Authorization":"Bearer "+create_access_token(account.id)}
    response=client.get(ROOT+"/search?q=HR-",headers=headers)
    assert response.status_code==200,response.text
    assert {p["id"] for p in response.json()["items"]}=={own.id,colleague.id}
    assert "9876543210" not in response.text and "sensitive@example.com" not in response.text
    detail=client.get(f"/api/v1/employees/{colleague.id}",headers=headers)
    assert detail.status_code==200 and "account_number" in detail.json()["restricted_fields"]
    changed=client.put(f"/api/v1/employees/{colleague.id}",headers=headers,json={"first_name":"Changed name"})
    assert changed.status_code==200,changed.text
    assert "123456789012" not in changed.text
    assert client.put(f"/api/v1/employees/{colleague.id}",headers=headers,json={"account_number":"123456789013"}).status_code==403
    assert client.get(ROOT+f"/people/{foreign.id}",headers=headers).status_code==404
    assert client.get(ROOT+f"/people/{foreign.id}/lifecycle-checklist",headers=headers).status_code==404
    assert client.post(ROOT+f"/people/{foreign.id}/actions",headers=headers,json={"action":"terminate_employment","version":"stale","reason":"Outside scope"}).status_code==404


def test_bulk_transfer_preview_and_future_application(client,db,superuser_headers):
    from app.models.company import Branch,Company,Department
    company=Company(name="Transfer company");db.add(company);db.flush()
    branch=Branch(company_id=company.id,name="Transfer branch");db.add(branch);db.flush()
    departments=[Department(branch_id=branch.id,name=name) for name in ("Before","After")];db.add_all(departments);db.flush()
    person=make_employee(db,branch_id=branch.id,department_id=departments[0].id)
    payload={"employee_ids":[person.id,999999],"changes":{"department_id":departments[1].id},"effective_from":str(date.today()+timedelta(days=3)),"reason":"Team restructure"}
    preview=client.post(ROOT+"/transfers/preview",headers=superuser_headers,json=payload)
    assert preview.status_code==200,preview.text
    assert preview.json()["count"]==1 and len(preview.json()["failures"])==1
    applied=client.post(ROOT+"/transfers/apply",headers=superuser_headers,json={**payload,"preview_version":preview.json()["version"]})
    assert applied.status_code==200,applied.text
    db.refresh(person);assert person.department_id==departments[0].id
    from app.models.employee import EmployeeLifecycleEvent
    event=db.query(EmployeeLifecycleEvent).filter_by(employee_id=person.id,event_type="Scheduled transfer").one()
    assert client.post(ROOT+f"/people/{person.id}/transfers/{event.id}/apply",headers=superuser_headers).status_code==409
    event.effective_from=date.today();db.commit()
    due=client.post(ROOT+f"/people/{person.id}/transfers/{event.id}/apply",headers=superuser_headers)
    assert due.status_code==200,due.text
    db.refresh(person);assert person.department_id==departments[1].id
    assert event.from_department_id==departments[0].id


def test_attendance_correction_respects_lock_and_breaks(client,db,superuser_headers):
    from app.models.attendance import AttendanceMonthLock
    person=make_employee(db)
    start=datetime.now(timezone.utc).replace(hour=9,minute=0,second=0,microsecond=0)
    row=Attendance(employee_id=person.id,attendance_date=date.today(),check_in=start);db.add(row);db.commit()
    payload={"check_in":start.isoformat(),"check_out":(start+timedelta(hours=9)).isoformat(),"break_minutes":60,"reason":"Verified punch correction"}
    response=client.post(ROOT+f"/attendance/{row.id}/correct",headers=superuser_headers,json=payload)
    assert response.status_code==200,response.text
    db.refresh(row);assert float(row.total_hours)==8 and float(row.overtime_hours)==0
    db.add(AttendanceMonthLock(month=date.today().month,year=date.today().year,status="Locked"));db.commit()
    assert client.post(ROOT+f"/attendance/{row.id}/correct",headers=superuser_headers,json=payload).status_code==423


def test_managed_hr_can_suspend_in_scope_with_edit_action_without_global_user_admin(client,db):
    from app.access.models import AccessPolicy
    from app.common.models import CommonPerson
    from app.models.user import Permission,Role
    from app.core.security import create_access_token
    permissions=[]
    for name in ("employee_view","employee_update"):
        permission=db.query(Permission).filter_by(name=name).first()
        if not permission:permission=Permission(name=name,module="employees");db.add(permission);db.flush()
        permissions.append(permission)
    role=Role(name="scoped_hr_work",permissions=permissions)
    actor=User(email="scoped-hr-work@example.com",hashed_password="unused",role=role,is_active=True)
    target=User(email="scoped-hr-target@example.com",hashed_password="unused",is_active=True)
    db.add_all([actor,target]);db.flush()
    db.add(CommonPerson(user_id=actor.id,organization_id=1,display_name="Scoped HR"))
    db.add(AccessPolicy(user_id=actor.id,company_id=1,status="active",grants={"hrms":{"enabled":True,"role":"manager","scope":"organization","permissions":["employee_view","employee_update"],"actions":["view","edit"]}}))
    db.commit()
    from app.models.company import Branch
    branch=Branch(company_id=1,name="Scoped HR branch");db.add(branch);db.commit()
    person=make_employee(db,user_id=target.id,branch_id=branch.id)
    headers={"Authorization":"Bearer "+create_access_token(actor.id)}
    panel=client.get(ROOT+f"/people/{person.id}",headers=headers)
    assert panel.status_code==200,panel.text
    response=client.post(ROOT+f"/people/{person.id}/actions",headers=headers,json={"action":"suspend_access","version":panel.json()["version"],"reason":"Scoped HR investigation"})
    assert response.status_code==200,response.text
    db.refresh(target);assert not target.is_active
    protected=User(email="protected-hr-admin@example.com",hashed_password="unused",is_active=True,is_superuser=True)
    db.add(protected);db.commit()
    if protected:
        protected_person=make_employee(db,"HR-PROTECTED",user_id=protected.id,branch_id=branch.id)
        panel=client.get(ROOT+f"/people/{protected_person.id}",headers=headers)
        assert panel.status_code==200,panel.text
        blocked=client.post(ROOT+f"/people/{protected_person.id}/actions",headers=headers,json={"action":"suspend_access","version":panel.json()["version"],"reason":"Not permitted"})
        assert blocked.status_code==403


def test_existing_account_link_is_reused_and_cannot_be_linked_twice(client,db,superuser_headers):
    from app.common.models import CommonPerson
    account=User(email="link-existing-hr@example.com",hashed_password="unused",is_active=True)
    db.add(account);db.flush();db.add(CommonPerson(user_id=account.id,organization_id=1,display_name="Existing identity"));db.commit()
    count=db.query(User).count()
    payload={"first_name":"Existing login","date_of_joining":str(date.today()),"existing_user_id":account.id}
    response=client.post(ROOT+"/quick-add",headers=superuser_headers,json=payload)
    assert response.status_code==201,response.text
    assert db.get(Employee,response.json()["id"]).user_id==account.id
    assert db.query(User).count()==count
    assert client.post(ROOT+"/quick-add",headers=superuser_headers,json=payload).status_code==403


def test_unified_leave_decision_updates_original_balance(client,db,superuser_headers):
    from app.models.leave import LeaveType,LeaveBalance,LeaveRequest
    person=make_employee(db)
    leave_type=LeaveType(name="HR annual",code="HR-ANNUAL",days_allowed=10);db.add(leave_type);db.flush()
    balance=LeaveBalance(employee_id=person.id,leave_type_id=leave_type.id,year=date.today().year,allocated=10,used=0,pending=2,carried_forward=0)
    request=LeaveRequest(company_id=1,employee_id=person.id,leave_type_id=leave_type.id,from_date=date.today(),to_date=date.today()+timedelta(days=1),days_count=2,status="Pending")
    db.add_all([balance,request]);db.commit()
    response=client.post(ROOT+"/approvals/decide",headers=superuser_headers,json={"keys":[f"leave:{request.id}"],"decision":"approve","reason":"Coverage confirmed"})
    assert response.status_code==200,response.text
    assert response.json()["results"][0]["ok"],response.text
    db.refresh(balance);db.refresh(request)
    assert request.status=="Approved" and float(balance.used)==2 and float(balance.pending)==0


def test_roster_preview_blocks_leave_and_rejects_stale_review(client,db,superuser_headers):
    from datetime import time
    from app.models.attendance import Shift,ShiftRoster,Holiday
    from app.models.leave import LeaveType,LeaveRequest
    person=make_employee(db)
    shift=Shift(name="Preview day",start_time=time(9),end_time=time(17),working_hours=8)
    leave_type=LeaveType(name="Roster leave",code="ROSTER-LEAVE",days_allowed=10)
    db.add_all([shift,leave_type]);db.flush()
    tomorrow=date.today()+timedelta(days=1)
    db.add(LeaveRequest(company_id=1,employee_id=person.id,leave_type_id=leave_type.id,from_date=tomorrow,to_date=tomorrow,days_count=1,status="Approved"));db.commit()
    payload={"employee_ids":[person.id],"shift_id":shift.id,"from_date":str(date.today()),"to_date":str(tomorrow)}
    preview=client.post(ROOT+"/roster/preview",headers=superuser_headers,json=payload)
    assert preview.status_code==200,preview.text
    assert preview.json()["affected"]==1 and preview.json()["exceptions"]==1
    db.add(Holiday(name="New holiday",holiday_date=date.today(),is_active=True));db.commit()
    assert client.post(ROOT+"/roster/apply",headers=superuser_headers,json={**payload,"preview_version":preview.json()["version"]}).status_code==409
    fresh=client.post(ROOT+"/roster/preview",headers=superuser_headers,json=payload).json()
    saved=client.post(ROOT+"/roster/apply",headers=superuser_headers,json={**payload,"preview_version":fresh["version"]})
    assert saved.status_code==200,saved.text
    assert db.query(ShiftRoster).filter_by(employee_id=person.id).count()==1


def test_payroll_variance_explains_actual_lines_and_currency(client,db,superuser_headers):
    from app.models.payroll import PayrollRun,PayrollRecord,PayrollComponent
    person=make_employee(db)
    previous=PayrollRun(company_id=1,month=9,year=2026,status="calculated")
    current=PayrollRun(company_id=1,month=10,year=2026,status="calculated")
    db.add_all([previous,current]);db.flush()
    before=PayrollRecord(payroll_run_id=previous.id,employee_id=person.id,basic=10000,gross_salary=10000,net_salary=10000,lop_days=0,salary_currency="INR")
    after=PayrollRecord(payroll_run_id=current.id,employee_id=person.id,basic=11000,gross_salary=11500,net_salary=11400,other_deductions=100,lop_days=1,salary_currency="INR")
    db.add_all([before,after]);db.flush()
    db.add(PayrollComponent(record_id=after.id,component_name="Overtime",component_type="earning",source_type="overtime",amount=500));db.commit()
    response=client.get(f"/api/v1/payroll/runs/{current.id}/variance",headers=superuser_headers)
    assert response.status_code==200,response.text
    row=response.json()[0]
    assert "Basic-pay earnings" in row["reason"] and "Unpaid leave" in row["reason"] and "Overtime" in row["reason"]
    assert row["previous_currency"]==row["current_currency"]=="INR"
