"""Read-only recovery/context helpers for the shared reservation editor."""
from datetime import datetime, timedelta, timezone
from collections import Counter
from fastapi import HTTPException


def request_status(db, actor, request_id):
    from app.apps.srm.industry_api import context, query, out
    from app.business_packs.operations import for_record_read
    branch = context(db, actor, appointments=True)
    for_record_read(db, actor, 'appointment')
    row = query(db,actor,branch).filter_by(kind='appointment',request_id=str(request_id),created_by=actor.id).first()
    return {'state':'confirmed','appointment':out(row,db,actor)} if row else {'state':'not_found'}


def customer_context(db, actor, customer_id, *, service_id=None, starts_at=None):
    from app.apps.srm.industry_api import context, query, out, get, Record
    from app.apps.srm.services.commercial import customer
    from app.business_packs.operations import for_record_read
    branch = context(db, actor, appointments=True)
    for_record_read(db, actor, 'appointment')
    customer(db,customer_id,actor)
    if starts_at and starts_at.utcoffset() is None:
        raise HTTPException(422,'Customer context time needs a timezone offset')
    now = datetime.now(timezone.utc)
    base = query(db,actor,branch).filter_by(kind='appointment',customer_id=customer_id)
    recent = base.filter(Record.starts_at < now).order_by(Record.starts_at.desc(),Record.id.desc()).limit(3).all()
    upcoming = base.filter(Record.starts_at >= now,Record.status.in_(['booked','checked_in','in_service'])).order_by(Record.starts_at,Record.id).limit(5).all()
    duplicate_query = base.filter(Record.status.in_(['booked','checked_in','in_service']))
    if service_id:
        duplicate_query = duplicate_query.filter(Record.data['service_id'].as_integer()==service_id)
    if starts_at:
        duplicate_query=duplicate_query.filter(Record.starts_at>=starts_at-timedelta(hours=2),Record.starts_at<=starts_at+timedelta(hours=2))
    else:
        duplicate_query=duplicate_query.filter(Record.starts_at>=now)
    duplicates=duplicate_query.order_by(Record.starts_at).limit(5).all() if service_id else []
    counts=Counter(identity for row in recent for identity in row.data.get('resource_ids',[]) if type(identity) is int)
    preferred=None
    for identity,_ in counts.most_common():
        try:
            resource=get(db,actor,branch,identity,'resource',lock=False)
            if resource.status=='active' and resource.data.get('employee_id'):
                preferred={'employee_id':resource.data['employee_id'],'name':resource.title}
                break
        except HTTPException as error:
            if error.status_code not in (403,404): raise
    return {'recent':[out(row,db,actor) for row in recent], 'upcoming':[out(row,db,actor) for row in upcoming],
            'possible_duplicates':[out(row,db,actor) for row in duplicates], 'preferred_provider':preferred}
