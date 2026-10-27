"""In-memory realtime hub for PMS collaboration events."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


@dataclass
class PMSRealtimeConnection:
    websocket: WebSocket
    user_id: int
    organization_id: int | None
    accessible_project_ids: set[int] = field(default_factory=set)
    project_ids: set[int] = field(default_factory=set)
    task_ids: set[int] = field(default_factory=set)
    session_id: int | None = None
    token_expires_at: float | None = None


class PMSRealtimeManager:
    def __init__(self, db_factory=None) -> None:
        self._db_factory = db_factory
        self._connections: dict[WebSocket, PMSRealtimeConnection] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        *,
        user_id: int,
        organization_id: int | None,
        accessible_project_ids: set[int],
        session_id: int | None = None,
        token_expires_at: float | None = None,
    ) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[websocket] = PMSRealtimeConnection(
                websocket=websocket,
                user_id=user_id,
                organization_id=organization_id,
                accessible_project_ids=accessible_project_ids,
                session_id=session_id,
                token_expires_at=token_expires_at,
            )

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.pop(websocket, None)

    async def revoke_projects(self, user_id: int, project_ids: set[int]) -> None:
        """Drop cached subscriptions immediately when workspace membership ends."""
        async with self._lock:
            for connection in self._connections.values():
                if connection.user_id == user_id:
                    connection.accessible_project_ids.difference_update(project_ids)
                    connection.project_ids.difference_update(project_ids)

    async def subscribe(self, websocket: WebSocket, *, project_ids: set[int], task_ids: set[int]) -> None:
        async with self._lock:
            connection = self._connections.get(websocket)
            if not connection:
                return
            connection.project_ids = project_ids
            connection.task_ids = task_ids

    def _authorized(self, user_id, project_id, session_id=None, token_expires_at=None):
        from app.db.session import SessionLocal
        from app.models.user import User, UserSession
        from .access import accessible_project_query
        from .models import PMSProject
        now = datetime.now(timezone.utc)
        if token_expires_at is not None and float(token_expires_at) <= now.timestamp():
            return False
        with (self._db_factory or SessionLocal)() as db:
            if session_id is not None:
                session = db.get(UserSession, int(session_id))
                expires = session.expires_at if session else None
                if expires and expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if not session or session.user_id != user_id or session.status.lower() != "active" or (expires and expires <= now):
                    return False
            user = db.get(User, user_id)
            if not user or not user.is_active:
                return False
            employee=getattr(user,'employee',None)
            if user.role and user.role.name.lower()=='intern' or employee and (employee.employment_type or '').lower()=='intern':
                return False
            from app.core.tenant_boundary import company_ids
            from app.access.service import check_background_access
            if not user.is_superuser and not company_ids(db, user):
                return False
            try:
                check_background_access(db, user, "project_management", "view")
            except Exception:
                return False
            if project_id is None:
                return True
            return accessible_project_query(db, user).filter(PMSProject.id == int(project_id)).first() is not None

    async def broadcast(self, event: dict[str, Any]) -> None:
        payload = json.dumps(event, default=str)
        project_id = event.get("projectId")
        task_id = event.get("taskId")
        organization_id = event.get("organizationId")
        async with self._lock:
            connections = list(self._connections.values())

        stale: list[WebSocket] = []
        for connection in connections:
            if event.get("recipientIds") is not None and connection.user_id not in event["recipientIds"]:
                continue
            if organization_id is not None and connection.organization_id != organization_id:
                continue
            if project_id is not None:
                try:
                    numeric_project_id = int(project_id)
                except (TypeError, ValueError):
                    continue
                if numeric_project_id not in connection.accessible_project_ids:
                    continue
                if connection.project_ids and numeric_project_id not in connection.project_ids:
                    if task_id is None or int(task_id) not in connection.task_ids:
                        continue
            # A connected socket is not a permanent authorization grant. Re-read
            # active identity and project access before delivering sensitive events.
            try:
                from starlette.concurrency import run_in_threadpool
                allowed = await run_in_threadpool(self._authorized, connection.user_id, project_id, connection.session_id, connection.token_expires_at)
                if not allowed:
                    continue
                await connection.websocket.send_text(payload)
            except Exception:
                stale.append(connection.websocket)

        if stale:
            async with self._lock:
                for websocket in stale:
                    self._connections.pop(websocket, None)


pms_realtime_manager = PMSRealtimeManager()


async def broadcast_pms_event(event: dict[str, Any]) -> None:
    event.setdefault("createdAt", datetime.utcnow().isoformat())
    from app.core.config import settings
    if settings.REALTIME_TRANSPORT == "database":
        from app.db.session import SessionLocal
        from .event_feed import append_event
        from starlette.concurrency import run_in_threadpool
        def persist():
            with SessionLocal() as db:
                append_event(db, event)
        await run_in_threadpool(persist)
    await pms_realtime_manager.broadcast(event)


def broadcast_pms_event_from_thread(event: dict[str, Any]) -> None:
    """Best-effort bridge from FastAPI sync endpoints to the async WebSocket hub."""
    try:
        import anyio

        anyio.from_thread.run(broadcast_pms_event, event)
    except Exception:
        # Realtime is an enhancement; persistence must not fail because a socket send failed.
        return
