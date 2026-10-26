from typing import Literal
from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

Provider = Literal["openai", "gemini", "claude"]


class ProviderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9._-]+$")
    api_key: SecretStr | None = None
    enabled: bool = False
    data_sharing_allowed: bool = False
    allow_workspace_inheritance: bool = False
    max_tokens: int = Field(default=3000, ge=512, le=8192)
    input_price: float | None = Field(default=None, ge=0, le=10000, allow_inf_nan=False)
    output_price: float | None = Field(default=None, ge=0, le=10000, allow_inf_nan=False)


class CommandInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: int = Field(gt=0)
    task_ids: list[int] = Field(min_length=1, max_length=25)
    command: str = Field(min_length=3, max_length=4000)
    provider: Provider
    request_key: str = Field(min_length=8, max_length=100)
    input_mode: Literal["text", "voice"] = "text"
    background: bool = False
    execution_mode: Literal["atomic", "checkpointed"] = "atomic"
    timezone: str = Field(default="Asia/Kolkata", max_length=80)
    parent_run_id: int | None = Field(default=None, gt=0)
    parent_plan_hash: str | None = None
    local_plan: "TaskPlan | None" = None

    @model_validator(mode="after")
    def validate_context(self):
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown timezone")
        if self.execution_mode == "checkpointed" and not self.background:
            raise ValueError("Checkpointed execution requires background mode")
        if self.parent_run_id and not self.background:
            raise ValueError("Follow-up planning requires background mode")
        return self


class TaskChanges(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["To Do", "In Progress", "In Review", "Blocked", "Done"] | None = None
    priority: Literal["Low", "Medium", "High", "Urgent"] | None = None
    assignee_user_ids: list[int] | None = Field(default=None, max_length=25)
    title: str | None = Field(default=None, min_length=1, max_length=220)
    description: str | None = Field(default=None, min_length=1, max_length=8000)
    estimated_hours: Decimal | None = Field(default=None, ge=0, le=10000, decimal_places=2, allow_inf_nan=False)
    story_points: int | None = Field(default=None, ge=0, le=1000)


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: Literal["update_task", "add_checklist", "move_to_sprint", "schedule_task", "add_dependency", "update_checklist", "add_comment"]
    task_id: int = Field(gt=0)
    changes: TaskChanges | None = None
    title: str | None = Field(default=None, min_length=1, max_length=220)
    sprint_id: int | None = Field(default=None, gt=0)
    start_date: date | None = None
    due_date: date | None = None
    source_task_id: int | None = Field(default=None, gt=0)
    dependency_id: int | None = Field(default=None, gt=0)
    item_id: int | None = Field(default=None, gt=0)
    is_completed: bool | None = None
    body: str | None = Field(default=None, min_length=1, max_length=8000)
    dependency_type: Literal["Finish To Start", "Start To Start", "Finish To Finish", "Start To Finish"] | None = None
    lag_days: int = Field(default=0, ge=-365, le=365)
    depends_on: list[int] | None = Field(default=None, max_length=75)

    @model_validator(mode="after")
    def validate_payload(self):
        provided = self.model_dump(exclude_none=True, exclude={"tool", "task_id", "depends_on", "lag_days"})
        allowed = {"update_task": {"changes"}, "add_checklist": {"title"}, "move_to_sprint": {"sprint_id"},
                   "schedule_task": {"start_date", "due_date"}, "add_dependency": {"source_task_id", "dependency_type"}, "remove_dependency": {"dependency_id"},
                   "update_checklist": {"item_id", "is_completed"}, "remove_checklist": {"item_id"}, "add_comment": {"body"}}
        if set(provided) - allowed[self.tool] or (self.lag_days and self.tool != "add_dependency"):
            raise ValueError("Fields do not match the selected tool")
        if self.tool == "update_task":
            if not self.changes or not self.changes.model_dump(exclude_none=True) or self.title or self.sprint_id:
                raise ValueError("update_task requires changes only")
        elif self.tool == "add_checklist":
            if not self.title or not self.title.strip() or self.changes or self.sprint_id:
                raise ValueError("add_checklist requires title only")
        elif self.tool == "move_to_sprint" and not self.sprint_id:
            raise ValueError("move_to_sprint requires sprint_id only")
        elif self.tool == "schedule_task" and (not (self.start_date or self.due_date) or self.start_date and self.due_date and self.start_date > self.due_date):
            raise ValueError("schedule_task requires valid dates")
        elif self.tool == "add_dependency" and (not self.source_task_id or self.source_task_id == self.task_id):
            raise ValueError("add_dependency requires a different source task")
        elif self.tool == "remove_dependency" and not self.dependency_id:
            raise ValueError("remove_dependency requires dependency_id")
        elif self.tool == "update_checklist" and (not self.item_id or self.is_completed is None):
            raise ValueError("update_checklist requires item_id and is_completed")
        elif self.tool == "remove_checklist" and not self.item_id:
            raise ValueError("remove_checklist requires item_id")
        elif self.tool == "add_comment" and (not self.body or not self.body.strip()):
            raise ValueError("add_comment requires body")
        return self


class TaskPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=1000)
    clarification: str | None = Field(default=None, max_length=1500)
    steps: list[PlanStep] = Field(max_length=75)

    @model_validator(mode="after")
    def validate_graph(self):
        for index, step in enumerate(self.steps, 1):
            if step.depends_on is not None and any(p < 1 or p >= index for p in step.depends_on):
                raise ValueError("Step dependencies must refer to earlier one-based step positions")
        return self


class RevisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command: str = Field(min_length=3, max_length=4000)
    request_key: str = Field(min_length=8, max_length=100)
    plan_hash: str | None = None
    input_mode: Literal["text", "voice"] = "text"


class ResumeInput(BaseModel):
    plan_hash: str = Field(min_length=64, max_length=64)


class ApproveInput(BaseModel):
    plan_hash: str = Field(min_length=64, max_length=64)


CommandInput.model_rebuild()
