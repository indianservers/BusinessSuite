"""Fresh, loopback-only real API fixture for Create-menu save acceptance."""
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import suite_navigation_qa_server as qa
from app.models.employee import Employee
from app.models.attendance import Attendance, Shift
from app.models.leave import LeaveType, LeaveBalance
from tests.rich_text_test_utils import workflow_seed_scope
from test_identity_utils import complete_workflow_company, own_workflow_records

with qa.SessionLocal() as db, workflow_seed_scope(db):
    complete_workflow_company(db, 1)
    admin = db.query(qa.User).filter_by(email="admin@suiteqa.example.com").one()
    manager = Employee(employee_id="CREATE-QA-MANAGER", first_name="Create QA", last_name="Manager", date_of_joining=date.today(), status="Active")
    db.add(manager)
    db.flush()
    employee = Employee(employee_id="CREATE-QA-ADMIN", first_name="Create QA", last_name="Administrator", date_of_joining=date.today(), user_id=admin.id, reporting_manager_id=manager.id, status="Active")
    db.add(employee)
    shift = Shift(name="Create QA shift", code="CREATE-QA", start_time=time(9), end_time=time(17), working_hours=8, is_active=True)
    leave_type = LeaveType(name="Create QA annual leave", code="CREATE-QA", days_allowed=30, is_active=True)
    db.add_all([shift, leave_type])
    db.flush()
    employee.shift_id = shift.id
    balance = LeaveBalance(employee_id=employee.id, leave_type_id=leave_type.id, year=date.today().year, allocated=30, used=0, pending=0)
    punch = Attendance(employee_id=employee.id, attendance_date=date.today()-timedelta(days=2), check_in=datetime.combine(date.today()-timedelta(days=2), time(9), timezone.utc), total_hours=2)
    db.add_all([balance, punch])
    own_workflow_records(db, manager, employee, shift, leave_type, balance, punch, company_id=1)
    db.commit()

if __name__ == "__main__":
    import uvicorn
    print("CREATE_QA_READY fresh disposable database; delivery workers disabled", flush=True)
    uvicorn.run(qa.app, host="127.0.0.1", port=int(os.environ.get("CREATE_QA_PORT", "1597")), log_level="warning")
