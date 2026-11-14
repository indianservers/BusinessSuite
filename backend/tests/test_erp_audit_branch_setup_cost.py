from app.apps.crm.models import CRMCompany
from app.branches import boundary
from app.branches.service import context
from tests.test_branch_access import setup


def test_all_branches_superuser_does_not_build_discarded_predicates(db,monkeypatch):
    boundary._read_guards.cache_clear()
    actor,a,b,visible,hidden,_=setup(db)
    actor.is_superuser=True;db.commit()
    calls=[];original=boundary.exists
    def measured(*args,**kwargs):
        calls.append(1);return original(*args,**kwargs)
    monkeypatch.setattr(boundary,"exists",measured)
    cleanup=boundary.install(db,actor,context(db,actor,1,"all"))
    try:
        assert {visible.id,hidden.id} <= {r.id for r in db.query(CRMCompany).all()}
        assert len(calls)==0, f"Built {len(calls)} ownership predicates that all-branches superuser discards"
    finally:cleanup()
    calls.clear()
    cleanup=boundary.install(db,actor,context(db,actor,1,str(a.id)))
    try:
        ids={r.id for r in db.query(CRMCompany).all()}
        assert visible.id in ids and hidden.id not in ids
        assert calls, "Selected branch must still apply ownership predicates to superusers"
    finally:cleanup()


def test_selected_branch_reuses_only_predicate_structure_and_reads_live_ownership(db,monkeypatch):
    boundary._read_guards.cache_clear()
    actor,a,b,visible,hidden,_=setup(db)
    actor.is_superuser=True;db.commit()
    calls=[];original=boundary.exists
    def measured(*args,**kwargs):calls.append(1);return original(*args,**kwargs)
    monkeypatch.setattr(boundary,"exists",measured)
    ctx=context(db,actor,1,str(a.id))
    cleanup=boundary.install(db,actor,ctx)
    try:assert visible.id in {r.id for r in db.query(CRMCompany).all()}
    finally:cleanup()
    calls.clear()
    cleanup=boundary.install(db,actor,context(db,actor,1,str(a.id)))
    try:
        assert visible.id in {r.id for r in db.query(CRMCompany).all()}
        assert not calls, "Repeated verified context should reuse SQL structure, not rebuild every model predicate"
    finally:cleanup()
    from app.branches.models import BranchOwnership
    row=db.query(BranchOwnership).filter_by(resource_table="crm_companies",resource_key=str(visible.id)).one()
    row.branch_id=b.id;db.commit()
    cleanup=boundary.install(db,actor,context(db,actor,1,str(a.id)))
    try:assert visible.id not in {r.id for r in db.query(CRMCompany).all()}, "Cached SQL must still read live ownership"
    finally:cleanup()
