"""Link a service visit to its one native POS checkout without double billing."""
from fastapi import HTTPException
from sqlalchemy import and_, inspect, select


def checkout_link(db, row):
    from app.apps.srm.service_checkout_models import MODELS, POSServiceCheckout, POSCheckoutLine, POSServiceOccurrence
    from app.apps.srm.service_checkout import installation_ready

    inspector = inspect(db.connection())
    if not any(inspector.has_table(model.__tablename__) for model in MODELS):
        return None
    if not installation_ready(db):
        raise HTTPException(503, 'Service checkout installation is incomplete')
    occurrence, line, checkout = POSServiceOccurrence.__table__, POSCheckoutLine.__table__, POSServiceCheckout.__table__
    mapping = db.connection().execute(select(occurrence.c.id).where(occurrence.c.appointment_id == row.id)).first()
    if mapping is None:
        return None
    linked = db.connection().execute(select(occurrence.c.checkout_id, occurrence.c.checkout_line_id,
        checkout.c.organization_id, checkout.c.branch_id, line.c.line_total).select_from(
            occurrence.join(line, and_(line.c.id == occurrence.c.checkout_line_id,
                                      line.c.checkout_id == occurrence.c.checkout_id)).join(checkout, checkout.c.id == occurrence.c.checkout_id)
        ).where(occurrence.c.appointment_id == row.id)).mappings().first()
    if linked is None:
        raise HTTPException(409, 'The linked service checkout must be reconciled before billing')
    if linked['organization_id'] != row.organization_id or linked['branch_id'] != row.branch_id or row.invoice_id is not None:
        raise HTTPException(409, 'The linked service checkout must be reconciled before billing')
    return linked


def require_standalone(db, row):
    if row.kind == 'appointment' and checkout_link(db, row) is not None:
        raise HTTPException(409, 'Manage this service invoice and payment through its linked checkout')


def group_billing(db, actor, row, *, requested_context_id=None):
    linked = checkout_link(db, row)
    if linked is None:
        return None
    from app.business_packs.access import resolve_context
    from app.apps.srm.service_checkout import servicecheckout_state

    branch = db.info.get('branch_context')
    scope = resolve_context(db, actor, branch, requested_context_id=requested_context_id
        if requested_context_id is not None else getattr(db.info.get('business_pack_scope'), 'context_id', None))
    installed = db.info.get('business_pack_scope')
    if installed is not None and installed != scope:
        raise HTTPException(403, 'Business Pack authorization changed')
    checkout = servicecheckout_state(db, actor, branch, linked['checkout_id'], pack_scope=scope)
    return {'appointment_id': row.id, 'revision': row.revision, 'visit_status': row.status,
            'group_checkout': {'id': linked['checkout_id'], 'line_id': linked['checkout_line_id'],
                               'service_charge': format(linked['line_total'], '.2f')},
            'checkout': checkout}
