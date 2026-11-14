"""Scoped named recipients for administrative approval configuration."""
from fastapi import HTTPException
from app.models.user import User

def queries(db, company_id):
    from app.enterprise.controls import company_user_ids
    from app.access.models import AccessMembership
    from app.models.user import Role
    from sqlalchemy import select, or_
    inactive = select(AccessMembership.user_id).where(
        AccessMembership.company_id == company_id, AccessMembership.active.is_(False))
    users = db.query(User).filter(User.id.in_(company_user_ids(db, company_id, active_only=True)),
                                  User.id.notin_(inactive))
    roles = db.query(Role).filter(or_(Role.is_system.is_(True),
        Role.id.in_(users.with_entities(User.role_id))))
    return users, roles


def lookup(db, company_id, search="", page=1, selected_user=None):
    from app.common.models import CommonPerson
    from app.common.services.identity import SharedIdentityService
    from sqlalchemy import or_
    users, roles = queries(db, company_id)
    selected = users.filter(User.id == selected_user).first() if selected_user else None
    if search:
        users = users.filter(or_(User.email.icontains(search, autoescape=True),
            User.person.has(CommonPerson.display_name.icontains(search, autoescape=True))))
    total = users.count()
    return {'users':[{'id':row.id, 'name':SharedIdentityService.display_name_for_user(row), 'email':row.email}
        for row in users.order_by(User.email, User.id).offset((page-1)*25).limit(25)],
        'roles':[{'id':row.id, 'name':row.name} for row in roles.order_by('name')],
        'selected_user':{'id':selected.id,'name':SharedIdentityService.display_name_for_user(selected),'email':selected.email} if selected else None,
        'page':page, 'total':total, 'has_more':page*25 < total}


def validate_step_recipients(db, user, step):
    from app.access.service import primary_company
    from app.models.user import Role
    users, roles = queries(db, getattr(user, 'organization_id', None) or primary_company(user))
    targets = [(step.approver_type, step.approver_value),
               (step.delegation_type, step.delegation_value),
               ('User', step.escalation_user_id), ('Role', step.escalation_role)]
    for kind, value in targets:
        if value is None or value == '':
            continue
        if str(kind).lower() == 'user':
            text = str(value)
            if not text.isascii() or not text.isdecimal() or len(text)>10:
                raise HTTPException(422, 'Choose an active workflow recipient in this company')
            ident = int(text)
            if not 0<ident<=2147483647 or not users.filter(User.id == ident).first():
                raise HTTPException(422, 'Choose an active workflow recipient in this company')
        elif str(kind).lower() == 'role' and (not isinstance(value,str) or not roles.filter(Role.name == value).first()):
            raise HTTPException(422, 'Choose an available workflow role in this company')


    for field in ('approver_type', 'delegation_type'):
        value = getattr(step, field)
        if isinstance(value, str) and value.lower() in {'role', 'user'}:
            setattr(step, field, value.title())


