from sqlalchemy.orm import Session

from app.common.services.identity import SharedIdentityService
from app.core.security import get_password_hash
from app.module_registry import is_app_enabled
from app.models.user import Permission, Role, User


COMMON_PERMISSIONS = [
    ("settings_view", "View platform settings", "settings"),
    ("settings_manage", "Manage platform settings", "settings"),
    ("reports_view", "View reports", "reports"),
    ("workflow_view", "View workflow inbox", "workflow"),
    ("notification_view", "View notification inbox", "notification"),
    ("pms_view", "View project management records", "project_management"),
    ("pms_manage_projects", "Manage projects and members", "project_management"),
    ("pms_manage_tasks", "Manage tasks, boards, and milestones", "project_management"),
    ("pms_time_manage", "Manage time logs and approvals", "project_management"),
    ("pms_client_portal", "Access project client portal", "project_management"),
    ("pms_admin", "Manage project settings and admin areas", "project_management"),
    ("srm_view", "View sales and revenue management records", "srm"),
    ("srm_manage", "Manage SRM sales orders, contracts, engagements, and billing", "srm"),
    ("srm_admin", "Administer SRM settings and lifecycle controls", "srm"),
    ("srm_invoice_view", "View SRM invoices", "srm"),
    ("srm_invoice_create", "Create SRM invoice drafts and invoices", "srm"),
    ("srm_invoice_approve", "Approve SRM invoices and sales orders", "srm"),
    ("srm_collection_view", "View SRM collections and aging", "srm"),
    ("srm_collection_create", "Create SRM receipts, allocations, and reminders", "srm"),
    ("srm_profitability_view", "View SRM profitability", "srm"),
    ("srm_settings_manage", "Manage SRM settings", "srm"),
]

COMMON_ROLES = [
    {
        "name": "super_admin",
        "description": "Full system access",
        "permissions": [item[0] for item in COMMON_PERMISSIONS],
    }
]


def init_common_db(db: Session) -> None:
    perm_map = {}
    for name, description, module in COMMON_PERMISSIONS:
        perm = db.query(Permission).filter(Permission.name == name).first()
        if not perm:
            perm = Permission(name=name, description=description, module=module)
            db.add(perm)
            db.flush()
        perm_map[name] = perm

    for role_data in COMMON_ROLES:
        role = db.query(Role).filter(Role.name == role_data["name"]).first()
        if not role:
            role = Role(name=role_data["name"], description=role_data["description"], is_system=True)
            db.add(role)
            db.flush()
        role.permissions = [perm_map[name] for name in role_data["permissions"] if name in perm_map]

    role = db.query(Role).filter(Role.name == "super_admin").first()
    user = db.query(User).filter(User.email == "admin@platform.local").first()
    if not user and role:
        user = User(
            email="admin@platform.local",
            hashed_password=get_password_hash("Admin@123456"),
            is_active=True,
            is_superuser=True,
            role_id=role.id,
        )
        db.add(user)
        db.flush()

    if user:
        SharedIdentityService.ensure_person_for_user(
            db,
            user,
            display_name="Platform Admin",
            source_module="common",
            source_record_type="user",
            source_record_id=user.id,
        )

    if is_app_enabled("hrms"):
        from app.models.employee import Employee

        employees = db.query(Employee).filter(Employee.user_id.isnot(None), Employee.deleted_at.is_(None)).limit(1000).all()
        for employee in employees:
            SharedIdentityService.sync_from_employee(db, employee)

    db.commit()
