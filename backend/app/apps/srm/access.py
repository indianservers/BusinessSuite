from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.apps.srm.models import SRMEngagement, SRMSalesOrder
from app.models.user import User


SRM_VIEW_PERMISSIONS = {
    "srm_view",
    "srm_manage",
    "srm_admin",
    "srm_invoice_view",
    "srm_invoice_create",
    "srm_collection_view",
    "srm_profitability_view",
}
SRM_MANAGE_PERMISSIONS = {"srm_manage", "srm_admin"}
SRM_INVOICE_PERMISSIONS = {"srm_invoice_view", "srm_invoice_create", "srm_invoice_approve", "srm_admin"}
SRM_COLLECTION_PERMISSIONS = {"srm_collection_view", "srm_collection_create", "srm_admin"}
SRM_PROFITABILITY_PERMISSIONS = {"srm_profitability_view", "srm_admin"}


def normalize_role(role: str | None) -> str:
    return (role or "").lower().replace(" ", "_")


def organization_id_for(user: User) -> int | None:
    return getattr(user, "organization_id", None)


def user_permission_names(user: User) -> set[str]:
    if user.is_superuser:
        return {"*"}
    return {permission.name for permission in (user.role.permissions if user.role else [])}


def has_any_permission(user: User, permissions: set[str]) -> bool:
    names = user_permission_names(user)
    return "*" in names or bool(names.intersection(permissions))


def can_view_all_srm(user: User) -> bool:
    role = normalize_role(user.role.name if user.role else None)
    return user.is_superuser or role in {
        "srm_admin",
        "srm_sales_manager",
        "srm_finance_manager",
        "srm_revenue_manager",
        "srm_business_owner",
        "srm_viewer",
        "super_admin",
    }


def sales_order_query(db: Session, user: User):
    query = db.query(SRMSalesOrder).filter(SRMSalesOrder.deleted_at == None)
    if user.is_superuser:
        return query
    if can_view_all_srm(user):
        return query.filter(SRMSalesOrder.organization_id == organization_id_for(user))
    return query.filter(SRMSalesOrder.assigned_user_id == user.id)


def engagement_query(db: Session, user: User):
    query = db.query(SRMEngagement).filter(SRMEngagement.deleted_at == None)
    if user.is_superuser:
        return query
    if can_view_all_srm(user):
        return query.filter(SRMEngagement.organization_id == organization_id_for(user))
    return query.filter((SRMEngagement.assigned_user_id == user.id) | (SRMEngagement.project_manager_user_id == user.id))


def get_sales_order_for_user(db: Session, sales_order_id: int, user: User) -> SRMSalesOrder:
    item = sales_order_query(db, user).filter(SRMSalesOrder.id == sales_order_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Sales order not found")
    return item


def get_engagement_for_user(db: Session, engagement_id: int, user: User) -> SRMEngagement:
    item = engagement_query(db, user).filter(SRMEngagement.id == engagement_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return item

