"""Direct synthetic legacy-root seeds require both native owner proofs."""
import pytest
from sqlalchemy import select
from app.models.payroll import TaxRegime,TaxSlab
from app.models.security_boundary import SecurityResourceOwnership
from app.branches.models import BranchOwnership
from tests.payroll_test_utils import init_payroll_test_db,commit_payroll_fixture


def new_slab(db):
    regime=TaxRegime(financial_year='2099-00',regime_code='QA',name='Synthetic owner proof')
    db.add(regime);db.flush()
    slab=TaxSlab(tax_regime_id=regime.id,min_income=0,max_income=100,rate_percent=5)
    db.add(slab);db.flush();return slab


def test_new_legacy_root_claim_matches_actual_native_branch_owner(db):
    init_payroll_test_db(db);slab=new_slab(db);commit_payroll_fixture(db)
    native=db.query(BranchOwnership).filter_by(resource_table='tax_slabs',resource_key=str(slab.id)).one()
    tenant=db.query(SecurityResourceOwnership).filter_by(resource_table='tax_slabs',resource_id=slab.id).one()
    assert tenant.company_id==native.company_id


def test_existing_tenant_claim_is_never_reassigned_by_fixture_helper(db):
    init_payroll_test_db(db);slab=new_slab(db)
    from app.models.company import Company
    foreign=Company(name='Foreign fixture owner');db.add(foreign);db.flush();foreign_id=foreign.id
    table=SecurityResourceOwnership.__table__
    old=db.connection().execute(select(table.c.company_id).where(table.c.resource_table=='tax_slabs',table.c.resource_id==slab.id)).first()
    if old:
        db.connection().execute(table.update().where(table.c.resource_table=='tax_slabs',table.c.resource_id==slab.id).values(company_id=foreign_id))
    else:
        db.connection().execute(table.insert().values(resource_table='tax_slabs',resource_id=slab.id,company_id=foreign_id))
    with pytest.raises(AssertionError,match='must never be overwritten'):commit_payroll_fixture(db)
    assert db.query(SecurityResourceOwnership).filter_by(resource_table='tax_slabs',resource_id=slab.id).one().company_id==foreign_id


def test_unrecorded_existing_source_is_not_adopted(db):
    init_payroll_test_db(db);regime=TaxRegime.__table__;table=TaxSlab.__table__
    parent=db.connection().execute(regime.insert().values(financial_year='2099-00',regime_code='UNCLAIMED',name='Unclaimed source').returning(regime.c.id)).scalar_one()
    ident=db.connection().execute(table.insert().values(tax_regime_id=parent,min_income=0,max_income=100,rate_percent=5).returning(table.c.id)).scalar_one()
    commit_payroll_fixture(db)
    assert db.query(SecurityResourceOwnership).filter_by(resource_table='tax_slabs',resource_id=ident).first() is None
    assert db.query(BranchOwnership).filter_by(resource_table='tax_slabs',resource_key=str(ident)).first() is None
