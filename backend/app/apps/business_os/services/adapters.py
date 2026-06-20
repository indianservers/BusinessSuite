from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.apps.business_os.models import BOSLifecycleEvent
from app.apps.business_os.services.module_service import company_id_for, is_module_enabled, normalize_module_key
from app.models.user import User


class BaseModuleAdapter:
    module_key = ""

    def __init__(self, db: Session, user: User, company_id: int | None = None):
        self.db = db
        self.user = user
        self.company_id = int(company_id or company_id_for(user))

    def is_enabled(self) -> bool:
        return is_module_enabled(self.db, self.module_key, self.company_id)

    def can_create_record(self, record_type: str | None = None) -> bool:
        return self.is_enabled()

    def create_linked_record(self, record_type: str, source: dict[str, Any]) -> dict[str, Any]:
        return self._unsupported("create_linked_record", record_type, source)

    def get_summary(self, entity_type: str, entity_id: int | str) -> dict[str, Any]:
        return {"module": self.module_key, "entity_type": entity_type, "entity_id": str(entity_id), "enabled": self.is_enabled()}

    def get_lifecycle_events(self, entity_type: str, entity_id: int | str) -> list[dict[str, Any]]:
        rows = (
            self.db.query(BOSLifecycleEvent)
            .filter(
                BOSLifecycleEvent.company_id == self.company_id,
                BOSLifecycleEvent.module_key == self.module_key,
                BOSLifecycleEvent.entity_type == entity_type,
                BOSLifecycleEvent.entity_id == str(entity_id),
            )
            .order_by(BOSLifecycleEvent.id.asc())
            .all()
        )
        return [{"event_name": row.event_name, "status": row.status, "message": row.message, "evidence": row.evidence_json or {}} for row in rows]

    def post_accounting(self, transaction_type: str, source: dict[str, Any]) -> dict[str, Any]:
        return self._unsupported("post_accounting", transaction_type, source)

    def _unsupported(self, action: str, record_type: str, source: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "not_implemented",
            "module": self.module_key,
            "action": action,
            "record_type": record_type,
            "source": source,
        }


class CRMAdapter(BaseModuleAdapter):
    module_key = "crm"


class SRMAdapter(BaseModuleAdapter):
    module_key = "srm"

    def create_linked_record(self, record_type: str, source: dict[str, Any]) -> dict[str, Any]:
        if record_type == "sales_order_from_crm_deal":
            from app.apps.srm.api.router import create_sales_order_from_crm_deal_service

            return create_sales_order_from_crm_deal_service(int(source["deal_id"]), self.db, self.user)
        return super().create_linked_record(record_type, source)


class PMSAdapter(BaseModuleAdapter):
    module_key = "project_management"


class FAMAdapter(BaseModuleAdapter):
    module_key = "fam"

    def post_accounting(self, transaction_type: str, source: dict[str, Any]) -> dict[str, Any]:
        if not self.is_enabled():
            return {
                "status": "skipped",
                "module": self.module_key,
                "transaction_type": transaction_type,
                "message": "Accounting posting skipped because FAM is not enabled",
                "source": source,
            }
        return {
            "status": "ready",
            "module": self.module_key,
            "transaction_type": transaction_type,
            "message": "FAM is enabled; accounting posting can proceed through the mapped FAM posting endpoint.",
            "source": source,
        }


class InventoryAdapter(BaseModuleAdapter):
    module_key = "srm"


class HRMSAdapter(BaseModuleAdapter):
    module_key = "hrms"


ADAPTERS = {
    "crm": CRMAdapter,
    "srm": SRMAdapter,
    "project_management": PMSAdapter,
    "pms": PMSAdapter,
    "fam": FAMAdapter,
    "accounts": FAMAdapter,
    "inventory": InventoryAdapter,
    "hrms": HRMSAdapter,
}


def get_adapter(module_key: str, db: Session, user: User, company_id: int | None = None) -> BaseModuleAdapter:
    normalized = normalize_module_key(module_key)
    adapter_cls = ADAPTERS.get(normalized, BaseModuleAdapter)
    adapter = adapter_cls(db, user, company_id)
    if not getattr(adapter, "module_key", None):
        adapter.module_key = normalized
    return adapter
