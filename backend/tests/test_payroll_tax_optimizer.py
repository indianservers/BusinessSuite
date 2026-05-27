from decimal import Decimal

from app.db.init_db import init_db
from app.models.employee import Employee
from app.models.payroll import TaxRegime, TaxSection, TaxSectionLimit, TaxSlab


def _login(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@aihrms.com", "password": "Admin@123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _add_slab(db, regime_id, min_income, max_income, rate_percent, sequence):
    db.add(
        TaxSlab(
            tax_regime_id=regime_id,
            min_income=Decimal(str(min_income)),
            max_income=Decimal(str(max_income)) if max_income is not None else None,
            rate_percent=Decimal(str(rate_percent)),
            sequence=sequence,
        )
    )


def _setup_tax_optimizer_data(db, financial_year="2099-00"):
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    assert employee

    old = TaxRegime(
        financial_year=financial_year,
        regime_code="OLD",
        name="Old Tax Regime",
        standard_deduction_amount=Decimal("50000"),
        cess_percent=Decimal("0"),
        is_active=True,
    )
    new = TaxRegime(
        financial_year=financial_year,
        regime_code="NEW",
        name="New Tax Regime",
        standard_deduction_amount=Decimal("75000"),
        cess_percent=Decimal("0"),
        is_active=True,
    )
    db.add_all([old, new])
    db.flush()

    for regime in (old,):
        _add_slab(db, regime.id, 0, 250000, 0, 1)
        _add_slab(db, regime.id, 250000, 500000, 5, 2)
        _add_slab(db, regime.id, 500000, 1000000, 20, 3)
        _add_slab(db, regime.id, 1000000, None, 30, 4)
    for regime in (new,):
        _add_slab(db, regime.id, 0, 300000, 0, 1)
        _add_slab(db, regime.id, 300000, 700000, 5, 2)
        _add_slab(db, regime.id, 700000, 1000000, 10, 3)
        _add_slab(db, regime.id, 1000000, 1200000, 15, 4)
        _add_slab(db, regime.id, 1200000, 1500000, 20, 5)
        _add_slab(db, regime.id, 1500000, None, 30, 6)

    configured_limits = {
        "80C": Decimal("150000"),
        "80D": Decimal("75000"),
        "80CCD(1B)": Decimal("50000"),
        "HOME_LOAN_INTEREST": Decimal("200000"),
    }
    for section_code, limit in configured_limits.items():
        section = TaxSection(section_code=section_code, name=section_code)
        db.add(section)
        db.flush()
        db.add(TaxSectionLimit(tax_section_id=section.id, financial_year=financial_year, limit_amount=limit))

    db.commit()
    return employee, financial_year


def _money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"))


def test_tax_optimizer_no_declarations_returns_section_recommendations(client, db):
    init_db(db)
    headers = _login(client)
    employee, fy = _setup_tax_optimizer_data(db, "2099-00")

    response = client.get(
        "/api/v1/payroll/tax/optimizer",
        params={"employee_id": employee.id, "financial_year": fy, "gross_taxable_income": "1200000"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    sections = {item["section"]: item for item in body["recommendations"]}
    assert body["recommended_regime"] == "NEW"
    assert _money(body["old_regime_tax"]) > _money(body["new_regime_tax"])
    assert sections["80C"]["suggested_amount"] == 150000
    assert sections["80D"]["max_allowed"] == 75000
    assert "Payroll estimate" in body["estimate_note"]

    compare = client.get(
        "/api/v1/payroll/tax/compare",
        params={"employee_id": employee.id, "financial_year": fy, "gross_taxable_income": "1200000"},
        headers=headers,
    )
    assert compare.status_code == 200
    assert compare.json()["recommended_regime"]["regime_code"] == "NEW"


def test_tax_optimizer_high_80c_and_hra_can_make_old_regime_better(client, db):
    init_db(db)
    headers = _login(client)
    employee, fy = _setup_tax_optimizer_data(db, "2099-01")

    response = client.post(
        "/api/v1/payroll/tax/optimizer",
        json={
            "employee_id": employee.id,
            "financial_year": fy,
            "gross_taxable_income": "1200000",
            "section_80c_declared": "150000",
            "section_80d_declared": "50000",
            "nps_80ccd_1b_declared": "50000",
            "home_loan_interest": "200000",
            "hra_basic_salary": "600000",
            "hra_received": "300000",
            "rent_paid": "300000",
            "hra_is_metro": False,
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommended_regime"] == "OLD"
    assert _money(body["old_regime_tax"]) < _money(body["new_regime_tax"])
    hra = next(item for item in body["recommendations"] if item["section"] == "HRA")
    assert hra["suggested_amount"] == 240000


def test_tax_optimizer_new_regime_better_with_low_declarations(client, db):
    init_db(db)
    headers = _login(client)
    employee, fy = _setup_tax_optimizer_data(db, "2099-02")

    response = client.post(
        "/api/v1/payroll/tax/optimizer",
        json={"employee_id": employee.id, "financial_year": fy, "gross_taxable_income": "900000"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommended_regime"] == "NEW"
    assert _money(body["projected_savings"]) == _money(_money(body["old_regime_tax"]) - _money(body["new_regime_tax"]))
