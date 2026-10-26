import ipaddress
import json
import logging
import os
import re
import time
import traceback
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import Request
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.audit_context import context

logger = logging.getLogger('businesssuite.audit')


def client_addresses(request):
    def valid(value):
        try:
            return str(ipaddress.ip_address(value.strip()))
        except (ValueError, AttributeError):
            return None
    peer = valid(request.client.host if request.client else None)
    hops = [valid(value) for value in request.headers.get('x-forwarded-for', '').split(',')[-20:]]
    hops = [value for value in hops if value]
    claimed = hops[0] if hops else None
    networks = []
    for cidr in os.getenv('AUDIT_TRUSTED_PROXY_CIDRS', '').split(','):
        try:
            networks.append(ipaddress.ip_network(cidr.strip()))
        except ValueError:
            continue
    trusted = lambda value: bool(value and any(ipaddress.ip_address(value) in net for net in networks))
    if trusted(peer) and hops:
        for hop in reversed(hops):
            if not trusted(hop):
                return hop, 'trusted_proxy', claimed
    return peer, 'peer', claimed


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Persist request outcomes independently of the business transaction."""
    def _should_skip(self, request):
        return request.method == 'OPTIONS' or not request.url.path.startswith('/api/') or request.url.path.endswith('/openapi.json')

    async def dispatch(self, request, call_next):
        if self._should_skip(request):
            return await call_next(request)
        started = time.perf_counter()
        value = {'task_ids': set(), 'changed_fields': set()}
        token = context.set(value)
        request.state.audit_context = value
        try:
            try:
                from app.core.security import verify_access_token
                from app.ai_agents.security import digest
                from starlette.responses import JSONResponse
                authorization=request.headers.get("authorization", "")
                claims=verify_access_token(authorization.partition(" ")[2]) if authorization.lower().startswith("bearer ") else None
                origin=(claims or {}).get("ai_origin")
                if origin:
                    value["ai_context"]={"is_ai":True,"user_id":claims.get("sub"),"company_id":origin.get("company_id"),"session_id":claims.get("sid")}
                    try:
                        raw=await request.body()
                        arguments=request.query_params.multi_items() if request.method=="GET" else json.loads(raw) if raw else None
                        valid=origin.get("arguments")==digest(arguments)
                    except (ValueError,TypeError):
                        valid=False
                    if not valid:
                        response=JSONResponse({"detail":"AI delegated arguments do not match"},status_code=403)
                    else:
                        response=await call_next(request)
                else:
                    response = await call_next(request)
            except Exception as exc:
                await self._log_request(request, 500, round((time.perf_counter() - started) * 1000), error=exc)
                raise
            await self._log_request(request, response.status_code, round((time.perf_counter() - started) * 1000))
            response.headers['X-Request-ID'] = getattr(request.state, 'request_id', '')
            return response
        finally:
            context.reset(token)

    async def _log_request(self, request, status_code, duration_ms, error=None):
        # Long-poll success traffic is excluded; failures are always retained.
        if status_code < 400 and request.url.path.endswith('/realtime/events'):
            return
        try:
            await run_in_threadpool(self._persist, request, status_code, duration_ms, error)
        except Exception as exc:
            value = getattr(request.state, 'audit_context', {})
            actor = value.get('actor', {})
            logger.error('audit_persistence_failed request_id=%s user_id=%s role=%s error_type=%s', getattr(request.state, 'request_id', None), actor.get('user_id'), actor.get('role'), type(exc).__name__)

    def _persist(self, request, status_code, duration_ms, error):
        from app.db.session import SessionLocal
        from app.models.audit import AuditLog, AuditLogTask
        from app.models.user import User
        from app.core.security import verify_access_token
        from app.apps.project_management.models import PMSTask, PMSProject
        factory = getattr(request.app.state, 'audit_session_factory', SessionLocal)
        close = getattr(request.app.state, 'audit_close_session', True)
        commit = getattr(request.app.state, 'audit_commit', True)
        db = factory()
        try:
            value = getattr(request.state, 'audit_context', {})
            actor = value.get('actor')
            if not actor:
                auth = request.headers.get('authorization', '')
                payload = verify_access_token(auth[7:]) if auth.startswith('Bearer ') else None
                subject = payload.get('sub') if payload else None
                person = db.query(User).filter_by(id=int(subject)).first() if subject and str(subject).isdigit() else None
                actor = {'user_id': person.id if person else None, 'email': person.email if person else None,
                         'role': person.role.name if person and person.role else None, 'authenticated': False}
            path = request.url.path
            # Replace sensitive dynamic path components with the registered route template.
            route = request.scope.get('route')
            endpoint = getattr(route, 'path', None) or re.sub(r'(?i)(/callback/|/reset/|/invitation/)[^/]+', r'\1[redacted]', path)
            def path_id(collection):
                match = re.search(r'/' + collection + r'/(\d+)(?:/|$)', path)
                return int(match.group(1)) if match else None
            task_id = path_id('tasks')
            task_ids = set(value.get('task_ids', set()))
            if task_id:
                task_ids.add(task_id)
            is_pms = path.startswith('/api/v1/project-management/')
            project_ids = set(value.get('project_ids', set()))
            if is_pms and path_id('projects'):
                project_ids.add(path_id('projects'))
            project_id = next(iter(project_ids)) if len(project_ids) == 1 else None
            workspace_id = path_id('workspaces') if is_pms else None
            if is_pms and task_id and not project_id and not project_ids:
                project_id = db.query(PMSTask.project_id).filter_by(id=task_id).scalar()
            if is_pms and not project_id and not project_ids and len(task_ids) == 1:
                project_id = db.query(PMSTask.project_id).filter_by(id=next(iter(task_ids))).scalar()
            if is_pms and project_ids and len(project_ids) > 1:
                workspaces = {r[0] for r in db.query(PMSProject.workspace_id).filter(PMSProject.id.in_(project_ids)).all()}
                workspace_id = next(iter(workspaces)) if len(workspaces) == 1 else None
            if is_pms and project_id and not workspace_id:
                workspace_id = db.query(PMSProject.workspace_id).filter_by(id=project_id).scalar()
            # No bodies, raw query values, cookies, auth headers or exception messages.
            safe_query = {key: val for key, val in request.query_params.multi_items()
                          if key in {'task_id', 'project_id', 'workspace_id', 'user_id', 'page', 'limit', 'skip'} and re.fullmatch(r'\d{1,10}', val)}
            request_id = getattr(request.state, 'request_id', None) or str(uuid4())
            ip, source, forwarded = client_addresses(request)
            parts = path.split('/')
            module = parts[3] if len(parts) > 3 else 'system'
            leaf = error
            while leaf and getattr(leaf, 'exceptions', None):
                leaf = leaf.exceptions[0]
            location = [{'file': Path(frame.filename).name, 'line': frame.lineno, 'function': frame.name} for frame in traceback.extract_tb(leaf.__traceback__)[-5:]] if leaf else []
            actor_id = actor.get('user_id')
            retained_actor_id = actor_id if actor_id and db.query(User.id).filter_by(id=actor_id).scalar() else None
            row = AuditLog(organization_id=getattr(request.state, "observed_company_id", None), user_id=retained_actor_id, actor_email=actor.get('email'), actor_role=actor.get('role'),
                           actor_authenticated=bool(actor.get('authenticated')), request_id=request_id[:64], module=module[:80],
                           method=request.method[:10], endpoint=endpoint[:500], ip_address=ip, ip_source=source, forwarded_ip=forwarded,
                           user_agent=request.headers.get('user-agent', '')[:500], status_code=status_code, duration_ms=duration_ms,
                           task_id=task_id or (next(iter(task_ids)) if len(task_ids) == 1 else None), project_id=project_id, workspace_id=workspace_id,
                           entity_type='task' if task_ids else 'project' if project_id else 'workspace' if workspace_id else None,
                           entity_id=task_id or (next(iter(task_ids)) if len(task_ids) == 1 else None) or project_id or workspace_id,
                           action='ERROR' if status_code >= 500 else 'REJECTED' if status_code >= 400 else request.method,
                           error_type=type(leaf).__name__[:160] if leaf else "HTTP500Response" if status_code >= 500 else None,
                           description=json.dumps({'actor_id': actor_id, 'safe_query': safe_query, 'changed_fields': sorted(value.get('changed_fields', set())),
                                                   'error_location': location, 'outcome': 'server_error' if status_code >= 500 else 'rejected' if status_code >= 400 else 'success'}),
                           created_at=datetime.now(timezone.utc))
            db.add(row)
            db.flush()
            from app.ai_agents.models import AiAuditLog
            ai_context = value.get("ai_context") or {}
            if (ai_context.get("is_ai") or path.startswith(("/api/v1/ai/", "/api/v1/ai-agents/", "/api/v1/ai-operator/"))) and not value.get("ai_events"):
                db.add(AiAuditLog(event_key=uuid4().hex, organization_id=ai_context.get("company_id") or getattr(request.state,"observed_company_id",None),
                    user_id=retained_actor_id, session_id=ai_context.get("session_id"), correlation_id=request_id[:64], module="AI",
                    action="AI_HTTP_DENIED" if status_code>=400 else "AI_HTTP_COMPLETED", status="failed" if status_code>=400 else "success",
                    input_json={}, output_json={"status":status_code}))
            for entry in value.get("ai_events",[]):
                if not db.connection().execute(AiAuditLog.__table__.select().where(AiAuditLog.__table__.c.event_key==entry["event_key"])).first():
                    db.add(AiAuditLog(**entry))
            for tid in sorted(task_ids):
                db.add(AuditLogTask(audit_log_id=row.id, task_id=tid))
            if commit:
                db.commit()
            else:
                db.flush()
        except Exception:
            if commit:
                db.rollback()
            raise
        finally:
            if close:
                db.close()
