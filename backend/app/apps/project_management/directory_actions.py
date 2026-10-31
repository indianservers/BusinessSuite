"""Reviewed directory membership actions. Every write rechecks tenant and destination scope."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, case
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.employee import Employee
from app.models.audit import AuditLog
from app.apps.interns_hub.management_models import InternBatch, InternBatchMembership
from .models import PMSProject, PMSProjectMember, PMSWorkspaceMember, PMSWorkspaceTeam, PMSWorkspaceTeamMember
from .access import accessible_project_query, can_access_project, organization_id_for
from .people_management import scoped_workspace, preview_data, record

router = APIRouter(prefix="/actions", tags=["Directory membership actions"])
KINDS = Literal["projects", "teams", "batches"]


class ActionInput(BaseModel):
    kind: KINDS
    action: Literal["add", "transfer", "remove", "role"] = "add"
    user_ids: list[int] = Field(min_length=1, max_length=100)
    destination_ids: list[int] = Field(min_length=1, max_length=10)
    source_id: int | None = None
    role: Literal["Member", "Viewer"] = "Member"
    reason: str = Field(min_length=3, max_length=1000)
    version: str | None = None


def _destination(db, actor, kind, identity, write=False):
    from .people_workspace import teams_query, batches_query
    if kind == "projects":
        item = accessible_project_query(db, actor).filter(PMSProject.id == identity).first()
        allowed = bool(item and can_access_project(db, item, actor, "manage_members"))
        if item and write and item.workspace_id:
            scoped_workspace(db, item.workspace_id, actor)
    elif kind == "teams":
        item = teams_query(db, actor).filter(PMSWorkspaceTeam.id == identity).first()
        try:
            if item: scoped_workspace(db, item.workspace_id, actor)
            allowed = bool(item)
        except HTTPException:
            allowed = False
    else:
        item = batches_query(db, actor).filter(InternBatch.id == identity).first()
        allowed = bool(item and item.status not in {"Completed", "Archived"})
    if not item: raise HTTPException(404, "Destination is outside your authorized scope")
    if write and not allowed: raise HTTPException(403, "Destination administration access is required, or this batch is closed")
    return item, allowed


def _membership(db, kind, identity, person):
    if kind == "projects": return db.query(PMSProjectMember).filter_by(project_id=identity, user_id=person.id).first()
    if kind == "teams": return db.query(PMSWorkspaceTeamMember).filter_by(team_id=identity, user_id=person.id).first()
    return db.query(InternBatchMembership).filter_by(batch_id=identity, employee_id=person.employee.id, status="Active").first() if person.employee else None


def _count(db, kind, identity):
    if kind == "projects": return db.query(PMSProjectMember).filter_by(project_id=identity).count()
    if kind == "teams": return db.query(PMSWorkspaceTeamMember).filter_by(team_id=identity).count()
    return db.query(InternBatchMembership).filter_by(batch_id=identity, status="Active").count()


@router.get("/destinations")
def destinations(kind: KINDS, q: str = Query("", max_length=150), preferred: str = Query("", max_length=1000), page: int = Query(1, ge=1), db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    from .people_workspace import teams_query, batches_query, scope, load_users
    query = accessible_project_query(db, actor) if kind == "projects" else teams_query(db, actor) if kind == "teams" else batches_query(db, actor)
    model = PMSProject if kind == "projects" else PMSWorkspaceTeam if kind == "teams" else InternBatch
    if q: query = query.filter(model.name.ilike(f"%{q}%"))
    total = query.count()
    rows = []
    preferred_ids = [int(i) for i in preferred.split(",") if i.isdigit()][:30]
    for item in query.order_by(case((model.id.in_(preferred_ids), 0), else_=1), model.name, model.id).offset((page-1)*30).limit(30):
        _, allowed = _destination(db, actor, kind, item.id)
        responsible_id = getattr(item, "lead_user_id", None) or getattr(item, "manager_user_id", None)
        leader = load_users(scope(db, actor).filter(User.id == responsible_id)).first() if responsible_id else None
        people_ids = db.query(PMSProjectMember.user_id).filter_by(project_id=item.id) if kind == "projects" else db.query(PMSWorkspaceTeamMember.user_id).filter_by(team_id=item.id) if kind == "teams" else db.query(Employee.user_id).join(InternBatchMembership, InternBatchMembership.employee_id == Employee.id).filter(InternBatchMembership.batch_id == item.id, InternBatchMembership.status == "Active")
        avatars = load_users(scope(db, actor).filter(User.id.in_(people_ids))).limit(3).all()
        count = _count(db, kind, item.id)
        rows.append({"id": item.id, "name": item.name, "kind": kind, "members": count,
            "capacity": getattr(item, "capacity", None), "batch_type": getattr(item, "batch_type", None), "available": max(0, item.capacity-count) if kind == "batches" else None,
            "status": getattr(item, "status", None), "start_date": getattr(item, "start_date", None), "end_date": getattr(item, "end_date", None),
            "lead": (leader.person.display_name if leader.person else leader.email) if leader else None,
            "avatars": [{"name": u.person.display_name if u.person else u.email} for u in avatars],
            "can_manage": allowed, "reason": None if allowed else "Administration access is required, or this batch is closed."})
    return {"items": rows, "total": total, "pages": (total+29)//30, "page": page}


@router.get("/selection")
def selection(ids: str = Query(..., max_length=1500), db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    from .people_workspace import scope, load_users, task_stats, serialize
    chosen = {int(i) for i in ids.split(",") if i.isdigit()}
    if not chosen or len(chosen)>100: raise HTTPException(422, "Select 1–100 people")
    accounts = load_users(scope(db, actor).filter(User.id.in_(chosen))).all()
    if {u.id for u in accounts} != chosen: raise HTTPException(404, "Selected people are outside your scope")
    identities = {p["id"]: p for p in serialize(db, actor, accounts)}
    visible_projects = accessible_project_query(db, actor).with_entities(PMSProject.id)
    projects = db.query(PMSProjectMember.user_id, PMSProjectMember.project_id).filter(PMSProjectMember.user_id.in_(chosen), PMSProjectMember.project_id.in_(visible_projects)).all()
    return {"people": [{**identities[u.id], "workload": task_stats(db, actor, [u.id])[1], "memberships": {"projects": [p.project_id for p in projects if p.user_id == u.id], "teams": [t["id"] for t in identities[u.id]["teams"]], "batches": [b["id"] for b in identities[u.id]["batches"]]}} for u in accounts]}


def _removal_guard(db, actor, kind, item, person):
    impact = preview_data(db, actor, person, item.workspace_id if kind == "teams" else None, item.id if kind == "projects" else item.project_id if kind == "batches" else None)
    if any(impact[key] for key in ["tasks", "projects", "approvals", "workflow_approvals", "blockers"]):
        raise HTTPException(409, "Open work or approvals require handover in Manage person before removing or transferring this membership.")


def _preview(db, actor, data):
    from .people_workspace import scope, load_users, task_stats
    if len(set(data.user_ids))*len(set(data.destination_ids)) > 500: raise HTTPException(422, "At most 500 person/destination combinations are supported")
    if data.action == "transfer" and (not data.source_id or data.source_id in data.destination_ids): raise HTTPException(422, "Choose a different source for transfer")
    if data.action == "role" and data.kind != "projects": raise HTTPException(422, "Bulk role changes apply to project Member/Viewer roles; team and batch membership has no separate role")
    people = {p.id: p for p in load_users(scope(db, actor).filter(User.id.in_(data.user_ids))).all()}
    if set(people) != set(data.user_ids): raise HTTPException(404, "One or more selected people are outside your scope")
    targets = [_destination(db, actor, data.kind, i, True)[0] for i in sorted(set(data.destination_ids))]
    source = _destination(db, actor, data.kind, data.source_id, True)[0] if data.action == "transfer" else None
    rows, allocations = [], {}
    for uid in sorted(people):
        person = people[uid]
        workload = task_stats(db, actor, [uid])[1]
        for item in targets:
            existing = _membership(db, data.kind, item.id, person)
            row = {"user_id": uid, "name": person.person.display_name if person.person else person.email, "email": person.email,
                "destination_id": item.id, "destination_name": item.name, "current_role": getattr(existing, "role", None),
                "open_tasks": workload["pending"], "overdue_tasks": workload["overdue"], "status": "ready", "reason": None,
                "workspace_access_added": False, "source": source.name if source else None}
            try:
                if not person.is_active: raise HTTPException(409, "Reactivate this account before changing memberships")
                if data.kind == "batches":
                    e = person.employee
                    if not e or e.deleted_at or e.status not in {"Active", "Probation"}: raise HTTPException(422, "An active employee record is required")
                    intern = (e.employment_type or "").lower() == "intern"
                    if (item.batch_type == "Intern" and not intern) or (item.batch_type == "Employee" and intern): raise HTTPException(422, "This person does not match the batch type")
                else:
                    if item.workspace_id:
                        scoped_workspace(db, item.workspace_id, actor)
                        workspace_member = db.query(PMSWorkspaceMember).filter_by(workspace_id=item.workspace_id, user_id=uid).first()
                        if workspace_member and workspace_member.role == "Guest" and data.action in {"add", "transfer"}: raise HTTPException(409, "Review the Guest workspace role in Manage person first")
                        row["workspace_access_added"] = not workspace_member and data.action in {"add", "transfer"}
                if data.action in {"remove", "role"}:
                    if not existing: row["status"] = "skipped"; row["reason"] = "No direct membership exists"
                    elif data.kind == "projects" and (item.owner_user_id == uid or item.manager_user_id == uid or existing.role not in {"Member", "Viewer"}): raise HTTPException(409, "Owner, manager, and administrator roles must be reviewed in Manage person")
                    elif data.action == "remove" or data.role == "Viewer": _removal_guard(db, actor, data.kind, item, person)
                elif existing:
                    row["status"] = "already_present"
                if source:
                    source_seat = _membership(db, data.kind, source.id, person)
                    row["source_membership_id"] = getattr(source_seat, "id", None)
                    row["source_role"] = getattr(source_seat, "role", None)
                    if not source_seat: raise HTTPException(409, "Person is not an active member of the selected source")
                    _removal_guard(db, actor, data.kind, source, person)
                    if existing: row["status"] = "ready"  # source still needs removal
                if data.kind == "batches" and not existing and data.action in {"add", "transfer"}:
                    used = _count(db, data.kind, item.id)+allocations.get(item.id, 0)
                    if used >= item.capacity: raise HTTPException(409, "Batch capacity would be exceeded")
                    allocations[item.id] = allocations.get(item.id, 0)+1
                row["membership_id"] = getattr(existing, "id", None)
            except HTTPException as exc:
                row["status"] = "failed"; row["reason"] = str(exc.detail)
            rows.append(row)
    if source and len(targets) != 1: raise HTTPException(422, "Transfer to one destination at a time")
    state = {"actor": actor.id, "company": organization_id_for(actor), "request": data.model_dump(exclude={"version"}), "rows": rows}
    version = hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()
    return {"rows": rows, "version": version, "action": data.action, "kind": data.kind}, people, targets, source


@router.post("/preview")
def preview(data: ActionInput, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    return _preview(db, actor, data)[0]


def _remove(db, kind, item, person, reason="Directory membership undo", transferred=False):
    membership = _membership(db, kind, item.id, person)
    if not membership: return
    if kind == "batches":
        membership.status = "Transferred" if transferred else "Inactive"; membership.active_slot = None; membership.left_at = datetime.now(timezone.utc); membership.reason = reason
    else: db.delete(membership)


def _add(db, actor, kind, item, person, reason="Directory membership update", source_id=None):
    added = []
    if kind != "batches" and item.workspace_id and not db.query(PMSWorkspaceMember).filter_by(workspace_id=item.workspace_id, user_id=person.id).first():
        db.add(PMSWorkspaceMember(workspace_id=item.workspace_id, user_id=person.id, role="Member"))
        added.append({"kind": "workspaces", "id": item.workspace_id})
    if not _membership(db, kind, item.id, person):
        if kind == "projects": db.add(PMSProjectMember(project_id=item.id, user_id=person.id, role="Member"))
        elif kind == "teams": db.add(PMSWorkspaceTeamMember(team_id=item.id, user_id=person.id))
        else: db.add(InternBatchMembership(batch_id=item.id, employee_id=person.employee.id, assigned_by=actor.id, status="Active", active_slot=1, reason=reason, previous_batch_id=source_id))
        added.append({"kind": kind, "id": item.id})
    if kind == "teams":
        db.flush()
        item.member_ids_json = json.dumps(sorted(m.user_id for m in db.query(PMSWorkspaceTeamMember).filter_by(team_id=item.id)))
    db.flush()
    for addition in added:
        seat = db.query(PMSWorkspaceMember).filter_by(workspace_id=addition["id"], user_id=person.id).first() if addition["kind"] == "workspaces" else _membership(db, kind, item.id, person)
        addition["membership_id"] = getattr(seat, "id", None)
    return added


@router.post("/apply")
def apply(data: ActionInput, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    # Serialize capacity and membership checks for these destinations in Postgres.
    model = PMSProject if data.kind == "projects" else PMSWorkspaceTeam if data.kind == "teams" else InternBatch
    db.query(model).filter(model.id.in_(sorted(set(data.destination_ids+([data.source_id] if data.source_id else []))))).order_by(model.id).with_for_update().all()
    plan, people, targets, source = _preview(db, actor, data)
    if not data.version or plan["version"] != data.version: raise HTTPException(409, "Membership or workload changed. Review a fresh preview.")
    results, undo_ids = [], []
    from sqlalchemy.exc import SQLAlchemyError
    by_id = {item.id: item for item in targets}
    for uid in sorted(people):
        person_rows = [r for r in plan["rows"] if r["user_id"] == uid]
        if any(r["status"] == "failed" for r in person_rows):
            results.extend([{**r, "status": "failed", "reason": r["reason"] or "Another selected destination failed; no changes made for this person"} for r in person_rows]); continue
        try:
            person_results, person_undo = [], []
            with db.begin_nested():
                additions = []
                for row in person_rows:
                    if row["status"] != "ready": person_results.append(row); continue
                    item, person = by_id[row["destination_id"]], people[uid]
                    before = {"role": getattr(_membership(db, data.kind, item.id, person), "role", None), "source": source.id if source else None}
                    if data.action in {"add", "transfer"}: additions.extend(_add(db, actor, data.kind, item, person, data.reason, source.id if source else None))
                    elif data.action == "remove": _remove(db, data.kind, item, person, data.reason)
                    else: _membership(db, data.kind, item.id, person).role = data.role
                    if source: _remove(db, data.kind, source, person, data.reason, transferred=True)
                    if data.kind == "teams":
                        db.flush()
                        for team in [item]+([source] if source else []): team.member_ids_json = json.dumps(sorted(m.user_id for m in db.query(PMSWorkspaceTeamMember).filter_by(team_id=team.id)))
                    record(db, actor, uid, "PMS_DIRECTORY_MEMBERSHIP", data.reason, before=before, after={"action": data.action, "kind": data.kind, "destination": item.name, "role": data.role if data.action == "role" else "Member"}, project_id=item.id if data.kind == "projects" else None, workspace_id=getattr(item, "workspace_id", None))
                if additions and data.action == "add":
                    log = AuditLog(organization_id=organization_id_for(actor), user_id=actor.id, actor_email=actor.email, method="POST", module="project_management", entity_type="user", entity_id=uid, action="PMS_DIRECTORY_UNDO", description="Reversible directory membership additions", new_values=json.dumps({"additions": additions, "expires": (datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()}))
                    db.add(log); db.flush(); person_undo.append(log.id)
                db.flush()
            results.extend(person_results)
            undo_ids.extend(person_undo)
            results.extend([{**r, "status": "applied"} for r in person_rows if r["status"] == "ready"])
        except (HTTPException, SQLAlchemyError) as exc:
            results.extend([{**r, "status": "failed", "reason": str(exc.detail) if isinstance(exc, HTTPException) else "Membership changed concurrently. Review and retry this person."} for r in person_rows])
    db.commit()
    return {"rows": results, "undo_ids": undo_ids, "failed_user_ids": sorted({r["user_id"] for r in results if r["status"] == "failed"})}


@router.post("/{log_id}/undo")
def undo(log_id: int, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    log = db.query(AuditLog).filter_by(id=log_id, organization_id=organization_id_for(actor), user_id=actor.id, action="PMS_DIRECTORY_UNDO").with_for_update().first()
    if not log: raise HTTPException(404, "Undo operation not found")
    payload = json.loads(log.new_values)
    if datetime.fromisoformat(payload["expires"]) < datetime.now(timezone.utc): raise HTTPException(409, "Undo expired; review memberships in Manage person")
    from .people_workspace import scope, load_users
    person = load_users(scope(db, actor).filter(User.id == log.entity_id)).first()
    if not person: raise HTTPException(404, "Person is no longer in your scope")
    if db.query(AuditLog.id).filter(AuditLog.organization_id == log.organization_id, AuditLog.entity_id == person.id, AuditLog.entity_type == "user", AuditLog.id > log.id, AuditLog.action.like("PMS_%")).first(): raise HTTPException(409, "Memberships changed after this operation; review them in Manage person")
    for addition in reversed(payload["additions"]):
        if addition["kind"] == "workspaces":
            member = db.query(PMSWorkspaceMember).filter_by(workspace_id=addition["id"], user_id=person.id).first()
            # Do not implicitly remove newer teams or project seats.
            project_ids = db.query(PMSProject.id).filter_by(workspace_id=addition["id"])
            team_ids = db.query(PMSWorkspaceTeam.id).filter_by(workspace_id=addition["id"])
            if db.query(PMSProjectMember).filter(PMSProjectMember.project_id.in_(project_ids), PMSProjectMember.user_id == person.id).first() or db.query(PMSWorkspaceTeamMember).filter(PMSWorkspaceTeamMember.team_id.in_(team_ids), PMSWorkspaceTeamMember.user_id == person.id).first(): raise HTTPException(409, "Other memberships now depend on workspace access; review in Manage person")
            if member and (member.id != addition.get("membership_id") or member.role != "Member"):
                raise HTTPException(409, "Workspace membership changed after this addition; review in Manage person")
            if member:
                scoped_workspace(db, member.workspace_id, actor)
                impact = preview_data(db, actor, person, member.workspace_id)
                if any(impact[k] for k in ["tasks", "projects", "approvals", "workflow_approvals", "owned_workspace_ids"]): raise HTTPException(409, "New work depends on this access; undo is unavailable")
                db.delete(member)
        else:
            item, _ = _destination(db, actor, addition["kind"], addition["id"], True)
            seat = _membership(db, addition["kind"], item.id, person)
            if seat and (getattr(seat, "id", None) != addition.get("membership_id") or getattr(seat, "role", "Member") != "Member"):
                raise HTTPException(409, "Membership changed after this addition; review in Manage person")
            _removal_guard(db, actor, addition["kind"], item, person)
            _remove(db, addition["kind"], item, person)
            db.flush()
            if addition["kind"] == "teams": item.member_ids_json = json.dumps(sorted(m.user_id for m in db.query(PMSWorkspaceTeamMember).filter_by(team_id=item.id)))
    log.action = "PMS_DIRECTORY_UNDONE"
    record(db, actor, person.id, "PMS_DIRECTORY_UNDONE", "Undid eligible directory additions")
    db.commit()
    return {"message": "Eligible membership additions undone"}
