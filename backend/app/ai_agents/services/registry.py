from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.ai_agents.models import AiAgent
from app.ai_agents.prompts import build_agent_prompt


AGENT_DEFINITIONS: list[dict[str, Any]] = [
    {
        "code": "crm_lead_qualification",
        "name": "Lead Qualification Agent",
        "module": "CRM",
        "description": "Analyzes CRM leads, scores them, classifies them, and suggests next action.",
        "requires_approval": True,
    },
    {
        "code": "crm_followup",
        "name": "CRM Follow-up Agent",
        "module": "CRM",
        "description": "Finds missed follow-ups and drafts follow-up actions.",
        "requires_approval": True,
    },
    {
        "code": "crm_deal_analyzer",
        "name": "Deal Analyzer Agent",
        "module": "CRM",
        "description": "Analyzes deal health, risk, probability, and next-best action.",
        "requires_approval": True,
    },
    {
        "code": "crm_customer_summary",
        "name": "Customer Summary Agent",
        "module": "CRM",
        "description": "Creates a 360-degree summary of customer activity, deals, and related work.",
        "requires_approval": False,
    },
    {
        "code": "pms_project_status",
        "name": "Project Status Agent",
        "module": "PMS",
        "description": "Summarizes project status, delays, blockers, milestones, and risks.",
        "requires_approval": False,
    },
    {
        "code": "pms_task_planning",
        "name": "Task Planning Agent",
        "module": "PMS",
        "description": "Converts requirements into task and subtask drafts.",
        "requires_approval": True,
    },
    {
        "code": "pms_deadline_risk",
        "name": "Deadline Risk Agent",
        "module": "PMS",
        "description": "Detects deadline risk based on delays, dependencies, and workload.",
        "requires_approval": True,
    },
    {
        "code": "pms_meeting_notes",
        "name": "Meeting Notes Agent",
        "module": "PMS",
        "description": "Converts meeting notes into decisions, action items, and task drafts.",
        "requires_approval": True,
    },
    {
        "code": "hrms_policy_assistant",
        "name": "HR Policy Assistant Agent",
        "module": "HRMS",
        "description": "Answers HR policy questions using approved HR policy content.",
        "requires_approval": False,
    },
    {
        "code": "hrms_leave_assistant",
        "name": "Leave Assistant Agent",
        "module": "HRMS",
        "description": "Checks leave balances, drafts leave requests, and supports leave review.",
        "requires_approval": True,
    },
    {
        "code": "hrms_recruitment_screening",
        "name": "Recruitment Screening Agent",
        "module": "HRMS",
        "description": "Screens candidates against job descriptions and generates interview questions.",
        "requires_approval": True,
    },
    {
        "code": "hrms_attendance_anomaly",
        "name": "Attendance Anomaly Agent",
        "module": "HRMS",
        "description": "Detects late arrivals, missing punches, absences, and attendance anomalies.",
        "requires_approval": True,
    },
    {
        "code": "hrms_letter_drafting",
        "name": "HR Letter Drafting Agent",
        "module": "HRMS",
        "description": "Drafts HR letters such as offer, appointment, experience, warning, salary, and relieving letters.",
        "requires_approval": True,
    },
    {
        "code": "business_summary",
        "name": "Business Summary Agent",
        "module": "CROSS",
        "description": "Gives management summary across CRM, PMS, and HRMS.",
        "requires_approval": False,
    },
    {
        "code": "smart_search",
        "name": "Smart Search Agent",
        "module": "CROSS",
        "description": "Searches CRM, PMS, and HRMS using natural language with permission control.",
        "requires_approval": False,
    },
    {
        "code": "smart_notification",
        "name": "Smart Notification Agent",
        "module": "CROSS",
        "description": "Detects important business events and proposes notifications.",
        "requires_approval": True,
    },
]


class AiAgentRegistryService:
    def __init__(self, db: Session):
        self.db = db

    def ensure_seed_data(self) -> None:
        for definition in AGENT_DEFINITIONS:
            agent = self.db.query(AiAgent).filter(AiAgent.code == definition["code"]).first()
            if not agent:
                agent = AiAgent(
                    code=definition["code"],
                    name=definition["name"],
                    module=definition["module"],
                    description=definition["description"],
                    system_prompt=build_agent_prompt(definition["code"]),
                    model=None,
                    temperature=0.2,
                    is_active=True,
                    requires_approval=definition["requires_approval"],
                )
                self.db.add(agent)
                continue

            # Same-value assignments still mark ORM objects dirty. Ordinary
            # catalog reads must not become writes to a protected global table.
            values = {
                "name": definition["name"],
                "module": definition["module"],
                "description": definition["description"],
                "system_prompt": build_agent_prompt(definition["code"]),
                "requires_approval": definition["requires_approval"],
            }
            for field, value in values.items():
                if getattr(agent, field) != value:
                    setattr(agent, field, value)
        self.db.flush()

    def list_agents(self, module: str | None = None) -> list[AiAgent]:
        self.ensure_seed_data()
        query = self.db.query(AiAgent)
        if module:
            query = query.filter(AiAgent.module == module.upper())
        return query.order_by(AiAgent.module.asc(), AiAgent.name.asc()).all()

    def get_agent(self, agent_id: int) -> AiAgent | None:
        self.ensure_seed_data()
        return self.db.query(AiAgent).filter(AiAgent.id == agent_id).first()

    def set_status(self, agent_id: int, is_active: bool) -> AiAgent | None:
        agent = self.get_agent(agent_id)
        if agent:
            agent.is_active = is_active
            self.db.flush()
        return agent
