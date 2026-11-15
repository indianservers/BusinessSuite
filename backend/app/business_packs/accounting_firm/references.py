"""Exact historical preparation authorship; never a user lookup permission."""
from sqlalchemy import inspect,select
from .models import AccountsPeriod
from app.models.user import User


def historical_preparer(db,scope,item,parent,pairs):
    if (type(item) is not AccountsPeriod or parent is not User.__table__ or len(pairs)!=1
            or pairs[0][0]!='prepared_by_user_id' or pairs[0][1] is not User.__table__.c.id):
        return False
    state=inspect(item)
    if not state.persistent or state.session is not db or state.attrs.prepared_by_user_id.history.has_changes():
        return False
    if item.prepared_by_user_id is None:
        return False
    # Revalidate the existing historical scalar only. It grants no User read or
    # foreign-user assignment and cannot certify a new or mutated authorship.
    table=AccountsPeriod.__table__
    actual=db.connection().scalar(select(table.c.prepared_by_user_id).where(table.c.id==item.id,
        table.c.organization_id==scope.company_id,table.c.branch_id==scope.branch_id,table.c.pack_context_id==scope.context_id))
    if actual!=item.prepared_by_user_id:
        return False
    from app.apps.srm.service_checkout import _source_scope
    _source_scope(db,scope,scope.company_id,scope.branch_id,AccountsPeriod,item.id)
    return True
