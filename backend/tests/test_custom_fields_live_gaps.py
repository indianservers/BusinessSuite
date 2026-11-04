from app.apps.crm.models import CRMContact
from app.apps.crm.api.router import _duplicate_groups


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
