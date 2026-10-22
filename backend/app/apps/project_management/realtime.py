"""In-memory realtime hub for PMS collaboration events."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
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


class PMSRealtimeManager:
    def __init__(self) -> None:
        self._connections: dict[WebSocket, PMSRealtimeConnection] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        *,
        user_id: int,
        organization_id: int | None,
        accessible_project_ids: set[int],
    ) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[websocket] = PMSRealtimeConnection(
                websocket=websocket,
                user_id=user_id,
                organization_id=organization_id,
                accessible_project_ids=accessible_project_ids,
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

    async def broadcast(self, event: dict[str, Any]) -> None:
        payload = json.dumps(event, default=str)
        project_id = event.get("projectId")
        task_id = event.get("taskId")
        organization_id = event.get("organizationId")
        async with self._lock:
            connections = list(self._connections.values())

        stale: list[WebSocket] = []
        for connection in connections:
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
            try:
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
