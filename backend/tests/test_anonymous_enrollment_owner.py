"""Focused candidate-only birth enrollment native ownership contracts."""
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from tests.test_anonymous_birth import graph, new_root, flush_graph, add_remainder
from app.business_packs import anonymous_birth as birth, anonymous_definitions as definitions
from app.business_packs.models import PackMasterAvailability
from app.branches.models import BranchOwnership

@pytest.mark.parametrize('existing_owner', ['new', 'exact', 'missing', 'foreign_branch', 'foreign_company', 'inactive'])
def test_birth_enrollment_exact_owner_and_no_adoption(graph, monkeypatch, existing_owner):
    db, actor, payload, _ = graph
    scope=SimpleNamespace(company_id=2, branch_id=3, context_id=11)
    db.info['business_pack_scope']=scope
    monkeypatch.setattr(definitions, '_authority', lambda db,user: (2,3,scope))
    table=PackMasterAvailability.__table__
    table.create(db.get_bind())
    owner=BranchOwnership.__table__
    with birth.canonical_account_birth(db,actor,payload):
        root=new_root(db,actor,payload)
        flush_graph(db)
        db.connection().execute(owner.insert().values(resource_table=root.__tablename__,resource_key=str(root.id),company_id=2,branch_id=3,source='test-root'))
        add_remainder(db,actor,root)
        flush_graph(db)
        if existing_owner != 'new':
            ident=db.connection().execute(table.insert().values(company_id=2,branch_id=3,context_id=11,resource_table=root.__tablename__,resource_key=str(root.id),active=existing_owner!='inactive',revision=1).returning(table.c.id)).scalar_one()
            if existing_owner != 'missing':
                db.connection().execute(owner.insert().values(resource_table=table.name,resource_key=str(ident),company_id=9 if existing_owner=='foreign_company' else 2,branch_id=9 if existing_owner=='foreign_branch' else 3,source='prior-owner'))
        before=list(db.connection().execute(select(owner).where(owner.c.resource_table==table.name)))
        if existing_owner in ('new','exact'):
            birth.enroll_born_account(db,actor,root)
            row=db.connection().execute(select(table)).one()
            assert (row.company_id,row.branch_id,row.context_id,row.revision,row.active)==(2,3,11,1,True)
            proof=db.connection().execute(select(owner).where(owner.c.resource_table==table.name)).one()
            assert (proof.resource_key,proof.company_id,proof.branch_id)==(str(row.id),2,3)
            assert proof.source==('anonymous-account-birth-enrollment' if existing_owner=='new' else 'prior-owner')
            birth.enroll_born_account(db,actor,root)
            assert db.connection().execute(select(func.count()).select_from(table)).scalar_one()==1
            assert db.connection().execute(select(func.count()).select_from(owner).where(owner.c.resource_table==table.name)).scalar_one()==1
        else:
            with pytest.raises(HTTPException) as error:
                birth.enroll_born_account(db,actor,root)
            assert error.value.status_code==403
            assert list(db.connection().execute(select(owner).where(owner.c.resource_table==table.name)))==before
            assert db.connection().execute(select(func.count()).select_from(table)).scalar_one()==1
    db.rollback()
    assert db.connection().execute(select(func.count()).select_from(table)).scalar_one()==0
    assert db.connection().execute(select(func.count()).select_from(owner)).scalar_one()==0
