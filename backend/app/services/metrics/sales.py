"""Current snapshot selection and explicit monetary units for sales statistics."""
from sqlalchemy import func
from .queries import amounts_by_currency


def latest_profitability_query(db,user):
    from app.apps.srm.models import SRMProfitabilitySnapshot,SRMEngagement
    from app.apps.srm.access import engagement_query
    from app.apps.srm.services.commercial import scoped
    visible=engagement_query(db,user).with_entities(SRMEngagement.id)
    query=db.query(SRMProfitabilitySnapshot).filter(scoped(SRMProfitabilitySnapshot.organization_id,user),SRMProfitabilitySnapshot.engagement_id.in_(visible))
    latest=query.with_entities(func.max(SRMProfitabilitySnapshot.id)).group_by(SRMProfitabilitySnapshot.engagement_id)
    return query.filter(SRMProfitabilitySnapshot.id.in_(latest))


def scalar_currency(rows):
    if not rows:return 0.0
    return float(rows[0]["amount"]) if len(rows)==1 and rows[0]["currency"]!="Unknown" else None


def invoice_statistics(query,today):
    from app.apps.srm.models import SRMInvoice
    columns={"total_invoiced_value":SRMInvoice.total_amount,"total_collected_value":SRMInvoice.paid_amount,"outstanding_value":SRMInvoice.balance_amount,"overdue_value":SRMInvoice.balance_amount}
    values={}
    for key,column in columns.items():
        selected=query.filter(SRMInvoice.balance_amount>0,SRMInvoice.due_date<today) if key=="overdue_value" else query
        values[key]=amounts_by_currency(selected,SRMInvoice.currency,column)
    return values
