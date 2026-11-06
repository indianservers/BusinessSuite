from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from app.models.company import Company, Branch
from app.models.user import User
from app.shared import sample_data
from app.shared.import_models import ImportBatch


@pytest.mark.parametrize("module", sorted(sample_data.MODULES))
def test_sample_pack_counts_links_and_guarded_removal(db, module):
    company = Company(name="Sample test company")
    user = User(email=f"sample-{module}@example.com", hashed_password="unused", is_active=True)
    db.add_all([company,user]); db.flush()
    branch = Branch(name="Sample branch", company_id=company.id)
    db.add(branch); db.flush()
    ctx = SimpleNamespace(company_id=company.id, branch_id=branch.id)
    changes, counts = sample_data.populate(db, ctx, user, [module])
    assert len(changes) >= 300
    assert sum(counts.values()) == len(changes)
    batch = ImportBatch(id="test-sample", organization_id=company.id, branch_id=branch.id, module="sample", entity="suite",
        source="company_sample", filename="sample", created_by=user.id, status="imported", table_json={}, changes_json=changes)
    db.add(batch); db.flush()
    from app.db.base import Base
    first = changes[0]
    table = Base.metadata.tables[first["table"]]
    # Every table's first row has a text label that can be changed.
    field = next(key for key in ("first_name", "name", "warehouse_name", "group_name") if key in table.c)
    db.execute(table.update().where(table.c.id == first["id"]).values({field: "Edited sample"}))
    with pytest.raises(HTTPException, match="409"):
        with db.begin_nested():
            sample_data.remove(db, batch)
    assert db.execute(select(func.count()).select_from(table).where(table.c.id == first["id"])).scalar() == 1
    db.execute(table.update().where(table.c.id == first["id"]).values({field: first["after"][field]}))
    # Restore exact snapshot, including the onupdate timestamp.
    from app.shared.import_service import restore_value
    db.execute(table.update().where(table.c.id == first["id"]).values({c.key:restore_value(c,first["after"][c.key]) for c in table.c}))
    if module == "crm":
        activity = Base.metadata.tables["crm_activities"]
        lead = next(item["id"] for item in changes if item["table"] == "crm_leads")
        external = db.connection().execute(activity.insert().values(organization_id=company.id, lead_id=lead,
            title="User created follow-up", subject="User created follow-up", activity_type="Task").returning(activity.c.id)).scalar_one()
        with pytest.raises(HTTPException, match="409"):
            with db.begin_nested():
                sample_data.remove(db, batch)
        # Even sample children deleted before encountering this dependency roll back.
        assert db.execute(select(func.count()).select_from(activity)).scalar() == counts["crm_activities"]+1
        db.connection().execute(activity.delete().where(activity.c.id == external))
    from sqlalchemy import Table, Column, Integer, ForeignKey
    optional = Table("qa_uninstalled_connector", Base.metadata, Column("id", Integer, primary_key=True),
        Column("sample_parent_id", Integer, ForeignKey(f"{first['table']}.id")))
    try:
        with db.begin_nested():
            sample_data.remove(db, batch)
    finally:
        Base.metadata.remove(optional)
    assert batch.status == "revoked"
    for item in changes:
        t = Base.metadata.tables[item["table"]]
        assert db.execute(select(t.c.id).where(t.c.id == item["id"])).first() is None
