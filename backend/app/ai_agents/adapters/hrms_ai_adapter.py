from __future__ import annotations
from app.access.catalog import permission_objects

from datetime import date
from typing import Any

from sqlalchemy import or_

from app.ai_agents.adapters.base import AiAdapterBase, model_to_dict, not_found, permission_denied
from app.crud import crud_leave
from app.crud.crud_attendance import crud_attendance
from app.crud.crud_employee import crud_employee
from app.models.attendance import Shift
from app.models.document import CompanyPolicy, DocumentTemplate, GeneratedDocument
from app.models.employee import Employee
from app.models.helpdesk import HelpdeskTicket
from app.models.leave import LeaveType
from app.models.recruitment import Candidate, Job
from app.models.user import User


class HrmsAiAdapter(AiAdapterBase):
    def _permission_names(self, user: User) -> set[str]:
        if user.is_superuser:
            return {"*"}
        return {permission.name for permission in (permission_objects(user))}

    def _can_view_employee(self, user: User, employee: Employee) -> bool:
        if user.is_superuser or "*" in self._permission_names(user) or "employee_view" in self._permission_names(user):
            return True
        viewer_emp = getattr(user, "employee", None)
        return bool(viewer_emp and (employee.id == viewer_emp.id or employee.reporting_manager_id == viewer_emp.id))

    def _get_employee(self, user: User, employee_id: int) -> Employee:
        employee = crud_employee.get_with_details(self.db, employee_id) or crud_employee.get(self.db, employee_id)
        if not employee or employee.deleted_at is not None:
            not_found("Employee not found")
        if not self._can_view_employee(user, employee):
            permission_denied("Employee access denied")
        return employee

    def get_employee_by_id(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        employee = self._get_employee(user, int(input["employee_id"]))
        data = model_to_dict(employee)
        data = self._mask_employee_data(user, data)
        return {"employee": data}

    def get_leave_balance(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        employee = self._get_employee(user, int(input["employee_id"]))
        rows = crud_leave.get_employee_leave_balances(self.db, employee.id, date.today().year)
        return {"leave_balances": [model_to_dict(row) for row in rows]}

    def get_team_leave_calendar(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        manager_id = input.get("manager_id") or (getattr(user, "employee", None).id if getattr(user, "employee", None) else None)
        if not manager_id:
            return {"leave_requests": [], "message": "Manager context is unavailable."}
        employees = self.db.query(Employee).filter(Employee.reporting_manager_id == int(manager_id), Employee.deleted_at == None).all()
        employee_ids = [employee.id for employee in employees]
        if not employee_ids:
            return {"leave_requests": []}
        items, _total = crud_leave.get_leave_requests(self.db, employee_id=None, status=None, skip=0, limit=1000)
        filtered = [item for item in items if item.employee_id in employee_ids]
        return {"leave_requests": [model_to_dict(row) for row in filtered[:100]]}

    def search_policy(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        query = str(input["query"])
        rows = (
            self.db.query(CompanyPolicy)
            .filter(CompanyPolicy.is_published == True, or_(CompanyPolicy.title.ilike(f"%{query}%"), CompanyPolicy.category.ilike(f"%{query}%"), CompanyPolicy.content.ilike(f"%{query}%")))
            .limit(20)
            .all()
        )
        return {"policies": [model_to_dict(row, ["id", "title", "category", "version", "effective_date", "document_url"]) for row in rows]}

    def get_policy_document(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        policy = self.db.query(CompanyPolicy).filter(CompanyPolicy.id == int(input["policy_id"]), CompanyPolicy.is_published == True).first()
        if not policy:
            not_found("Policy document not found")
        return {"policy": model_to_dict(policy, ["id", "title", "category", "content", "document_url", "version", "effective_date"])}

    def get_attendance(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        employee = self._get_employee(user, int(input["employee_id"]))
        rows = crud_attendance.get_employee_attendance(self.db, employee.id, date.fromisoformat(input["from_date"]), date.fromisoformat(input["to_date"]))
        return {"attendance": [model_to_dict(row) for row in rows]}

    def get_shift(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        employee = self._get_employee(user, int(input["employee_id"]))
        shift = crud_attendance.get_shift_for_day(self.db, employee.id, date.today()) or (self.db.query(Shift).filter(Shift.id == employee.shift_id).first() if employee.shift_id else None)
        return {"shift": model_to_dict(shift) if shift else None}

    def get_job_opening(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        job = self.db.query(Job).filter(Job.id == int(input["job_id"])).first()
        if not job:
            not_found("Job opening not found")
        return {"job": model_to_dict(job)}

    def get_candidate(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        candidate = self.db.query(Candidate).filter(Candidate.id == int(input["candidate_id"])).first()
        if not candidate:
            not_found("Candidate not found")
        return {"candidate": model_to_dict(candidate)}

    def get_candidate_resume_text(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        candidate = self.db.query(Candidate).filter(Candidate.id == int(input["candidate_id"])).first()
        if not candidate:
            not_found("Candidate not found")
        return {"resume_text": candidate.resume_parsed_data, "resume_url": candidate.resume_url}

    def generate_letter_draft(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        employee = self._get_employee(user, int(input["employee_id"]))
        template = self.db.query(DocumentTemplate).filter(DocumentTemplate.template_type.ilike(f"%{input['letter_type']}%"), DocumentTemplate.is_active == True).first()
        return {"draft": {"employee": model_to_dict(employee, ["id", "employee_id", "first_name", "last_name", "work_email"]), "letter_type": input["letter_type"], "template_id": template.id if template else None, "extra_details": input.get("extra_details", {}), "note": "Draft only. No letter has been issued."}}

    def create_leave_request_proposal(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        employee = self._get_employee(user, int(input["employee_id"]))
        return {"proposed_action": {**input, "employee_id": employee.id, "requested_by": user.id, "note": "Proposal only. No leave request has been created."}}

    def create_attendance_alert_proposal(self, user: User, input: dict[str, Any]) -> dict[str, Any]:
        employee = self._get_employee(user, int(input["employee_id"]))
        return {"proposed_action": {**input, "employee_id": employee.id, "created_by": user.id, "note": "Proposal only. No attendance action has been taken."}}

    def attendance_summary(self, user: User) -> dict[str, Any]:
        employee = getattr(user, "employee", None)
        if not employee:
            return {"message": "Employee context is unavailable."}
        return crud_attendance.get_monthly_summary(self.db, employee.id, date.today().month, date.today().year)

    def leave_summary(self, user: User) -> dict[str, Any]:
        employee = getattr(user, "employee", None)
        if not employee:
            return {"message": "Employee context is unavailable."}
        rows = crud_leave.get_employee_leave_balances(self.db, employee.id, date.today().year)
        return {"leave_balances": [model_to_dict(row) for row in rows]}

    def execute_create_leave_request(self, user: User, proposed_action: dict[str, Any]) -> dict[str, Any]:
        input = self._approval_input(proposed_action)
        employee = self._get_employee(user, int(input["employee_id"]))
        leave_type = self._find_leave_type(str(input["leave_type"]))
        if not leave_type:
            not_found("Leave type not found")
        try:
            request = crud_leave.create_leave_request(
                self.db,
                employee.id,
                {
                    "leave_type_id": leave_type.id,
                    "from_date": date.fromisoformat(str(input["from_date"])[:10]),
                    "to_date": date.fromisoformat(str(input["to_date"])[:10]),
                    "reason": input.get("reason"),
                    "is_half_day": False,
                },
            )
        except ValueError as exc:
            raise ValueError(str(exc))
        return {"success": True, "record_type": "leave_request", "record_id": request.id, "status": request.status}

    def execute_create_attendance_alert(self, user: User, proposed_action: dict[str, Any]) -> dict[str, Any]:
        input = self._approval_input(proposed_action)
        employee = self._get_employee(user, int(input["employee_id"]))
        ticket = HelpdeskTicket(
            ticket_number=self._next_ticket_number(),
            employee_id=employee.id,
            subject=f"AI Attendance Alert: {str(input['alert_type']).replace('_', ' ').title()}"[:300],
            description=f"{input.get('details', '')}\n\nRecommended action: {input.get('recommended_action', '')}".strip(),
            priority="High" if input.get("alert_type") in {"frequent_absence", "unusual_pattern"} else "Medium",
            status="Open",
        )
        self.db.add(ticket)
        self.db.flush()
        return {"success": True, "record_type": "helpdesk_ticket", "record_id": ticket.id, "ticket_number": ticket.ticket_number}

    def execute_create_letter_draft(self, user: User, proposed_action: dict[str, Any]) -> dict[str, Any]:
        input = self._approval_input(proposed_action)
        employee = self._get_employee(user, int(input["employee_id"]))
        template = self.db.query(DocumentTemplate).filter(DocumentTemplate.template_type.ilike(f"%{input['letter_type']}%"), DocumentTemplate.is_active == True).first()
        document = GeneratedDocument(
            template_id=template.id if template else None,
            employee_id=employee.id,
            document_type=str(input["letter_type"])[:100],
            document_name=f"AI Draft - {str(input['letter_type']).replace('_', ' ').title()}",
            file_url=None,
            generated_by=user.id,
            is_signed=False,
        )
        self.db.add(document)
        self.db.flush()
        return {"success": True, "record_type": "generated_document", "record_id": document.id, "draft_only": True}

    def execute_save_candidate_screening_summary(self, user: User, proposed_action: dict[str, Any]) -> dict[str, Any]:
        input = self._approval_input(proposed_action)
        candidate = self.db.query(Candidate).filter(Candidate.id == int(input["candidate_id"])).first()
        if not candidate:
            not_found("Candidate not found")
        candidate.ai_summary = str(input.get("summary") or input.get("screening_summary") or "")[:5000]
        if input.get("score") is not None:
            candidate.ai_score = input.get("score")
        self.db.flush()
        return {"success": True, "record_type": "candidate", "record_id": candidate.id, "saved_fields": ["ai_summary", "ai_score" if input.get("score") is not None else None]}

    def _approval_input(self, proposed_action: dict[str, Any]) -> dict[str, Any]:
        return proposed_action.get("input") if isinstance(proposed_action.get("input"), dict) else proposed_action

    def _find_leave_type(self, value: str) -> LeaveType | None:
        if value.isdigit():
            row = self.db.query(LeaveType).filter(LeaveType.id == int(value), LeaveType.is_active == True).first()
            if row:
                return row
        return (
            self.db.query(LeaveType)
            .filter(LeaveType.is_active == True, or_(LeaveType.code.ilike(value), LeaveType.name.ilike(value), LeaveType.name.ilike(f"%{value}%")))
            .first()
        )

    def _next_ticket_number(self) -> str:
        count = self.db.query(HelpdeskTicket).count()
        while True:
            count += 1
            ticket_number = f"AI-{date.today().strftime('%Y%m%d')}-{count:04d}"
            exists = self.db.query(HelpdeskTicket.id).filter(HelpdeskTicket.ticket_number == ticket_number).first()
            if not exists:
                return ticket_number

    def _mask_employee_data(self, user: User, data: dict[str, Any]) -> dict[str, Any]:
        permissions = self._permission_names(user)
        masked = dict(data)
        for field in ("account_number", "bank_account_number", "aadhaar_number", "uan", "pan_number", "passport_number"):
            if field in masked and "*" not in permissions:
                value = str(masked[field] or "")
                masked[field] = f"***{value[-4:]}" if value else None
        if "*" not in permissions and not permissions.intersection({"payroll_view", "salary_view", "payroll_manage"}):
            for field in ("salary", "basic_salary", "gross_salary", "ctc", "current_ctc", "bank_name", "ifsc_code"):
                masked.pop(field, None)
        for field in ("medical_notes", "health_information", "confidential_notes"):
            masked.pop(field, None)
        return masked
