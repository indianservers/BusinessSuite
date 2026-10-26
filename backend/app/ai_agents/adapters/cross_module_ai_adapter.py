from __future__ import annotations

from typing import Any

from sqlalchemy import or_

from app.ai_agents.adapters.base import AiAdapterBase, model_to_dict
from app.ai_agents.models import AiActionApproval
from app.apps.crm.models import CRMCompany, CRMDeal, CRMLead
from app.apps.project_management.access import accessible_project_query
from app.apps.project_management.models import PMSProject, PMSTask
from app.models.employee import Employee
from app.models.user import User


class CrossModuleAiAdapter(AiAdapterBase):
    def get_business_summary(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        org_id = self.org_id(user)
        crm_leads = self.db.query(CRMLead).filter(CRMLead.deleted_at == None)
        crm_deals = self.db.query(CRMDeal).filter(CRMDeal.deleted_at == None)
        employees = self.db.query(Employee).filter(Employee.deleted_at == None)
        if not user.is_superuser and org_id is not None:
            crm_leads = crm_leads.filter(CRMLead.organization_id == org_id)
            crm_deals = crm_deals.filter(CRMDeal.organization_id == org_id)
        projects = accessible_project_query(self.db, user).all()
        return {
            "crm": {"lead_count": crm_leads.count(), "deal_count": crm_deals.count()},
            "pms": {"project_count": len(projects)},
            "hrms": {"employee_count": employees.count()},
        }

    def get_pending_approvals(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        query = self.db.query(AiActionApproval).filter(AiActionApproval.status == "pending")
        if input.get("module"):
            query = query.filter(AiActionApproval.module == str(input["module"]).upper())
        from app.ai_agents.security import company, visible_history
        query = query.filter(AiActionApproval.user_id == user.id,AiActionApproval.organization_id == company(user))
        rows = visible_history(self.db,user,query.order_by(AiActionApproval.created_at.desc()).limit(100).all())
        return {"approvals": [model_to_dict(row) for row in rows], "count": len(rows)}

    def safe_search_crm(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        query_text = str(input["query"])
        limit = min(int(input.get("limit") or 20), 50)
        org_id = self.org_id(user)
        lead_query = self.db.query(CRMLead).filter(CRMLead.deleted_at == None, or_(CRMLead.full_name.ilike(f"%{query_text}%"), CRMLead.email.ilike(f"%{query_text}%"), CRMLead.company_name.ilike(f"%{query_text}%")))
        deal_query = self.db.query(CRMDeal).filter(CRMDeal.deleted_at == None, or_(CRMDeal.name.ilike(f"%{query_text}%"), CRMDeal.description.ilike(f"%{query_text}%")))
        company_query = self.db.query(CRMCompany).filter(CRMCompany.deleted_at == None, or_(CRMCompany.name.ilike(f"%{query_text}%"), CRMCompany.email.ilike(f"%{query_text}%"), CRMCompany.website.ilike(f"%{query_text}%")))
        if not user.is_superuser and org_id is not None:
            lead_query = lead_query.filter(CRMLead.organization_id == org_id)
            deal_query = deal_query.filter(CRMDeal.organization_id == org_id)
            company_query = company_query.filter(CRMCompany.organization_id == org_id)
        return {
            "leads": [model_to_dict(row) for row in lead_query.limit(limit).all()],
            "deals": [model_to_dict(row) for row in deal_query.limit(limit).all()],
            "customers": [model_to_dict(row) for row in company_query.limit(limit).all()],
        }

    def safe_search_pms(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        query_text = str(input["query"])
        limit = min(int(input.get("limit") or 20), 50)
        project_ids = [row.id for row in accessible_project_query(self.db, user).all()]
        project_rows = self.db.query(PMSProject).filter(PMSProject.id.in_(project_ids), PMSProject.name.ilike(f"%{query_text}%")).limit(limit).all() if project_ids else []
        task_rows = self.db.query(PMSTask).filter(PMSTask.project_id.in_(project_ids), PMSTask.deleted_at == None, or_(PMSTask.title.ilike(f"%{query_text}%"), PMSTask.task_key.ilike(f"%{query_text}%"))).limit(limit).all() if project_ids else []
        return {"projects": [model_to_dict(row) for row in project_rows], "tasks": [model_to_dict(row) for row in task_rows]}

    def safe_search_hrms(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        query_text = str(input["query"])
        limit = min(int(input.get("limit") or 20), 50)
        org_id = self.org_id(user)
        query = self.db.query(Employee).filter(Employee.deleted_at == None, or_(Employee.first_name.ilike(f"%{query_text}%"), Employee.last_name.ilike(f"%{query_text}%"), Employee.employee_id.ilike(f"%{query_text}%"), Employee.work_email.ilike(f"%{query_text}%")))
        rows = query.limit(limit).all()
        return {"employees": [model_to_dict(row, ["id", "employee_id", "first_name", "last_name", "work_email", "status", "department_id", "designation_id"]) for row in rows]}

    def get_alerts(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        self.missing("existing_alert_aggregation_service")
