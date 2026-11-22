"""Boolean native cutover inventory. No business bodies, adoption, writes or ORM filters."""
from sqlalchemy import select, exists, or_, and_, false, inspect, Integer, String, cast
from fastapi import HTTPException

CONTROL = frozenset({'branches','fam_branches','business_pack_master_availability','industry_targets','feature_plans'})
RECONCILE = 'This branch has operational history or ambiguous native ownership. A reviewed reconciliation is required; records are never adopted automatically.'

def reasons(db, company, branch):
    from app.db.base_class import Base
    from app.branches.catalog import SHARED, parents, key_expression
    from app.branches.models import BranchOwnership
    from app.business_packs.models import PackContext, PackRecordOwnership
    from app.business_packs.native_policy import MASTER_TABLES
    from app.models.security_boundary import SecurityResourceOwnership
    connection=db.connection(); inspector=inspect(connection)
    b,p,c,s=(m.__table__ for m in (BranchOwnership,PackRecordOwnership,PackContext,SecurityResourceOwnership))
    if any(not inspector.has_table(t.name) for t in (b,p,c,s)):
        return ['Native cutover ownership installation is incomplete.']
    if (connection.scalar(select(exists().where(c.c.branch_id==branch,or_(c.c.ever_activated.is_(True),c.c.state!='draft'))))
            or connection.scalar(select(exists().where(p.c.branch_id==branch)))):
        return [RECONCILE]
    safe=SHARED|MASTER_TABLES|CONTROL
    from .cutover_audit import setup_predicate
    from app.models.audit import AuditLog
    from app.apps.srm.models import SRMAuditLog
    from app.models.email_outbox import EmailOutbox
    setup_owner=or_(*(and_(b.c.company_id==company,b.c.resource_table==model.__tablename__,
        exists(select(next(iter(model.__table__.primary_key.columns))).where(
            key_expression(model.__table__)==b.c.resource_key,setup_predicate(model.__table__,company,branch))))
        for model in (AuditLog,SRMAuditLog,EmailOutbox)))
    if connection.scalar(select(exists().where(b.c.branch_id==branch,~b.c.resource_table.in_(safe),~setup_owner))):
        return [RECONCILE]
    # These native models can be absent from metadata until their first use.
    # Load them for the inventory even when readiness is the first request.
    from app.apps.srm import anonymous_cash_models  # noqa: F401
    from app.business_packs import delivery_source_models  # noqa: F401
    from app.business_packs.pharma import recall_models  # noqa: F401
    from app.models import target  # noqa: F401
    tables=dict(Base.metadata.tables)
    from .legacy_cutover import legacy_tables,LegacyInventoryIncomplete
    try:tables.update(legacy_tables(inspector))
    except LegacyInventoryIncomplete:
        return ['Native cutover source inventory is incomplete.']
    physical=set(inspector.get_table_names())
    # Provisioning owns the singleton identity table and restricts runtime
    # writes to it. It contains routing metadata and no branch business data.
    if physical-set(tables)-{'alembic_version','suite_tenant_identity'}:
        return ['Native cutover source inventory is incomplete.']
    present=physical & set(tables)
    def native_owner(t):
        return exists(select(b.c.resource_key).where(b.c.resource_table==t.name,b.c.resource_key==key_expression(t)))
    def security_identity(t):
        key=next(iter(t.primary_key.columns))
        # The native legacy sidecar has a numeric resource ID. Never coerce an
        # opaque UUID/string native key to a number or discard its source table.
        return s.c.resource_id==key if isinstance(key.type,Integer) else cast(s.c.resource_id,String)==key_expression(t)
    def company_evidence(t):
        choices=[t.c[n]==company for n in ('organization_id','company_id') if n in t.c]
        choices.append(exists(select(b.c.resource_key).where(b.c.resource_table==t.name,
            b.c.resource_key==key_expression(t),b.c.company_id==company)))
        if len(t.primary_key.columns)==1:
            key=next(iter(t.primary_key.columns))
            choices.append(exists(select(s.c.resource_id).where(s.c.resource_table==t.name,
                security_identity(t),s.c.company_id==company)))
        return or_(*choices)
    def direct_location(t):
        choices=[exists(select(b.c.resource_key).where(b.c.resource_table==t.name,
            b.c.resource_key==key_expression(t),b.c.company_id==company,b.c.branch_id==branch))]
        if 'branch_id' in t.c:choices.append(t.c.branch_id==branch)
        return or_(*choices)
    def location(t):
        choices=[direct_location(t)]
        # Scan EVERY native table. A missing-owner FK chain is caught at its first
        # child of a located parent, without exponential recursive SQL expansion.
        for child,parent,key in parents(t,tables):
            if parent.name in present and parent.name != t.name and parent.name not in SHARED:
                choices.append(exists(select(key).where(key==child,direct_location(parent))))
        return or_(*choices)
    for name in sorted(present-safe):
        t=tables[name]
        if not list(t.primary_key):return ['Native cutover source inventory is incomplete.']
        # Direct branch evidence cannot be hidden by company, role, tombstone or pack filters.
        business=setup_predicate(t,company,branch).is_not(True)
        if 'branch_id' in t.c and connection.scalar(select(exists().where(t.c.branch_id==branch,business))):
            return [RECONCILE]
        missing=~native_owner(t)
        predicates=[and_(missing,location(t))]
        # A company-owned but unlocated master cannot make its unowned business
        # children disappear from the inventory merely because it is shareable.
        for child,parent,parent_key in parents(t,tables):
            if parent.name in present and parent.name not in SHARED and parent.name!=t.name:
                unlocated=~native_owner(parent)
                if 'branch_id' in parent.c:unlocated=and_(unlocated,parent.c.branch_id.is_(None))
                predicates.append(and_(missing,exists(select(parent_key).where(
                    parent_key==child,unlocated,company_evidence(parent)))))
        company_columns=[t.c[n] for n in ('organization_id','company_id') if n in t.c]
        ambiguous=or_(*(column==company for column in company_columns)) if company_columns else false()
        if len(t.primary_key.columns)==1:
            key=next(iter(t.primary_key.columns))
            ambiguous=or_(ambiguous,exists(select(s.c.resource_id).where(s.c.resource_table==name,
                security_identity(t),s.c.company_id==company)))
        if 'branch_id' in t.c:ambiguous=and_(ambiguous,t.c.branch_id.is_(None))
        predicates.append(and_(missing,ambiguous))
        if not company_columns and 'branch_id' not in t.c and not list(parents(t,tables)):
            unknown=missing
            if len(t.primary_key.columns)==1:
                unknown=and_(unknown,~exists(select(s.c.resource_id).where(s.c.resource_table==name,security_identity(t))))
            predicates.append(unknown)  # Neither company nor branch provenance exists for an opaque root.
        if connection.scalar(select(select(next(iter(t.primary_key.columns))).where(or_(*predicates),business).exists())):
            return [RECONCILE]
    return []


def require_empty(db,company,branch):
    problems=reasons(db,company,branch)
    if problems:raise HTTPException(409,{'message':'First activation requires a verified empty branch','reasons':problems})
