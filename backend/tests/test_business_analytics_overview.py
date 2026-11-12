from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.company import Branch, Company
from app.models.user import User
from app.apps.crm.models import CRMLead
from app.apps.srm.models import SRMInvoice, SRMSalesOrder
from app.branches.models import BranchOwnership
from test_identity_utils import attach_test_identity, attach_workflow_branch

ROOT = "/api/v1/analytics/overview"


@pytest.fixture
def overview_data(db, superuser_headers):
    actor = db.query(User).filter_by(email="testadmin@test.com").one()
    attach_test_identity(db, actor)
    first = attach_workflow_branch(db, actor)
    second = Branch(company_id=1, name="Analytics second branch", code="ANALYTICS-B")
    foreign_company = Company(name="Foreign analytics company", is_active=True)
    db.add_all([second, foreign_company]); db.flush()
    foreign = Branch(company_id=foreign_company.id, name="Foreign analytics branch", code="FOREIGN")
    db.add(foreign); db.flush()
    db.get(Company, 1).default_timezone = "UTC"

    def own(row, branch):
        db.add(row); db.flush()
        db.add(BranchOwnership(company_id=branch.company_id, branch_id=branch.id, resource_table=row.__tablename__, resource_key=str(row.id), source="overview-regression"))
        return row

    now = datetime.now(timezone.utc)
    for index, (branch, age, deleted) in enumerate([(first, 2, False), (second, 9, False), (first, 40, False), (foreign, 2, False), (first, 1, True)]):
        own(CRMLead(organization_id=branch.company_id, branch_id=branch.id, first_name="Synthetic", full_name=f"Synthetic {index}", created_at=now-timedelta(days=age), deleted_at=now if deleted else None), branch)
    own(SRMSalesOrder(organization_id=1, order_number="ANALYTICS-ORDER", title="Synthetic order"), second)
    for index, (currency, value, status) in enumerate([("INR", 100, "issued"), ("USD", 20, "issued"), ("INR", 900, "draft")]):
        own(SRMInvoice(organization_id=1, invoice_number=f"ANALYTICS-{index}", status=status, currency=currency, total_amount=value, paid_amount=0, balance_amount=value), second)
    db.commit()
    return superuser_headers, first.id, second.id


def test_all_branches_uses_real_totals_and_separate_period_counts(client, overview_data):
    headers, first, second = overview_data
    response = client.get(ROOT, params={"days": 7}, headers={**headers, "X-Suite-Branch": "all"})
    assert response.status_code == 200, response.text
    data = response.json()
    modules = {item["key"]: item for item in data["modules"]}
    assert set(modules) == {"crm", "hrms", "pms", "sales", "finance"}
    assert (modules["crm"]["total"], modules["crm"]["current"], modules["crm"]["previous"]) == (3, 1, 1)
    assert sum(point["current"]["crm"] for point in data["series"]) == 1
    assert sum(point["previous"]["crm"] for point in data["series"]) == 1
    assert modules["sales"]["total"] == 1
    assert data["context"]["branch_scope"] == "all"
    assert {item["id"] for item in data["branches"]} == {first, second}
    assert sum(item["counts"].get("crm", 0) for item in data["branches"]) == 3
    assert data["money"]["invoiced"] == [{"currency": "INR", "amount": "100.00"}, {"currency": "USD", "amount": "20.00"}]
    assert response.headers["cache-control"] == "private, no-store"
    assert "X-Suite-Branch" in response.headers["vary"]


def test_selected_branch_does_not_include_other_branch_records(client, overview_data):
    headers, first, _ = overview_data
    response = client.get(ROOT, headers={**headers, "X-Suite-Branch": str(first)})
    assert response.status_code == 200, response.text
    data = response.json()
    modules = {item["key"]: item for item in data["modules"]}
    assert modules["crm"]["total"] == 2
    assert modules["sales"]["total"] == 0
    assert data["context"]["branch_count"] == 1
    assert data["money"]["invoiced"] == []


def test_all_branches_does_not_expand_a_branch_scoped_readers_access(client, db):
    from admin_security_test_utils import auth_headers
    headers = auth_headers(client, db, "analytics-limited@example.com", "analytics_limited", permissions=["analytics_view", "crm_view"])
    result = client.get(ROOT, headers={**headers, "X-Suite-Branch": "all"})
    assert result.status_code == 403, result.text
    result = client.get(ROOT, headers=headers)
    assert result.status_code == 200, result.text
    modules = {item["key"]: item for item in result.json()["modules"]}
    assert modules["crm"]["status"] == "available"
    for key in ["hrms", "pms", "sales", "finance"]:
        assert modules[key]["status"] == "restricted"
        assert modules[key]["total"] is None
    assert result.json()["money"] == {}


def test_finance_counts_only_posted_vouchers(client, db, overview_data):
    from app.apps.fam.models import FAMFinancialYear, FAMVoucherType, FAMVoucher
    headers, first, _ = overview_data
    year = FAMFinancialYear(company_id=1, name="Overview test year", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
    kind = FAMVoucherType(company_id=1, voucher_type_code="OVERVIEW", voucher_type_name="Overview journal", category="journal", numbering_prefix="OV")
    db.add_all([year, kind]); db.flush()
    for index, status in enumerate(["posted", "draft", "cancelled"]):
        # overview_data explicitly selects UTC; the host may already be on
        # tomorrow's date in Asia/Kolkata while this organization is not.
        row = FAMVoucher(company_id=1, financial_year_id=year.id, voucher_type_id=kind.id, voucher_number=f"OV-{index}", voucher_date=datetime.now(timezone.utc).date(), status=status)
        db.add(row); db.flush()
        db.add(BranchOwnership(company_id=1, branch_id=first, resource_table=row.__tablename__, resource_key=str(row.id), source="overview-regression"))
    db.commit()
    response = client.get(ROOT, headers={**headers, "X-Suite-Branch": "all"})
    assert response.status_code == 200, response.text
    finance = next(item for item in response.json()["modules"] if item["key"] == "finance")
    assert finance["total"] == 1
    assert finance["current"] == 1


def test_daily_activity_uses_organization_timezone(client, db, overview_data):
    from datetime import time
    from zoneinfo import ZoneInfo
    headers, first, _ = overview_data
    zone = ZoneInfo("Asia/Kolkata")
    db.get(Company, 1).default_timezone = zone.key
    day = datetime.now(zone).date()
    instant = datetime.combine(day, time(0, 30), zone).astimezone(timezone.utc)
    row = CRMLead(organization_id=1, branch_id=first, first_name="Boundary", full_name="Timezone boundary", created_at=instant)
    db.add(row); db.flush()
    db.add(BranchOwnership(company_id=1, branch_id=first, resource_table=row.__tablename__, resource_key=str(row.id), source="overview-regression"))
    db.commit()
    response = client.get(ROOT, params={"days": 1}, headers={**headers, "X-Suite-Branch": "all"})
    assert response.status_code == 200, response.text
    assert response.json()["series"][0]["current"]["crm"] == 1


@pytest.mark.parametrize("days", [0, -1, 91, "invalid"])
def test_overview_date_range_is_bounded(client, overview_data, days):
    headers, first, _ = overview_data
    response = client.get(ROOT, params={"days": days}, headers={**headers, "X-Suite-Branch": str(first)})
    assert response.status_code == 422, response.text
