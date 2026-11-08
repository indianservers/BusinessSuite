from datetime import datetime, timezone

from app.apps.crm.models import CRMCompany
from app.models.company import Company


def test_customer_name_lookup_is_bounded_and_tenant_scoped(client, db, superuser_headers):
    for ident in [1, 2]:
        if not db.get(Company, ident):
            db.add(Company(id=ident, name=f"Directory tenant {ident}"))
    rows = [CRMCompany(organization_id=1, name=f"List customer {i:02}", account_type="Customer") for i in range(55)]
    foreign = CRMCompany(organization_id=2, name="Other tenant buyer", account_type="Customer")
    deleted = CRMCompany(organization_id=1, name="Deleted buyer", account_type="Customer", deleted_at=datetime.now(timezone.utc))
    vendor = CRMCompany(organization_id=1, name="Vendor only", account_type="Vendor")
    db.add_all([*rows, foreign, deleted, vendor])
    from test_identity_utils import own_workflow_records
    own_workflow_records(db, *rows, deleted, vendor)
    db.commit()
    requested = [rows[0].id, rows[-1].id, foreign.id, deleted.id, vendor.id]
    response = client.get("/api/v1/srm/business/customers", headers=superuser_headers, params=[("ids", ident) for ident in requested])
    assert response.status_code == 200, response.text
    assert {item["id"] for item in response.json()["items"]} == {rows[0].id, rows[-1].id}
    assert response.json()["next"] is None

    ordinary = client.get("/api/v1/srm/business/customers", headers=superuser_headers)
    assert ordinary.status_code == 200, ordinary.text
    assert len(ordinary.json()["items"]) == 50
    assert ordinary.json()["next"] is not None

    too_many = client.get("/api/v1/srm/business/customers", headers=superuser_headers, params=[("ids", ident) for ident in range(201)])
    assert too_many.status_code == 422
