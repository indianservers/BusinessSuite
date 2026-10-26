"""Durable orchestration using existing automation definitions/jobs and approvals.

Native mutations use the canonical API allowlist. Unknown write outcomes require
reconciliation; they are never blindly retried.
"""

import copy
import hmac
import uuid
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import event, inspect, or_
from sqlalchemy.orm import Session
from app.apps.automation.models import (
    AutomationWorkflow,
    AutomationScheduledJob,
    AutomationExecutionLog,
)
from app.models.approval_os import ApprovalRequest, ApprovalHistory
from app.models.user import User
from app.shared.models import ServiceEvent, WorkflowVersion
from app.shared.contracts import authorize, service_identity
from app.shared.gateway import digest, read_record, invoke_tool, business_snapshot
from app.shared.communications import notify
from app.shared.settings import effective

DEPTH = ContextVar("shared_event_depth", default=0)
NODES = {
    "start",
    "trigger",
    "condition",
    "approval",
    "assignment",
    "notification",
    "update_record",
    "create_record",
    "delay",
    "wait_event",
    "parallel",
    "merge",
    "escalation",
    "webhook",
    "end",
}


def now():
    return datetime.now(timezone.utc)


def validate_condition(rule, depth=0):
    from app.apps.automation.services.engine import validate_condition_schema

    if depth > 8 or not isinstance(rule, dict):
        raise HTTPException(422, "Invalid condition group")
    if "all" in rule or "any" in rule:
        key = "all" if "all" in rule else "any"
        if (
            set(rule) != {key}
            or not isinstance(rule[key], list)
            or not 1 <= len(rule[key]) <= 30
        ):
            raise HTTPException(422, "Invalid AND/OR condition group")
        for child in rule[key]:
            validate_condition(child, depth + 1)
        return
    if not isinstance(rule.get("field"), str) or not 1 <= len(rule["field"]) <= 160:
        raise HTTPException(422, "Condition requires a bounded field path")
    if not isinstance(rule.get("operator", "equals"), str):
        raise HTTPException(422, "Condition operator must be text")
    if rule.get("operator") in ("date_before", "date_after"):
        try:
            datetime.fromisoformat(rule["value"])
        except (ValueError, TypeError, KeyError):
            raise HTTPException(422, "Date condition requires an ISO date") from None
    else:
        validate_condition_schema(rule)


def condition(rule, values, depth=0):
    from app.apps.automation.services.engine import evaluate_condition

    if depth > 8 or not isinstance(rule, dict):
        raise HTTPException(422, "Invalid condition nesting")
    if "all" in rule or "any" in rule:
        key = "all" if "all" in rule else "any"
        children = rule[key]
        if not isinstance(children, list) or len(children) > 30:
            raise HTTPException(422, "Condition group exceeds limits")
        results = [condition(child, values, depth + 1) for child in children]
        return all(results) if key == "all" else any(results)
    if rule.get("operator") in ("date_before", "date_after"):
        from app.apps.automation.services.engine import _value_for

        actual = _value_for(values, rule["field"])
        if not actual:
            return False
        try:
            left = datetime.fromisoformat(str(actual))
            right = datetime.fromisoformat(rule["value"])
            left = (
                left.replace(tzinfo=timezone.utc)
                if left.tzinfo is None
                else left.astimezone(timezone.utc)
            )
            right = (
                right.replace(tzinfo=timezone.utc)
                if right.tzinfo is None
                else right.astimezone(timezone.utc)
            )
            return left < right if rule["operator"] == "date_before" else left > right
        except (ValueError, TypeError):
            raise HTTPException(422, "Record date cannot be compared") from None
    try:
        return evaluate_condition(rule, values)
    except (ValueError, TypeError, OverflowError):
        raise HTTPException(422, "Condition values are incompatible") from None


def mapped_payload(value, record, depth=0):
    if depth > 8:
        raise HTTPException(422, "Record mapping is too deeply nested")
    if isinstance(value, dict) and set(value) == {"$record"}:
        current = record
        path = value["$record"]
        if (
            not isinstance(path, str)
            or len(path) > 160
            or any(part.startswith("_") for part in path.split("."))
        ):
            raise HTTPException(422, "Invalid record mapping")
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                raise HTTPException(422, "Mapped source field is unavailable")
            current = current[part]
        return current
    if isinstance(value, dict):
        return {
            key: mapped_payload(item, record, depth + 1) for key, item in value.items()
        }
    if isinstance(value, list):
        if len(value) > 100:
            raise HTTPException(422, "Mapping list exceeds limits")
        return [mapped_payload(item, record, depth + 1) for item in value]
    return value


def validate_graph(graph):
    if not isinstance(graph, dict) or set(graph) - {"nodes", "edges"}:
        raise HTTPException(422, "Graph requires nodes and edges")
    nodes, edges = graph.get("nodes", []), graph.get("edges", [])
    if (
        not isinstance(nodes, list)
        or not isinstance(edges, list)
        or not 2 <= len(nodes) <= 60
        or len(edges) > 150
    ):
        raise HTTPException(422, "Graph exceeds bounded execution limits")
    if any(not isinstance(n, dict) or not isinstance(n.get("id"), str) for n in nodes):
        raise HTTPException(422, "Nodes require string identifiers")
    ids = {n.get("id") for n in nodes if isinstance(n, dict)}
    if len(ids) != len(nodes) or any(
        not isinstance(i, str) or not 1 <= len(i) <= 60 for i in ids
    ):
        raise HTTPException(422, "Use unique node identifiers")
    if sum(n.get("type") == "start" for n in nodes) != 1 or not any(
        n.get("type") == "end" for n in nodes
    ):
        raise HTTPException(422, "One start and at least one end are required")
    for node in nodes:
        if (
            not isinstance(node.get("type"), str)
            or node.get("type") not in NODES
            or not isinstance(node.get("config", {}), dict)
        ):
            raise HTTPException(422, "Unsupported workflow node")
        if set(node) - {"id", "type", "config", "x", "y"}:
            raise HTTPException(422, "Unsupported node properties")
        config = node.get("config", {})
        if node["type"] == "condition":
            validate_condition(config.get("condition"))
        import math

        if any(
            type(node.get(key, 0)) not in {int, float}
            or not math.isfinite(node.get(key, 0))
            or abs(node.get(key, 0)) > 10000
            for key in ("x", "y")
        ):
            raise HTTPException(422, "Invalid canvas coordinates")
        if any(
            k in config
            for k in (
                "sql",
                "code",
                "url",
                "target_url",
                "headers",
                "authorization",
                "secret",
                "password",
                "api_key",
                "token",
            )
        ):
            raise HTTPException(
                422, "Use registered actions/connections, not arbitrary execution"
            )
        if node["type"] in {"create_record", "update_record", "assignment"}:
            from app.ai_operator.suite_tools import TOOLS

            if config.get("tool") not in TOOLS:
                raise HTTPException(422, "Select a registered action tool")
        if node["type"] == "delay" and (
            type(config.get("seconds")) is not int
            or not 1 <= config["seconds"] <= 2592000
        ):
            raise HTTPException(422, "Delay must be between one second and 30 days")
        if node["type"] == "wait_event" and not config.get("event"):
            raise HTTPException(422, "Select an event to wait for")
        if node["type"] == "approval" and (
            config.get("mode", "all") not in {"all", "any", "sequential"}
            or (
                config.get("resolver")
                not in {"reporting_manager", "department_head", "module_role"}
                and (
                    not isinstance(config.get("approvers"), list)
                    or not 1 <= len(config["approvers"]) <= 20
                    or any(
                        type(identifier) is not int or identifier < 1
                        for identifier in config["approvers"]
                    )
                )
            )
        ):
            raise HTTPException(422, "Configure approval mode and approvers")
        if node["type"] in {"notification", "escalation"} and (
            type(config.get("recipientId")) is not int
            or config["recipientId"] < 1
            or not isinstance(config.get("title"), str)
            or not 1 <= len(config["title"]) <= 200
        ):
            raise HTTPException(
                422,
                "Notification requires an authorized recipient ID and bounded title",
            )
        if node["type"] == "webhook" and (
            type(config.get("connectionId")) is not int
            or config["connectionId"] < 1
            or not isinstance(config.get("operation"), str)
        ):
            raise HTTPException(422, "Select a registered connection and operation")
    adjacency = {i: [] for i in ids}
    for edge in edges:
        if (
            not isinstance(edge, dict)
            or set(edge) - {"source", "target", "when"}
            or not isinstance(edge.get("source"), str)
            or not isinstance(edge.get("target"), str)
            or edge.get("source") not in ids
            or edge.get("target") not in ids
            or edge.get("when") not in (None, "true", "false")
        ):
            raise HTTPException(422, "Invalid connection")
        adjacency[edge["source"]].append(edge["target"])
    visiting, visited = set(), set()

    def walk(key):
        if key in visiting:
            raise HTTPException(
                422, "Cycles must use bounded wait/delay executions, not graph loops"
            )
        if key in visited:
            return
        visiting.add(key)
        for target in adjacency[key]:
            walk(target)
        visiting.remove(key)
        visited.add(key)

    start = next(n["id"] for n in nodes if n["type"] == "start")
    walk(start)
    if visited != ids:
        raise HTTPException(422, "Connect every node to the start")
    for node in nodes:
        if node["type"] == "end" and adjacency[node["id"]]:
            raise HTTPException(422, "End nodes cannot have outgoing connections")
        if node["type"] != "end" and not adjacency[node["id"]]:
            raise HTTPException(422, "Every path must reach an end")
    return graph


def resolve_approvers(db, source, config):
    resolver = config.get("resolver")
    if not resolver:
        return config.get("approvers", [])
    if resolver == "module_role":
        from app.access.api import users_in_company
        from app.access.service import policy_for, resolved_grants

        role = config.get("role")
        if not isinstance(role, str) or not role:
            raise HTTPException(422, "Select the effective module role")
        candidates = []
        for user in users_in_company(db, source.organization_id):
            policy = policy_for(db, user, source.organization_id)
            grant = (
                resolved_grants(db, policy).get(source.module_key, {}) if policy else {}
            )
            if (
                user.id != source.actor_id
                and user.is_active
                and policy
                and policy.status == "active"
                and grant.get("enabled")
                and grant.get("role") == role
            ):
                candidates.append(user.id)
        if not candidates or len(candidates) > 20:
            raise HTTPException(
                422, "Module role must resolve to 1–20 independent approvers"
            )
        return candidates
    from sqlalchemy import select, func
    from app.models.employee import Employee
    from app.models.company import Branch, Department

    employees, branches, departments = (
        Employee.__table__,
        Branch.__table__,
        Department.__table__,
    )
    person = (
        db.connection()
        .execute(
            select(employees.c.reporting_manager_id, employees.c.department_id)
            .select_from(
                employees.outerjoin(branches, branches.c.id == employees.c.branch_id)
            )
            .where(
                employees.c.user_id == source.actor_id,
                func.coalesce(branches.c.company_id, 1) == source.organization_id,
            )
        )
        .first()
    )
    if not person:
        raise HTTPException(422, "Requester has no employee identity in this company")
    employee_id = (
        person.reporting_manager_id
        if resolver == "reporting_manager"
        else db.connection()
        .execute(
            select(departments.c.head_employee_id).where(
                departments.c.id == person.department_id
            )
        )
        .scalar()
    )
    identifier = (
        db.connection()
        .execute(select(employees.c.user_id).where(employees.c.id == employee_id))
        .scalar()
    )
    if not identifier or identifier == source.actor_id:
        raise HTTPException(422, "No independent approver is configured")
    return [identifier]


def emit(db, actor, company, module, event_type, entity, entity_id, request_key, data):
    authorize(db, actor, company, module)
    if (
        not isinstance(request_key, str)
        or not 8 <= len(request_key) <= 180
        or not isinstance(event_type, str)
        or not 1 <= len(event_type) <= 120
    ):
        raise HTTPException(422, "Bounded event name and idempotency key required")
    if (
        type(entity_id) is not int
        or entity_id < 1
        or not isinstance(data, dict)
        or len(str(data)) > 16000
    ):
        raise HTTPException(422, "Invalid event reference or payload")
    row = (
        db.query(ServiceEvent)
        .filter_by(organization_id=company, request_key=request_key)
        .first()
    )
    if row:
        if (
            row.module_key,
            row.event_type,
            row.entity_type,
            row.entity_id,
            row.payload_json.get("data"),
        ) != (module, event_type, entity, entity_id, data):
            raise HTTPException(409, "Idempotency key was used for a different event")
        return row
    row = ServiceEvent(
        organization_id=company,
        module_key=module,
        event_type=event_type,
        entity_type=entity,
        entity_id=entity_id,
        actor_id=actor.id,
        request_key=request_key,
        payload_json={"data": data, "depth": DEPTH.get()},
        status="depth_limited" if DEPTH.get() >= 6 else "pending",
    )
    db.add(row)
    db.flush()
    return row


def request_approval(
    db,
    actor,
    company,
    module,
    entity,
    entity_id,
    approvers,
    title,
    key,
    mode="all",
    requester_id=None,
):
    authorize(db, actor, company, module)
    if (
        mode not in {"all", "any", "sequential"}
        or not isinstance(approvers, list)
        or not 1 <= len(approvers) <= 20
        or len(set(approvers)) != len(approvers)
    ):
        raise HTTPException(
            422, "Choose distinct bounded approvers and a supported mode"
        )
    if actor.id in approvers or requester_id in approvers:
        raise HTTPException(403, "Segregation of duties forbids self approval")
    snapshot = business_snapshot(
        read_record(db, actor, company, module, entity, entity_id)
    )
    existing = (
        db.query(ServiceEvent)
        .filter_by(organization_id=company, request_key=key)
        .first()
    )
    if existing:
        if (
            (
                existing.event_type,
                existing.module_key,
                existing.entity_type,
                existing.entity_id,
                existing.actor_id,
            )
            != (
                "approval.requested",
                module,
                entity,
                entity_id,
                requester_id or actor.id,
            )
            or existing.payload_json.get("approvers") != approvers
            or existing.payload_json.get("mode") != mode
        ):
            raise HTTPException(
                409, "Approval idempotency key refers to a different request"
            )
        return existing
    for identifier in approvers:
        person = db.get(User, identifier)
        read_record(db, person, company, module, entity, entity_id)
    record = ServiceEvent(
        organization_id=company,
        module_key=module,
        event_type="approval.requested",
        entity_type=entity,
        entity_id=entity_id,
        actor_id=requester_id or actor.id,
        request_key=key,
        status="approval_pending",
        payload_json={
            "snapshot": snapshot,
            "hash": digest(snapshot),
            "mode": mode,
            "approvers": approvers,
            "decisions": {},
            "executionActor": actor.id,
        },
    )
    db.add(record)
    db.flush()
    requests = []
    for index, identifier in enumerate(approvers):
        row = ApprovalRequest(
            organization_id=company,
            source_module=module,
            approval_type="shared.workflow",
            entity_type=entity,
            entity_id=entity_id,
            title=str(title)[:220],
            requester_user_id=record.actor_id,
            assigned_to_user_id=identifier,
            status="Pending" if mode != "sequential" or index == 0 else "Waiting",
            context_json={"_shared": record.id, "snapshotHash": digest(snapshot)},
        )
        db.add(row)
        db.flush()
        requests.append(row.id)
    record.payload_json = {**record.payload_json, "requests": requests}
    return record


def decide_approval(db, actor, approval_id, decision, reason):
    row = db.query(ApprovalRequest).filter_by(id=approval_id).first()
    if not row or not (row.context_json or {}).get("_shared"):
        raise HTTPException(404, "Shared approval not found")
    source_id = row.context_json["_shared"]
    source = (
        db.query(ServiceEvent)
        .filter_by(id=source_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if source is None:
        raise HTTPException(404, "Shared approval group not found")
    row = (
        db.query(ApprovalRequest)
        .filter_by(id=approval_id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    if (row.context_json or {}).get("_shared") != source_id:
        raise HTTPException(409, "Approval group changed")
    authorize(db, actor, source.organization_id, source.module_key, "approve")
    if (
        row.delegated_to_user_id or row.assigned_to_user_id
    ) != actor.id or row.requester_user_id == actor.id:
        raise HTTPException(403, "Only the assigned independent approver can decide")
    if row.status != "Pending" or source.status != "approval_pending":
        raise HTTPException(409, "Approval is no longer pending")
    data = copy.deepcopy(source.payload_json)
    if (
        row.id not in data.get("requests", [])
        or row.requester_user_id != source.actor_id
        or (row.source_module, row.entity_type, row.entity_id)
        != (source.module_key, source.entity_type, source.entity_id)
        or row.assigned_to_user_id not in data.get("approvers", [])
    ):
        raise HTTPException(
            409, "Approval is not a member of the immutable request group"
        )
    if actor.id in data.get("decisionActors", []):
        raise HTTPException(
            403, "Independent approvals require distinct deciding users"
        )
    if (
        row.context_json.get("snapshotHash") != data["hash"]
        or digest(data["snapshot"]) != data["hash"]
    ):
        raise HTTPException(409, "Approval snapshot was tampered with")
    execution_actor = db.get(User, data["executionActor"])
    current = business_snapshot(
        read_record(
            db,
            execution_actor,
            source.organization_id,
            source.module_key,
            source.entity_type,
            source.entity_id,
        )
    )
    if digest(current) != data["hash"]:
        raise HTTPException(409, "Business record changed; resubmit for approval")
    if decision not in {"approve", "reject"}:
        raise HTTPException(422, "Unsupported decision")
    row.status = "Approved" if decision == "approve" else "Rejected"
    row.decided_by, row.decided_at, row.decision_reason = actor.id, now(), reason
    data["decisions"][str(row.assigned_to_user_id)] = decision
    data.setdefault("decisionActors", []).append(actor.id)
    db.add(
        ApprovalHistory(
            request_id=row.id,
            event_type="shared." + decision,
            actor_user_id=actor.id,
            before_status="Pending",
            after_status=row.status,
            reason=reason,
        )
    )
    if decision == "reject":
        source.status = "rejected"
    elif data["mode"] == "any" or len(data["decisions"]) == len(data["approvers"]):
        source.status = "approved"
    if data["mode"] == "sequential" and source.status == "approval_pending":
        next_index = len(data["decisions"])
        db.get(ApprovalRequest, data["requests"][next_index]).status = "Pending"
    if source.status != "approval_pending":
        for request_id in data["requests"]:
            sibling = db.get(ApprovalRequest, request_id)
            if sibling.status in {"Pending", "Waiting"}:
                sibling.status = "Cancelled"
    source.payload_json = data
    return row


def dispatch_events(db, limit=20):
    events = (
        db.query(ServiceEvent)
        .filter_by(status="pending")
        .order_by(ServiceEvent.id)
        .with_for_update(skip_locked=True)
        .limit(limit)
        .all()
    )
    for source in events:
        definitions = (
            db.query(AutomationWorkflow)
            .filter_by(
                organization_id=source.organization_id,
                module_name=source.module_key,
                record_type=source.entity_type,
                trigger_type=source.event_type,
                is_active=True,
            )
            .all()
        )
        quota_blocked = False
        for workflow in definitions:
            from app.enterprise.controls import quota

            db.flush()
            try:
                quota(db, source.organization_id, "automation_runs")
            except HTTPException as exc:
                if exc.status_code != 429:
                    raise
                quota_blocked = True
                break
            if not workflow.published_version:
                continue
            version = (
                db.query(WorkflowVersion)
                .filter_by(
                    workflow_id=workflow.id,
                    version=workflow.published_version,
                    organization_id=source.organization_id,
                )
                .one()
            )
            payload = {
                "versionId": version.id,
                "eventId": source.id,
                "actorId": version.run_as_user_id,
                "frontier": [
                    next(
                        n["id"]
                        for n in version.graph_json["nodes"]
                        if n["type"] == "start"
                    )
                ],
                "done": [],
                "results": {},
                "steps": 0,
                "depth": source.payload_json.get("depth", 0),
            }
            db.add(
                AutomationScheduledJob(
                    organization_id=source.organization_id,
                    job_type="shared_workflow",
                    module_name=source.module_key,
                    record_type=source.entity_type,
                    record_id=source.entity_id,
                    status="scheduled",
                    run_at=now(),
                    payload_json=payload,
                    created_by=source.actor_id,
                )
            )
        source.status = "quota_blocked" if quota_blocked else "dispatched"
    db.commit()
    return len(events)


def run_job(db, job):
    if job.created_at and job.created_at.replace(
        tzinfo=timezone.utc
    ) < now() - timedelta(days=30):
        raise HTTPException(409, "Execution exceeded the maximum 30-day lifetime")
    state = copy.deepcopy(job.payload_json)
    version = db.get(WorkflowVersion, state["versionId"])
    source = db.get(ServiceEvent, state["eventId"])
    actor = db.get(User, state["actorId"])
    if version and state["actorId"] != version.run_as_user_id:
        raise HTTPException(
            409, "Execution identity differs from the published version"
        )
    if (
        not version
        or not source
        or version.organization_id != job.organization_id
        or source.organization_id != job.organization_id
        or digest(version.graph_json) != version.digest
    ):
        raise HTTPException(409, "Invalid published execution reference")
    service_identity(db, actor, job.organization_id, job.module_name)
    ai_origin = (source.payload_json or {}).get("ai_origin")
    if ai_origin:
        from app.ai_agents.security import verify

        if actor.id != source.actor_id:
            raise HTTPException(
                403,
                "AI-originated events cannot execute under another service identity",
            )
        previous = getattr(actor, "organization_id", None)
        actor.organization_id = job.organization_id
        try:
            verify(db, actor, ai_origin)
        finally:
            if previous is None:
                actor.__dict__.pop("organization_id", None)
            else:
                actor.organization_id = previous
    policy = effective(db, job.organization_id, job.module_name)["values"]
    graph = version.graph_json
    nodes = {n["id"]: n for n in graph["nodes"]}

    def reaches(source_key, target_key, seen=None):
        seen = set() if seen is None else seen
        if source_key in seen:
            return False
        seen.add(source_key)
        return any(
            edge["target"] == target_key or reaches(edge["target"], target_key, seen)
            for edge in graph["edges"]
            if edge["source"] == source_key
        )

    node_id = next(
        (
            key
            for key in state["frontier"]
            if key not in state["done"]
            and (
                nodes[key]["type"] != "merge"
                or not any(
                    other != key and reaches(other, key) for other in state["frontier"]
                )
            )
        ),
        None,
    )
    if node_id is None:
        job.status = "completed"
        return
    node = nodes[node_id]
    config, kind = node.get("config", {}), node["type"]
    if ai_origin:
        if kind == "webhook" or "email" in config.get("channels", []):
            raise HTTPException(
                403,
                "AI workflow external communications require a separately confirmed approved tool",
            )
        if kind in {"action", "create_record", "update_record", "assignment", "assign_record"}:
            raise HTTPException(403, "AI-triggered workflow mutations need a separate exact user confirmation")
    if state["steps"] >= policy["workflow_max_steps"]:
        raise HTTPException(409, "Workflow execution budget exceeded")
    token = DEPTH.set(state.get("depth", 0) + 1)
    try:
        result = {}
        if kind == "condition":
            result["matched"] = condition(
                config.get("condition", {}),
                read_record(
                    db,
                    actor,
                    job.organization_id,
                    job.module_name,
                    job.record_type,
                    job.record_id,
                ),
            )
        elif kind == "delay" and node_id not in state.get("waiting", []):
            state.setdefault("waiting", []).append(node_id)
            job.status, job.run_at, job.payload_json = (
                "scheduled",
                now() + timedelta(seconds=config["seconds"]),
                state,
            )
            return
        elif kind == "wait_event":
            received = (
                db.query(ServiceEvent)
                .filter(
                    ServiceEvent.organization_id == job.organization_id,
                    ServiceEvent.module_key == job.module_name,
                    ServiceEvent.entity_type == job.record_type,
                    ServiceEvent.entity_id == job.record_id,
                    ServiceEvent.event_type == config["event"],
                    ServiceEvent.id > source.id,
                )
                .first()
            )
            if not received:
                job.status, job.run_at = "scheduled", now() + timedelta(seconds=30)
                return
        elif kind == "approval":
            event_id = state["results"].get(node_id, {}).get("approvalEventId")
            if not event_id:
                approval = request_approval(
                    db,
                    actor,
                    job.organization_id,
                    job.module_name,
                    job.record_type,
                    job.record_id,
                    resolve_approvers(db, source, config),
                    config.get("title", "Workflow approval"),
                    f"job:{job.id}:node:{node_id}",
                    config.get("mode", "all"),
                    source.actor_id,
                )
                state["results"][node_id] = {"approvalEventId": approval.id}
                job.payload_json, job.status, job.run_at = (
                    state,
                    "scheduled",
                    now() + timedelta(seconds=30),
                )
                return
            approval = db.get(ServiceEvent, event_id)
            if approval.status == "approval_pending":
                job.status, job.run_at = "scheduled", now() + timedelta(seconds=30)
                return
            if approval.status != "approved":
                raise HTTPException(409, "Workflow approval was rejected or cancelled")
        elif kind in {"notification", "escalation"}:
            result = {
                "notificationId": notify(
                    db,
                    actor,
                    job.organization_id,
                    job.module_name,
                    job.record_type,
                    job.record_id,
                    int(config["recipientId"]),
                    config["title"],
                    config.get("message", "Workflow notification"),
                    config.get("channels"),
                    kind == "escalation",
                ).id
            }
        elif kind in {"create_record", "update_record", "assignment", "webhook"}:
            source_record = read_record(
                db,
                actor,
                job.organization_id,
                job.module_name,
                job.record_type,
                job.record_id,
            )
            if kind != "webhook" and config.get("tool") not in {
                "crm.create_task",
                "crm.update_task",
                "pms.create_task",
            }:
                approvals = [
                    state["results"].get(key, {}).get("approvalEventId")
                    for key in state["done"]
                    if nodes[key]["type"] == "approval"
                ]
                approved = [db.get(ServiceEvent, key) for key in approvals if key]
                if not any(
                    a
                    and a.status == "approved"
                    and a.payload_json["hash"]
                    == digest(business_snapshot(source_record))
                    for a in approved
                ):
                    raise HTTPException(
                        403,
                        "This action requires an independent approval of the current record snapshot",
                    )
            payload = mapped_payload(config.get("payload", {}), source_record)
            # Persist the uncertainty boundary before invoking independently committing APIs.
            job.status = "reconciliation_required"
            job.payload_json = {**state, "uncertainNode": node_id}
            db.commit()
            if kind == "webhook":
                from app.shared.integrations import invoke

                result = invoke(
                    db,
                    actor,
                    job.organization_id,
                    job.module_name,
                    config["connectionId"],
                    config["operation"],
                    payload,
                )
            else:
                result = invoke_tool(
                    db,
                    actor,
                    job.organization_id,
                    config["tool"],
                    payload,
                    config.get("recordId", job.record_id),
                )
        state["steps"] += 1
        state["done"].append(node_id)
        state["results"][node_id] = {
            **state["results"].get(node_id, {}),
            "status": "completed",
            **({"matched": result["matched"]} if "matched" in result else {}),
        }
        state["frontier"] = [key for key in state["frontier"] if key != node_id]
        for edge in graph["edges"]:
            if edge["source"] == node_id and (
                kind != "condition"
                or edge.get("when") in {None, str(result["matched"]).lower()}
            ):
                if (
                    edge["target"] not in state["done"]
                    and edge["target"] not in state["frontier"]
                ):
                    state["frontier"].append(edge["target"])
        # Merge waits for every *active* parallel predecessor, not skipped condition paths.
        state.pop("uncertainNode", None)
        job.payload_json, job.status, job.run_at = (
            state,
            "scheduled" if state["frontier"] else "completed",
            now(),
        )
        db.add(
            AutomationExecutionLog(
                organization_id=job.organization_id,
                workflow_id=version.workflow_id,
                module_name=job.module_name,
                record_type=job.record_type,
                record_id=job.record_id,
                trigger_type=source.event_type,
                status="success",
                created_by=actor.id,
                result_json={
                    "jobId": job.id,
                    "node": node_id,
                    "version": version.version,
                    "result": state["results"][node_id],
                },
            )
        )
        from app.access.service import audit

        audit(
            db,
            actor,
            job.organization_id,
            "shared.execution.step",
            "Authorized shared workflow stage",
            after={
                "jobId": job.id,
                "module": job.module_name,
                "node": node_id,
                "status": job.status,
            },
        )
    finally:
        DEPTH.reset(token)


def process_batch(db, limit=20):
    if not inspect(db.connection()).has_table("suite_service_events"):
        return {"status": "migration_required", "processed": 0}
    dispatched = dispatch_events(db, limit)
    processed = 0
    for _ in range(limit):
        job = (
            db.query(AutomationScheduledJob)
            .filter(
                AutomationScheduledJob.job_type == "shared_workflow",
                AutomationScheduledJob.status == "scheduled",
                or_(
                    AutomationScheduledJob.run_at <= now(),
                    AutomationScheduledJob.run_at.is_(None),
                ),
            )
            .order_by(AutomationScheduledJob.id)
            .with_for_update(skip_locked=True)
            .first()
        )
        if not job:
            break
        version = db.get(WorkflowVersion, job.payload_json.get("versionId"))
        frontier = job.payload_json.get("frontier", [])
        external = bool(
            version
            and any(
                n["id"] in frontier
                and n["type"]
                in {"create_record", "update_record", "assignment", "webhook"}
                for n in version.graph_json["nodes"]
            )
        )
        transaction = None if external else db.begin_nested()
        try:
            run_job(db, job)
            if transaction:
                transaction.commit()
            job.last_error = None
        except Exception as error:
            if transaction and transaction.is_active:
                transaction.rollback()
            elif not isinstance(error, HTTPException):
                db.rollback()
            db.expire(job)
            job.attempts += 1
            code = error.status_code if isinstance(error, HTTPException) else 500
            job.last_error = (
                str(error.detail)[:500]
                if isinstance(error, HTTPException)
                else "Internal execution failure; inspect server correlation logs"
            )
            if job.status != "reconciliation_required":
                job.status = (
                    "dead_letter"
                    if code in {401, 403, 404, 409, 422}
                    or job.attempts
                    >= effective(db, job.organization_id, job.module_name)["values"][
                        "workflow_retries"
                    ]
                    else "scheduled"
                )
                job.run_at = now() + timedelta(seconds=30 * (2**job.attempts))
        db.commit()
        processed += 1
    from app.shared.communications import drain_email

    return {
        "dispatched": dispatched,
        "processed": processed,
        "emailProcessed": drain_email(db, min(limit, 10)),
    }


CAPTURE = {
    "CRMLead": ("crm", "lead"),
    "PMSTask": ("project_management", "task"),
    "PMSProject": ("project_management", "project"),
    "LeaveRequest": ("hrms", "leave"),
    "ExpenseClaim": ("hrms", "expense"),
    "SRMInvoice": ("srm", "invoice"),
}


@event.listens_for(Session, "after_flush")
def capture_changes(db, context):
    actor = db.info.get("shared_actor")
    if not actor or db.info.get("shared_capture_disabled"):
        return
    if "shared_schema_ready" not in db.info:
        db.info["shared_schema_ready"] = inspect(db.connection()).has_table(
            "suite_service_events"
        )
    if not db.info["shared_schema_ready"]:
        return
    for item in list(db.new | db.dirty):
        binding = CAPTURE.get(type(item).__name__)
        if not binding or not getattr(item, "id", None):
            continue
        module, entity = binding
        if item in db.new:
            event_type = "record.created"
        elif db.is_modified(item, include_collections=False):
            event_type = (
                "status.changed"
                if hasattr(item, "status")
                and inspect(item).attrs.status.history.has_changes()
                else "record.updated"
            )
        else:
            continue
        company = getattr(item, "organization_id", None) or actor[1]
        if company != actor[1]:
            continue
        ai_context = db.info.get("ai_request_context") or {}
        ai_origin = None
        if ai_context.get("is_ai"):
            from app.ai_agents.security import seal

            ai_origin = seal(db, db.get(User, actor[0]), tenant=company)
        db.add(
            ServiceEvent(
                organization_id=company,
                module_key=module,
                event_type=event_type,
                entity_type=entity,
                entity_id=item.id,
                actor_id=actor[0],
                request_key=str(uuid.uuid4()),
                payload_json={
                    "depth": DEPTH.get(),
                    "data": {},
                    **({"ai_origin": ai_origin} if ai_origin else {}),
                },
                status="depth_limited" if DEPTH.get() >= 6 else "pending",
            )
        )
