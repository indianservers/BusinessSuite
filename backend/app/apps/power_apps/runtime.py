"""Durable transactional orchestrator for the canonical Power Apps graph.

Each queue job performs one bounded local action. Fenced claims and the run lock
commit output, events and successor jobs atomically. External actions commit
dispatch intent and release local checkpoints before bounded provider I/O.
"""

import copy
import hashlib
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import or_, func, case
from app.apps.power_apps.models import (
    PowerResource,
    PowerVersion,
    PowerExecution,
    PowerEnvironment,
)
from app.apps.power_apps.runtime_models import (
    AutomationDeployment as Deployment,
    AutomationRun as Run,
    AutomationStep as Step,
    AutomationJob as Job,
    AutomationWait as Wait,
    AutomationEvent as Event,
    AutomationDeadLetter as DeadLetter,
)
from app.apps.power_apps.graph import VisualWorkflowDefinition, VisualNode
from app.apps.power_apps.studio import topology, validate_graph, resolve
from app.apps.power_apps.authoring import bounded, map_value, redact_debug, condition
from app.apps.power_apps.node_registry import NODES, configuration_errors
from app.apps.power_apps.runtime_contracts import RuntimePolicy
from app.apps.power_apps.runtime_executors import EXECUTORS
from app.apps.power_apps.service import validate_environment, scoped

TERMINAL = {"completed", "failed", "cancelled", "skipped"}
LIVE = {"queued", "running", "waiting", "retry_scheduled"}
from app.core.config import settings

TENANT_CONCURRENCY = settings.POWER_RUNTIME_TENANT_ACTIVE
ENV_CONCURRENCY = settings.POWER_RUNTIME_ENVIRONMENT_ACTIVE
TENANT_QUEUE = settings.POWER_RUNTIME_TENANT_QUEUE
MAX_STEPS = 5000
MAX_RUN_OUTPUT_BYTES = 4 * 1024 * 1024


def now():
    return datetime.now(timezone.utc)


def utc(value):
    return (
        value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value
    )


def scope_values(row):
    return {
        k: getattr(row, k) for k in ("organization_id", "environment", "owner_user_id")
    }


def event(db, run, kind, step=None, details=None):
    root = db.get(PowerExecution, run.id)
    db.add(
        Event(
            **scope_values(run),
            run_id=run.id,
            resource_id=root.resource_id,
            step_id=step.id if step else None,
            kind=kind,
            details=redact_debug(details or {}),
        )
    )


def authority(
    db,
    user_id,
    company,
    environment,
    owner_id,
    permission="power_apps_execute",
    service=False,
):
    from app.models.user import User
    from app.core.tenant_boundary import company_ids
    from app.access.service import background_scope
    from app.access.catalog import permission_names

    user = db.query(User).filter(User.id == user_id).populate_existing().first()
    if not user or not user.is_active or company not in company_ids(db, user):
        raise HTTPException(
            403, "Execution identity is inactive or company membership was revoked"
        )
    user.organization_id = company
    db.expire(user, ["role"])
    user._suite_permission_objects = None
    if service:
        from app.shared.contracts import service_identity

        service_identity(db, user, company, "power_apps")
    with background_scope(db, user, "power_apps", "view"):
        if not user.is_superuser and not {
            "power_apps_view",
            permission,
        } <= permission_names(user):
            raise HTTPException(403, "Execution authority was revoked")
        validate_environment(db, user, environment)
        grant = (getattr(user, "_suite_grants", None) or {}).get("power_apps", {})
        from app.access.service import policy_for

        if (
            not user.is_superuser
            and policy_for(db, user, company)
            and "create" not in grant.get("actions", [])
        ):
            raise HTTPException(
                403, "Current module policy does not permit execution requests"
            )
        if (
            user.id != owner_id
            and not user.is_superuser
            and grant.get("scope") != "organization"
        ):
            raise HTTPException(403, "Execution identity cannot access this workflow")
    return user


def validate_runtime(definition):
    if len(json.dumps(definition)) > 1048576:
        raise HTTPException(422, "Published definition exceeds 1 MB")
    try:
        graph = VisualWorkflowDefinition.model_validate(definition)
        safe_strings(graph.model_dump())
        safe_data(graph.variables)
    except (ValueError, TypeError):
        raise HTTPException(
            422,
            "Save a valid schema-2 definition in the visual editor before publishing",
        ) from None
    if redact_debug(graph.model_dump()) != graph.model_dump():
        raise HTTPException(
            422,
            "Secret-shaped literals cannot enter a published definition or execution history",
        )
    report = validate_graph(graph)
    issues = [x for x in report["issues"] if x["severity"] == "error"]
    by_id, incoming, outgoing, order, ancestors = topology(graph)
    setters = {}
    for item in graph.nodes:
        if item.type == "set_variable" and item.config.get("name"):
            setters.setdefault(item.config["name"], []).append(item.id)
    from app.apps.power_apps.node_registry import expression_paths

    for item in graph.nodes:
        for name, writers in setters.items():
            reads = any(
                path == f"workflow.variables.{name}"
                for path in expression_paths(
                    {
                        "config": item.config,
                        "mappings": {
                            k: v.model_dump() for k, v in item.mappings.items()
                        },
                    }
                )
            )
            if reads or item.id in writers:
                if any(
                    writer != item.id
                    and writer not in ancestors[item.id]
                    and item.id not in ancestors[writer]
                    for writer in writers
                ):
                    issues.append(
                        {
                            "node_id": item.id,
                            "code": "variable_race",
                            "message": "Unordered branches cannot read or write the same mutable workflow variable",
                        }
                    )
    for n in graph.nodes:
        if n.type == "set_variable" and "name" in n.mappings:
            issues.append(
                {
                    "node_id": n.id,
                    "code": "variable_name",
                    "message": "Variable names must be literal so parallel writes can be checked",
                }
            )
        if redact_debug(n.config) != n.config:
            issues.append(
                {
                    "node_id": n.id,
                    "code": "secret",
                    "message": "Secret-shaped literals cannot be published",
                }
            )
        if n.type == "set_variable" and n.config.get("name"):
            import re

            name = n.config["name"]
            if (
                not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", name)
                or name.startswith("__")
                or name in {"constructor", "prototype"}
            ):
                issues.append(
                    {
                        "node_id": n.id,
                        "code": "variable",
                        "message": "Invalid workflow variable name",
                    }
                )
        if n.disabled:
            issues.append(
                {
                    "node_id": n.id,
                    "code": "disabled",
                    "message": "Disabled nodes cannot be published",
                }
            )
        if n.type not in EXECUTORS and n.type not in {"loop", "for_each"}:
            issues.append(
                {
                    "node_id": n.id,
                    "code": "executor",
                    "message": "No production executor registered for " + n.type,
                }
            )
        if n.type.startswith("connector_"):
            from app.apps.power_apps.integrations.registry import INPUTS
            try:
                if not isinstance(n.config.get("input",{}),dict): raise ValueError("Connector input must be an object")
                model=INPUTS[n.type.removeprefix("connector_"), n.config.get("action")]
                if not expression_paths(n.config.get("input",{})): model.model_validate(n.config.get("input",{}))
            except (KeyError,ValueError,TypeError):
                issues.append({"node_id":n.id,"code":"connector_input","message":"Choose a supported integration action and configure its required inputs"})
        if n.credential_reference and not n.type.startswith("connector_"):
            issues.append(
                {
                    "node_id": n.id,
                    "code": "credential",
                    "message": "This runtime has no credential-consuming executors",
                }
            )
        if n.type == "wait_until":
            try:
                value = datetime.fromisoformat(n.config["until"].replace("Z", "+00:00"))
                if value.tzinfo is None:
                    raise ValueError()
            except (ValueError, KeyError):
                issues.append(
                    {
                        "node_id": n.id,
                        "code": "timezone",
                        "message": "Wait until requires an offset-aware ISO timestamp",
                    }
                )
    try:
        regions = loop_regions(graph)
        for loop_id, body in regions.items():
            loop_node = by_id[loop_id]
            if (
                loop_node.config.get("mode") == "bounded_parallel"
                and loop_node.config.get("concurrency", 1) > 1
                and any(
                    by_id[key].type == "set_variable" and by_id[key].config.get("name")
                    for key in body
                )
            ):
                raise ValueError(
                    "Parallel loop bodies use isolated step outputs; shared variable writes require sequential mode"
                )
        if regions and any(len(n.id) > 40 for n in graph.nodes):
            raise ValueError(
                "Loop graph identifiers must be at most 40 characters for durable instance IDs"
            )
        templates = set().union(*regions.values()) if regions else set()
        by_id = {n.id: n for n in graph.nodes}

        def cost(key):
            node = by_id[key]
            if key not in regions:
                return 1
            if len(key) > 40:
                raise ValueError(
                    "Loop identifiers are limited to 40 characters for durable instance IDs"
                )
            if (
                type(node.config.get("max_iterations")) is not int
                or type(node.config.get("concurrency", 1)) is not int
            ):
                raise ValueError("Loop count and concurrency must be integers")
            inner = (
                set().union(
                    *(
                        region
                        for other, region in regions.items()
                        if other in regions[key]
                    )
                )
                if any(other in regions[key] for other in regions)
                else set()
            )
            count = (
                len(node.config["items"])
                if node.type == "for_each"
                and isinstance(node.config.get("items"), list)
                else node.config["max_iterations"]
            )
            return 1 + count * sum(cost(child) for child in regions[key] - inner)

        if sum(cost(n.id) for n in graph.nodes if n.id not in templates) > MAX_STEPS:
            raise ValueError("Declared loop expansion exceeds 5000 processed steps")
    except ValueError as exc:
        issues.append({"code": "loop", "message": str(exc)})
    if issues:
        raise HTTPException(
            422, {"message": "Workflow is not executable", "issues": issues}
        )
    return graph


def loop_regions(graph):
    by_id, incoming, outgoing, order, ancestors = topology(graph)

    def descendants(roots):
        found = set()
        todo = list(roots)
        while todo:
            key = todo.pop()
            if key in found:
                continue
            found.add(key)
            todo.extend(e.target for e in outgoing[key])
        return found

    regions = {}
    for n in graph.nodes:
        if n.type not in {"loop", "for_each"}:
            continue
        body = descendants(e.target for e in outgoing[n.id] if e.source_port == "body")
        done = descendants(e.target for e in outgoing[n.id] if e.source_port == "done")
        if body & done:
            raise ValueError(
                "Loop body must terminate independently; continuation connects only to done"
            )
        if not body:
            raise ValueError("Loop requires a bounded body")
        for key in body:
            if any(e.source not in body | {n.id} for e in incoming[key]):
                raise ValueError("Loop body cannot accept outside branch inputs")
        regions[n.id] = body
    for key, body in regions.items():
        depth = sum(key in region for region in regions.values()) + 1
        if depth > 2:
            raise ValueError("Maximum nested loop depth is two")
    return regions


def deployment(db, row, lock=False):
    query = db.query(Deployment).filter_by(
        resource_id=row.id,
        organization_id=row.organization_id,
        environment=row.environment,
    )
    if lock:
        query = query.with_for_update()
    state = query.populate_existing().first()
    if state is None:
        state = Deployment(
            **scope_values(row),
            resource_id=row.id,
            status="draft",
            policy=RuntimePolicy().model_dump(),
        )
        db.add(state)
        db.flush()
    return state


def lifecycle(db, row, user, action, expected_version, policy=None):
    # Serialize authoring transitions with saves, publications and enqueue decisions.
    row = (
        db.query(PowerResource)
        .filter_by(id=row.id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    if row.version != expected_version:
        raise HTTPException(409, "Draft version changed; reload before continuing")
    state = deployment(db, row, True)
    if state.status == "archived":
        raise HTTPException(
            409, "Archived runtimes cannot transition; create a draft copy"
        )
    if action == "validate":
        validate_runtime(row.definition)
        state.validated_version = row.version
        if state.status in {"draft", "validated"}:
            state.status = "validated"
    elif action == "publish":
        if state.status == "active":
            raise HTTPException(409, "Pause before replacing the published version")
        if state.validated_version != row.version:
            raise HTTPException(409, "Validate this draft version before publication")
        validate_runtime(row.definition)
        version = (
            db.query(PowerVersion)
            .filter_by(
                resource_id=row.id,
                organization_id=row.organization_id,
                version=row.version,
            )
            .one()
        )
        chosen = RuntimePolicy.model_validate(policy or state.policy)
        if chosen.identity == "owner" and user.id != row.owner_user_id:
            raise HTTPException(
                403, "Only the workflow owner may delegate owner authority"
            )
        if chosen.input_schema:
            from app.apps.power_apps.runtime_triggers import validate_schema

            try:
                validate_schema(chosen.input_schema)
            except (ValueError, TypeError):
                raise HTTPException(422, "Invalid published input schema") from None
        if chosen.identity == "service":
            from app.core.deps import RequirePermission

            RequirePermission("power_apps_manage_environment")(user)
            authority(
                db,
                chosen.service_user_id,
                row.organization_id,
                row.environment,
                row.owner_user_id,
                service=True,
            )
        from app.apps.power_apps.integrations.registry import get_action
        from app.apps.power_apps.integrations import vault
        connector_actor = None
        for external_node in VisualWorkflowDefinition.model_validate(row.definition).nodes:
            if not external_node.type.startswith("connector_"): continue
            if connector_actor is None: connector_actor = authority(db, chosen.service_user_id if chosen.identity == "service" else row.owner_user_id if chosen.identity == "owner" else user.id, row.organization_id, row.environment, row.owner_user_id)
            if not external_node.credential_reference or not external_node.credential_reference.isdecimal(): raise HTTPException(422,"Choose a saved connection for every integration node")
            connection = vault.connection(db, connector_actor, row.environment, int(external_node.credential_reference))
            if connection.connector_id != external_node.type.removeprefix("connector_") or not connection.enabled: raise HTTPException(422,"Connection does not match this integration node")
            try: external_action=get_action(connection.connector_id,external_node.config.get("action"))
            except ValueError: raise HTTPException(422,"Choose a supported connector action") from None
            external_mutates = external_action.mutates or connection.connector_id == "http" and external_node.config.get("input",{}).get("method","GET") not in {"GET","HEAD"}
            if external_mutates and not (connection.writes_enabled and external_node.config.get("confirm_write") is True): raise HTTPException(422,"External writes need connection opt-in and explicit node authorization")
        state.version_id = version.id
        state.policy = chosen.model_dump()
        state.status = "published"
    elif action == "activate":
        if state.status not in {"published", "paused"} or not state.version_id:
            raise HTTPException(409, "Publish before activation")
        validate_runtime(db.get(PowerVersion, state.version_id).snapshot["definition"])
        state.status = "active"
    elif action == "pause":
        if state.status != "active":
            raise HTTPException(409, "Only active workflows can be paused")
        state.status = "paused"
    elif action == "archive":
        if state.status not in {"paused", "published", "validated", "draft"}:
            raise HTTPException(409, "Pause before archiving")
        state.status = "archived"
    else:
        raise HTTPException(422, "Unknown lifecycle action")
    state.revision += 1
    db.add(
        Event(
            **scope_values(row),
            resource_id=row.id,
            kind="lifecycle_" + action,
            details={
                "actor_user_id": user.id,
                "draft_version": row.version,
                "version_id": state.version_id,
            },
        )
    )
    db.flush()
    return state


def safe_strings(value):
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str) and "\x00" in item:
            raise ValueError("Runtime data cannot contain NUL characters")
        if isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return value


def safe_data(value):
    bounded(value)
    return safe_strings(value)


def payload(value):
    try:
        safe_data(value)
    except (ValueError, TypeError):
        raise HTTPException(
            422, "Execution input exceeds bounds or contains unsafe/secret fields"
        ) from None
    if "record" in value and not isinstance(value["record"], dict):
        raise HTTPException(422, "Trigger record must be an object")
    if len(json.dumps(value)) > 32768:
        raise HTTPException(413, "Execution input exceeds 32 KB")
    # History is an inspection surface: credential-shaped values may not enter runtime state.
    if redact_debug(value) != value:
        raise HTTPException(
            422, "Execution input contains secret-shaped data; use a credential adapter"
        )
    return value


def enqueue(db, row, user, data, key, kind="manual", trigger=None):
    if redact_debug(key) != key:
        raise HTTPException(
            422, "Idempotency keys must be opaque request identifiers, not secrets"
        )
    row = (
        db.query(PowerResource)
        .filter_by(id=row.id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    state = deployment(db, row, True)
    prior = (
        db.query(PowerExecution)
        .filter_by(
            organization_id=row.organization_id,
            environment=row.environment,
            resource_id=row.id,
            idempotency_key=key,
        )
        .first()
    )
    if prior:
        old = db.query(Run).filter_by(id=prior.id).first()
        if not old or old.input_payload != data or old.trigger_kind != kind:
            raise HTTPException(
                409, "Idempotency key was already used with different input"
            )
        return prior
    if state.status != "active" or not state.version_id or row.archived_at:
        raise HTTPException(409, "Workflow is not active")
    policy = RuntimePolicy.model_validate(state.policy)
    effective_id = (
        user.id
        if policy.identity == "initiator"
        else (
            policy.service_user_id
            if policy.identity == "service"
            else row.owner_user_id
        )
    )
    if (
        kind != "manual"
        and policy.identity != "service"
        and (policy.identity != "owner" or not policy.delegated_owner)
    ):
        raise HTTPException(
            403, "Background triggers require explicit owner delegation"
        )
    authority(
        db,
        effective_id,
        row.organization_id,
        row.environment,
        row.owner_user_id,
        service=policy.identity == "service",
    )
    graph = validate_runtime(
        db.get(PowerVersion, state.version_id).snapshot["definition"]
    )
    trigger_node = next(n for n in graph.nodes if NODES[n.type]["trigger"])
    allowed = {
        "manual": {"manual_trigger"},
        "scheduled": {"scheduled_trigger"},
        "webhook": {"webhook_trigger"},
        "internal": {"record_created", "record_updated", "status_changed"},
    }
    if trigger_node.type not in allowed.get(kind, set()):
        raise HTTPException(422, "Trigger does not match the published version")
    data = payload(data)
    if policy.input_schema:
        from app.apps.power_apps.runtime_triggers import schema_check

        try:
            schema_check(data, policy.input_schema)
        except (ValueError, TypeError):
            raise HTTPException(
                422, "Execution input does not match the published input schema"
            )
    # A tenant environment row is also the quota mutex: enqueue and worker claims take it first.
    quota_lock(db, row.organization_id, row.environment)
    pending = (
        db.query(PowerExecution)
        .filter_by(organization_id=row.organization_id)
        .filter(PowerExecution.status.in_(LIVE))
        .count()
    )
    own = (
        db.query(PowerExecution)
        .filter_by(resource_id=row.id)
        .filter(PowerExecution.status.in_(LIVE))
        .count()
    )
    active = (
        db.query(PowerExecution)
        .filter_by(resource_id=row.id)
        .filter(PowerExecution.status.in_({"running", "waiting", "retry_scheduled"}))
        .count()
    )
    if pending >= TENANT_QUEUE or own >= policy.max_queued:
        raise HTTPException(429, "Durable queue quota reached")
    if active >= policy.concurrency and policy.overflow in {"reject", "ignore"}:
        raise HTTPException(429, "Workflow concurrency limit reached")
    root = PowerExecution(
        **scope_values(row),
        resource_id=row.id,
        workflow_version=db.get(PowerVersion, state.version_id).version,
        actor_user_id=user.id,
        idempotency_key=key,
        status="queued",
    )
    db.add(root)
    db.flush()
    run = Run(
        **scope_values(row),
        id=root.id,
        version_id=state.version_id,
        trigger_id=trigger.id if trigger else None,
        trigger_kind=kind,
        effective_user_id=effective_id,
        correlation_id=str(uuid.uuid4()),
        input_payload=data,
        variables=copy.deepcopy(graph.variables),
        deadline=now() + timedelta(seconds=policy.max_duration_seconds),
        plan={
            "nodes": [n.model_dump() for n in graph.nodes],
            "edges": [e.model_dump() for e in graph.edges],
            "loops": {},
            "identity_policy": policy.model_dump(),
        },
    )
    db.add(run)
    db.flush()
    regions = loop_regions(graph)
    templates = set().union(*regions.values()) if regions else set()
    for n in graph.nodes:
        if n.id not in templates:
            db.add(
                Step(
                    **scope_values(run),
                    run_id=run.id,
                    node_id=n.id,
                    original_node_id=n.id,
                    status="pending",
                    local_context={},
                )
            )
    db.flush()
    event(
        db,
        run,
        "queued",
        details={
            "trigger": kind,
            "version_id": state.version_id,
            "correlation_id": run.correlation_id,
        },
    )
    advance(db, run)
    return root


def plan_graph(run):
    nodes = {n["id"]: VisualNode.model_validate(n) for n in run.plan["nodes"]}
    incoming = {key: [] for key in nodes}
    for edge in run.plan["edges"]:
        if edge["target"] in incoming:
            incoming[edge["target"]].append(edge)
    return nodes, incoming


def context_for(run, steps, step):
    context = {
        "trigger": {
            "input": run.input_payload,
            "record": run.input_payload.get("record", run.input_payload),
        },
        "steps": {
            s.node_id: {"output": s.output} for s in steps if s.output is not None
        },
        "workflow": {"variables": run.variables},
        "env": {"name": run.environment},
    }
    context["steps"].update((step.local_context or {}).get("steps", {}))
    return context


def new_job(db, run, step, available=None):
    step.status = "queued"
    existing = db.query(Job).filter_by(step_id=step.id).first()
    if existing:
        existing.status = "queued"
        existing.available_at = available or now()
        existing.lease_token = None
        existing.lease_until = None
    else:
        db.add(
            Job(
                **scope_values(run),
                run_id=run.id,
                step_id=step.id,
                status="queued",
                available_at=available or now(),
            )
        )


def finish(db, run, status, error_type=None, error=None):
    db.flush()
    root = db.get(PowerExecution, run.id)
    root.status = status
    run.finished_at = now()
    run.error_type = error_type
    run.error = error
    db.query(Job).filter(
        Job.run_id == run.id, Job.status.in_({"queued", "running"})
    ).update(
        {"status": "cancelled", "lease_token": None, "lease_until": None},
        synchronize_session="fetch",
    )
    db.query(Wait).filter_by(run_id=run.id, status="waiting").update(
        {"status": "cancelled"}, synchronize_session="fetch"
    )
    db.query(Step).filter(Step.run_id == run.id, ~Step.status.in_(TERMINAL)).update(
        {"status": "cancelled", "finished_at": now()}, synchronize_session="fetch"
    )
    event(db, run, status, details={"error_type": error_type})
    from app.apps.power_apps.approvals.service import runtime_finished,domain
    with domain(db):
        runtime_finished(db,run,status)
        db.flush()
    if status == "failed":
        from app.models.user import User
        from app.models.notification import Notification, NotificationDeliveryLog
        from app.core.tenant_boundary import company_ids

        recipient = db.get(User, run.owner_user_id)
        if (
            recipient
            and recipient.is_active
            and run.organization_id in company_ids(db, recipient)
        ):
            notification = Notification(
                company_id=run.organization_id,
                user_id=recipient.id,
                title="Automation execution failed",
                message=f"Execution #{run.id} requires inspection. Correlation {run.correlation_id}.",
                module="power_apps",
                event_type="power_automation.failed",
                related_entity_type="automation_execution",
                related_entity_id=run.id,
                action_url=f"/power-apps/automations/executions/{run.id}?environment={run.environment}",
                channels=["in_app"],
            )
            db.add(notification)
            db.flush()
            db.add(
                NotificationDeliveryLog(
                    notification_id=notification.id,
                    channel="in_app",
                    recipient=f"user:{recipient.id}",
                    status="delivered",
                    delivered_at=now(),
                )
            )


def advance(db, run):
    db.flush()
    root = db.get(PowerExecution, run.id)
    if root.status in TERMINAL:
        return
    if now() > utc(run.deadline):
        finish(db, run, "failed", "WorkflowTimeout", "Workflow duration exceeded")
        return
    # Loop continuations create separate durable step instances, never graph cycles.
    advance_loops(db, run)
    nodes, incoming = plan_graph(run)
    steps = db.query(Step).filter_by(run_id=run.id).all()
    by_id = {s.node_id: s for s in steps}
    changed = True
    while changed:
        changed = False
        for step in steps:
            if step.status != "pending":
                continue
            edges = incoming[step.node_id]
            node = nodes[step.node_id]
            sources = [(edge, by_id.get(edge["source"])) for edge in edges]
            active = [
                (e, s)
                for e, s in sources
                if s
                and (
                    s.status in TERMINAL
                    or (
                        s.status == "waiting"
                        and s.node_id in run.plan.get("loops", {})
                        and e["source_port"] == "body"
                    )
                )
                and e["source_port"] in (s.active_ports or [])
            ]
            if (
                node.type == "merge"
                and node.config.get("strategy") == "first_successful"
            ):
                active = [(e, s) for e, s in active if s.status == "completed"]
            unresolved = [
                s
                for e, s in sources
                if s
                and s.status not in TERMINAL
                and not (
                    s.status == "waiting"
                    and s.node_id in run.plan.get("loops", {})
                    and e["source_port"] == "body"
                )
            ]
            if not edges:
                ready = NODES[node.type]["trigger"]
            elif node.type == "merge" and node.config.get("strategy") in {
                "first",
                "first_completed",
                "first_successful",
            }:
                ready = bool(active)
            else:
                ready = bool(active) and not unresolved
            if ready:
                new_job(db, run, step)
                changed = True
            elif (
                not unresolved
                and edges
                and node.type == "merge"
                and node.config.get("strategy") == "first_successful"
                and any(s and s.status == "failed" for e, s in sources)
            ):
                step.status = "failed"
                step.error_type = "NoSuccessfulBranch"
                step.error = "Every join branch failed or was skipped"
                finish(db, run, "failed", "NoSuccessfulBranch", step.error)
                return
            elif not unresolved and edges:
                step.status = "skipped"
                step.finished_at = now()
                event(db, run, "step_skipped", step)
                changed = True
        if changed:
            db.flush()
    if all(s.status in TERMINAL for s in steps):
        finish(db, run, "completed")
        return
    if root.status != "queued":
        statuses = {s.status for s in steps}
        root.status = (
            "waiting"
            if "waiting" in statuses
            and not statuses & {"queued", "running", "retry_scheduled"}
            else (
                "retry_scheduled"
                if "retry_scheduled" in statuses
                and not statuses & {"queued", "running"}
                else "running"
            )
        )


def quota_lock(db, company, environment, skip=False):
    from app.models.company import Company

    tenant = (
        db.query(Company)
        .filter_by(id=company)
        .with_for_update(skip_locked=skip, key_share=True)
        .first()
    )
    if not tenant:
        return None
    return (
        db.query(PowerEnvironment)
        .filter_by(organization_id=company, key=environment)
        .with_for_update(skip_locked=skip)
        .first()
    )


def claim(db, worker_id):
    instant = now()
    eligible = or_(
        (Job.status == "queued") & (Job.available_at <= instant),
        (Job.status == "running") & (Job.lease_until < instant),
    )
    last_dispatch = (
        db.query(
            Job.organization_id.label("company"),
            func.max(Job.heartbeat_at).label("last_at"),
        )
        .group_by(Job.organization_id)
        .subquery()
    )
    tenant_heads = (
        db.query(func.min(Job.id))
        .outerjoin(last_dispatch, Job.organization_id == last_dispatch.c.company)
        .filter(eligible)
        .group_by(Job.organization_id, last_dispatch.c.last_at)
        .order_by(
            last_dispatch.c.last_at.asc().nullsfirst(), func.min(Job.available_at)
        )
        .limit(100)
        .all()
    )
    candidates = []
    for (head,) in tenant_heads:
        company = db.get(Job, head).organization_id
        candidates.extend(
            db.query(Job.id)
            .join(PowerExecution, PowerExecution.id == Job.run_id)
            .filter(eligible, Job.organization_id == company)
            .order_by(
                case((PowerExecution.status == "queued", 1), else_=0),
                Job.available_at,
                Job.id,
            )
            .limit(20)
            .all()
        )
    for (job_id,) in candidates:
        hint = db.get(Job, job_id)
        # Lock quota before job/run everywhere. CAS protects SQLite test fallback.
        env = quota_lock(db, hint.organization_id, hint.environment, skip=True)
        if not env:
            db.rollback()
            continue
        job = (
            db.query(Job)
            .filter(Job.id == job_id, eligible)
            .with_for_update(skip_locked=True)
            .populate_existing()
            .first()
        )
        if not job:
            db.rollback()
            continue
        leases = db.query(Job).filter(
            Job.organization_id == job.organization_id,
            Job.status == "running",
            Job.lease_until > instant,
        )
        if (
            leases.count() >= TENANT_CONCURRENCY
            or leases.filter(Job.environment == job.environment).count()
            >= ENV_CONCURRENCY
        ):
            db.rollback()
            continue
        root = (
            db.query(PowerExecution)
            .filter_by(id=job.run_id)
            .with_for_update()
            .populate_existing()
            .one()
        )
        run = db.get(Run, root.id)
        if root.status in TERMINAL:
            job.status = "cancelled"
            db.commit()
            continue
        if root.status == "queued":
            state = db.query(Deployment).filter_by(resource_id=root.resource_id).first()
            policy = RuntimePolicy.model_validate(state.policy)
            query = db.query(PowerExecution).filter(
                PowerExecution.organization_id == root.organization_id,
                PowerExecution.status.in_({"running", "waiting", "retry_scheduled"}),
            )
            if (
                query.count() >= TENANT_CONCURRENCY
                or query.filter_by(environment=root.environment).count()
                >= ENV_CONCURRENCY
                or query.filter_by(resource_id=root.resource_id).count()
                >= policy.concurrency
            ):
                db.rollback()
                continue
            root.status = "running"
            run.started_at = instant
            event(db, run, "running")
        if job.claims >= 10:
            fail_job(
                db,
                job,
                run,
                db.get(Step, job.step_id),
                "LeaseRecoveryLimit",
                "Too many interrupted claims",
                False,
            )
            db.commit()
            continue
        token = str(uuid.uuid4())
        changed = (
            db.query(Job)
            .filter(Job.id == job.id, eligible)
            .update(
                {
                    "status": "running",
                    "lease_token": token,
                    "lease_until": instant + timedelta(seconds=30),
                    "heartbeat_at": instant,
                    "claims": Job.claims + 1,
                },
                synchronize_session=False,
            )
        )
        if changed:
            step = db.get(Step, job.step_id)
            step.status = "running"
            step.attempt += 1
            step.started_at = instant
            root.attempt = max(root.attempt, step.attempt)
            event(db, run, "step_leased", step, {"attempt": step.attempt})
            db.commit()
            return job_id, token
        db.rollback()
    return None


def heartbeat(db, job_id, token):
    return bool(
        db.query(Job)
        .filter_by(id=job_id, status="running", lease_token=token)
        .filter(Job.lease_until > now())
        .update(
            {"lease_until": now() + timedelta(seconds=30), "heartbeat_at": now()},
            synchronize_session=False,
        )
    )


def fail_job(db, job, run, step, error_type, message, retryable):
    nodes, _ = plan_graph(run)
    node = nodes[step.node_id]
    step.error_type = error_type
    step.error = redact_debug(str(message))[:400]
    retry_limit = min(node.advanced.retry_attempts, 10)
    job.lease_token = None
    job.lease_until = None
    if retryable and step.attempt < retry_limit:
        snapshot = db.get(PowerVersion, run.version_id).snapshot["definition"]
        base = snapshot.get("settings", {}).get("retry_backoff_seconds", 60)
        # Stable bounded jitter avoids synchronized retries and is reproducible after restart.
        jitter = int(
            hashlib.sha256(
                f"{run.id}:{step.node_id}:{step.attempt}".encode()
            ).hexdigest()[:4],
            16,
        ) % max(1, base // 4 + 1)
        available = now() + timedelta(
            seconds=min(86400, base * 2 ** max(0, step.attempt - 1) + jitter)
        )
        new_job(db, run, step, available)
        step.status = "retry_scheduled"
        event(
            db,
            run,
            "retry_scheduled",
            step,
            {
                "attempt": step.attempt,
                "available_at": available.isoformat(),
                "error_type": error_type,
            },
        )
    else:
        job.status = "dead"
        step.status = "failed"
        step.finished_at = now()
        db.add(
            DeadLetter(
                **scope_values(run), run_id=run.id, job_id=job.id, reason=error_type
            )
        )
        if node.advanced.error_strategy == "branch":
            step.active_ports = ["error"]
            step.output = {"error": step.error}
            advance(db, run)
        elif node.advanced.error_strategy == "continue":
            step.active_ports = ["out"]
            step.output = {"error": step.error}
            advance(db, run)
        else:
            targets = [
                nodes[e["target"]]
                for e in run.plan["edges"]
                if e["source"] == step.node_id and e["source_port"] != "error"
            ]
            if targets and all(
                n.type == "merge"
                and n.config.get("strategy") in {"first_successful", "first_completed"}
                for n in targets
            ):
                step.active_ports = ["out"]
                step.output = {"error": step.error}
                advance(db, run)
            else:
                finish(db, run, "failed", error_type, step.error)
        event(
            db,
            run,
            "step_failed",
            step,
            {"error_type": error_type, "attempt": step.attempt},
        )


def process(db, job_id, token):
    hint = db.get(Job, job_id)
    if not hint:
        return "missing"
    # Claims commit quota reservations before execution. Only this run's checkpoint is locked here.
    root = (
        db.query(PowerExecution)
        .filter_by(id=hint.run_id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    job = (
        db.query(Job)
        .filter_by(id=job_id, status="running", lease_token=token)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not job or utc(job.lease_until) <= now():
        db.rollback()
        return "lost_lease"
    run = db.get(Run, job.run_id)
    step = db.get(Step, job.step_id)
    if root.status in TERMINAL:
        job.status = "cancelled"
        db.commit()
        return root.status
    if now() > utc(run.deadline):
        finish(db, run, "failed", "WorkflowTimeout", "Workflow duration exceeded")
        db.commit()
        return "failed"
    checkpoint = db.begin_nested()
    try:
        authority(
            db,
            run.effective_user_id,
            run.organization_id,
            run.environment,
            run.owner_user_id,
            service=run.plan.get("identity_policy", {}).get("identity") == "service",
        )
        nodes, incoming = plan_graph(run)
        node = nodes[step.node_id]
        if node.type not in EXECUTORS and node.type not in {"loop", "for_each"}:
            raise ValueError("Unsupported executor")
        step.status = "running"
        step.started_at = now()
        root.attempt = max(root.attempt, step.attempt)
        steps = db.query(Step).filter_by(run_id=run.id).all()
        stored_output_bytes = sum(
            len(json.dumps(item.output)) for item in steps if item.output is not None
        )
        if stored_output_bytes > MAX_RUN_OUTPUT_BYTES:
            raise ValueError("Run outputs exceed the aggregate history budget")
        context = context_for(run, steps, step)
        config = resolve(node.config, context)
        for field, binding in node.mappings.items():
            config[field] = map_value(binding.model_dump(), context)
        safe_data(config)
        if redact_debug(config) != config:
            raise ValueError("Resolved configuration contains secret-shaped data")
        errors = configuration_errors(node.type, config)
        if errors:
            raise ValueError("; ".join(errors))
        step.input_payload = config
        previous_steps = [
            s
            for e in incoming[step.node_id]
            for s in steps
            if s.node_id == e["source"]
            and e["source_port"] in (s.active_ports or [])
            and s.output is not None
        ]
        if node.type == "merge" and config.get("strategy") in {
            "first",
            "first_successful",
            "first_completed",
        }:
            if config.get("strategy") == "first_successful":
                previous_steps = [s for s in previous_steps if s.status == "completed"]
            previous_steps.sort(key=lambda s: (utc(s.finished_at) or now(), s.id))
        previous = [s.output for s in previous_steps]
        if node.type in {"loop", "for_each"}:
            start_loop(db, run, step, node, config, context)
            job.status = "completed"
            job.lease_token = None
            job.lease_until = None
            advance(db, run)
            checkpoint.commit()
            db.commit()
            return "waiting"
        if node.type in {"delay", "wait_until"}:
            wake = (
                now() + timedelta(seconds=config["seconds"])
                if node.type == "delay"
                else utc(datetime.fromisoformat(config["until"].replace("Z", "+00:00")))
            )
            if wake > utc(run.deadline):
                raise ValueError("Wait exceeds the maximum workflow duration")
            if wake > now():
                db.add(
                    Wait(
                        **scope_values(run),
                        run_id=run.id,
                        step_id=step.id,
                        wake_at=wake,
                        event_key=config.get("event_key") or None,
                        status="waiting",
                    )
                )
                step.status = "waiting"
                job.status = "completed"
                job.lease_token = None
                job.lease_until = None
                event(db, run, "waiting", step, {"wake_at": wake.isoformat()})
                advance(db, run)
                checkpoint.commit()
                db.commit()
                return "waiting"
        if node.type == "approval_wait":
            from app.apps.power_apps.approvals.service import open_stage,domain
            with domain(db):
                waiting=open_stage(db,run,step,config)
                if not waiting:
                    step.output={"request_id":run.input_payload["approval_request_id"],"status":"Skipped"}
                    step.active_ports=["out"];step.status="completed";step.finished_at=now()
                job.status="completed";job.lease_token=None;job.lease_until=None
                advance(db,run)
                checkpoint.commit();db.commit()
            return "waiting" if waiting else "completed"
        started = time.monotonic()
        if node.type.startswith("connector_"):
            from app.apps.power_apps.integrations import service as connector_service, vault
            from app.apps.power_apps.integrations.contracts import IntegrationFailure
            checkpoint.commit();db.commit()
            try:
                actor=authority(db,run.effective_user_id,run.organization_id,run.environment,run.owner_user_id)
                if not node.credential_reference or not node.credential_reference.isdecimal(): raise ValueError("A saved connection is required")
                conn=vault.connection(db,actor,run.environment,int(node.credential_reference))
                if conn.connector_id!=node.type.removeprefix("connector_"):raise ValueError("Connection/provider mismatch")
                output=connector_service.invoke(db,actor,conn,config["action"],config.get("input",{}),confirmed=config.get("confirm_write") is True,key=f"run:{run.id}:step:{step.id}",run_id=run.id,step_id=step.id)
                from app.apps.power_apps.integrations.providers import PROFILES
                if conn.connector_id not in PROFILES:
                    raw_output=output
                    output={**(raw_output if isinstance(raw_output,dict) else {}), "data":raw_output, "http_status":raw_output.get("http_status",raw_output.get("status_code")) if isinstance(raw_output,dict) else None}
                external_error=None
            except (IntegrationFailure,HTTPException,ValueError,TypeError) as exc:
                external_error=exc
            db.rollback()
            root=db.query(PowerExecution).filter_by(id=run.id).with_for_update().populate_existing().one()
            job=db.query(Job).filter_by(id=job_id).with_for_update().populate_existing().one()
            if job.lease_token!=token or job.status!="running" or utc(job.lease_until)<=now() or root.status in TERMINAL:
                db.rollback();return "lost_lease"
            db.refresh(run);db.refresh(step)
            checkpoint=db.begin_nested()
            if external_error:
                fail_job(db,job,run,step,"ExternalActionFailed",str(external_error) if isinstance(external_error,IntegrationFailure) else "Connection authority or input is unavailable",False)
                checkpoint.commit();db.commit();return step.status
            active={"out"}
        else:
            output, active = EXECUTORS[node.type].execute(node, config, run.input_payload, previous)
        if not node.type.startswith("connector_") and time.monotonic() - started > min(
            node.advanced.timeout_seconds, EXECUTORS[node.type].timeout_seconds
        ):
            raise TimeoutError("Executor timeout")
        safe_data(output)
        if stored_output_bytes + len(json.dumps(output)) > MAX_RUN_OUTPUT_BYTES:
            raise ValueError("Run outputs exceed the aggregate history budget")
        if len(json.dumps(output)) > 65536:
            raise ValueError("Step output exceeds 64 KB")
        if redact_debug(output) != output:
            raise ValueError("Executor output contains secret-shaped data")
        step.output = output
        step.active_ports = sorted(active)
        step.status = "completed"
        step.finished_at = now()
        job.status = "completed"
        job.lease_token = None
        job.lease_until = None
        event(
            db,
            run,
            "step_completed",
            step,
            {"attempt": step.attempt, "active_ports": step.active_ports},
        )
        if node.type == "log_event":
            event(
                db,
                run,
                "structured_log",
                step,
                {"message": output.get("value"), "level": config.get("level", "info")},
            )
        if node.type == "set_variable":
            name = config.get("name")
            if name:
                import re

                if (
                    not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", name)
                    or name.startswith("__")
                    or name in {"constructor", "prototype"}
                ):
                    raise ValueError("Invalid workflow variable name")
                run.variables = safe_data({**run.variables, name: output["value"]})
        if node.type == "stop_workflow":
            finish(db, run, "completed")
        else:
            advance(db, run)
        checkpoint.commit()
        db.commit()
        return step.status
    except HTTPException as exc:
        checkpoint.rollback()
        db.refresh(step)
        db.refresh(job)
        db.refresh(run)
        fail_job(
            db,
            job,
            run,
            step,
            "AuthorizationRevoked",
            "Execution authority is unavailable",
            False,
        )
        db.commit()
        return "failed"
    except (ValueError, TypeError, KeyError, OverflowError, TimeoutError) as exc:
        checkpoint.rollback()
        db.refresh(step)
        db.refresh(job)
        db.refresh(run)
        fail_job(
            db,
            job,
            run,
            step,
            type(exc).__name__,
            str(exc),
            isinstance(exc, TimeoutError),
        )
        db.commit()
        return step.status


def tick(db, limit=100):
    resumed = 0
    ids = [
        x[0]
        for x in db.query(Wait.id)
        .filter_by(status="waiting")
        .filter(Wait.wake_at <= now())
        .order_by(Wait.wake_at)
        .limit(limit)
        .all()
    ]
    for wait_id in ids:
        hint = db.get(Wait, wait_id)
        quota_lock(db, hint.organization_id, hint.environment)
        root = (
            db.query(PowerExecution)
            .filter_by(id=hint.run_id)
            .with_for_update()
            .populate_existing()
            .one()
        )
        wait = (
            db.query(Wait)
            .filter_by(id=wait_id, status="waiting")
            .with_for_update()
            .populate_existing()
            .first()
        )
        if not wait:
            db.rollback()
            continue
        run = db.get(Run, root.id)
        step = db.get(Step, wait.step_id)
        if root.status in TERMINAL:
            wait.status = "cancelled"
            db.commit()
            continue
        try:
            authority(
                db,
                run.effective_user_id,
                run.organization_id,
                run.environment,
                run.owner_user_id,
                service=run.plan.get("identity_policy", {}).get("identity")
                == "service",
            )
        except HTTPException:
            finish(
                db,
                run,
                "failed",
                "AuthorizationRevoked",
                "Execution authority was revoked",
            )
            db.commit()
            continue
        if wait.kind == "approval":
            from app.apps.power_apps.approvals.service import due,domain
            with domain(db):
                due(db,run,wait)
                db.commit()
            resumed+=1
            continue
        if wait.kind == "loop_timeout":
            wait.status = "timed_out"
            finish(db, run, "failed", "LoopTimeout", "Loop duration exceeded")
            db.commit()
            continue
        if wait.event_key:
            wait.status = "timed_out"
            job = db.query(Job).filter_by(step_id=step.id).one()
            fail_job(
                db,
                job,
                run,
                step,
                "WaitEventTimeout",
                "Authorized event was not received before timeout",
                False,
            )
            db.commit()
            continue
        wait.status = "resumed"
        step.output = {"value": "resumed"}
        step.active_ports = ["out"]
        step.status = "completed"
        step.finished_at = now()
        event(db, run, "resumed", step)
        advance(db, run)
        db.commit()
        resumed += 1
    # Deadlines cover queued, sleeping and loop runs, even without runnable jobs.
    for run in (
        db.query(Run)
        .filter(Run.finished_at.is_(None), Run.deadline < now())
        .limit(limit)
        .all()
    ):
        db.query(PowerExecution).filter_by(id=run.id).with_for_update().one()
        finish(db, run, "failed", "WorkflowTimeout", "Workflow duration exceeded")
        db.commit()
    return resumed


# Loop helpers are below to keep the queue's safety invariants visible above.
def start_loop(db, run, step, node, config, context):
    graph = VisualWorkflowDefinition.model_validate(
        db.get(PowerVersion, run.version_id).snapshot["definition"]
    )
    original_regions = loop_regions(graph)
    body = original_regions[step.original_node_id]
    items = (
        config.get("items")
        if node.type == "for_each"
        else list(range(int(config["max_iterations"])))
    )
    if not isinstance(items, list) or len(items) > min(
        int(config["max_iterations"]), 1000
    ):
        raise ValueError("Loop item count exceeds declared bounds")
    plan = copy.deepcopy(run.plan)
    # Locate the cloned template region when this is a nested loop instance.
    prefix = step.node_id[: -len(step.original_node_id)]
    ids = {prefix + key for key in body}
    templates = [n for n in plan["nodes"] if n["id"] in ids]
    edges = [
        e
        for e in plan["edges"]
        if e["target"] in ids and e["source"] in ids | {step.node_id}
    ]
    plan["loops"][step.node_id] = {
        "templates": templates,
        "edges": edges,
        "items": items,
        "next": 0,
        "batches": [],
        "finished": False,
        "config": config,
        "prefix": prefix,
        "body": list(body),
    }
    run.plan = plan
    step.status = "waiting"
    step.active_ports = ["body"]
    step.output = {"value": items}
    db.add(
        Wait(
            **scope_values(run),
            run_id=run.id,
            step_id=step.id,
            wake_at=now() + timedelta(seconds=node.advanced.timeout_seconds),
            kind="loop_timeout",
            status="waiting",
        )
    )
    spawn_iterations(db, run, step)
    event(
        db,
        run,
        "loop_started",
        step,
        {"items": len(items), "mode": config.get("mode", "sequential")},
    )


def spawn_iterations(db, run, parent):
    plan = copy.deepcopy(run.plan)
    loop = plan["loops"][parent.node_id]
    config = loop["config"]
    limit = (
        1
        if config.get("mode", "sequential") == "sequential"
        else min(int(config.get("concurrency", 1)), 10)
    )
    existing = db.query(Step).filter_by(run_id=run.id).all()
    by_id = {s.node_id: s for s in existing}
    added_count = 0
    active = sum(
        any(by_id.get(k) and by_id[k].status not in TERMINAL for k in batch)
        for batch in loop["batches"]
    )
    while active < limit and loop["next"] < len(loop["items"]):
        index = loop["next"]
        loop["next"] += 1
        prefix = f"i{parent.id}_{index}_"
        mapping = {
            n["id"]: prefix + n["id"][len(loop["prefix"]) :] for n in loop["templates"]
        }

        def replace(value):
            if isinstance(value, str):
                for old, new in mapping.items():
                    value = value.replace("steps." + old + ".", "steps." + new + ".")
                return value
            if isinstance(value, dict):
                return {k: replace(v) for k, v in value.items()}
            if isinstance(value, list):
                return [replace(v) for v in value]
            return value

        children = []
        # Inner loop bodies are templates, materialized by their own parent later.
        source_graph = VisualWorkflowDefinition.model_validate(
            db.get(PowerVersion, run.version_id).snapshot["definition"]
        )
        regions = loop_regions(source_graph)
        inner = (
            set().union(*(r for key, r in regions.items() if key in loop["body"]))
            if any(key in loop["body"] for key in regions)
            else set()
        )
        for raw in loop["templates"]:
            node = replace(copy.deepcopy(raw))
            node["id"] = mapping[raw["id"]]
            plan["nodes"].append(node)
            original = raw["id"][len(loop["prefix"]) :]
            if original in inner:
                continue
            local = copy.deepcopy(parent.local_context or {})
            local.setdefault("steps", {})[parent.node_id] = {
                "output": {"value": loop["items"][index]}
            }
            child = Step(
                **scope_values(run),
                run_id=run.id,
                node_id=node["id"],
                original_node_id=original,
                scope=parent.node_id,
                local_context=local,
                status="pending",
            )
            db.add(child)
            children.append(node["id"])
        for raw in loop["edges"]:
            edge = copy.deepcopy(raw)
            edge["source"] = mapping.get(edge["source"], edge["source"])
            edge["target"] = mapping[edge["target"]]
            edge["id"] = prefix + edge["id"]
            plan["edges"].append(edge)
        loop["batches"].append(children)
        active += 1
        added_count += len(children)
        if len(existing) + added_count > MAX_STEPS:
            raise ValueError("Expanded workflow exceeds 5000 processed steps")
    plan["loops"][parent.node_id] = loop
    if len(json.dumps(plan)) > 2097152:
        raise ValueError("Expanded execution plan exceeds 2 MB")
    run.plan = plan
    db.flush()


def advance_loops(db, run):
    if not run.plan.get("loops"):
        return
    for key in list(run.plan["loops"]):
        loop = run.plan["loops"][key]
        if loop["finished"]:
            continue
        parent = db.query(Step).filter_by(run_id=run.id, node_id=key).one()
        steps = {s.node_id: s for s in db.query(Step).filter_by(run_id=run.id).all()}
        # Exit conditions are evaluated against the most recently completed batch.
        if loop["config"].get("exit_condition") and loop["batches"]:
            batch = loop["batches"][-1]
            if batch and all(steps[k].status in TERMINAL for k in batch):
                ctx = context_for(run, list(steps.values()), parent)
                if condition(resolve(loop["config"]["exit_condition"], ctx)):
                    plan = copy.deepcopy(run.plan)
                    plan["loops"][key]["next"] = len(loop["items"])
                    run.plan = plan
        spawn_iterations(db, run, parent)
        loop = run.plan["loops"][key]
        if loop["next"] >= len(loop["items"]) and all(
            steps.get(k) and steps[k].status in TERMINAL
            for batch in loop["batches"]
            for k in batch
        ):
            parent.status = "completed"
            parent.active_ports = ["done"]
            parent.finished_at = now()
            parent.output = {
                "value": [
                    {
                        "iteration": i,
                        "outputs": {
                            steps[k].original_node_id: steps[k].output for k in batch
                        },
                    }
                    for i, batch in enumerate(loop["batches"])
                ]
            }
            bounded(parent.output)
            plan = copy.deepcopy(run.plan)
            plan["loops"][key]["finished"] = True
            run.plan = plan
            db.query(Wait).filter_by(
                step_id=parent.id, status="waiting", kind="loop_timeout"
            ).update({"status": "resumed"}, synchronize_session="fetch")
            event(db, run, "loop_completed", parent)
