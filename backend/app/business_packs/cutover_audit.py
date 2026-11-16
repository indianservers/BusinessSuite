"""Fixed setup telemetry predicates for the cutover inventory; no audit-body reads."""
from sqlalchemy import select,exists,and_,or_,false,func
from types import MappingProxyType

SETUP_HTTP = frozenset({
    ('GET','/access/me','access'),
    ('GET','/business-packs/catalog','access'),('GET','/business-packs/configuration','access'),
    ('GET','/business-packs/readiness','access'),('GET','/business-packs/history','access'),
    ('GET','/business-packs/contexts/{context_id}/master-options','access'),
    ('GET','/business-packs/contexts/{context_id}/user-options','access'),
    ('POST','/business-packs/preview','access'),('POST','/business-packs/activations','access'),
    ('POST','/business-packs/contexts','access'),('POST','/business-packs/contexts/{context_id}/grant-preview','access'),
    ('POST','/business-packs/activations/{ident}/activate','access'),
    ('POST','/business-packs/contexts/{ident}/activate','access'),
    ('PUT','/business-packs/contexts/{context_id}/masters','access'),
    ('PUT','/business-packs/contexts/{context_id}/grants/{user_id}','access'),
    ('POST','/branches','branches'),('GET','/branches/context','branches'),('GET','/branches/manage','branches'),
})

def _product(source_id,company,creator,branch):
    from app.apps.srm.models import SRMProduct
    from app.branches.models import BranchOwnership
    from app.models.security_boundary import SecurityResourceOwnership
    from .models import PackRecordOwnership
    from app.branches.catalog import key_expression
    from app.shared.catalog_branches import availability_clause
    t,b,s,p=(m.__table__ for m in (SRMProduct,BranchOwnership,SecurityResourceOwnership,PackRecordOwnership))
    return exists(select(t.c.id).where(t.c.id==source_id,t.c.organization_id==company,t.c.created_by==creator,
        t.c.deleted_at.is_(None),availability_clause(SRMProduct,branch),
        ~exists(select(p.c.id).where(p.c.resource_table==t.name,p.c.resource_key==key_expression(t))),
        ~exists(select(s.c.resource_id).where(s.c.resource_table==t.name,s.c.resource_id==t.c.id,s.c.company_id!=company)),
        ~exists(select(b.c.resource_key).where(b.c.resource_table==t.name,b.c.resource_key==key_expression(t),
            or_(b.c.company_id!=company,b.c.branch_id!=branch)))))

def _not_private(table):
    from .models import PackRecordOwnership
    from app.branches.catalog import key_expression
    p=PackRecordOwnership.__table__
    return ~exists(select(p.c.id).where(p.c.resource_table==table.name,p.c.resource_key==key_expression(table)))


def setup_predicate(table,company,branch):
    from app.models.audit import AuditLog
    from app.apps.srm.models import SRMAuditLog
    if table is AuditLog.__table__:
        t=table.c
        no_business=and_(t.entity_type.is_(None),t.entity_id.is_(None),t.task_id.is_(None),t.project_id.is_(None),t.workspace_id.is_(None))
        native_outcome=or_(and_(t.status_code.between(200,399),t.action==t.method),
            and_(t.status_code.between(400,499),t.action=='REJECTED'),
            and_(t.status_code.between(500,599),t.action=='ERROR'))
        setup=and_(no_business,native_outcome,or_(*(and_(t.method==method,t.endpoint==endpoint,t.module==module)
            for method,endpoint,module in SETUP_HTTP)))
        master=and_(t.method=='POST',t.endpoint=='/srm/inventory/items',t.module=='srm',t.status_code==201,t.action=='POST',
            t.entity_type=='canonical:srm_product_created',t.task_id.is_(None),t.project_id.is_(None),t.workspace_id.is_(None),
            _product(t.entity_id,company,t.user_id,branch))
        return and_(_not_private(table),t.organization_id==company,t.actor_authenticated.is_(True),t.user_id.is_not(None),or_(setup,master))
    if table is SRMAuditLog.__table__:
        t=table.c
        return and_(_not_private(table),t.organization_id==company,t.entity_type=='product',t.action=='CREATE',t.actor_user_id.is_not(None),
            _product(t.entity_id,company,t.actor_user_id,branch))
    from app.models.email_outbox import EmailOutbox
    if table is EmailOutbox.__table__:
        # Signup control receipt only. Never inspect invitation bodies or tokens.
        from app.apps.saas.models import TenantSubscription,TenantSubscriptionPlan
        from app.models.user import User
        t=table.c
        subscription,plan,user=(m.__table__ for m in (TenantSubscription,TenantSubscriptionPlan,User))
        receipt=plan.c.config_json['platform_provisioning']
        return and_(_not_private(table),t.organization_id==company,t.module=='public_signup',
            exists(select(subscription.c.id).select_from(subscription.join(plan,subscription.c.plan_id==plan.c.id).join(
                user,user.c.id==receipt['user_id'].as_integer())).where(
                subscription.c.company_id==company,plan.c.code.like('platform-signup-%'),
                t.event_key==func.replace(plan.c.code,'platform-signup-','signup-approved:'),
                receipt['company_id'].as_integer()==company,
                receipt['email'].as_string()==t.recipient,user.c.email==t.recipient)))
    return false()
