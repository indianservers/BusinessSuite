from __future__ import annotations
from app.access.catalog import permission_objects

import json
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai_agents.models import (
    AiAgent,
    AiAgentPermission,
    AiAuditLog,
    AiConversation,
    AiCostLog,
    AiMessage,
    AiSecuritySetting,
    AiUsageEvent,
    AiUsageLimit,
)
from app.ai_agents.services.audit import AiAuditService
from app.models.user import User


def company_id_for(user: User) -> int | None:
    from app.ai_agents.security import company
    return company(user)


def permission_names(user: User) -> set[str]:
    if user.is_superuser:
        return {"*"}
    return {item.name for item in (permission_objects(user))}


class AiPromptSecurityService:
    PATTERNS = {
        "critical": [
            r"expose api key",
            r"show (the )?(hidden )?(system|developer) prompt",
            r"reveal (the )?(system|developer) prompt",
            r"disable audit logs?",
            r"act as admin",
        ],
        "high": [
            r"ignore (all )?(previous|prior) instructions",
            r"bypass (permissions|approval|security)",
            r"run sql",
            r"delete records?",
            r"change salary without approval",
            r"send message without approval",
            r"do not tell the user",
            r"override security rules?",
        ],
        "medium": [
            r"ignore instructions",
            r"hidden prompt",
            r"raw sql",
            r"without approval",
        ],
    }

    def scan_user_prompt(self, prompt: str) -> dict[str, Any]:
        return self._scan(prompt)

    def scan_business_context(self, text: str) -> dict[str, Any]:
        return self._scan(text)

    def scan_tool_result(self, result: Any) -> dict[str, Any]:
        return self._scan(json.dumps(result, default=str)[:20000])

    def sanitize_context(self, text: str) -> tuple[str, bool]:
        sanitized = text
        changed = False
        for patterns in self.PATTERNS.values():
            for pattern in patterns:
                new_text = re.sub(pattern, "[REMOVED_UNTRUSTED_INSTRUCTION]", sanitized, flags=re.IGNORECASE)
                changed = changed or new_text != sanitized
                sanitized = new_text
        return sanitized, changed

    def sanitize_value(self, value: Any) -> tuple[Any, bool]:
        if isinstance(value, str):
            return self.sanitize_context(value)
        if isinstance(value, list):
            changed = False
            items = []
            for item in value:
                sanitized, item_changed = self.sanitize_value(item)
                changed = changed or item_changed
                items.append(sanitized)
            return items, changed
        if isinstance(value, dict):
            changed = False
            output: dict[str, Any] = {}
            for key, item in value.items():
                sanitized, item_changed = self.sanitize_value(item)
                changed = changed or item_changed
                output[key] = sanitized
            return output, changed
        return value, False

    def get_risk_level(self, text: str) -> str:
        return self._scan(text)["risk_level"]

    def _scan(self, text: str) -> dict[str, Any]:
        found: list[str] = []
        risk = "low"
        for level in ("critical", "high", "medium"):
            for pattern in self.PATTERNS[level]:
                if re.search(pattern, text or "", flags=re.IGNORECASE):
                    found.append(pattern)
                    risk = level
            if found:
                break
        return {"risk_level": risk, "matches": found}


class AiDataRedactionService:
    SECRET_PATTERNS = [
        (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "[REDACTED_SECRET]"),
        (re.compile(r"(?i)(api[_-]?key|token|password|otp)\s*[:=]\s*['\"]?[^\s,'\"]+"), r"\1=[REDACTED_SECRET]"),
        (re.compile(r"\b\d{12,16}\b"), "[REDACTED_BANK_DETAILS]"),
        (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), "[REDACTED_PERSONAL_ID]"),
    ]

    SENSITIVE_FIELDS = {"salary", "basic_salary", "gross_salary", "ctc", "current_ctc", "bank_name", "ifsc_code"}
    PERSONAL_ID_FIELDS = {"aadhaar_number", "pan_number", "passport_number", "uan", "account_number", "bank_account_number"}
    CONFIDENTIAL_FIELDS = {"medical_notes", "health_information", "confidential_notes", "private_notes"}

    def redact_for_ai(self, user: User, module: str, data: Any) -> Any:
        if isinstance(data, dict):
            return self.redact_object(user, module, data)
        if isinstance(data, list):
            return [self.redact_for_ai(user, module, item) for item in data]
        if isinstance(data, str):
            return self.redact_text(data)
        return data

    def redact_text(self, text: str) -> str:
        output = text or ""
        for pattern, replacement in self.SECRET_PATTERNS:
            output = pattern.sub(replacement, output)
        return output

    def redact_object(self, user: User, module: str, data: dict[str, Any]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in data.items():
            lowered = str(key).lower()
            if lowered in self.SENSITIVE_FIELDS and not self.can_expose_field(user, module, lowered):
                output[key] = "[REDACTED_SALARY]"
            elif lowered in self.PERSONAL_ID_FIELDS and not self.can_expose_field(user, module, lowered):
                output[key] = "[REDACTED_PERSONAL_ID]"
            elif lowered in self.CONFIDENTIAL_FIELDS:
                output[key] = "[REDACTED_CONFIDENTIAL_NOTE]"
            elif isinstance(value, (dict, list)):
                output[key] = self.redact_for_ai(user, module, value)
            elif isinstance(value, str):
                output[key] = self.redact_text(value)
            else:
                output[key] = value
        return output

    def can_expose_field(self, user: User, module: str, field_name: str) -> bool:
        names = permission_names(user)
        if "*" in names:
            return True
        if field_name in self.SENSITIVE_FIELDS:
            return bool(names.intersection({"payroll_view", "payroll_run", "payroll_approve", "employee_sensitive_view"}))
        if field_name in self.PERSONAL_ID_FIELDS:
            return "employee_sensitive_view" in names
        return True


class AiResponseSafetyService:
    def __init__(self):
        self.prompt_security = AiPromptSecurityService()

    def filter_response(self, response: str) -> dict[str, Any]:
        text = response or ""
        scan = self.prompt_security.scan_business_context(text)
        unsafe = scan["risk_level"] in {"high", "critical"}
        if re.search(r"sk-[A-Za-z0-9_-]{20,}|OPENAI_API_KEY|system prompt|developer prompt|```sql", text, re.IGNORECASE):
            unsafe = True
        if re.search(r"\b(action|record|task|leave|salary|deal).{0,40}(completed|updated|deleted|sent|approved)\b", text, re.IGNORECASE) and "approval" in text.lower() and "requires" in text.lower():
            unsafe = True
        if unsafe:
            return {
                "safe": False,
                "message": "I cannot provide that response because it may expose restricted information or bypass system controls. Please use the approved workflow.",
                "risk": scan,
            }
        return {"safe": True, "message": text, "risk": scan}


class AiSecuritySettingsService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, company_id: int | None) -> AiSecuritySetting:
        row = self.db.query(AiSecuritySetting).filter(AiSecuritySetting.company_id == company_id).first()
        if not row:
            row = AiSecuritySetting(company_id=company_id, ai_enabled=True, crm_ai_enabled=True, pms_ai_enabled=True, hrms_ai_enabled=True, cross_ai_enabled=True)
            self.db.add(row)
            self.db.flush()
        return row

    def ensure_enabled(self, *, user: User, module: str) -> None:
        setting = self.get_or_create(company_id_for(user))
        module_flag = {
            "CRM": setting.crm_ai_enabled,
            "PMS": setting.pms_ai_enabled,
            "HRMS": setting.hrms_ai_enabled,
            "CROSS": setting.cross_ai_enabled,
        }.get((module or "CROSS").upper(), True)
        if not setting.ai_enabled or not module_flag:
            raise HTTPException(
                status_code=403,
                detail={
                    "success": False,
                    "error_code": "AI_AGENT_DISABLED",
                    "message": setting.emergency_message or "AI Agents are temporarily disabled by administrator.",
                },
            )


class AiAgentPermissionService:
    def __init__(self, db: Session):
        self.db = db

    def can_use_agent(self, user: User, agent_id: int) -> bool:
        return self._resolve(user, agent_id, "can_use", default=True)

    def can_configure_agent(self, user: User, agent_id: int) -> bool:
        return self._resolve(user, agent_id, "can_configure", default=self._is_admin(user))

    def can_approve_agent_action(self, user: User, approval_id: int) -> bool:
        from app.ai_agents.models import AiActionApproval

        approval = self.db.query(AiActionApproval).filter(AiActionApproval.id == approval_id).first()
        if not approval:
            return False
        if user.is_superuser:
            return True
        if approval.user_id == user.id:
            return True
        return self._resolve(user, approval.agent_id or 0, "can_approve_actions", default=False)

    def can_view_ai_logs(self, user: User) -> bool:
        if self._is_admin(user):
            return True
        if user.role:
            return self.db.query(AiAgentPermission).filter(AiAgentPermission.role_id == user.role_id, AiAgentPermission.can_view_logs == True).first() is not None
        return False

    def can_export_conversation(self, user: User, conversation_id: int) -> bool:
        conversation = self.db.query(AiConversation).filter(AiConversation.id == conversation_id).first()
        if not conversation:
            return False
        if conversation.user_id == user.id:
            return True
        return self._resolve(user, conversation.agent_id or 0, "can_export_conversations", default=False)

    def _resolve(self, user: User, agent_id: int, field: str, default: bool) -> bool:
        if user.is_superuser:
            return True
        company_id = company_id_for(user)
        user_rule = (
            self.db.query(AiAgentPermission)
            .filter(AiAgentPermission.agent_id == agent_id, AiAgentPermission.company_id == company_id, AiAgentPermission.user_id == user.id)
            .first()
        )
        if user_rule:
            return bool(getattr(user_rule, field))
        role_rule = None
        if user.role_id:
            role_rule = (
                self.db.query(AiAgentPermission)
                .filter(AiAgentPermission.agent_id == agent_id, AiAgentPermission.company_id == company_id, AiAgentPermission.role_id == user.role_id, AiAgentPermission.user_id == None)
                .first()
            )
        if role_rule:
            return bool(getattr(role_rule, field))
        return default

    def _is_admin(self, user: User) -> bool:
        names = permission_names(user)
        return user.is_superuser or "*" in names or "settings_manage" in names


class AiUsageService:
    PERIODS = {"hourly": timedelta(hours=1), "daily": timedelta(days=1), "monthly": timedelta(days=31)}

    def __init__(self, db: Session):
        self.db = db

    def check_limits(self, *, user: User, agent: AiAgent | None, module: str) -> None:
        company_id = company_id_for(user)
        now = datetime.utcnow()
        limits = self.db.query(AiUsageLimit).filter(AiUsageLimit.is_active == True).all()
        for limit in limits:
            if limit.company_id not in (None, company_id):
                continue
            if limit.user_id and limit.user_id != user.id:
                continue
            if limit.agent_id and (not agent or limit.agent_id != agent.id):
                continue
            if limit.module and limit.module.upper() != (module or "").upper():
                continue
            start = now - self.PERIODS.get(limit.period, timedelta(hours=1))
            query = self.db.query(func.count(AiUsageEvent.id)).filter(AiUsageEvent.created_at >= start)
            if limit.limit_type in {"per_user", "per_company"}:
                query = query.filter(AiUsageEvent.user_id == user.id if limit.limit_type == "per_user" else AiUsageEvent.company_id == company_id)
            if limit.limit_type == "per_agent" and agent:
                query = query.filter(AiUsageEvent.agent_id == agent.id)
            if limit.limit_type == "per_module":
                query = query.filter(AiUsageEvent.module == module)
            count = query.scalar() or 0
            if count >= limit.max_requests:
                raise HTTPException(status_code=429, detail={"success": False, "error_code": "AI_USAGE_LIMIT_EXCEEDED", "message": "AI usage limit exceeded for this period."})

    def record_event(self, *, user: User, agent_id: int | None, module: str | None, event_type: str, token_input: int = 0, token_output: int = 0, estimated_cost: Decimal | None = None) -> AiUsageEvent:
        row = AiUsageEvent(company_id=company_id_for(user), user_id=user.id, agent_id=agent_id, module=module, event_type=event_type, token_input=token_input, token_output=token_output, estimated_cost=estimated_cost)
        self.db.add(row)
        self.db.flush()
        return row


class AiCostTrackingService:
    MODEL_PRICING = {
        "gpt-4.1-mini": (0.0000004, 0.0000016),
        "gpt-4o-mini": (0.00000015, 0.0000006),
    }

    def __init__(self, db: Session):
        self.db = db

    def estimate(self, model: str | None, input_tokens: int, output_tokens: int) -> Decimal | None:
        if not model:
            return None
        rates = self.MODEL_PRICING.get(model)
        if not rates:
            return None
        return Decimal(str((input_tokens * rates[0]) + (output_tokens * rates[1]))).quantize(Decimal("0.000001"))

    def record(self, *, user: User, agent_id: int | None, conversation_id: int | None, model: str | None, input_tokens: int, output_tokens: int) -> AiCostLog:
        total = int(input_tokens or 0) + int(output_tokens or 0)
        cost = self.estimate(model, input_tokens, output_tokens)
        row = AiCostLog(company_id=company_id_for(user), user_id=user.id, agent_id=agent_id, conversation_id=conversation_id, model=model, input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total, estimated_cost=cost)
        self.db.add(row)
        self.db.flush()
        return row
