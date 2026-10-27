"""Approval domain operations. Only Phase 3 advances workflow nodes and jobs."""

import copy, hashlib, hmac, json, uuid
from datetime import timedelta, datetime
from fastapi import HTTPException
from sqlalchemy import or_, event, inspect
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.deps import RequirePermission
from app.models.approval_os import ApprovalRequest, ApprovalComment, ApprovalHistory
from app.models.user import User
from app.models.notification import Notification, NotificationDeliveryLog
from app.apps.power_apps.models import PowerResource, PowerVersion, PowerExecution
from app.apps.power_apps.service import (
    organization,
    validate_environment,
    record_change,
    serialize,
)
from app.apps.power_apps.runtime import (
    now,
    utc,
    scope_values,
    safe_data,
    resolve,
    context_for,
    advance,
    finish,
    enqueue,
    lifecycle,
)
from app.apps.power_apps.runtime_models import (
    AutomationRun as Run,
    AutomationStep as Step,
    AutomationWait as Wait,
    AutomationJob as Job,
)
from app.apps.power_apps.authoring import condition
from app.apps.power_apps.approvals.models import (
    ApprovalPolicy,
    RequestState,
    Assignment,
    Delegation,
    Attachment,
)
from app.apps.power_apps.approvals.contracts import Process, Stage
from app.apps.power_apps.approvals.resolver import ApproverResolver
from app.apps.power_apps.approvals.calendar import deadline

TERMINAL = {"Approved", "Rejected", "Cancelled", "Expired", "Failed"}


def scoped(db, model, user, env):
    validate_environment(db, user, env)
    return db.query(model).filter_by(
        organization_id=organization(user), environment=env
    )


def administrator(user):
    from app.access.catalog import permission_names

    return user.is_superuser or "power_apps_approval_manage" in permission_names(user)


def visible_ids(db, user, env):
    base = scoped(db, RequestState, user, env)
    if administrator(user):
        return base.with_entities(RequestState.id)
    ids = (
        scoped(db, Assignment, user, env)
        .filter(
            or_(Assignment.user_id == user.id, Assignment.original_user_id == user.id)
        )
        .with_entities(Assignment.request_id)
    )
    return base.filter(
        or_(RequestState.owner_user_id == user.id, RequestState.id.in_(ids))
    ).with_entities(RequestState.id)


def visible(db, user, env, id, lock=False):
    query = scoped(db, RequestState, user, env).filter(
        RequestState.id == id, RequestState.id.in_(visible_ids(db, user, env))
    )
    state = query.first()
    if not state:
        raise HTTPException(404, "Approval request not found")
    if lock:
        # Global lock order: runtime execution -> request root -> state -> assignments.
        if state.run_id:
            db.query(PowerExecution).filter_by(
                id=state.run_id
            ).with_for_update().populate_existing().one()
    root = (
        db.query(ApprovalRequest)
        .filter_by(
            id=id, organization_id=organization(user), source_module="power_apps"
        )
        .with_for_update()
        if lock
        else db.query(ApprovalRequest).filter_by(
            id=id, organization_id=organization(user), source_module="power_apps"
        )
    )
    root = root.populate_existing().first()
    if not root:
        raise HTTPException(404, "Approval request not found")
    if lock:
        state = query.with_for_update().populate_existing().one()
    return root, state


def definition(db, state):
    return Process.model_validate(
        db.get(PowerVersion, state.version_id).snapshot["definition"]
    )


def notify(db, state, users, event_type, title):
    from app.models.user import User
    from app.core.tenant_boundary import company_ids

    for id in sorted(set(users)):
        user = db.get(User, id)
        if (
            not user
            or not user.is_active
            or state.organization_id not in company_ids(db, user)
        ):
            continue
        item = Notification(
            company_id=state.organization_id,
            user_id=id,
            title=title[:200],
            message="Review the approval request and its decision history.",
            module="power_apps",
            event_type="power_approval." + event_type,
            related_entity_type="approval_request",
            related_entity_id=state.id,
            action_url=f"/power-apps/approvals/requests?request={state.id}&environment={state.environment}",
            channels=["in_app"],
        )
        db.add(item)
        db.flush()


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def summary_hash(root):
    return digest(
        {
            "title": root.title,
            "description": root.description,
            "priority": root.priority,
            "requester_user_id": root.requester_user_id,
            "policy_id": root.entity_id,
        }
    )


def state_hash(root, state):
    return digest(
        {
            "status": root.status,
            "revision": state.revision,
            "cycle": state.cycle,
            "fields": state.fields,
            "decided_by": root.decided_by,
            "decided_at": utc(root.decided_at).isoformat() if root.decided_at else None,
            "decision_reason": root.decision_reason,
        }
    )


def signature(key, body):
    return hmac.new(
        key.encode(), b"power-approval-evidence-v1\0" + canonical(body), hashlib.sha256
    ).hexdigest()


def evidence(db, root, state, actor, event_type, reason="", details=None):
    last = (
        db.query(ApprovalHistory)
        .filter_by(request_id=root.id)
        .order_by(ApprovalHistory.id.desc())
        .first()
    )
    before = (
        (last.details_json or {}).get("evidence", {}).get("after_status")
        if last
        else None
    )
    version = db.get(PowerVersion, state.version_id)
    body = {
        "version": 1,
        "request_id": root.id,
        "organization_id": state.organization_id,
        "environment": state.environment,
        "revision": state.revision,
        "policy_version_id": state.version_id,
        "policy_hash": digest(version.snapshot),
        "request_hash": summary_hash(root),
        "state_hash": state_hash(root, state),
        "run_id": state.run_id,
        "actor_user_id": actor,
        "event": event_type,
        "reason": reason,
        "before_status": before,
        "after_status": root.status,
        "details": {"cycle": state.cycle, **(details or {})},
        "at": now().isoformat(),
        "previous": state.head_hash,
        "correlation_id": str(uuid.uuid4()),
    }
    proof = signature(settings.SECRET_KEY, body)
    db.add(
        ApprovalHistory(
            request_id=root.id,
            event_type=event_type,
            actor_user_id=actor,
            before_status=before,
            after_status=root.status,
            reason=reason,
            created_at=datetime.fromisoformat(body["at"]),
            details_json={"evidence": body, "hash": proof},
        )
    )
    state.head_hash = proof
    db.flush()


def verify_history(db, state):
    root = db.get(ApprovalRequest, state.id)
    version = db.get(PowerVersion, state.version_id)
    if not root or not version:
        return False
    expected_policy_hash = digest(version.snapshot)
    expected_summary_hash = summary_hash(root)
    previous = ""
    last_state = None
    vote_evidence = {}
    attachment_evidence = {}
    rows = (
        db.query(ApprovalHistory)
        .filter_by(request_id=state.id)
        .order_by(ApprovalHistory.id)
        .all()
    )
    try:
        for row in rows:
            data = row.details_json or {}
            body = data.get("evidence")
            proof = data.get("hash")
            if not isinstance(body, dict) or not isinstance(proof, str):
                return False
            keys = [settings.SECRET_KEY, getattr(settings, "SECRET_KEY_PREVIOUS", "")]
            if not (
                body.get("previous") == previous
                and body.get("request_id") == state.id
                and body.get("organization_id") == state.organization_id
                and body.get("environment") == state.environment
                and body.get("policy_version_id") == state.version_id
                and body.get("policy_hash") == expected_policy_hash
                and body.get("request_hash") == expected_summary_hash
                and body.get("actor_user_id") == row.actor_user_id
                and body.get("event") == row.event_type
                and body.get("reason") == row.reason
                and body.get("before_status") == row.before_status
                and body.get("after_status") == row.after_status
                and body.get("at") == utc(row.created_at).isoformat()
                and any(
                    hmac.compare_digest(proof, signature(key, body))
                    for key in keys
                    if key
                )
            ):
                return False
            if body.get("event") in {"approve", "reject", "changes"}:
                vote_evidence[body["details"]["assignment_id"]] = body
            if body.get("event") == "attachment_added":
                attachment_evidence[body["details"]["attachment_id"]] = body["details"][
                    "sha256"
                ]
            previous = proof
            last_state = body.get("state_hash")
        if previous != state.head_hash or last_state != state_hash(root, state):
            return False
        for assignment in db.query(Assignment).filter(
            Assignment.request_id == state.id, Assignment.decided_at.is_not(None)
        ):
            vote = vote_evidence.get(assignment.id)
            if (
                not vote
                or vote["actor_user_id"] != assignment.decision_actor_id
                or vote["reason"] != assignment.decision_reason
                or vote["details"].get("original_user_id")
                != assignment.original_user_id
                or vote["details"].get("delegation_id") != assignment.delegation_id
                or vote["details"].get("decision_at")
                != utc(assignment.decided_at).isoformat()
                or assignment.status
                != {"approve": "approved", "reject": "rejected", "changes": "changes"}[
                    vote["event"]
                ]
            ):
                return False
        for file in db.query(Attachment).filter_by(request_id=state.id):
            if attachment_evidence.get(file.id) != file.sha256:
                return False
        return True
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def ensure_integrity(db, state):
    if not verify_history(db, state):
        raise HTTPException(
            409,
            "Approval evidence verification failed; administrative investigation is required before changing this request",
        )


def validate_fields(process, fields):
    safe_data(fields)
    declared = {f.key: f for f in process.fields}
    if set(fields) - set(declared):
        raise HTTPException(422, "Unknown form field")
    for key, field in declared.items():
        if field.when and not condition(
            resolve(field.when.model_dump(), {"trigger": {"input": {"fields": fields}}})
        ):
            continue
        value = fields.get(key)
        if field.required and value in (None, ""):
            raise HTTPException(422, f"{field.label} is required")
        if value is None:
            continue
        if field.kind == "number" and (
            type(value) not in (int, float) or abs(value) > 1e14
        ):
            raise HTTPException(422, "Invalid numeric field")
        if field.kind in {"text", "date", "select"} and (
            not isinstance(value, str) or len(value) > 4000
        ):
            raise HTTPException(422, "Invalid text field")
        if field.kind == "select" and value not in field.options:
            raise HTTPException(422, "Choose a permitted option")
        if field.kind == "date":
            from datetime import date

            try:
                date.fromisoformat(value)
            except ValueError:
                raise HTTPException(422, "Use an ISO date") from None


def compile_process(process):
    def node(id, type, label, config, x):
        return {
            "id": id,
            "type": type,
            "label": label,
            "position": process.layout.get(id, {"x": x, "y": 160}),
            "config": config,
        }

    nodes = [node("start", "manual_trigger", "Start request", {}, 0)]
    edges = []
    previous = "start"
    for index, stage in enumerate(process.stages):
        nodes.append(
            node(
                stage.id,
                "approval_wait",
                stage.name,
                {"stage": stage.model_dump(mode="json")},
                (index + 1) * 300,
            )
        )
        edges.append(
            {
                "id": f"e{index}",
                "source": previous,
                "target": stage.id,
                "source_port": "out",
                "target_port": "in",
            }
        )
        previous = stage.id
    nodes.append(node("end", "stop_workflow", "End approval", {}, (len(nodes)) * 300))
    edges.append(
        {
            "id": "end_edge",
            "source": previous,
            "target": "end",
            "source_port": "out",
            "target_port": "in",
        }
    )
    for index, stage in enumerate(process.stages):
        rejection_id = "_reject_" + stage.id
        nodes.append(
            node(
                rejection_id,
                "stop_workflow",
                "End rejected request",
                {},
                (index + 1) * 300,
            )
        )
        nodes[-1]["position"]["y"] = 500
        edges.append(
            {
                "id": "reject_" + stage.id,
                "source": stage.id,
                "target": rejection_id,
                "source_port": "rejected",
                "target_port": "in",
            }
        )
    return {
        "schema_version": 2,
        "nodes": nodes,
        "edges": edges,
        "settings": {"retention_days": 365},
    }


def publish_policy(db, user, env, policy_id, expected, enabled=True):
    RequirePermission("power_apps_approval_manage")(user)
    RequirePermission("power_apps_publish")(user)
    RequirePermission("power_apps_execute")(user)
    policy = (
        scoped(db, ApprovalPolicy, user, env)
        .filter_by(id=policy_id)
        .with_for_update()
        .first()
    )
    if not policy or policy.owner_user_id != user.id:
        raise HTTPException(404, "Approval workflow not found")
    resource = db.get(PowerResource, policy.resource_id)
    if resource.version != expected:
        raise HTTPException(409, "Approval workflow changed")
    if not enabled:
        policy.enabled = False
        return policy
    process = Process.model_validate(resource.definition)
    resolver = ApproverResolver(db, organization(user))
    for stage in process.stages:
        for selector in stage.selectors:
            if selector.kind in {"user", "group", "role", "organization_owner"}:
                resolver.resolve(selector, user.id, {})
    version = (
        db.query(PowerVersion)
        .filter_by(resource_id=resource.id, version=resource.version)
        .one()
    )
    runtime = (
        db.get(PowerResource, policy.runtime_resource_id)
        if policy.runtime_resource_id
        else None
    )
    if not runtime:
        runtime = PowerResource(
            **scope_values(policy),
            application_id="automations",
            name=resource.name + " — approval execution",
            definition=compile_process(process),
        )
        db.add(runtime)
        db.flush()
        record_change(db, user, runtime, "approval_runtime_created")
        policy.runtime_resource_id = runtime.id
    else:
        from app.apps.power_apps.runtime_models import AutomationDeployment

        deployment = (
            db.query(AutomationDeployment).filter_by(resource_id=runtime.id).first()
        )
        if deployment and deployment.status == "active":
            lifecycle(db, runtime, user, "pause", runtime.version)
        runtime.definition = compile_process(process)
        runtime.version += 1
        record_change(db, user, runtime, "approval_runtime_updated")
    identity = {
        "identity": "owner",
        "delegated_owner": True,
        "max_duration_seconds": 2592000,
    }  # bounded below to existing runtime maximum
    identity["max_duration_seconds"] = 604800
    for action in ["validate", "publish", "activate"]:
        lifecycle(db, runtime, user, action, runtime.version, identity)
    policy.published_version_id = version.id
    policy.enabled = True
    return policy


def submit(db, user, env, data):
    RequirePermission("power_apps_approval_submit")(user)
    validate_environment(db, user, env)
    existing = (
        scoped(db, RequestState, user, env)
        .filter_by(owner_user_id=user.id, submission_key=data.request_key)
        .first()
    )
    if existing:
        root = db.get(ApprovalRequest, existing.id)
        if (
            existing.policy_id != data.policy_id
            or existing.fields != data.fields
            or root.title != data.title
            or root.description != data.description
            or root.priority != data.priority
        ):
            raise HTTPException(409, "Submission key already refers to different input")
        return root, existing
    policy = (
        scoped(db, ApprovalPolicy, user, env)
        .filter_by(id=data.policy_id, enabled=True)
        .with_for_update()
        .first()
    )
    if not policy or not policy.published_version_id:
        raise HTTPException(409, "Choose an explicitly activated approval workflow")
    version = db.get(PowerVersion, policy.published_version_id)
    process = Process.model_validate(version.snapshot["definition"])
    validate_fields(process, data.fields)
    root = ApprovalRequest(
        organization_id=organization(user),
        source_module="power_apps",
        approval_type="universal",
        entity_type="power_approval_policy",
        entity_id=policy.id,
        title=data.title,
        description=data.description,
        requester_user_id=user.id,
        priority=data.priority,
        status="Pending",
        context_json={"power_apps": True, "environment": env},
    )
    db.add(root)
    db.flush()
    state = RequestState(
        organization_id=organization(user),
        environment=env,
        owner_user_id=user.id,
        id=root.id,
        policy_id=policy.id,
        version_id=version.id,
        fields=data.fields,
        submission_key=data.request_key,
    )
    db.add(state)
    db.flush()
    runtime = db.get(PowerResource, policy.runtime_resource_id)
    result = enqueue(
        db,
        runtime,
        user,
        {"approval_request_id": root.id, "fields": data.fields},
        "approval-" + str(root.id),
    )
    state.run_id = result.id
    evidence(db, root, state, user.id, "submitted", details={"fields": data.fields})
    notify(db, state, [user.id], "requested", root.title)
    return root, state


def stage_for(db, state):
    run = db.get(Run, state.run_id)
    step = db.get(Step, state.active_step_id)
    raw = next(n for n in run.plan["nodes"] if n["id"] == step.node_id)
    return Stage.model_validate(raw["config"]["stage"])


def _open_stage(db, run, step, config):
    id = run.input_payload.get("approval_request_id")
    state = (
        db.query(RequestState)
        .filter_by(
            id=id,
            run_id=run.id,
            organization_id=run.organization_id,
            environment=run.environment,
        )
        .with_for_update()
        .first()
    )
    if not state:
        raise ValueError("Approval node requires a linked authorized request")
    root = (
        db.query(ApprovalRequest)
        .filter_by(
            id=id, source_module="power_apps", organization_id=run.organization_id
        )
        .with_for_update()
        .one()
    )
    if root.status in TERMINAL:
        raise ValueError("Approval request is already closed")
    ensure_integrity(db, state)
    stage = Stage.model_validate(config["stage"])
    if stage.when and not condition(
        resolve(
            stage.when.model_dump(), {"trigger": {"input": {"fields": state.fields}}}
        )
    ):
        return False
    process = definition(db, state)
    if (
        process.documents_required
        and not db.query(Attachment).filter_by(request_id=id).first()
    ):
        root.status = "Resolution Required"
        evidence(db, root, state, None, "documents_required")
    state.active_step_id = step.id
    state.revision += 1
    assignments = (
        db.query(Assignment)
        .filter_by(request_id=id, step_id=step.id, cycle=state.cycle)
        .all()
    )
    if not assignments:
        try:
            ids = set()
            resolver = ApproverResolver(db, run.organization_id)
            for selector in stage.selectors:
                ids.update(
                    resolver.resolve(selector, root.requester_user_id, state.fields)
                )
            if root.requester_user_id in ids:
                raise HTTPException(422, "Requester cannot approve their own request")
            if stage.mode == "quorum" and stage.quorum > len(ids):
                raise HTTPException(422, "Quorum exceeds eligible approvers")
            from app.models.user import User

            if any(
                sum(str(db.get(User, uid).role_id) == role for uid in ids) < count
                for role, count in stage.role_quorum.items()
            ):
                raise HTTPException(
                    422, "The resolved group cannot satisfy its published role quorum"
                )
            for uid in sorted(ids):
                from app.models.user import User

                delegation = (
                    db.query(Delegation)
                    .filter(
                        Delegation.organization_id == run.organization_id,
                        Delegation.environment == run.environment,
                        Delegation.owner_user_id == uid,
                        Delegation.enabled.is_(True),
                        Delegation.starts_at <= now(),
                        Delegation.ends_at > now(),
                        or_(
                            Delegation.policy_id == state.policy_id,
                            Delegation.policy_id.is_(None),
                        ),
                    )
                    .all()
                )
                acting = uid
                delegation_id = None
                if stage.allow_delegation and delegation:
                    if len(delegation) != 1:
                        raise HTTPException(
                            422,
                            "Conflicting delegations require administrative resolution",
                        )
                    acting = delegation[0].alternate_user_id
                    delegation_id = delegation[0].id
                    resolver.eligible(acting)
                    if acting == root.requester_user_id or acting in ids:
                        raise HTTPException(
                            422, "Delegation violates independent participation"
                        )
                if resolver.on_leave(acting):
                    raise HTTPException(
                        422,
                        "Approver is on approved leave; configure an independent authorized alternate",
                    )
                if any(a.user_id == acting for a in assignments):
                    raise HTTPException(
                        422, "An alternate cannot occupy multiple approval seats"
                    )
                row = Assignment(
                    **scope_values(state),
                    request_id=id,
                    step_id=step.id,
                    stage_name=stage.name,
                    cycle=state.cycle,
                    user_id=acting,
                    original_user_id=uid,
                    role_id=db.get(User, uid).role_id,
                    delegation_id=delegation_id,
                    due_at=deadline(
                        step.started_at, stage.sla_seconds, process.business_calendar
                    ),
                    assigned_at=now(),
                )
                db.add(row)
                assignments.append(row)
            root.sla_due_at = deadline(
                step.started_at, stage.sla_seconds, process.business_calendar
            )
        except HTTPException as exc:
            # Do not leave a partially resolved group that could satisfy a quorum.
            for assignment in assignments:
                if assignment in db.new:
                    db.expunge(assignment)
            assignments = []
            root.status = "Resolution Required"
            evidence(db, root, state, None, "resolution_required", str(exc.detail))
            notify(db, state, [run.owner_user_id], "resolution_required", root.title)
    step.status = "waiting"
    step.active_ports = []
    step.output = None
    existing_wait = db.query(Wait).filter_by(step_id=step.id).first()
    if not existing_wait:
        db.add(
            Wait(
                **scope_values(run),
                run_id=run.id,
                step_id=step.id,
                kind="approval",
                event_key="approval:" + str(root.id),
                wake_at=min(
                    deadline(step.started_at, seconds, process.business_calendar)
                    for seconds in [
                        stage.remind_after_seconds,
                        stage.sla_seconds,
                        stage.expire_after_seconds,
                    ]
                ),
            )
        )
    evidence(
        db,
        root,
        state,
        None,
        "stage_assigned",
        details={
            "step_id": step.id,
            "stage": stage.name,
            "assignees": [a.user_id for a in assignments],
        },
    )
    notify(db, state, [a.user_id for a in assignments], "assigned", root.title)
    return True


def complete_wait(db, root, state, outcome):
    run = db.get(Run, state.run_id)
    step = db.get(Step, state.active_step_id)
    wait = (
        db.query(Wait)
        .filter_by(run_id=run.id, step_id=step.id, kind="approval", status="waiting")
        .with_for_update()
        .first()
    )
    if not wait:
        raise HTTPException(409, "This approval no longer has an active workflow wait")
    wait.status = "resumed"
    step.output = {"request_id": root.id, "status": outcome, "revision": state.revision}
    step.active_ports = ["out"] if outcome == "Approved" else ["rejected"]
    step.status = "completed"
    step.finished_at = now()
    for a in (
        db.query(Assignment)
        .filter_by(request_id=root.id, step_id=step.id, status="pending")
        .all()
    ):
        a.status = "closed"
    state.active_step_id = None
    advance(db, run)


def decide(db, user, env, id, data):
    RequirePermission("power_apps_approval_decide")(user)
    root, state = visible(db, user, env, id, True)
    ensure_integrity(db, state)
    assignment = (
        db.query(Assignment)
        .filter_by(id=data.assignment_id, request_id=id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not assignment or assignment.user_id != user.id:
        raise HTTPException(
            403, "Only the currently assigned independent approver may decide"
        )
    if root.requester_user_id == user.id:
        raise HTTPException(403, "Self approval is prohibited")
    ApproverResolver(db, state.organization_id).eligible(user.id)
    if assignment.status != "pending":
        if (
            assignment.decision_key == data.request_key
            and assignment.decision_actor_id == user.id
            and assignment.status
            == {"approve": "approved", "reject": "rejected", "changes": "changes"}[
                data.decision
            ]
            and assignment.decision_reason == data.reason
        ):
            return root, state
        raise HTTPException(409, "This assignment already has a decision or is closed")
    if (
        state.revision != data.expected_revision
        or state.active_step_id != assignment.step_id
        or assignment.cycle != state.cycle
        or root.status != "Pending"
    ):
        raise HTTPException(409, "Approval changed; reload before deciding")
    authority = None
    if assignment.delegation_id:
        ApproverResolver(db, state.organization_id).eligible(
            assignment.original_user_id
        )
        authority = db.get(Delegation, assignment.delegation_id)
        if (
            not authority
            or not authority.enabled
            or not utc(authority.starts_at) <= now() < utc(authority.ends_at)
        ):
            raise HTTPException(403, "Delegation authority expired")
    if any(
        a.decision_actor_id == user.id
        for a in db.query(Assignment)
        .filter_by(request_id=id, step_id=assignment.step_id, cycle=state.cycle)
        .all()
    ):
        raise HTTPException(403, "One person may occupy only one decision seat")
    stage = stage_for(db, state)
    required_roles = {
        role
        for selector in stage.selectors
        if selector.kind == "role"
        for role in selector.ids
    }
    original = db.get(
        User,
        assignment.original_user_id,
    )
    if (
        required_roles
        and all(selector.kind == "role" for selector in stage.selectors)
        and (not original or original.role_id not in required_roles)
    ):
        raise HTTPException(
            403, "The original role authority for this seat was revoked"
        )
    if str(assignment.role_id) in stage.role_quorum and (
        not original or original.role_id != assignment.role_id
    ):
        raise HTTPException(
            403, "The role authority required by this quorum was revoked"
        )
    if (
        data.decision in {"reject", "changes"}
        and stage.require_reason
        and not data.reason.strip()
    ):
        raise HTTPException(422, "A reason is required")
    assignment.status = {
        "approve": "approved",
        "reject": "rejected",
        "changes": "changes",
    }[data.decision]
    assignment.decision_actor_id = user.id
    assignment.decision_reason = data.reason
    assignment.decision_key = data.request_key
    assignment.decided_at = now()
    state.revision += 1
    evidence(
        db,
        root,
        state,
        user.id,
        data.decision,
        data.reason,
        {
            "assignment_id": assignment.id,
            "step_id": assignment.step_id,
            "original_user_id": assignment.original_user_id,
            "delegation_id": assignment.delegation_id,
            "decision_at": utc(assignment.decided_at).isoformat(),
            "delegation_context": (
                {
                    "id": authority.id,
                    "delegator_id": authority.owner_user_id,
                    "alternate_user_id": authority.alternate_user_id,
                    "starts_at": utc(authority.starts_at).isoformat(),
                    "ends_at": utc(authority.ends_at).isoformat(),
                    "reason": authority.reason,
                }
                if authority
                else None
            ),
            "actor_role_id": user.role_id,
        },
    )
    if data.decision == "changes":
        root.status = "Changes Requested"
        evidence(db, root, state, user.id, "changes_requested", data.reason)
        for a in (
            db.query(Assignment)
            .filter_by(request_id=id, step_id=assignment.step_id, status="pending")
            .all()
        ):
            a.status = "closed"
        notify(db, state, [root.requester_user_id], "changes_requested", root.title)
        return root, state
    rows = (
        db.query(Assignment)
        .filter_by(request_id=id, step_id=assignment.step_id, cycle=state.cycle)
        .all()
    )
    yes = sum(a.status == "approved" for a in rows)
    remaining = sum(a.status == "pending" for a in rows)
    threshold = (
        len(rows)
        if stage.mode == "all"
        else (
            1
            if stage.mode == "any"
            else len(rows) // 2 + 1 if stage.mode == "majority" else stage.quorum
        )
    )
    role_ok = all(
        sum(a.status == "approved" and str(a.role_id) == role for a in rows) >= count
        for role, count in stage.role_quorum.items()
    )
    role_possible = all(
        sum(
            a.status in {"approved", "pending"} and str(a.role_id) == role for a in rows
        )
        >= count
        for role, count in stage.role_quorum.items()
    )
    rejected = (
        (data.decision == "reject" and stage.reject_rule == "veto")
        or yes + remaining < threshold
        or not role_possible
    )
    if rejected:
        root.status = "Rejected"
        root.decided_by = user.id
        root.decided_at = now()
        root.decision_reason = data.reason
        evidence(db, root, state, user.id, "request_rejected", data.reason)
        complete_wait(db, root, state, "Rejected")
        notify(db, state, [root.requester_user_id], "rejected", root.title)
    elif yes >= threshold and role_ok:
        complete_wait(db, root, state, "Approved")
    return root, state


def runtime_finished(db, run, status):
    state = db.query(RequestState).filter_by(run_id=run.id).with_for_update().first()
    if not state:
        return
    root = (
        db.query(ApprovalRequest)
        .filter_by(id=state.id, source_module="power_apps")
        .with_for_update()
        .one()
    )
    for assignment in (
        db.query(Assignment).filter_by(request_id=root.id, status="pending").all()
    ):
        assignment.status = "closed"
    if not verify_history(db, state):
        return
    if root.status in TERMINAL:
        return
    root.status = (
        "Approved"
        if status == "completed"
        else "Cancelled" if status == "cancelled" else "Failed"
    )
    root.decided_at = now()
    state.revision += 1
    for a in db.query(Assignment).filter_by(request_id=root.id, status="pending").all():
        a.status = "closed"
    evidence(db, root, state, None, "workflow_" + status)
    notify(db, state, [root.requester_user_id], "completed", root.title)


def due(db, run, wait):
    state = db.query(RequestState).filter_by(run_id=run.id).with_for_update().first()
    if not state:
        return
    root = db.query(ApprovalRequest).filter_by(id=state.id).with_for_update().one()
    ensure_integrity(db, state)
    if root.status in TERMINAL:
        wait.status = "cancelled"
        return
    step = db.get(Step, wait.step_id)
    stage = stage_for(db, state)
    calendar = definition(db, state).business_calendar
    reminder_at = deadline(step.started_at, stage.remind_after_seconds, calendar)
    escalation_at = deadline(step.started_at, stage.sla_seconds, calendar)
    expiry_at = deadline(step.started_at, stage.expire_after_seconds, calendar)
    history = {
        r.event_type
        for r in db.query(ApprovalHistory).filter_by(request_id=root.id).all()
        if (r.details_json or {}).get("evidence", {}).get("details", {}).get("step_id")
        == step.id
        and (r.details_json or {}).get("evidence", {}).get("details", {}).get("cycle")
        == state.cycle
    }
    if now() >= expiry_at:
        root.status = "Expired"
        state.revision += 1
        evidence(db, root, state, None, "expired")
        finish(db, run, "cancelled")
        notify(db, state, [root.requester_user_id], "expired", root.title)
        return
    if now() >= reminder_at and "reminder" not in history:
        recipients = [
            a.user_id
            for a in db.query(Assignment).filter_by(
                request_id=root.id, step_id=step.id, status="pending"
            )
        ]
        notify(db, state, recipients, "reminder", root.title)
        evidence(db, root, state, None, "reminder", details={"step_id": step.id})
    if now() >= escalation_at and "escalated" not in history:
        root.escalated_at = now()
        recipients = [run.owner_user_id]
        if stage.escalation:
            try:
                recipients = ApproverResolver(db, run.organization_id).resolve(
                    stage.escalation, root.requester_user_id, state.fields
                )
                if stage.escalation_action == "reassign":
                    pending_assignments = (
                        db.query(Assignment)
                        .filter_by(
                            request_id=root.id, step_id=step.id, status="pending"
                        )
                        .order_by(Assignment.id)
                        .all()
                    )
                    occupied = {
                        a.user_id
                        for a in db.query(Assignment)
                        .filter_by(request_id=root.id, step_id=step.id)
                        .all()
                        if a.status != "pending"
                    }
                    if (
                        len(recipients) != len(pending_assignments)
                        or root.requester_user_id in recipients
                        or occupied.intersection(recipients)
                    ):
                        raise HTTPException(
                            422,
                            "Escalation recipients do not preserve independent approval seats",
                        )
                    for assignment, user_id in zip(
                        pending_assignments, sorted(recipients)
                    ):
                        assignment.user_id = user_id
                        assignment.delegation_id = None
            except HTTPException:
                root.status = "Resolution Required"
        evidence(db, root, state, None, "escalated", details={"step_id": step.id})
        notify(db, state, recipients, "escalated", root.title)
    pending = (
        [expiry_at]
        + ([reminder_at] if reminder_at > now() else [])
        + ([escalation_at] if escalation_at > now() else [])
    )
    wait.wake_at = min(pending)


from contextlib import contextmanager


@contextmanager
def domain(db):
    previous = db.info.get("power_approval_domain")
    db.info["power_approval_domain"] = True
    try:
        yield
    finally:
        if previous is None:
            db.info.pop("power_approval_domain", None)
        else:
            db.info["power_approval_domain"] = previous


def restart_revision(db, root, state, fields, actor, reason):
    """Materialize a new approval cycle in the same Phase 3 execution plan.

    Old decisions/steps remain intact; earlier approvals never carry over to changed data.
    """
    ensure_integrity(db, state)
    process = definition(db, state)
    validate_fields(process, fields)
    run = db.get(Run, state.run_id)
    old_step = db.get(Step, state.active_step_id)
    if not old_step or old_step.status != "waiting":
        raise HTTPException(409, "The approval wait is no longer active")
    wait = (
        db.query(Wait)
        .filter_by(step_id=old_step.id, kind="approval", status="waiting")
        .one()
    )
    state.fields = fields
    state.revision += 1
    state.cycle += 1
    raw = compile_process(process)
    prefix = f"r{state.cycle}_"
    additions = [copy.deepcopy(node) for node in raw["nodes"] if node["id"] != "start"]
    for node in additions:
        node["id"] = prefix + node["id"]
    plan = copy.deepcopy(run.plan)
    if len(plan["nodes"]) + len(additions) > 5000:
        raise HTTPException(
            422,
            "Resubmission exceeds the existing 5000-step execution budget; create a new request",
        )
    plan["nodes"] += additions
    for edge in raw["edges"]:
        edge = copy.deepcopy(edge)
        edge["id"] = prefix + edge["id"]
        edge["target"] = prefix + edge["target"]
        edge["source"] = (
            old_step.node_id if edge["source"] == "start" else prefix + edge["source"]
        )
        plan["edges"].append(edge)
    if len(json.dumps(plan)) > 2097152:
        raise HTTPException(422, "Resubmission exceeds the execution-plan budget")
    for step in db.query(Step).filter_by(run_id=run.id).all():
        if step.id != old_step.id and step.status in {"pending", "queued"}:
            step.status = "skipped"
            step.finished_at = now()
    for job in db.query(Job).filter_by(run_id=run.id, status="queued").all():
        job.status = "cancelled"
    wait.status = "resumed"
    old_step.output = {
        "request_id": root.id,
        "status": "Changes Requested",
        "superseded_by_cycle": state.cycle,
    }
    old_step.status = "completed"
    old_step.active_ports = ["out"]
    old_step.finished_at = now()
    run.plan = plan
    run.input_payload = {**run.input_payload, "fields": fields}
    for node in additions:
        db.add(
            Step(
                **scope_values(run),
                run_id=run.id,
                node_id=node["id"],
                original_node_id=node["id"][len(prefix) :],
                scope=f"resubmission_{state.cycle}",
                local_context={},
                status="pending",
            )
        )
    root.status = "Pending"
    root.sla_due_at = None
    state.active_step_id = None
    evidence(
        db,
        root,
        state,
        actor,
        "resubmitted",
        reason,
        {"fields": fields, "restart": "all_stages", "cycle": state.cycle},
    )
    db.flush()
    advance(db, run)


def open_stage(db, run, step, config):
    with db.no_autoflush:
        return _open_stage(db, run, step, config)
