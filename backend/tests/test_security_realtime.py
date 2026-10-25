from contextlib import contextmanager
from datetime import date
import pytest
from starlette.websockets import WebSocketDisconnect
from app.core.security import create_access_token
from app.models.user import User,Role
from app.models.employee import Employee
from app.apps.project_management.realtime import PMSRealtimeManager


def test_intern_portal_token_is_rejected_at_pms_websocket(client):
    token=create_access_token('1',portal='interns_hub')
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect('/api/v1/project-management/realtime?token='+token):
            pass
    assert exc.value.code==1008


def test_open_realtime_identity_is_rechecked_after_becoming_an_intern(db):
    user=User(email='synthetic-realtime@example.com',hashed_password='unused',is_active=True,role=Role(name='employee'))
    db.add(user);db.commit()
    @contextmanager
    def factory():
        yield db
    manager=PMSRealtimeManager(db_factory=factory)
    assert manager._authorized(user.id,None)
    db.add(Employee(employee_id='SYNTHETIC-WS',first_name='Synthetic',last_name='Realtime',date_of_joining=date.today(),employment_type='Intern',user_id=user.id));db.commit();db.expire_all()
    assert not manager._authorized(user.id,None)
