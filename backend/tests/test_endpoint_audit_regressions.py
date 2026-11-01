from decimal import Decimal

from app.models.company import Department
from app.models.recruitment import Job
from app.apps.fam.models import FAMStockItem
from app.apps.fam.api.router import fam_integrity_results, bootstrap
from app.models.user import User


def test_global_search_matches_department(client, db, superuser_token):
    from app.db.init_db import init_db
    init_db(db)
    department = db.query(Department).first()
    from test_identity_utils import attach_test_identity
    actor = db.query(User).filter_by(email="testadmin@test.com").one()
    attach_test_identity(db, actor, department.branch.company_id)
    department.name = "Audit Engineering"
    db.flush()
    db.add(Job(title="Release specialist", department_id=department.id, branch_id=department.branch_id))
    db.commit()
    response = client.get("/api/v1/reports/global-search?q=Audit", headers={"Authorization": f"Bearer {superuser_token}"})
    assert response.status_code == 200, response.text
    assert any(item["title"] == "Release specialist" for item in response.json()["results"]), response.text


def test_integrity_values_stock_from_quantity_and_cost(client, db, superuser_token):
    user = db.query(User).filter(User.email == "testadmin@test.com").one()
    company_id = bootstrap(db, user)
    db.add(FAMStockItem(company_id=company_id, sku="AUDIT-STOCK", item_name="Audit stock", current_quantity=Decimal("3"), average_cost=Decimal("12.50")))
    db.flush()
    results = fam_integrity_results(db, company_id)
    valuation = next(item for item in results if item["check"] == "inventory_valuation_vs_layers")
    assert valuation["details"]["stock_value"] == 37.5
