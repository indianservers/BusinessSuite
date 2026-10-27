"""Shared connection/message budgets and bounded websocket input."""

import asyncio
import json
from starlette.requests import HTTPConnection
from starlette.concurrency import run_in_threadpool
from app.core.security import verify_access_token
from app.core.middleware.audit import client_addresses
from app.core.request_limits import enabled, factory, consume, acquire, release


class WebSocketBoundaryMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        connection = HTTPConnection(scope)
        token = connection.query_params.get("token", "")
        claims = verify_access_token(token) if len(token) <= 4096 else None
        if not claims:
            return await send({"type": "websocket.close", "code": 1008})
        user = claims.get("sub")
        ip = client_addresses(connection)[0] or "unknown"
        leases = []
        if enabled(connection):

            def reserve():
                with factory(connection)() as db:
                    db.info["security_store_timeout"] = True
                    retry = consume(
                        db,
                        [(f"socket-ip:{ip}", 30, 60), (f"socket-user:{user}", 15, 60)],
                    )
                    if not retry:
                        for key, maximum in [
                            (f"socket-work-ip:{ip}", 20),
                            (f"socket-work-user:{user}", 5),
                        ]:
                            lease = acquire(db, key, maximum, 610)
                            if lease is None:
                                retry = 5
                                break
                            leases.append(lease)
                    db.commit()
                    return retry

            try:
                retry = await run_in_threadpool(reserve)
            except Exception:
                retry = 5
            if retry:
                await run_in_threadpool(release, connection, leases)
                return await send({"type": "websocket.close", "code": 1013})
        closed = False
        deadline = asyncio.get_running_loop().time() + 600

        async def guarded_send(message):
            nonlocal closed
            if not closed:
                if message["type"] == "websocket.close":
                    closed = True
                await send(message)

        async def guarded_receive():
            remaining = deadline - asyncio.get_running_loop().time()
            try:
                message = await asyncio.wait_for(receive(), max(0.001, remaining))
            except TimeoutError:
                await guarded_send({"type": "websocket.close", "code": 1001})
                return {"type": "websocket.disconnect", "code": 1001}
            if message["type"] == "websocket.receive":
                from app.core.middleware.request_boundary import (
                    validate_json,
                    InvalidEnvelope,
                )

                raw = message.get("bytes") or message.get("text", "").encode()
                if len(raw) > 65536:
                    await guarded_send({"type": "websocket.close", "code": 1009})
                    return {"type": "websocket.disconnect", "code": 1009}
                try:
                    validate_json(json.loads(raw))
                except (ValueError, TypeError, InvalidEnvelope):
                    await guarded_send({"type": "websocket.close", "code": 1008})
                    return {"type": "websocket.disconnect", "code": 1008}
                if enabled(connection):

                    def message_budget():
                        with factory(connection)() as db:
                            db.info["security_store_timeout"] = True
                            retry = consume(db, [(f"socket-messages:{user}", 120, 60)])
                            db.commit()
                            return retry

                    try:
                        retry = await run_in_threadpool(message_budget)
                    except Exception:
                        retry = 5
                    if retry:
                        await guarded_send({"type": "websocket.close", "code": 1013})
                        return {"type": "websocket.disconnect", "code": 1013}
            return message

        try:
            await self.app(scope, guarded_receive, guarded_send)
        finally:
            await run_in_threadpool(release, connection, leases)
