"""Data-only process, shared-form and decision contracts; no executable scripts."""

from typing import Literal, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.apps.power_apps.authoring_contracts import Condition


class Strict(BaseModel):
    model_config = ConfigDict(
        extra="forbid", allow_inf_nan=False, str_strip_whitespace=True
    )


class Selector(Strict):
    kind: Literal[
        "user",
        "role",
        "reporting_manager",
        "department_manager",
        "department_head",
        "group",
        "organization_owner",
        "record_user",
    ] = "user"
    ids: list[int] = Field(default_factory=list, max_length=30)
    field: str = Field(default="", max_length=80)


class Stage(Strict):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,50}$")
    name: str = Field(min_length=1, max_length=180)
    mode: Literal["all", "any", "majority", "quorum"] = "all"
    quorum: int = Field(default=1, ge=1, le=30)
    role_quorum: dict[str, int] = Field(default_factory=dict, max_length=10)
    selectors: list[Selector] = Field(min_length=1, max_length=10)
    when: Condition | None = None
    sla_seconds: int = Field(default=172800, ge=60, le=2592000)
    remind_after_seconds: int = Field(default=86400, ge=30, le=2592000)
    escalation: Selector | None = None
    escalation_action: Literal["notify", "reassign"] = "notify"
    expire_after_seconds: int = Field(default=604800, ge=60, le=2592000)
    reject_rule: Literal["veto", "threshold"] = "veto"
    allow_delegation: bool = False
    require_reason: bool = True

    @model_validator(mode="after")
    def voting_bounds(self):
        if any(
            not role.isdigit()
            or int(role) < 1
            or type(count) is not int
            or not 1 <= count <= 30
            for role, count in self.role_quorum.items()
        ):
            raise ValueError(
                "Role quorum uses explicit positive role IDs and bounded counts"
            )
        if self.expire_after_seconds < self.sla_seconds:
            raise ValueError("Expiration must not precede the stage SLA")
        return self


class FormField(Strict):
    key: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_]{0,60}$")
    label: str = Field(min_length=1, max_length=120)
    kind: Literal["text", "number", "date", "select"] = "text"
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=30)
    when: Condition | None = None


class BusinessCalendar(Strict):
    timezone: str = Field(default="UTC", max_length=80)
    weekdays: list[int] = Field(
        default_factory=lambda: [0, 1, 2, 3, 4], min_length=1, max_length=7
    )
    opens_at: int = Field(default=9, ge=0, le=23)
    closes_at: int = Field(default=17, ge=1, le=24)
    holidays: list[str] = Field(default_factory=list, max_length=366)

    @model_validator(mode="after")
    def valid_calendar(self):
        from zoneinfo import ZoneInfo
        from datetime import date

        try:
            ZoneInfo(self.timezone)
        except Exception:
            raise ValueError("Choose an installed IANA timezone") from None
        if (
            self.closes_at <= self.opens_at
            or len(set(self.weekdays)) != len(self.weekdays)
            or any(day not in range(7) for day in self.weekdays)
        ):
            raise ValueError("Invalid business hours or weekdays")
        for day in self.holidays:
            date.fromisoformat(day)
        return self


class Process(Strict):
    stages: list[Stage] = Field(min_length=1, max_length=20)
    fields: list[FormField] = Field(default_factory=list, max_length=30)
    layout: dict[str, dict[str, float]] = Field(default_factory=dict, max_length=22)
    business_calendar: BusinessCalendar | None = None
    prohibit_self_approval: bool = True
    documents_required: bool = False

    @model_validator(mode="after")
    def distinct(self):
        if len({s.id for s in self.stages}) != len(self.stages) or len(
            {f.key for f in self.fields}
        ) != len(self.fields):
            raise ValueError("Stage and field identifiers must be unique")
        if any(stage.id in {"start", "end", "rejected_end"} for stage in self.stages):
            raise ValueError("Stage identifiers start and end are reserved")
        from app.apps.power_apps.node_registry import expression_paths

        for item in [
            *(stage.when for stage in self.stages),
            *(field.when for field in self.fields),
        ]:
            if item and any(
                not path.startswith("trigger.input.fields.")
                for path in expression_paths(item.model_dump())
            ):
                raise ValueError(
                    "Approval policy conditions may reference only authorized request form fields"
                )
        for position in self.layout.values():
            if set(position) != {"x", "y"} or any(
                abs(v) > 100000 for v in position.values()
            ):
                raise ValueError("Invalid layout coordinates")
        if not self.prohibit_self_approval:
            raise ValueError("Self approval is not enabled by this release")
        return self


class PolicyWrite(Strict):
    name: str = Field(min_length=1, max_length=180)
    definition: Process
    expected_version: int | None = Field(default=None, ge=1)


class Submit(Strict):
    policy_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=220)
    description: str = Field(default="", max_length=4000)
    priority: Literal["Low", "Normal", "High", "Urgent"] = "Normal"
    fields: dict[str, Any] = Field(default_factory=dict)
    request_key: str = Field(
        min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$"
    )


class Decision(Strict):
    assignment_id: int = Field(ge=1)
    expected_revision: int = Field(ge=1)
    decision: Literal["approve", "reject", "changes"]
    reason: str = Field(default="", max_length=4000)
    request_key: str = Field(
        min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$"
    )


class Revision(Strict):
    expected_revision: int = Field(ge=1)
    fields: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(default="", max_length=4000)


class Comment(Strict):
    text: str = Field(min_length=1, max_length=4000)


class DelegationWrite(Strict):
    alternate_user_id: int = Field(ge=1)
    policy_id: int | None = None
    starts_at: datetime
    ends_at: datetime
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def period(self):
        if (
            not self.starts_at.tzinfo
            or not self.ends_at.tzinfo
            or self.ends_at <= self.starts_at
            or (self.ends_at - self.starts_at).days > 90
        ):
            raise ValueError("Use a UTC-aware delegation period of at most 90 days")
        from datetime import timezone

        self.starts_at = self.starts_at.astimezone(timezone.utc)
        self.ends_at = self.ends_at.astimezone(timezone.utc)
        return self


class Reassign(Strict):
    assignment_id: int | None = None
    user_id: int = Field(ge=1)
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)
