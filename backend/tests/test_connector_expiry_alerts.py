from datetime import timedelta
from tests.test_power_apps import actors
from tests.test_marketplace_sync_workflows import native_actor,create_connection
from tests.test_marketplace_provider_authorization import CASES
from app.apps.power_apps.integrations.models import Connection
from app.apps.power_apps.integrations.health_alerts import dispatch
from app.apps.power_apps.integrations.vault import public_connection
from app.apps.power_apps.runtime import now
from app.models.notification import Notification


def test_expiry_alerts_are_owner_scoped_deduplicated_and_do_not_send_external_messages(client,db,native_actor):
    headers,user=native_actor
    ident=create_connection(client,headers,next(c for c in CASES if c[0]=='facebook_lead_ads'))
    conn=db.get(Connection,ident)
    conn.expires_at=now()+timedelta(hours=24);db.commit()
    assert public_connection(conn)['expiry_status']=='expiring'
    assert dispatch(db)=={'notified':1}
    assert dispatch(db)=={'notified':0}
    notification=db.query(Notification).filter_by(event_type='connector_expiring').one()
    assert notification.user_id==user.id and notification.company_id==conn.organization_id
    assert notification.channels==['in_app']
    conn.expires_at=now()-timedelta(hours=1);db.commit()
    assert public_connection(conn)['health']=='expired'
    assert dispatch(db)=={'notified':1}
    assert dispatch(db)=={'notified':0}
    conn.expires_at=now()+timedelta(days=30);db.commit()
    assert public_connection(conn)['expiry_status'] is None and dispatch(db)=={'notified':0}
    conn.enabled=False;conn.expires_at=now()-timedelta(days=1);db.commit()
    assert dispatch(db)=={'notified':0}
