"""Resolve authorized, active company identities. Ambiguity is never guessed."""

from datetime import date
from fastapi import HTTPException
from app.models.user import User
from app.models.employee import Employee
from app.models.company import Department
from app.core.tenant_boundary import company_ids
from app.apps.power_apps.approvals.contracts import Selector
from app.core.deps import RequirePermission


class ApproverResolver:
    def __init__(self, db, company):
        self.db = db
        self.company = company

    def eligible(self, user_id):
        user = self.db.get(User, user_id)
        if (
            not user
            or not user.is_active
            or self.company not in company_ids(self.db, user)
        ):
            raise HTTPException(422, "Approver is inactive or outside the company")
        from copy import copy
        from app.access.service import (
            check_background_access,
            resolved_grants,
            effective_objects,
        )

        actor = copy(user)
        actor.organization_id = self.company
        policy = check_background_access(self.db, actor, "power_apps", "view")
        actor._suite_permission_objects = (
            effective_objects(self.db, resolved_grants(self.db, policy), "power_apps")
            if policy
            else None
        )
        if policy and "approve" not in resolved_grants(self.db, policy).get(
            "power_apps", {}
        ).get("actions", []):
            raise HTTPException(
                422, "Approver lacks the current central approve action"
            )
        RequirePermission("power_apps_approval_decide")(actor)
        return user

    def resolve(self, selector, requester, fields):
        selector = Selector.model_validate(selector)
        ids = []
        if selector.kind in {"user", "group"}:
            ids = selector.ids
        elif selector.kind == "role":
            ids = [
                u.id
                for u in self.db.query(User)
                .filter(User.role_id.in_(selector.ids), User.is_active.is_(True))
                .all()
                if self.company in company_ids(self.db, u)
            ]
        elif selector.kind == "record_user":
            value = fields.get(selector.field)
            if type(value) is not int:
                raise HTTPException(
                    422, "Authorized form data does not identify an approver"
                )
            # Dynamic values are constrained by a published allowlist, never arbitrary requester IDs.
            if value not in selector.ids:
                raise HTTPException(
                    422, "Dynamic approver is outside the published allowlist"
                )
            ids = [value]
        elif selector.kind in {
            "reporting_manager",
            "department_manager",
            "department_head",
        }:
            from sqlalchemy import select
            from app.models.company import Branch

            employee, branch, department = (
                Employee.__table__,
                Branch.__table__,
                Department.__table__,
            )
            row = (
                self.db.connection()
                .execute(
                    select(employee.c.reporting_manager_id, employee.c.department_id)
                    .select_from(
                        employee.join(branch, employee.c.branch_id == branch.c.id)
                    )
                    .where(
                        employee.c.user_id == requester,
                        branch.c.company_id == self.company,
                    )
                )
                .first()
            )
            if not row:
                raise HTTPException(
                    422, "Requester has no authorized company reporting relationship"
                )
            manager_id = row[0]
            if selector.kind != "reporting_manager":
                manager_id = (
                    self.db.connection()
                    .execute(
                        select(department.c.head_employee_id)
                        .select_from(
                            department.join(
                                branch, department.c.branch_id == branch.c.id
                            )
                        )
                        .where(
                            department.c.id == row[1],
                            branch.c.company_id == self.company,
                        )
                    )
                    .scalar()
                )
            manager_user = (
                self.db.connection()
                .execute(
                    select(employee.c.user_id)
                    .select_from(
                        employee.join(branch, employee.c.branch_id == branch.c.id)
                    )
                    .where(
                        employee.c.id == manager_id, branch.c.company_id == self.company
                    )
                )
                .scalar()
                if manager_id
                else None
            )
            if not manager_user:
                raise HTTPException(
                    422, "The configured manager relationship is missing"
                )
            ids = [manager_user]
        elif selector.kind == "organization_owner":
            # Existing memberships have no universal owner field. Require explicit published owner identities.
            if len(selector.ids) != 1:
                raise HTTPException(
                    422, "Configure the verified organization owner identity explicitly"
                )
            ids = selector.ids
        ids = sorted(set(ids))
        if not ids or len(ids) > 30:
            raise HTTPException(
                422, "Approver resolution is empty or exceeds 30 identities"
            )
        for id in ids:
            self.eligible(id)
        return ids

    def on_leave(self, user_id):
        from sqlalchemy import select
        from app.models.leave import LeaveRequest
        from app.models.company import Branch

        employee, branch, leave = (
            Employee.__table__,
            Branch.__table__,
            LeaveRequest.__table__,
        )
        return (
            self.db.connection()
            .execute(
                select(leave.c.id)
                .select_from(
                    leave.join(employee, leave.c.employee_id == employee.c.id).join(
                        branch, employee.c.branch_id == branch.c.id
                    )
                )
                .where(
                    employee.c.user_id == user_id,
                    branch.c.company_id == self.company,
                    leave.c.status == "Approved",
                    leave.c.deleted_at.is_(None),
                    leave.c.from_date <= date.today(),
                    leave.c.to_date >= date.today(),
                )
                .limit(1)
            )
            .first()
            is not None
        )
