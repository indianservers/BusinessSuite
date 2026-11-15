"""Blind native duplicate-billing reservation check; never a project read grant."""
from fastapi import HTTPException
from sqlalchemy import select,exists,and_,or_,inspect


def reserved_billing(db,actor,*,sales_order=None,engagement=None,project_id=None):
    from app.apps.srm.models import SRMSalesOrder,SRMEngagement
    from app.apps.srm.commercial_models import ProjectCommercial
    from app.apps.project_management.models import PMSProject
    from app.apps.srm.industry_models import IndustryRecord
    from app.apps.srm.service_checkout import _source_scope
    from app.branches.models import BranchOwnership
    from app.business_packs.boundary import _current
    scope=db.info.get('business_pack_scope')
    def deny():raise HTTPException(403,'Native billing source authorization changed')
    if scope is None or getattr(actor,'id',None)!=scope.user_id:deny()
    shared=db.info.get('shared_actor');branch=db.info.get('branch_context')
    if (shared is not None and shared!=(scope.user_id,scope.company_id)) or getattr(branch,'company_id',None)!=scope.company_id or getattr(branch,'branch_id',None)!=scope.branch_id:deny()
    connection=db.connection();_current(scope,connection)
    if project_id is not None:
        raise HTTPException(503,'Direct project billing requires a reviewed native project adapter')
    links=[]
    for row,model,column in ((sales_order,SRMSalesOrder,'sales_order_id'),(engagement,SRMEngagement,'engagement_id')):
        if row is None:continue
        state=inspect(row,raiseerr=False)
        if type(row) is not model or state is None or state.session is not db or not state.persistent or state.modified or row.organization_id!=scope.company_id:deny()
        _source_scope(db,scope,scope.company_id,scope.branch_id,model,row.id)
        table=model.__table__;owner=BranchOwnership.__table__
        if not connection.scalar(select(exists().where(table.c.id==row.id,table.c.organization_id==scope.company_id,
                exists().where(owner.c.resource_table==table.name,owner.c.resource_key==str(row.id),owner.c.company_id==scope.company_id,owner.c.branch_id==scope.branch_id)))):deny()
        links.append(getattr(ProjectCommercial.__table__.c,column)==row.id)
        if model is SRMEngagement and row.pms_project_id:
            if scope.pack_key == 'accounting_firm':
                from .accounting_firm.billing import linked_engagement_authorized
                linked_engagement_authorized(db,actor,row)
            else:
                raise HTTPException(503,'Linked project engagement billing requires a reviewed native project adapter')
    if not links:return False
    commercial=ProjectCommercial.__table__;project=PMSProject.__table__;record=IndustryRecord.__table__
    linked=or_(*links)
    # A foreign or corrupt link cannot be interpreted as an unrelated project.
    invalid=connection.scalar(select(exists().select_from(commercial.outerjoin(project,project.c.id==commercial.c.project_id)).where(
        linked,or_(commercial.c.seller_id!=scope.company_id,project.c.id.is_(None),project.c.organization_id.is_(None),project.c.organization_id!=scope.company_id))))
    if invalid:raise HTTPException(409,'Native billing links require reconciliation')
    inconsistent_record=connection.scalar(select(exists().select_from(commercial.join(project,project.c.id==commercial.c.project_id).join(record,record.c.project_id==project.c.id)).where(
        linked,record.c.kind.in_(['boq','variation']),record.c.status=='approved',or_(record.c.organization_id.is_(None),record.c.organization_id!=scope.company_id))))
    if inconsistent_record:raise HTTPException(409,'Native billing links require reconciliation')
    return bool(connection.scalar(select(exists().select_from(commercial.join(project,project.c.id==commercial.c.project_id).join(record,record.c.project_id==project.c.id)).where(
        linked,commercial.c.seller_id==scope.company_id,project.c.organization_id==scope.company_id,
        record.c.organization_id==scope.company_id,record.c.kind.in_(['boq','variation']),record.c.status=='approved'))))


def selected_order_source_reserved(db,source_type,source_id):
    """Fixed existence-only invoice reservation over one proven native order."""
    from app.apps.srm.models import SRMSalesOrder,SRMSalesOrderLine,SRMEngagement,SRMBillingPlan,SRMBillingMilestone,SRMInvoiceLine,SRMInvoice
    from app.apps.srm.service_checkout import _source_scope
    from app.branches.models import BranchOwnership
    from app.business_packs.boundary import _current
    scope=db.info.get('business_pack_scope')
    if scope is not None and scope.pack_key=='accounting_firm' and source_type=='accounts_period':
        from .accounting_firm.billing import source_reserved
        return source_reserved(db,source_id)
    if scope is not None and scope.pack_key=='construction' and source_type=='industry_measurement':
        from .construction_billing import source_reserved
        return source_reserved(db,source_id)
    if scope is None or source_type not in {'sales_order','sales_order_line'}:
        raise HTTPException(503,'This selected invoice source requires a reviewed adapter')
    connection=db.connection();_current(scope,connection)
    shared=db.info.get('shared_actor')
    branch=db.info.get('branch_context')
    if (shared is not None and shared!=(scope.user_id,scope.company_id)) or getattr(branch,'company_id',None)!=scope.company_id or getattr(branch,'branch_id',None)!=scope.branch_id:
        raise HTTPException(403,'Native invoice source authorization changed')
    child_id=None
    if source_type=='sales_order_line':
        child=db.get(SRMSalesOrderLine,source_id)
        child_state=inspect(child,raiseerr=False) if child is not None else None
        if type(child) is not SRMSalesOrderLine or child_state.session is not db or not child_state.persistent or child_state.modified:
            raise HTTPException(403,'Native invoice source authorization changed')
        _source_scope(db,scope,scope.company_id,scope.branch_id,SRMSalesOrderLine,child.id)
        actual_parent=connection.scalar(select(SRMSalesOrderLine.__table__.c.sales_order_id).where(SRMSalesOrderLine.__table__.c.id==child.id))
        if actual_parent!=child.sales_order_id:
            raise HTTPException(403,'Native invoice source authorization changed')
        child_id=child.id;source_id=actual_parent
    row=db.get(SRMSalesOrder,source_id)
    state=inspect(row,raiseerr=False) if row is not None else None
    if type(row) is not SRMSalesOrder or state.session is not db or not state.persistent or state.modified or row.organization_id!=scope.company_id:
        raise HTTPException(403,'Native invoice source authorization changed')
    _source_scope(db,scope,scope.company_id,scope.branch_id,SRMSalesOrder,row.id)
    owner=BranchOwnership.__table__;order=SRMSalesOrder.__table__
    if not connection.scalar(select(exists().where(order.c.id==row.id,order.c.organization_id==scope.company_id,
            exists().where(owner.c.resource_table==order.name,owner.c.resource_key==str(row.id),owner.c.company_id==scope.company_id,owner.c.branch_id==scope.branch_id)))):
        raise HTTPException(403,'Native invoice source authorization changed')
    line=SRMSalesOrderLine.__table__;engagement=SRMEngagement.__table__;plan=SRMBillingPlan.__table__;milestone=SRMBillingMilestone.__table__;invoice_line=SRMInvoiceLine.__table__
    order_lines=select(line.c.id).where(line.c.sales_order_id==row.id)
    engagements=select(engagement.c.id).where(engagement.c.sales_order_id==row.id)
    plans=select(plan.c.id).where(plan.c.engagement_id.in_(engagements))
    if connection.scalar(select(exists().where(engagement.c.sales_order_id==row.id,or_(engagement.c.organization_id.is_(None),engagement.c.organization_id!=scope.company_id)))):
        return True
    if connection.scalar(select(exists().where(plan.c.engagement_id.in_(engagements),or_(plan.c.organization_id.is_(None),plan.c.organization_id!=scope.company_id)))):
        return True
    milestones=select(milestone.c.id).where(milestone.c.billing_plan_id.in_(plans))
    guard=or_(and_(invoice_line.c.source_type=='sales_order',invoice_line.c.source_id==row.id),
        and_(invoice_line.c.source_type=='sales_order_line',invoice_line.c.source_id.in_(order_lines)),
        and_(invoice_line.c.source_type=='engagement',invoice_line.c.source_id.in_(engagements)),
        and_(invoice_line.c.source_type=='billing_milestone',invoice_line.c.source_id.in_(milestones)))
    # A malformed foreign link must also reserve the source for reconciliation;
    # its company or hidden context never makes an existing reservation vanish.
    if child_id is not None:
        guard=and_(invoice_line.c.source_type=='sales_order_line',invoice_line.c.source_id==child_id)
    invoice=SRMInvoice.__table__
    joined=invoice_line.outerjoin(invoice,invoice.c.id==invoice_line.c.invoice_id)
    if connection.scalar(select(exists().select_from(joined).where(guard,or_(invoice.c.id.is_(None),invoice.c.organization_id.is_(None),invoice.c.organization_id!=scope.company_id)))):
        raise HTTPException(409,'Native invoice links require reconciliation')
    return bool(connection.scalar(select(exists().select_from(joined).where(guard,invoice.c.organization_id==scope.company_id))))
