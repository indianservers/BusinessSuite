"""Exact Power Apps approval participants for the shared ORM scope guard."""

from sqlalchemy import select, and_, or_, false


def predicate(model, user, company, grants):
    if getattr(user, "_suite_current_module", None) != "power_apps":
        return None
    grant = grants.get("power_apps", {})
    if not grant.get("enabled"):
        return false()
    from app.apps.power_apps.approvals.models import (
        RequestState,
        Assignment,
        ApprovalPolicy,
    )
    from app.models.approval_os import ApprovalRequest, ApprovalHistory, ApprovalComment
    from app.apps.power_apps.models import PowerResource, PowerVersion, PowerExecution

    state = RequestState.__table__
    assignment = Assignment.__table__
    policy = ApprovalPolicy.__table__
    admin = "power_apps_approval_manage" in grant.get("permissions", [])
    participant = or_(
        state.c.owner_user_id == user.id,
        state.c.id.in_(
            select(assignment.c.request_id).where(
                assignment.c.organization_id == company,
                or_(
                    assignment.c.user_id == user.id,
                    assignment.c.original_user_id == user.id,
                ),
            )
        ),
    )
    visible = select(state.c.id).where(
        state.c.organization_id == company, True if admin else participant
    )
    if model is ApprovalRequest:
        return and_(
            model.organization_id == company,
            model.source_module == "power_apps",
            model.id.in_(visible),
        )
    if model in {ApprovalHistory, ApprovalComment}:
        return model.request_id.in_(visible)
    if model is RequestState:
        return and_(model.organization_id == company, model.id.in_(visible))
    if model is Assignment:
        return and_(model.organization_id == company, model.request_id.in_(visible))
    if model.__tablename__ == "power_approval_delegations":
        return and_(
            model.organization_id == company,
            or_(
                model.owner_user_id == user.id,
                model.alternate_user_id == user.id,
                admin,
            ),
        )
    if model.__tablename__ == "power_approval_attachments":
        return and_(model.organization_id == company, model.request_id.in_(visible))
    if model is ApprovalPolicy:
        return model.organization_id == company
    public_runtime = select(policy.c.runtime_resource_id).where(
        policy.c.organization_id == company
    )
    visible_runs = select(state.c.run_id).where(
        state.c.organization_id == company, True if admin else participant
    )
    if model is PowerExecution:
        return and_(
            model.organization_id == company,
            or_(
                model.owner_user_id == user.id,
                grant.get("scope") == "organization",
                model.id.in_(visible_runs),
            ),
        )
    if (
        model.__module__ == "app.apps.power_apps.runtime_models"
        and model.__tablename__
        not in {
            "power_automation_workers",
            "power_automation_triggers",
            "power_automation_deployments",
        }
    ):
        column = (
            model.id
            if model.__tablename__ == "power_automation_run_states"
            else getattr(model, "run_id", None)
        )
        if column is not None:
            return and_(
                model.organization_id == company,
                or_(
                    model.owner_user_id == user.id,
                    grant.get("scope") == "organization",
                    column.in_(visible_runs),
                ),
            )
    if model is PowerResource:
        return and_(
            model.organization_id == company,
            or_(
                model.owner_user_id == user.id,
                grant.get("scope") == "organization",
                model.application_id == "approvals",
                model.id.in_(public_runtime),
            ),
        )
    if model is PowerVersion:
        resources = select(PowerResource.__table__.c.id).where(
            PowerResource.__table__.c.organization_id == company,
            PowerResource.__table__.c.application_id == "approvals",
        )
        return and_(
            model.organization_id == company,
            or_(
                model.owner_user_id == user.id,
                grant.get("scope") == "organization",
                model.resource_id.in_(resources),
                model.resource_id.in_(public_runtime),
            ),
        )
    return None


def domain_write(db, item, user, company):
    """A private server operation marker never arrives from request JSON.

    Domain services first enforce exact RBAC, participant checks and lock order.
    This permits their cross-participant inserts without widening generic CRUD.
    Tenant and FK boundary guards continue to run independently.
    """
    if not db.info.get("power_approval_domain"):
        return False
    from app.models.approval_os import ApprovalRequest, ApprovalHistory, ApprovalComment
    from app.models.notification import Notification, NotificationDeliveryLog
    from app.apps.power_apps.models import (
        PowerResource,
        PowerVersion,
        PowerExecution,
        PowerActivity,
    )
    from app.apps.power_apps.runtime_models import (
        AutomationDeployment,
        AutomationRun,
        AutomationStep,
        AutomationJob,
        AutomationEvent,
        AutomationWait,
    )

    approval = item.__class__.__module__.startswith("app.apps.power_apps.approvals.")
    allowed = approval or isinstance(
        item,
        (
            ApprovalRequest,
            ApprovalHistory,
            ApprovalComment,
            Notification,
            NotificationDeliveryLog,
            PowerResource,
            PowerVersion,
            PowerExecution,
            PowerActivity,
            AutomationDeployment,
            AutomationRun,
            AutomationStep,
            AutomationJob,
            AutomationEvent,
            AutomationWait,
        ),
    )
    if not allowed:
        return False
    organization = getattr(
        item, "organization_id", getattr(item, "company_id", company)
    )
    if organization is not None and organization != company:
        return False
    if isinstance(item, ApprovalRequest) and item.source_module != "power_apps":
        return False
    return True
