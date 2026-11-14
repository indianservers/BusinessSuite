from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import or_

from app.ai_agents.adapters.base import AiAdapterBase, model_to_dict, not_found
from app.apps.crm.models import CRMActivity, CRMCompany, CRMDeal, CRMEmailLog, CRMLead, CRMNote, CRMTask
from app.models.user import User


class CrmAiAdapter(AiAdapterBase):
    def _query_org(self, model: Any, user: User):
        org_id = self.org_id(user)
        query = self.db.query(model)
        if hasattr(model, "deleted_at"):
            query = query.filter(model.deleted_at == None)
        if not user.is_superuser and hasattr(model, "organization_id"):
            query = query.filter(model.organization_id == org_id)
        return query

    def _get_lead(self, user: User, lead_id: int) -> CRMLead:
        lead = self._query_org(CRMLead, user).filter(CRMLead.id == lead_id).first()
        if not lead:
            not_found("Lead not found or not accessible")
        return lead

    def _get_deal(self, user: User, deal_id: int) -> CRMDeal:
        deal = self._query_org(CRMDeal, user).filter(CRMDeal.id == deal_id).first()
        if not deal:
            not_found("Deal not found or not accessible")
        return deal

    def _get_customer(self, user: User, customer_id: int) -> CRMCompany:
        customer = self._query_org(CRMCompany, user).filter(CRMCompany.id == customer_id).first()
        if not customer:
            not_found("Customer not found or not accessible")
        return customer

    def get_lead_by_id(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        lead = self._get_lead(user, int(input["lead_id"]))
        return {"lead": model_to_dict(lead)}

    def search_duplicate_leads(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        query = self._query_org(CRMLead, user)
        conditions = []
        lead_id = input.get("lead_id")
        if lead_id:
            lead = self._get_lead(user, int(lead_id))
            if lead.email:
                conditions.append(CRMLead.email == lead.email)
            if lead.phone:
                conditions.append(CRMLead.phone == lead.phone)
            if lead.company_name:
                conditions.append(CRMLead.company_name.icontains(lead.company_name, autoescape=True))
            query = query.filter(CRMLead.id != lead.id)
        for field, column in (("email", CRMLead.email), ("mobile", CRMLead.phone), ("company_name", CRMLead.company_name)):
            value = input.get(field)
            if value:
                conditions.append(column.icontains(str(value), autoescape=True) if field == "company_name" else column == value)
        if not conditions:
            return {"duplicates": [], "message": "Provide lead_id, email, mobile, or company_name to search duplicates."}
        rows = query.filter(or_(*conditions)).limit(25).all()
        return {"duplicates": [model_to_dict(row) for row in rows], "count": len(rows)}

    def get_lead_activities(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        lead = self._get_lead(user, int(input["lead_id"]))
        activities = self._query_org(CRMActivity, user).filter(or_(CRMActivity.lead_id == lead.id, (CRMActivity.entity_type == "lead") & (CRMActivity.entity_id == lead.id))).order_by(CRMActivity.created_at.desc()).limit(50).all()
        tasks = self._query_org(CRMTask, user).filter(CRMTask.lead_id == lead.id).order_by(CRMTask.created_at.desc()).limit(50).all()
        notes = self._query_org(CRMNote, user).filter(CRMNote.lead_id == lead.id).order_by(CRMNote.created_at.desc()).limit(50).all()
        return {
            "activities": [model_to_dict(row) for row in activities],
            "tasks": [model_to_dict(row) for row in tasks],
            "notes": [model_to_dict(row) for row in notes],
        }

    def get_overdue_followups(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        now = datetime.utcnow()
        query = self._query_org(CRMTask, user).filter(CRMTask.due_date != None, CRMTask.due_date < now, CRMTask.completed_at == None)
        if input.get("owner_id"):
            query = query.filter(CRMTask.owner_user_id == int(input["owner_id"]))
        rows = query.order_by(CRMTask.due_date.asc()).limit(100).all()
        return {"followups": [model_to_dict(row) for row in rows], "count": len(rows)}

    def get_deal_by_id(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        return {"deal": model_to_dict(self._get_deal(user, int(input["deal_id"])))}

    def get_deal_notes(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        deal = self._get_deal(user, int(input["deal_id"]))
        rows = self._query_org(CRMNote, user).filter(CRMNote.deal_id == deal.id).order_by(CRMNote.created_at.desc()).limit(50).all()
        return {"notes": [model_to_dict(row) for row in rows]}

    def get_deal_activities(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        deal = self._get_deal(user, int(input["deal_id"]))
        rows = self._query_org(CRMActivity, user).filter(or_(CRMActivity.deal_id == deal.id, (CRMActivity.entity_type == "deal") & (CRMActivity.entity_id == deal.id))).order_by(CRMActivity.created_at.desc()).limit(50).all()
        return {"activities": [model_to_dict(row) for row in rows]}

    def get_customer_by_id(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        return {"customer": model_to_dict(self._get_customer(user, int(input["customer_id"])))}

    def get_customer_deals(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        customer = self._get_customer(user, int(input["customer_id"]))
        rows = self._query_org(CRMDeal, user).filter(CRMDeal.company_id == customer.id).order_by(CRMDeal.created_at.desc()).limit(50).all()
        return {"deals": [model_to_dict(row) for row in rows]}

    def get_customer_activities(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        customer = self._get_customer(user, int(input["customer_id"]))
        rows = self._query_org(CRMActivity, user).filter(or_(CRMActivity.company_id == customer.id, (CRMActivity.entity_type == "customer") & (CRMActivity.entity_id == customer.id), (CRMActivity.entity_type == "account") & (CRMActivity.entity_id == customer.id))).order_by(CRMActivity.created_at.desc()).limit(50).all()
        return {"activities": [model_to_dict(row) for row in rows]}

    def create_followup_task_draft(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        return {"draft": {**input, "created_by": user.id, "status": "draft", "note": "Draft only. No CRM task has been created."}}

    def propose_lead_update(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        lead = self._get_lead(user, int(input["lead_id"]))
        return {"proposed_action": {"lead_id": lead.id, "current_status": lead.status, "current_score": lead.lead_score, **input}}

    def draft_crm_message(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        return {
            "draft": {
                "message_type": input.get("message_type"),
                "purpose": input.get("purpose"),
                "tone": input.get("tone", "professional"),
                "key_points": input.get("key_points", []),
                "body": "",
                "note": "Draft structure only. Message generation and sending are not connected in this step.",
            }
        }

    def execute_create_followup_task(self, user: User, proposed_action: dict[str, Any]) -> dict[str, Any]:
        input = self._approval_input(proposed_action)
        entity_type = str(input.get("related_entity_type", "")).lower()
        entity_id = int(input["related_entity_id"])
        task_kwargs: dict[str, Any] = {}
        organization_id = self.org_id(user)

        if entity_type == "lead":
            record = self._get_lead(user, entity_id)
            task_kwargs["lead_id"] = record.id
            organization_id = record.organization_id
        elif entity_type == "deal":
            record = self._get_deal(user, entity_id)
            task_kwargs["deal_id"] = record.id
            organization_id = record.organization_id
        elif entity_type in {"customer", "company", "account"}:
            record = self._get_customer(user, entity_id)
            task_kwargs["company_id"] = record.id
            organization_id = record.organization_id
        else:
            raise ValueError("related_entity_type must be lead, deal, or customer")

        task = CRMTask(
            organization_id=organization_id,
            owner_user_id=user.id,
            title=str(input["title"])[:220],
            description=input.get("description"),
            status="To Do",
            priority=self._priority(input.get("priority")),
            due_date=self._parse_datetime(input.get("due_date")),
            created_by_user_id=user.id,
            updated_by_user_id=user.id,
            **task_kwargs,
        )
        self.db.add(task)
        self.db.flush()
        return {"success": True, "record_type": "crm_task", "record_id": task.id, "title": task.title}

    def execute_lead_score_status_update(self, user: User, proposed_action: dict[str, Any]) -> dict[str, Any]:
        input = self._approval_input(proposed_action)
        lead = self._get_lead(user, int(input["lead_id"]))
        changes: dict[str, Any] = {}
        if input.get("proposed_score") not in (None, ""):
            score = int(input["proposed_score"])
            if score < 0 or score > 100:
                raise ValueError("proposed_score must be between 0 and 100")
            lead.lead_score = score
            lead.lead_score_mode = "manual"
            changes["lead_score"] = score
        if input.get("proposed_status"):
            lead.status = str(input["proposed_status"])[:40]
            changes["status"] = lead.status
        lead.updated_by_user_id = user.id
        note = CRMNote(
            organization_id=lead.organization_id,
            author_user_id=user.id,
            lead_id=lead.id,
            body=f"AI-approved lead update. Reason: {input.get('reason', 'No reason provided')}",
            is_internal=True,
            created_by_user_id=user.id,
        )
        self.db.add(note)
        self.db.flush()
        return {"success": True, "record_type": "crm_lead", "record_id": lead.id, "changes": changes}

    def execute_create_draft_message(self, user: User, proposed_action: dict[str, Any]) -> dict[str, Any]:
        input = self._approval_input(proposed_action)
        if str(input.get("message_type", "email")).lower() != "email":
            return {
                "success": False,
                "error_code": "ACTION_NOT_SUPPORTED_IN_FIRST_RELEASE",
                "message": "Only CRM email drafts are supported for AI approval execution in the first release.",
            }

        entity_type = str(input.get("related_entity_type", "")).lower()
        entity_id = int(input["related_entity_id"])
        entity_kwargs: dict[str, Any] = {"entity_type": entity_type, "entity_id": entity_id}
        organization_id = self.org_id(user)
        to_email = input.get("to_email")
        if entity_type == "lead":
            record = self._get_lead(user, entity_id)
            entity_kwargs["lead_id"] = record.id
            organization_id = record.organization_id
            to_email = to_email or record.email
        elif entity_type == "deal":
            record = self._get_deal(user, entity_id)
            entity_kwargs["deal_id"] = record.id
            organization_id = record.organization_id
        elif entity_type in {"customer", "company", "account"}:
            record = self._get_customer(user, entity_id)
            entity_kwargs["company_id"] = record.id
            organization_id = record.organization_id

        if not to_email:
            raise ValueError("A recipient email address is required to save a CRM email draft")

        body = input.get("body") or "\n".join(str(item) for item in input.get("key_points", [])) or input.get("purpose") or ""
        draft = CRMEmailLog(
            organization_id=organization_id,
            owner_user_id=user.id,
            subject=str(input.get("subject") or input.get("purpose") or "AI drafted follow-up")[:220],
            body=body,
            to_email=str(to_email)[:150],
            status="draft",
            direction="Outbound",
            created_by_user_id=user.id,
            updated_by_user_id=user.id,
            **entity_kwargs,
        )
        self.db.add(draft)
        self.db.flush()
        return {"success": True, "record_type": "crm_email_log", "record_id": draft.id, "status": draft.status}

    def _approval_input(self, proposed_action: dict[str, Any]) -> dict[str, Any]:
        return proposed_action.get("input") if isinstance(proposed_action.get("input"), dict) else proposed_action

    def _parse_datetime(self, value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    def _priority(self, value: Any) -> str:
        mapping = {"low": "Low", "medium": "Medium", "high": "High", "critical": "Critical"}
        return mapping.get(str(value or "medium").lower(), "Medium")
