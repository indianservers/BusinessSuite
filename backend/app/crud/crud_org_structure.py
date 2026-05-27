from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session


class OrgStructureCRUD:
    def __init__(
        self,
        model: type,
        *,
        name_attr: str = "name",
        code_attr: str = "code",
        organization_attr: str = "organization_id",
        company_attr: str | None = "company_id",
    ):
        self.model = model
        self.name_attr = name_attr
        self.code_attr = code_attr
        self.organization_attr = organization_attr
        self.company_attr = company_attr

    def get_all(self, db: Session, *, organization_id: int | None = None, include_inactive: bool = False) -> list[Any]:
        query = db.query(self.model)
        if hasattr(self.model, "is_active") and not include_inactive:
            query = query.filter(self.model.is_active == True)
        if organization_id is not None:
            if hasattr(self.model, self.organization_attr) and self.company_attr and hasattr(self.model, self.company_attr):
                query = query.filter(or_(
                    getattr(self.model, self.organization_attr) == organization_id,
                    getattr(self.model, self.company_attr) == organization_id,
                ))
            elif hasattr(self.model, self.organization_attr):
                query = query.filter(getattr(self.model, self.organization_attr) == organization_id)
            elif self.company_attr and hasattr(self.model, self.company_attr):
                query = query.filter(getattr(self.model, self.company_attr) == organization_id)
        return query.order_by(getattr(self.model, self.name_attr).asc()).all()

    def get_by_id(self, db: Session, item_id: int) -> Any | None:
        return db.query(self.model).filter(self.model.id == item_id).first()

    def create(self, db: Session, *, data: dict[str, Any], created_by: int | None = None) -> Any:
        payload = self._to_model_payload(data)
        if created_by is not None and hasattr(self.model, "created_by"):
            payload["created_by"] = created_by
        item = self.model(**payload)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def update(self, db: Session, *, item: Any, data: dict[str, Any]) -> Any:
        for key, value in self._to_model_payload(data).items():
            if hasattr(item, key):
                setattr(item, key, value)
        db.commit()
        db.refresh(item)
        return item

    def soft_delete(self, db: Session, *, item: Any) -> Any:
        item.is_active = False
        db.commit()
        db.refresh(item)
        return item

    def _to_model_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        payload = dict(data)
        organization_id = payload.get("organization_id")
        if self.company_attr and organization_id is not None and hasattr(self.model, self.company_attr):
            payload.setdefault(self.company_attr, organization_id)
        if self.name_attr != "name" and "name" in payload:
            payload[self.name_attr] = payload.pop("name")
        if self.code_attr != "code" and "code" in payload:
            payload[self.code_attr] = payload.pop("code")
        return {
            key: value
            for key, value in payload.items()
            if hasattr(self.model, key)
        }


def to_org_response(item: Any, *, name_attr: str = "name", code_attr: str = "code") -> dict[str, Any]:
    organization_id = getattr(item, "organization_id", None) or getattr(item, "company_id", None)
    response = {
        "id": item.id,
        "organization_id": organization_id,
        "name": getattr(item, name_attr, None),
        "code": getattr(item, code_attr, None),
        "description": getattr(item, "description", None),
        "is_active": bool(getattr(item, "is_active", True)),
        "created_at": getattr(item, "created_at", None),
        "updated_at": getattr(item, "updated_at", None),
        "created_by": getattr(item, "created_by", None),
    }
    for key in (
        "branch_id",
        "department_id",
        "address",
        "city",
        "state",
        "country",
        "pincode",
        "phone",
        "email",
        "location_type",
        "latitude",
        "longitude",
        "radius_meters",
        "level",
        "min_ctc",
        "max_ctc",
        "currency",
        "business_unit_id",
        "owner_employee_id",
        "budget_amount",
        "parent_id",
        "head_employee_id",
        "cost_center_id",
        "location_id",
        "designation_id",
        "job_profile_id",
        "grade_band_id",
        "manager_position_id",
        "incumbent_employee_id",
        "status",
        "budgeted_ctc",
    ):
        if hasattr(item, key):
            response[key] = getattr(item, key)
    return response
