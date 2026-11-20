from app.apps.crm.models import CRMContact
from app.apps.crm.api import router
from app.apps.crm.api.router import _duplicate_groups
import pytest


def test_detail_duplicate_scan_keeps_transitive_matches(db):
    rows=[CRMContact(organization_id=1,first_name="QA",full_name="Alpha",email="shared@example.test"),
          CRMContact(organization_id=1,first_name="QA",full_name="Beta",email="shared@example.test",phone="9876543210",phone_country_code="+91"),
          CRMContact(organization_id=1,first_name="QA",full_name="Gamma",email="gamma@example.test",phone="9876543210",phone_country_code="+91"),
          CRMContact(organization_id=1,first_name="QA",full_name="Unrelated",email="unrelated@example.test")]
    db.add_all(rows);db.flush()
    full=_duplicate_groups(db,1,"contacts")
    expected=[g for g in full if rows[2].id in g["recordIds"]]
    assert len(expected)==1 and set(expected[0]["recordIds"])=={r.id for r in rows[:3]}
    assert _duplicate_groups(db,1,"contacts",target_id=rows[2].id)==expected


def test_duplicate_budget_preserves_record_detail(db, monkeypatch):
    db.add_all([
        CRMContact(organization_id=1, first_name="First", full_name="First Contact"),
        CRMContact(organization_id=1, first_name="Second", full_name="Second Contact"),
    ])
    db.flush()
    identity = db.query(CRMContact.id).first()[0]
    monkeypatch.setattr(router, "MAX_DUPLICATE_SCAN_RECORDS", 1)

    with pytest.raises(router._DuplicateScanBudgetExceeded) as error:
        router._duplicate_groups(db, 1, "contacts")
    assert error.value.status_code == 422
    assert router._duplicate_summary_for(db, 1, "contacts", identity) == {
        "count": None, "groups": [], "truncated": True,
    }
