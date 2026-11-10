"""A signed identity is valid only inside the database which issued it."""
from datetime import datetime,timedelta,timezone
import jwt
import pytest
from starlette.websockets import WebSocketDisconnect
from app.core.config import settings
from app.apps.project_management.api import router as pms_router


def test_foreign_database_token_is_rejected_before_websocket_queries(client,monkeypatch):
    monkeypatch.setattr(settings,'TENANT_DATABASES_ENABLED',False)
    class DefaultDatabase:
        info={}
        def query(self,*args):
            raise AssertionError('Foreign database token reached a default-database query')
        def close(self):pass
    monkeypatch.setattr(pms_router,'SessionLocal',lambda:DefaultDatabase())
    token=jwt.encode({'sub':'1','type':'access','tenant':'11111111-1111-4111-8111-111111111111','exp':datetime.now(timezone.utc)+timedelta(minutes=5)},settings.SECRET_KEY,algorithm=settings.ALGORITHM)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect('/api/v1/project-management/realtime?token='+token):
            pass
    assert exc.value.code==1008
