"""Deduplicated in-app expiry alerts for authorized connector owners."""
import hashlib
from datetime import timedelta
from app.apps.power_apps.runtime import now,utc
from app.apps.power_apps.integrations.models import Connection
from app.models.notification import Notification
from app.models.user import User
from app.shared.models import ServicePolicy


def expiry_status(connection):
    if not connection.enabled or not connection.expires_at: return None
    remaining=utc(connection.expires_at)-now()
    return 'expired' if remaining.total_seconds()<=0 else 'expiring' if remaining<=timedelta(hours=72) else None


def dispatch(db):
    # Lock connection before checking the receipt so multiple workers cannot
    # create the same notification. This matches the connector journal lock order.
    ids=db.query(Connection.id).filter(Connection.enabled.is_(True),Connection.expires_at.is_not(None),
        Connection.expires_at<=now()+timedelta(hours=72)).all()
    notified=0
    for (ident,) in ids:
        try:
            conn=db.query(Connection).filter_by(id=ident).with_for_update().populate_existing().one()
            status=expiry_status(conn)
            owner=db.get(User,conn.owner_user_id)
            if not status or not owner or not owner.is_active: continue
            fingerprint=hashlib.sha256(f'{conn.id}:{utc(conn.expires_at).isoformat()}:{status}'.encode()).hexdigest()
            key='connector-expiry:'+fingerprint
            if db.query(ServicePolicy.id).filter_by(scope_key=key,kind='connector_expiry_alert',organization_id=conn.organization_id).first(): continue
            notification=Notification(company_id=conn.organization_id,user_id=owner.id,module='power_apps',event_type='connector_'+status,
                title=f'{conn.name}: authorization {"expired" if status=="expired" else "expires soon"}'[:200],
                message='Reconnect this provider to keep scheduled imports and automations running.',
                related_entity_type='connector',related_entity_id=conn.id,
                action_url='/power-apps/integrations?connector='+conn.connector_id,channels=['in_app'])
            db.add(notification);db.flush()
            db.add(ServicePolicy(scope_key=key,organization_id=conn.organization_id,module_key='power_apps',kind='connector_expiry_alert',
                updated_by=owner.id,values_json={'connection_id':conn.id,'notification_id':notification.id,'status':status,'notified_at':now().isoformat()}))
            db.commit();notified+=1
        except Exception:
            db.rollback()
    return {'notified':notified}
