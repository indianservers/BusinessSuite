"""Shared native HR helpdesk ownership, tenancy and optimistic locking."""
from fastapi import HTTPException
from sqlalchemy import and_,or_,select
from app.models.helpdesk import HelpdeskTicket
from app.models.employee import Employee
from app.models.company import Branch
from app.models.user import User
from app.access.service import primary_company,companies_for
from app.core.masking import user_has_permission


def company(user):
    return getattr(user,'organization_id',None) or primary_company(user)


def manager(user):return user_has_permission(user,'helpdesk_manage')


def tickets(db,user):
    tenant=company(user)
    # Match the native employee router's company-1 legacy unbranched records.
    legacy=select(Employee.id).outerjoin(Branch,Employee.branch_id==Branch.id).where(or_(
        Branch.company_id==tenant,and_(Employee.branch_id.is_(None),tenant==1)))
    query=db.query(HelpdeskTicket).filter(HelpdeskTicket.module_key.is_(None),or_(
        HelpdeskTicket.organization_id==tenant,and_(HelpdeskTicket.organization_id.is_(None),HelpdeskTicket.employee_id.in_(legacy))))
    if not manager(user):
        employee=getattr(user,'employee',None)
        query=query.filter(or_(HelpdeskTicket.employee_id==(employee.id if employee else -1),
            HelpdeskTicket.assigned_to==user.id,HelpdeskTicket.escalated_to==user.id))
    return query


def ticket(db,user,ident,*,lock=False,expected_version=None):
    if type(ident) is not int or not 0<ident<=2147483647:raise HTTPException(404,'Ticket not found')
    query=tickets(db,user).filter(HelpdeskTicket.id==ident)
    if lock:query=query.populate_existing().with_for_update()
    row=query.first()
    if row is None:raise HTTPException(404,'Ticket not found')
    if expected_version is not None and row.version!=expected_version:raise HTTPException(409,'Ticket changed; prepare a fresh review')
    return row


def assignee(db,user,ident):
    if ident is None:return
    target=db.query(User).filter(User.id==ident,User.is_active.is_(True)).first()
    if not target or company(user) not in companies_for(db,target):raise HTTPException(422,'Assignee must be an active member of this company')


def changed(row):
    from datetime import datetime,timezone
    row.version+=1
    row.updated_at=datetime.now(timezone.utc)
