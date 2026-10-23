from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from tests.test_srm_gantt_schedules import module_access_uses_test_database  # noqa: F401
from app.apps.srm.models import SRMSalesOrder, SRMContract, SRMEngagement, SRMPurchaseOrder
from app.apps.crm.models import CRMTask
from app.apps.fam.models import FAMFinancialYear
from app.models.company import Company
from app.models.employee import Employee
from app.models.leave import LeaveType, LeaveBalance, LeaveRequest, LeaveBalanceLedger


def seed(db, module, source):
    if module == "crm":
        rows = [CRMTask(organization_id=1, title=f"Task {i}", due_date=datetime(2026, 10, 10+i*10, 15, tzinfo=timezone.utc)) for i in range(2)]
        native = "due_date"
    elif module == "fam":
        if not db.get(Company, 1):
            db.add(Company(id=1, name="Schedule tenant")); db.flush()
        rows = [FAMFinancialYear(company_id=1, name=f"FY {2026+i*2}", start_date=date(2026+i*2, 1, 1), end_date=date(2026+i*2, 12, 31), status="open") for i in range(2)]
        native = "end_date"
    elif module == "hrms":
        emp = Employee(employee_id="SCHEDULE-1", first_name="Maya", last_name="Rao", date_of_joining=date(2025, 1, 1))
        leave_type = LeaveType(name="Annual", code="SCHED", days_allowed=100)
        db.add_all([emp, leave_type]); db.flush()
        db.add(LeaveBalance(employee_id=emp.id, leave_type_id=leave_type.id, year=2026, allocated=100, pending=6, used=0, carried_forward=0))
        rows = [LeaveRequest(employee_id=emp.id, leave_type_id=leave_type.id, from_date=date(2026, 10, 10+i*10), to_date=date(2026, 10, 12+i*10), days_count=3, status="Pending") for i in range(2)]
        native = "to_date"
    elif module == "inventory":
        rows = [SRMPurchaseOrder(po_number=f"PO-{i}", order_date=date(2026, 10, 10+i*10), expected_date=date(2026, 10, 12+i*10), status="ordered") for i in range(2)]
        native = "expected_date"
    elif source == "sales-orders":
        rows = [SRMSalesOrder(order_number=f"SO-{i}", title=f"Order {i}", expected_start_date=date(2026, 10, 10+i*10), expected_end_date=date(2026, 10, 12+i*10)) for i in range(2)]
        native = "expected_end_date"
    elif source == "contracts":
        rows = [SRMContract(contract_number=f"CTR-{i}", title=f"Contract {i}", effective_date=date(2026, 10, 10+i*10), expiry_date=date(2026, 10, 12+i*10)) for i in range(2)]
        native = "expiry_date"
    else:
        rows = [SRMEngagement(engagement_number=f"ENG-{i}", name=f"Engagement {i}", planned_start_date=date(2026, 10, 10+i*10), planned_end_date=date(2026, 10, 12+i*10)) for i in range(2)]
        native = "planned_end_date"
    db.add_all(rows); db.commit()
    return rows, [f"tasks:{row.id}" if module == "crm" else str(row.id) for row in rows], native


def read(client, headers, url, keys):
    response = client.get(url, headers=headers, params={"ids": ",".join(keys)})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("module,source", [("crm", "calendar"), ("srm", "sales-orders"), ("srm", "contracts"), ("srm", "engagements"), ("inventory", "purchase-orders"), ("hrms", "leave"), ("fam", "financial-years")])
def test_native_dates_dependencies_reload_and_stale_writes(client, db, superuser_headers, module, source):
    rows, keys, native = seed(db, module, source)
    url = f"/api/v1/scheduling/{module}/{source}"
    state = read(client, superuser_headers, url, keys)
    assert all(record["can_edit"] for record in state["records"].values())
    before = state["records"][keys[0]]
    dates = {"start": "2026-10-13", "end": "2026-10-15", "revision": state["revision"], "expected_start": before["start"], "expected_end": before["end"]}
    changed = client.patch(f"{url}/records/{keys[0]}", headers=superuser_headers, json=dates)
    assert changed.status_code == 200, changed.text
    db.expire_all()
    value = getattr(rows[0], native)
    assert str(value)[:10] == dates["end"]
    if module == "crm":
        assert value.hour == 15
    if module == "hrms":
        assert db.query(LeaveBalance).first().pending == Decimal("6")
        assert db.query(LeaveBalanceLedger).count() == 2
    state = read(client, superuser_headers, url, keys)
    assert state["records"][keys[0]]["start"] == dates["start"]
    assert client.patch(f"{url}/records/{keys[0]}", headers=superuser_headers, json=dates).status_code == 409
    link = {"source_id": keys[0], "target_id": keys[1], "type": "FS", "lag": 1, "revision": state["revision"]}
    created = client.post(f"{url}/dependencies", headers=superuser_headers, json=link)
    assert created.status_code == 201, created.text
    state = read(client, superuser_headers, url, keys)
    assert len(state["dependencies"]) == 1
    reverse = {**link, "source_id": keys[1], "target_id": keys[0], "revision": state["revision"]}
    assert client.post(f"{url}/dependencies", headers=superuser_headers, json=reverse).status_code == 409
    removed = client.delete(f"{url}/dependencies/{created.json()['dependency']['id']}", headers=superuser_headers, params={"revision": state["revision"]})
    assert removed.status_code == 200, removed.text
    assert not read(client, superuser_headers, url, keys)["dependencies"]


def test_cross_tenant_links_and_locked_records_are_rejected(client, db, superuser_headers):
    rows, keys, _ = seed(db, "srm", "sales-orders")
    rows[1].organization_id = 99; db.commit()
    url = "/api/v1/scheduling/srm/sales-orders"
    state = read(client, superuser_headers, url, keys)
    assert keys[1] not in state["records"]
    link = {"source_id": keys[0], "target_id": keys[1], "revision": 0}
    assert client.post(url + "/dependencies", headers=superuser_headers, json=link).status_code == 404
    rows[0].status = "closed"; db.commit()
    assert not read(client, superuser_headers, url, keys)["records"][keys[0]]["can_edit"]
    body = {"start": "2026-10-13", "end": "2026-10-15", "revision": 0, "expected_start": "2026-10-10", "expected_end": "2026-10-12"}
    assert client.patch(url + f"/records/{keys[0]}", headers=superuser_headers, json=body).status_code == 403


def test_leave_validation_preserves_balance_on_failure(client, db, superuser_headers):
    rows, keys, _ = seed(db, "hrms", "leave")
    url = "/api/v1/scheduling/hrms/leave"
    balance = db.query(LeaveBalance).first()
    balance.allocated = 6; db.commit()
    before = read(client, superuser_headers, url, keys)["records"][keys[0]]
    body = {"revision": 0, "expected_start": before["start"], "expected_end": before["end"]}
    for start, end, message in [("2026-10-01", "2026-10-09", "Insufficient"), ("2026-10-20", "2026-10-22", "overlap"), ("2026-12-31", "2027-01-01", "balance year")]:
        response = client.patch(url + f"/records/{keys[0]}", headers=superuser_headers, json={**body, "start": start, "end": end})
        assert response.status_code in (409, 422), response.text
        assert message in response.json()["detail"]
        db.expire_all()
        assert balance.pending == Decimal("6")
        assert rows[0].from_date == date(2026, 10, 10)
        assert not db.query(LeaveBalanceLedger).count()
    rows[0].status = "Approved"; db.commit()
    assert not read(client, superuser_headers, url, keys)["records"][keys[0]]["can_edit"]


def test_finance_and_inventory_history_locks(client, db, superuser_headers):
    from app.apps.fam.models import FAMAccountingPeriod
    from app.apps.srm.models import SRMGoodsReceipt
    rows, keys, _ = seed(db, "fam", "financial-years")
    url = "/api/v1/scheduling/fam/financial-years"
    before = read(client, superuser_headers, url, keys)["records"][keys[0]]
    body = {"revision": 0, "expected_start": before["start"], "expected_end": before["end"], "start": "2026-01-01", "end": "2028-12-31"}
    assert client.patch(url + f"/records/{keys[0]}", headers=superuser_headers, json=body).status_code == 409
    db.add(FAMAccountingPeriod(financial_year_id=rows[0].id, period_name="January", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31)))
    db.commit()
    assert not read(client, superuser_headers, url, keys)["records"][keys[0]]["can_edit"]
    body.update(start="2026-01-02", end="2026-12-30")
    assert client.patch(url + f"/records/{keys[0]}", headers=superuser_headers, json=body).status_code == 403
    orders, order_keys, _ = seed(db, "inventory", "purchase-orders")
    db.add(SRMGoodsReceipt(grn_number="GRN-1", purchase_order_id=orders[0].id, receipt_date=date(2026, 10, 12)))
    db.commit()
    assert not read(client, superuser_headers, "/api/v1/scheduling/inventory/purchase-orders", order_keys)["records"][order_keys[0]]["can_edit"]


def test_viewer_cannot_mutate_dates_or_dependencies(client, db, superuser_headers):
    from app.models.user import User, Permission
    rows, keys, _ = seed(db, "crm", "calendar")
    user = db.query(User).filter_by(email="testadmin@test.com").one()
    user.is_superuser = False; user.role.name = "crm_viewer"
    view = db.query(Permission).filter_by(name="crm_view").first() or Permission(name="crm_view")
    user.role.permissions = [view]
    for row in rows: row.owner_user_id = user.id
    db.commit()
    url = "/api/v1/scheduling/crm/calendar"
    state = read(client, superuser_headers, url, keys)
    assert state["records"] and not any(row["can_edit"] for row in state["records"].values())
    before = state["records"][keys[0]]
    body = {"revision": 0, "expected_start": before["start"], "expected_end": before["end"], "start": "2026-10-11", "end": "2026-10-12"}
    assert client.patch(url + f"/records/{keys[0]}", headers=superuser_headers, json=body).status_code == 403
    assert client.post(url + "/dependencies", headers=superuser_headers, json={"revision": 0, "source_id": keys[0], "target_id": keys[1]}).status_code == 403
