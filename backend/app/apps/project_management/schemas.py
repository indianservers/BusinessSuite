"""Pydantic schemas for Project Management (KaryaFlow) module."""
from datetime import date, datetime
from typing import Any, Optional, List
from decimal import Decimal

from pydantic import BaseModel, Field, validator


# ============= CLIENT SCHEMAS =============
class PMSClientBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=180)
    company_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    notes: Optional[str] = None


class PMSClientCreate(PMSClientBase):
    pass


class PMSClientUpdate(BaseModel):
    name: Optional[str] = None
    company_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    notes: Optional[str] = None


class PMSClientResponse(PMSClientBase):
    id: int
    organization_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============= PROJECT SCHEMAS =============
class PMSProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=180)
    project_key: str = Field(..., min_length=1, max_length=20)
    description: Optional[str] = None
    client_id: Optional[int] = None
    manager_user_id: Optional[int] = None
    owner_user_id: Optional[int] = None
    department_id: Optional[int] = None
    branch_id: Optional[int] = None
    category: Optional[str] = None
    status: str = "Draft"
    priority: str = "Medium"
    health: str = "Good"
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    planned_start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    actual_start_date: Optional[date] = None
    actual_end_date: Optional[date] = None
    budget_amount: Optional[Decimal] = None
    estimated_hours: Optional[Decimal] = None
    estimated_cost: Optional[Decimal] = None
    actual_cost: Optional[Decimal] = None
    billing_status: str = "Unbilled"
    progress_percent: int = 0
    is_client_visible: bool = False
    is_template: bool = False
    is_archived: bool = False

    @validator("project_key")
    def project_key_uppercase(cls, v):
        return v.upper()


class PMSProjectCreate(PMSProjectBase):
    pass


class PMSProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    client_id: Optional[int] = None
    manager_user_id: Optional[int] = None
    owner_user_id: Optional[int] = None
    department_id: Optional[int] = None
    branch_id: Optional[int] = None
    category: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    health: Optional[str] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    planned_start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    actual_start_date: Optional[date] = None
    actual_end_date: Optional[date] = None
    budget_amount: Optional[Decimal] = None
    estimated_hours: Optional[Decimal] = None
    estimated_cost: Optional[Decimal] = None
    actual_cost: Optional[Decimal] = None
    billing_status: Optional[str] = None
    progress_percent: Optional[int] = None
    is_client_visible: Optional[bool] = None
    is_template: Optional[bool] = None
    is_archived: Optional[bool] = None


class PMSProjectResponse(PMSProjectBase):
    id: int
    organization_id: Optional[int] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PMSProjectIntakeBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=180)
    description: Optional[str] = None
    requester_name: Optional[str] = None
    requester_email: Optional[str] = None
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    priority: str = "Medium"
    desired_start_date: Optional[date] = None
    desired_due_date: Optional[date] = None
    budget_amount: Optional[Decimal] = None


class PMSProjectIntakeCreate(PMSProjectIntakeBase):
    pass


class PMSProjectIntakeReview(BaseModel):
    status: str
    review_notes: Optional[str] = None
    project_key: Optional[str] = None
    manager_user_id: Optional[int] = None


class PMSProjectIntakeResponse(PMSProjectIntakeBase):
    id: int
    organization_id: Optional[int] = None
    requester_user_id: Optional[int] = None
    status: str
    review_notes: Optional[str] = None
    reviewed_by_user_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_project_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============= PROJECT MEMBER SCHEMAS =============
class PMSProjectMemberBase(BaseModel):
    user_id: int
    role: str = "Member"
    allocation_percent: Optional[Decimal] = Decimal("100")


class PMSProjectMemberCreate(PMSProjectMemberBase):
    pass


class PMSProjectMemberUpdate(BaseModel):
    role: Optional[str] = None
    allocation_percent: Optional[Decimal] = None


class PMSProjectMemberResponse(PMSProjectMemberBase):
    id: int
    project_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============= PLANNING OBJECT SCHEMAS =============
class PMSEpicBase(BaseModel):
    epic_key: str = Field(..., min_length=1, max_length=60)
    name: str = Field(..., min_length=1, max_length=180)
    description: Optional[str] = None
    status: str = "Planned"
    owner_user_id: Optional[int] = None
    color: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    target_date: Optional[date] = None

    @validator("epic_key")
    def epic_key_uppercase(cls, v):
        return v.upper()


class PMSEpicCreate(PMSEpicBase):
    pass


class PMSEpicUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    owner_user_id: Optional[int] = None
    color: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    target_date: Optional[date] = None


class PMSEpicResponse(PMSEpicBase):
    id: int
    organization_id: Optional[int] = None
    project_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PMSComponentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = None
    lead_user_id: Optional[int] = None
    default_assignee_user_id: Optional[int] = None
    is_active: bool = True


class PMSComponentCreate(PMSComponentBase):
    pass


class PMSComponentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    lead_user_id: Optional[int] = None
    default_assignee_user_id: Optional[int] = None
    is_active: Optional[bool] = None


class PMSComponentResponse(PMSComponentBase):
    id: int
    project_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PMSReleaseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = None
    status: str = "Planning"
    release_date: Optional[date] = None
    owner_user_id: Optional[int] = None
    readiness_percent: int = 0
    launch_notes: Optional[str] = None


class PMSReleaseCreate(PMSReleaseBase):
    pass


class PMSReleaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    release_date: Optional[date] = None
    owner_user_id: Optional[int] = None
    readiness_percent: Optional[int] = None
    launch_notes: Optional[str] = None


class PMSReleaseResponse(PMSReleaseBase):
    id: int
    project_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============= BOARD & COLUMN SCHEMAS =============
class PMSBoardColumnBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    status_key: str = Field(..., min_length=1, max_length=60)
    position: int = 0
    wip_limit: Optional[int] = None
    is_collapsed: bool = False
    color: Optional[str] = None


class PMSBoardColumnCreate(PMSBoardColumnBase):
    pass


class PMSBoardColumnUpdate(BaseModel):
    name: Optional[str] = None
    status_key: Optional[str] = None
    position: Optional[int] = None
    wip_limit: Optional[int] = None
    is_collapsed: Optional[bool] = None
    color: Optional[str] = None


class PMSBoardColumnResponse(PMSBoardColumnBase):
    id: int
    board_id: int

    class Config:
        from_attributes = True


class PMSBoardBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=140)
    board_type: str = "Kanban"


class PMSBoardCreate(PMSBoardBase):
    columns: Optional[List[PMSBoardColumnCreate]] = []


class PMSBoardUpdate(BaseModel):
    name: Optional[str] = None
    board_type: Optional[str] = None


class PMSBoardResponse(PMSBoardBase):
    id: int
    project_id: int
    created_at: datetime
    columns: Optional[List[PMSBoardColumnResponse]] = []

    class Config:
        from_attributes = True


# ============= SPRINT SCHEMAS =============
class PMSSprintBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    goal: Optional[str] = None
    status: str = "Planned"
    start_date: date
    end_date: date
    capacity_hours: Optional[Decimal] = None
    velocity_points: Optional[int] = None


class PMSSprintCreate(PMSSprintBase):
    pass


class PMSSprintUpdate(BaseModel):
    name: Optional[str] = None
    goal: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    capacity_hours: Optional[Decimal] = None
    velocity_points: Optional[int] = None
    review_notes: Optional[str] = None
    retrospective_notes: Optional[str] = None
    what_went_well: Optional[str] = None
    what_did_not_go_well: Optional[str] = None
    outcome: Optional[str] = None


class PMSSprintResponse(PMSSprintBase):
    id: int
    project_id: int
    committed_task_count: int = 0
    committed_story_points: int = 0
    completed_story_points: int = 0
    scope_change_count: int = 0
    carry_forward_task_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed_by_user_id: Optional[int] = None
    commitment_snapshot: Optional[str] = None
    completion_summary: Optional[str] = None
    review_notes: Optional[str] = None
    retrospective_notes: Optional[str] = None
    what_went_well: Optional[str] = None
    what_did_not_go_well: Optional[str] = None
    outcome: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SprintCompleteRequest(BaseModel):
    carry_forward_sprint_id: Optional[int] = None
    incomplete_action: str = Field("move_to_next_sprint", pattern="^(move_to_backlog|move_to_next_sprint|keep_in_sprint)$")
    review_notes: Optional[str] = None
    retrospective_notes: Optional[str] = None
    what_went_well: Optional[str] = None
    what_did_not_go_well: Optional[str] = None
    outcome: Optional[str] = None
    action_items: List[dict[str, Any]] = []
    create_action_item_tasks: bool = False


class PMSSprintRetroActionItemResponse(BaseModel):
    id: int
    sprint_id: int
    title: str
    owner_user_id: Optional[int] = None
    due_date: Optional[date] = None
    created_task_id: Optional[int] = None
    status: str = "Open"
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PMSSprintReviewResponse(BaseModel):
    sprint: PMSSprintResponse
    action_items: List[PMSSprintRetroActionItemResponse] = []
    completed_tasks: List[dict[str, Any]] = []
    incomplete_tasks: List[dict[str, Any]] = []


class SprintBurndownPoint(BaseModel):
    date: date
    ideal_remaining_points: float
    actual_remaining_points: int
    completed_points: int


class SprintBurndownResponse(BaseModel):
    sprint_id: int
    committed_story_points: int
    completed_story_points: int
    remaining_story_points: int
    points: List[SprintBurndownPoint] = []


class ProjectVelocityResponse(BaseModel):
    project_id: int
    average_velocity_points: float
    sprints: List[dict[str, Any]] = []


# ============= MILESTONE SCHEMAS =============
class PMSMilestoneBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=180)
    description: Optional[str] = None
    status: str = "Not Started"
    owner_user_id: Optional[int] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    progress_percent: int = 0
    client_approval_status: str = "Not Required"


class PMSMilestoneCreate(PMSMilestoneBase):
    pass


class PMSMilestoneUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    owner_user_id: Optional[int] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    progress_percent: Optional[int] = None
    client_approval_status: Optional[str] = None


class PMSMilestoneResponse(PMSMilestoneBase):
    id: int
    project_id: int
    completed_at: Optional[datetime] = None
    client_approved_at: Optional[datetime] = None
    client_rejected_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============= TAG SCHEMAS =============
class PMSTagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: Optional[str] = None


class PMSTagCreate(PMSTagBase):
    pass


class PMSTagUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


class PMSTagResponse(PMSTagBase):
    id: int
    organization_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============= TASK SCHEMAS =============
class PMSChecklistItemBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=220)
    is_completed: bool = False
    position: int = 0


class PMSChecklistItemCreate(PMSChecklistItemBase):
    pass


class PMSChecklistItemUpdate(BaseModel):
    title: Optional[str] = None
    is_completed: Optional[bool] = None
    position: Optional[int] = None


class PMSChecklistItemResponse(PMSChecklistItemBase):
    id: int
    task_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PMSTaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=220)
    description: Optional[str] = None
    task_key: str = Field(..., min_length=1, max_length=30)
    work_type: str = "Task"
    epic_key: Optional[str] = None
    initiative: Optional[str] = None
    component: Optional[str] = None
    severity: Optional[str] = None
    environment: Optional[str] = None
    affected_version: Optional[str] = None
    fix_version: Optional[str] = None
    release_name: Optional[str] = None
    status: str = "To Do"
    priority: str = "Medium"
    assignee_user_id: Optional[int] = None
    reporter_user_id: Optional[int] = None
    milestone_id: Optional[int] = None
    sprint_id: Optional[int] = None
    epic_id: Optional[int] = None
    component_id: Optional[int] = None
    release_id: Optional[int] = None
    parent_task_id: Optional[int] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    estimated_hours: Optional[Decimal] = None
    actual_hours: Optional[Decimal] = None
    original_estimate_hours: Optional[Decimal] = None
    remaining_estimate_hours: Optional[Decimal] = None
    story_points: Optional[int] = Field(None, ge=0)
    rank: Optional[int] = None
    security_level: str = "Internal"
    development_branch: Optional[str] = None
    development_commits: int = 0
    development_prs: int = 0
    development_deployments: int = 0
    development_build: str = "Pending"
    position: int = 0
    is_client_visible: bool = False
    is_blocking: bool = False
    recurrence_rule: Optional[str] = None
    recurrence_interval: Optional[int] = 1
    recurrence_until: Optional[date] = None


class PMSTaskCreate(PMSTaskBase):
    column_id: Optional[int] = None


class PMSTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    work_type: Optional[str] = None
    epic_key: Optional[str] = None
    initiative: Optional[str] = None
    component: Optional[str] = None
    severity: Optional[str] = None
    environment: Optional[str] = None
    affected_version: Optional[str] = None
    fix_version: Optional[str] = None
    release_name: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee_user_id: Optional[int] = None
    reporter_user_id: Optional[int] = None
    column_id: Optional[int] = None
    milestone_id: Optional[int] = None
    sprint_id: Optional[int] = None
    epic_id: Optional[int] = None
    component_id: Optional[int] = None
    release_id: Optional[int] = None
    parent_task_id: Optional[int] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    estimated_hours: Optional[Decimal] = None
    actual_hours: Optional[Decimal] = None
    original_estimate_hours: Optional[Decimal] = None
    remaining_estimate_hours: Optional[Decimal] = None
    story_points: Optional[int] = Field(None, ge=0)
    rank: Optional[int] = None
    security_level: Optional[str] = None
    development_branch: Optional[str] = None
    development_commits: Optional[int] = None
    development_prs: Optional[int] = None
    development_deployments: Optional[int] = None
    development_build: Optional[str] = None
    position: Optional[int] = None
    is_client_visible: Optional[bool] = None
    is_blocking: Optional[bool] = None
    recurrence_rule: Optional[str] = None
    recurrence_interval: Optional[int] = None
    recurrence_until: Optional[date] = None


class PMSTaskResponse(PMSTaskBase):
    id: int
    project_id: int
    board_id: Optional[int] = None
    column_id: Optional[int] = None
    subtask_count: int = 0
    completed_subtask_count: int = 0
    attachment_count: int = 0
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============= TASK DEPENDENCY SCHEMAS =============
class PMSTaskDependencyBase(BaseModel):
    depends_on_task_id: int
    dependency_type: str = "Finish To Start"
    lag_days: int = 0


class PMSTaskDependencyCreate(PMSTaskDependencyBase):
    pass


class PMSTaskDependencyResponse(PMSTaskDependencyBase):
    id: int
    task_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class PMSTaskDependencyDetail(PMSTaskDependencyResponse):
    task_key: Optional[str] = None
    depends_on_task_key: Optional[str] = None
    task_title: Optional[str] = None
    depends_on_task_title: Optional[str] = None
    source_task_id: Optional[int] = None
    target_task_id: Optional[int] = None
    source_task_key: Optional[str] = None
    target_task_key: Optional[str] = None
    source_task_title: Optional[str] = None
    target_task_title: Optional[str] = None


class TaskBulkUpdateRequest(BaseModel):
    task_ids: List[int] = Field(..., min_items=1)
    status: Optional[str] = None
    assignee_user_id: Optional[int] = None
    priority: Optional[str] = None
    sprint_id: Optional[int] = None
    release_id: Optional[int] = None
    component_id: Optional[int] = None


class TaskBulkUpdateResponse(BaseModel):
    updated_count: int
    tasks: List[PMSTaskResponse] = []


class PMSSavedFilterBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=140)
    view_type: str = "board"
    entity_type: str = "task"
    query: Optional[str] = None
    filters: Optional[dict[str, Any]] = None
    sort: Optional[dict[str, Any]] = None
    columns: Optional[Any] = None
    visibility: str = "private"
    is_default: bool = False
    is_shared: bool = False


class PMSSavedFilterCreate(PMSSavedFilterBase):
    project_id: Optional[int] = None


class PMSSavedFilterUpdate(BaseModel):
    name: Optional[str] = None
    view_type: Optional[str] = None
    entity_type: Optional[str] = None
    query: Optional[str] = None
    filters: Optional[dict[str, Any]] = None
    sort: Optional[dict[str, Any]] = None
    columns: Optional[Any] = None
    visibility: Optional[str] = None
    is_default: Optional[bool] = None
    is_shared: Optional[bool] = None


class PMSSavedFilterResponse(PMSSavedFilterBase):
    id: int
    organization_id: Optional[int] = None
    project_id: Optional[int] = None
    user_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PMSActivityResponse(BaseModel):
    id: int
    project_id: int
    task_id: Optional[int] = None
    sprint_id: Optional[int] = None
    actor_user_id: Optional[int] = None
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    summary: str
    metadata_json: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReleaseReadinessResponse(BaseModel):
    release_id: int
    release_name: str
    readiness_percent: int
    health: str
    total_tasks: int
    done_tasks: int
    open_blockers: int
    overdue_tasks: int
    severity_counts: dict[str, int] = {}


class WorkloadItem(BaseModel):
    user_id: Optional[int] = None
    sprint_id: Optional[int] = None
    task_count: int = 0
    story_points: int = 0
    estimated_hours: float = 0
    overdue_tasks: int = 0
    capacity_hours: Optional[float] = None
    load_percent: Optional[float] = None


class WorkloadResponse(BaseModel):
    project_id: int
    group_by: str
    items: List[WorkloadItem] = []


# ============= FILE ASSET SCHEMAS =============
class PMSFileAssetBase(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=240)
    original_name: str = Field(..., min_length=1, max_length=240)
    mime_type: Optional[str] = None
    size_bytes: int = 0
    storage_path: str = Field(..., min_length=1, max_length=500)
    visibility: str = "Internal"


class PMSFileAssetCreate(PMSFileAssetBase):
    uploaded_by_user_id: Optional[int] = None
    project_id: Optional[int] = None
    task_id: Optional[int] = None
    milestone_id: Optional[int] = None


class PMSFileAssetUpdate(BaseModel):
    visibility: Optional[str] = None
    file_name: Optional[str] = None


class PMSFileAssetResponse(PMSFileAssetBase):
    id: int
    uploaded_by_user_id: Optional[int] = None
    uploaded_by_name: Optional[str] = None
    project_id: Optional[int] = None
    task_id: Optional[int] = None
    milestone_id: Optional[int] = None
    version_number: int = 1
    download_url: Optional[str] = None
    preview_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============= COMMENT SCHEMAS =============
class PMSCommentBase(BaseModel):
    body: str = Field(..., min_length=1)
    body_format: str = "markdown"
    is_internal: bool = True


class PMSCommentCreate(PMSCommentBase):
    author_user_id: Optional[int] = None
    project_id: Optional[int] = None
    task_id: Optional[int] = None
    milestone_id: Optional[int] = None
    parent_comment_id: Optional[int] = None
    mentioned_user_ids: List[int] = []


class PMSCommentUpdate(BaseModel):
    body: Optional[str] = None
    body_format: Optional[str] = None
    is_internal: Optional[bool] = None


class PMSCommentResponse(PMSCommentBase):
    id: int
    author_user_id: Optional[int] = None
    project_id: Optional[int] = None
    task_id: Optional[int] = None
    milestone_id: Optional[int] = None
    parent_comment_id: Optional[int] = None
    is_edited: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    mentions: List[dict[str, Any]] = []

    class Config:
        from_attributes = True


# ============= TIME LOG SCHEMAS =============
class PMSTimeLogBase(BaseModel):
    log_date: date
    duration_minutes: int = Field(..., gt=0)
    description: Optional[str] = None
    is_billable: bool = False
    approval_status: str = "Pending"
    task_id: Optional[int] = None


class PMSTimeLogCreate(PMSTimeLogBase):
    project_id: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class PMSTimeLogUpdate(BaseModel):
    log_date: Optional[date] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, gt=0)
    description: Optional[str] = None
    is_billable: Optional[bool] = None
    approval_status: Optional[str] = None
    task_id: Optional[int] = None


class PMSTimeLogResponse(PMSTimeLogBase):
    id: int
    timesheet_id: Optional[int] = None
    user_id: int
    project_id: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PMSTimesheetEntryInput(BaseModel):
    project_id: int
    task_id: Optional[int] = None
    log_date: date
    duration_minutes: int = Field(..., ge=0)
    description: Optional[str] = None
    is_billable: bool = False
    time_log_id: Optional[int] = None


class PMSTimesheetCreate(BaseModel):
    week_start_date: date
    user_id: Optional[int] = None
    entries: List[PMSTimesheetEntryInput] = []


class PMSTimesheetUpdate(BaseModel):
    week_start_date: Optional[date] = None
    entries: List[PMSTimesheetEntryInput] = []


class PMSTimesheetRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=1)


class PMSTimesheetResponse(BaseModel):
    id: int
    organization_id: Optional[int] = None
    user_id: int
    week_start_date: date
    status: str
    submitted_at: Optional[datetime] = None
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    total_minutes: int = 0
    billable_minutes: int = 0
    non_billable_minutes: int = 0
    daily_totals: dict[str, int] = {}
    entries: List[dict[str, Any]] = []
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PMSRiskBase(BaseModel):
    project_id: int
    linked_task_id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=220)
    description: Optional[str] = None
    category: Optional[str] = None
    probability: int = Field(3, ge=1, le=5)
    impact: int = Field(3, ge=1, le=5)
    status: str = "open"
    owner_user_id: Optional[int] = None
    mitigation_plan: Optional[str] = None
    contingency_plan: Optional[str] = None
    due_date: Optional[date] = None


class PMSRiskCreate(PMSRiskBase):
    pass


class PMSRiskUpdate(BaseModel):
    project_id: Optional[int] = None
    linked_task_id: Optional[int] = None
    title: Optional[str] = Field(None, min_length=1, max_length=220)
    description: Optional[str] = None
    category: Optional[str] = None
    probability: Optional[int] = Field(None, ge=1, le=5)
    impact: Optional[int] = Field(None, ge=1, le=5)
    status: Optional[str] = None
    owner_user_id: Optional[int] = None
    mitigation_plan: Optional[str] = None
    contingency_plan: Optional[str] = None
    due_date: Optional[date] = None


class PMSRiskResponse(PMSRiskBase):
    id: int
    organization_id: Optional[int] = None
    risk_score: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============= CLIENT APPROVAL SCHEMAS =============
class PMSClientApprovalBase(BaseModel):
    status: str = "Pending"
    remarks: Optional[str] = None


class PMSClientApprovalCreate(BaseModel):
    project_id: int
    milestone_id: Optional[int] = None
    client_user_id: Optional[int] = None
    requested_by_user_id: Optional[int] = None


class PMSClientApprovalUpdate(BaseModel):
    status: Optional[str] = None
    remarks: Optional[str] = None


class PMSClientApprovalResponse(PMSClientApprovalBase):
    id: int
    project_id: int
    milestone_id: Optional[int] = None
    requested_by_user_id: Optional[int] = None
    client_user_id: Optional[int] = None
    decided_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============= KANBAN BOARD SCHEMAS =============
class KanbanTaskCard(PMSTaskResponse):
    """Task card for Kanban board display."""
    assignee_name: Optional[str] = None
    tags: Optional[List[PMSTagResponse]] = []


class KanbanColumn(PMSBoardColumnResponse):
    """Kanban column with tasks."""
    tasks: Optional[List[KanbanTaskCard]] = []
    task_count: int = 0


class KanbanBoard(PMSBoardResponse):
    """Full Kanban board with columns and tasks."""
    columns: Optional[List[KanbanColumn]] = []


class TaskReorderRequest(BaseModel):
    """Request to reorder tasks within or between columns."""
    task_id: int
    column_id: int
    position: int


# ============= DASHBOARD SCHEMAS =============
class ProjectMetrics(BaseModel):
    """Project overview metrics."""
    total_projects: int = 0
    active_projects: int = 0
    completed_projects: int = 0
    overdue_projects: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    overdue_tasks: int = 0
    high_risks: int = 0
    pending_approvals: int = 0
    team_utilization: float = 0.0
    hours_logged_this_week: Decimal = Decimal(0)
    upcoming_milestones: int = 0
    recent_activities: int = 0


class DashboardResponse(BaseModel):
    """Dashboard data response."""
    metrics: ProjectMetrics
    recent_projects: Optional[List[PMSProjectResponse]] = []
    recent_tasks: Optional[List[PMSTaskResponse]] = []
    recent_comments: Optional[List[PMSCommentResponse]] = []
