from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base_class import Base


class PMSClient(Base):
    __tablename__ = "pms_clients"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    company_name = Column(String(180))
    email = Column(String(150), index=True)
    phone = Column(String(40))
    website = Column(String(200))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class PMSProject(Base):
    __tablename__ = "pms_projects"
    __table_args__ = (UniqueConstraint("organization_id", "project_key", name="uq_pms_project_org_key"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    client_id = Column(Integer, ForeignKey("pms_clients.id", ondelete="SET NULL"), nullable=True, index=True)
    manager_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    project_key = Column(String(20), nullable=False, index=True)
    category = Column(String(80), index=True)
    description = Column(Text)
    status = Column(String(40), default="Draft", index=True)
    priority = Column(String(30), default="Medium", index=True)
    health = Column(String(30), default="Good", index=True)
    start_date = Column(Date)
    due_date = Column(Date, index=True)
    planned_start_date = Column(Date)
    planned_end_date = Column(Date)
    actual_start_date = Column(Date)
    actual_end_date = Column(Date)
    completed_at = Column(DateTime(timezone=True))
    budget_amount = Column(Numeric(12, 2))
    estimated_hours = Column(Numeric(10, 2))
    estimated_cost = Column(Numeric(12, 2))
    actual_cost = Column(Numeric(12, 2))
    billing_status = Column(String(40), default="Unbilled", index=True)
    progress_percent = Column(Integer, default=0)
    is_client_visible = Column(Boolean, default=False)
    is_template = Column(Boolean, default=False, index=True)
    is_archived = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class PMSProjectIntake(Base):
    __tablename__ = "pms_project_intakes"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    title = Column(String(180), nullable=False, index=True)
    description = Column(Text)
    requester_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    requester_name = Column(String(180))
    requester_email = Column(String(150), index=True)
    client_id = Column(Integer, ForeignKey("pms_clients.id", ondelete="SET NULL"), nullable=True, index=True)
    client_name = Column(String(180))
    priority = Column(String(30), default="Medium", index=True)
    desired_start_date = Column(Date)
    desired_due_date = Column(Date)
    budget_amount = Column(Numeric(12, 2))
    status = Column(String(30), default="submitted", index=True)
    review_notes = Column(Text)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True))
    created_project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PMSProjectMember(Base):
    __tablename__ = "pms_project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_pms_project_member"),)

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(40), default="Member", index=True)
    allocation_percent = Column(Numeric(5, 2), default=100)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PMSEpic(Base):
    __tablename__ = "pms_epics"
    __table_args__ = (UniqueConstraint("project_id", "epic_key", name="uq_pms_epic_project_key"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    epic_key = Column(String(60), nullable=False, index=True)
    name = Column(String(180), nullable=False)
    description = Column(Text)
    status = Column(String(40), default="Planned", index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    color = Column(String(30))
    start_date = Column(Date)
    end_date = Column(Date, index=True)
    target_date = Column(Date, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class PMSComponent(Base):
    __tablename__ = "pms_components"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_pms_component_project_name"),)

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False, index=True)
    description = Column(Text)
    lead_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    default_assignee_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PMSRelease(Base):
    __tablename__ = "pms_releases"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_pms_release_project_name"),)

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False, index=True)
    description = Column(Text)
    status = Column(String(40), default="Planning", index=True)
    release_date = Column(Date, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    readiness_percent = Column(Integer, default=0)
    launch_notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class PMSBoard(Base):
    __tablename__ = "pms_boards"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(140), nullable=False)
    board_type = Column(String(40), default="Kanban", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PMSBoardColumn(Base):
    __tablename__ = "pms_board_columns"

    id = Column(Integer, primary_key=True, index=True)
    board_id = Column(Integer, ForeignKey("pms_boards.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    status_key = Column(String(60), nullable=False, index=True)
    position = Column(Integer, default=0)
    wip_limit = Column(Integer)
    is_collapsed = Column(Boolean, default=False)
    color = Column(String(30))


class PMSSprint(Base):
    __tablename__ = "pms_sprints"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    goal = Column(Text)
    status = Column(String(30), default="Planned", index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    capacity_hours = Column(Numeric(8, 2))
    velocity_points = Column(Integer)
    committed_task_count = Column(Integer, default=0)
    committed_story_points = Column(Integer, default=0)
    completed_story_points = Column(Integer, default=0)
    scope_change_count = Column(Integer, default=0)
    carry_forward_task_count = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    completed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    commitment_snapshot = Column(Text)
    completion_summary = Column(Text)
    review_notes = Column(Text)
    retrospective_notes = Column(Text)
    what_went_well = Column(Text)
    what_did_not_go_well = Column(Text)
    outcome = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PMSSprintRetroActionItem(Base):
    __tablename__ = "pms_sprint_retro_action_items"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    sprint_id = Column(Integer, ForeignKey("pms_sprints.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(220), nullable=False)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    due_date = Column(Date)
    created_task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(30), default="Open", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PMSMilestone(Base):
    __tablename__ = "pms_milestones"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(180), nullable=False)
    description = Column(Text)
    status = Column(String(40), default="Not Started", index=True)
    start_date = Column(Date)
    due_date = Column(Date, index=True)
    completed_at = Column(DateTime(timezone=True))
    progress_percent = Column(Integer, default=0)
    client_approval_status = Column(String(40), default="Not Required", index=True)
    client_approved_at = Column(DateTime(timezone=True))
    client_rejected_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PMSTask(Base):
    __tablename__ = "pms_tasks"
    __table_args__ = (UniqueConstraint("project_id", "task_key", name="uq_pms_task_project_key"),)

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    board_id = Column(Integer, ForeignKey("pms_boards.id", ondelete="SET NULL"), nullable=True, index=True)
    column_id = Column(Integer, ForeignKey("pms_board_columns.id", ondelete="SET NULL"), nullable=True, index=True)
    milestone_id = Column(Integer, ForeignKey("pms_milestones.id", ondelete="SET NULL"), nullable=True, index=True)
    sprint_id = Column(Integer, ForeignKey("pms_sprints.id", ondelete="SET NULL"), nullable=True, index=True)
    epic_id = Column(Integer, ForeignKey("pms_epics.id", ondelete="SET NULL"), nullable=True, index=True)
    component_id = Column(Integer, ForeignKey("pms_components.id", ondelete="SET NULL"), nullable=True, index=True)
    release_id = Column(Integer, ForeignKey("pms_releases.id", ondelete="SET NULL"), nullable=True, index=True)
    parent_task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    assignee_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reporter_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(220), nullable=False)
    description = Column(Text)
    task_key = Column(String(30), nullable=False, index=True)
    work_type = Column(String(40), default="Task", index=True)
    epic_key = Column(String(60), index=True)
    initiative = Column(String(160))
    component = Column(String(120), index=True)
    severity = Column(String(20), index=True)
    environment = Column(String(80))
    affected_version = Column(String(80))
    fix_version = Column(String(80), index=True)
    release_name = Column(String(120), index=True)
    status = Column(String(50), default="To Do", index=True)
    priority = Column(String(30), default="Medium", index=True)
    start_date = Column(Date)
    due_date = Column(Date, index=True)
    completed_at = Column(DateTime(timezone=True))
    estimated_hours = Column(Numeric(8, 2))
    actual_hours = Column(Numeric(8, 2))
    original_estimate_hours = Column(Numeric(8, 2))
    remaining_estimate_hours = Column(Numeric(8, 2))
    story_points = Column(Integer)
    rank = Column(Integer, index=True)
    security_level = Column(String(40), default="Internal", index=True)
    development_branch = Column(String(200))
    development_commits = Column(Integer, default=0)
    development_prs = Column(Integer, default=0)
    development_deployments = Column(Integer, default=0)
    development_build = Column(String(30), default="Pending", index=True)
    position = Column(Integer, default=0)
    is_client_visible = Column(Boolean, default=False)
    is_blocking = Column(Boolean, default=False, index=True)
    recurrence_rule = Column(String(40), index=True)
    recurrence_interval = Column(Integer, default=1)
    recurrence_until = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class PMSTaskDependency(Base):
    __tablename__ = "pms_task_dependencies"
    __table_args__ = (UniqueConstraint("task_id", "depends_on_task_id", name="uq_pms_task_dependency"),)

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    depends_on_task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    dependency_type = Column(String(40), default="Finish To Start")
    lag_days = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PMSDevIntegration(Base):
    __tablename__ = "pms_dev_integrations"
    __table_args__ = (UniqueConstraint("project_id", "provider", "repo_owner", "repo_name", name="uq_pms_dev_integration_repo"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(30), nullable=False, index=True)
    repo_owner = Column(String(160), nullable=False, index=True)
    repo_name = Column(String(180), nullable=False, index=True)
    access_token_encrypted = Column(Text)
    webhook_secret_encrypted = Column(Text)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PMSDevLink(Base):
    __tablename__ = "pms_dev_links"
    __table_args__ = (UniqueConstraint("task_id", "provider", "link_type", "external_id", name="uq_pms_dev_link_external"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(30), nullable=False, index=True)
    link_type = Column(String(30), nullable=False, index=True)
    external_id = Column(String(240), nullable=False, index=True)
    title = Column(String(300))
    url = Column(String(800))
    status = Column(String(60), index=True)
    author = Column(String(160))
    metadata_json = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PMSSavedFilter(Base):
    __tablename__ = "pms_saved_filters"
    __table_args__ = (UniqueConstraint("project_id", "user_id", "name", name="uq_pms_saved_filter_owner_name"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(140), nullable=False)
    view_type = Column(String(40), default="board", index=True)
    entity_type = Column(String(40), default="task", index=True)
    query = Column(Text, nullable=False)
    filters_json = Column(Text)
    sort_json = Column(Text)
    columns_json = Column(Text)
    visibility = Column(String(30), default="private", index=True)
    is_default = Column(Boolean, default=False, index=True)
    is_shared = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PMSActivity(Base):
    __tablename__ = "pms_activities"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    sprint_id = Column(Integer, ForeignKey("pms_sprints.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    entity_type = Column(String(40), nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    summary = Column(String(300), nullable=False)
    metadata_json = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class PMSChecklistItem(Base):
    __tablename__ = "pms_checklist_items"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(220), nullable=False)
    is_completed = Column(Boolean, default=False)
    position = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PMSTag(Base):
    __tablename__ = "pms_tags"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_pms_tag_org_name"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(100), nullable=False)
    color = Column(String(30))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PMSTaskTag(Base):
    __tablename__ = "pms_task_tags"

    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("pms_tags.id", ondelete="CASCADE"), primary_key=True)


class PMSFileAsset(Base):
    __tablename__ = "pms_file_assets"

    id = Column(Integer, primary_key=True, index=True)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=True, index=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    milestone_id = Column(Integer, ForeignKey("pms_milestones.id", ondelete="CASCADE"), nullable=True, index=True)
    file_name = Column(String(240), nullable=False)
    original_name = Column(String(240), nullable=False)
    mime_type = Column(String(120))
    size_bytes = Column(Integer, default=0)
    storage_path = Column(String(500), nullable=False)
    version_number = Column(Integer, default=1)
    visibility = Column(String(40), default="Internal", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class PMSComment(Base):
    __tablename__ = "pms_comments"

    id = Column(Integer, primary_key=True, index=True)
    author_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=True, index=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    milestone_id = Column(Integer, ForeignKey("pms_milestones.id", ondelete="CASCADE"), nullable=True, index=True)
    parent_comment_id = Column(Integer, ForeignKey("pms_comments.id", ondelete="CASCADE"), nullable=True, index=True)
    body = Column(Text, nullable=False)
    body_format = Column(String(20), default="markdown", index=True)
    is_internal = Column(Boolean, default=True, index=True)
    is_edited = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class PMSMention(Base):
    __tablename__ = "pms_mentions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    comment_id = Column(Integer, ForeignKey("pms_comments.id", ondelete="CASCADE"), nullable=True, index=True)
    mentioned_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mentioned_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    notification_id = Column(Integer, ForeignKey("notifications.id", ondelete="SET NULL"), nullable=True, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class PMSTimeLog(Base):
    __tablename__ = "pms_time_logs"

    id = Column(Integer, primary_key=True, index=True)
    timesheet_id = Column(Integer, ForeignKey("pms_timesheets.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    log_date = Column(Date, nullable=False, index=True)
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    duration_minutes = Column(Integer, nullable=False)
    description = Column(Text)
    is_billable = Column(Boolean, default=False, index=True)
    approval_status = Column(String(30), default="Pending", index=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PMSTimesheet(Base):
    __tablename__ = "pms_timesheets"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", "week_start_date", name="uq_pms_timesheet_user_week"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    week_start_date = Column(Date, nullable=False, index=True)
    status = Column(String(30), default="draft", index=True)
    submitted_at = Column(DateTime(timezone=True))
    approved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    approved_at = Column(DateTime(timezone=True))
    rejection_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PMSUserCapacity(Base):
    __tablename__ = "pms_user_capacity"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", "week_start_date", name="uq_pms_user_capacity_week"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    week_start_date = Column(Date, nullable=False, index=True)
    capacity_hours = Column(Numeric(8, 2), nullable=False, default=40)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PMSRisk(Base):
    __tablename__ = "pms_risks"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    linked_task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(220), nullable=False)
    description = Column(Text)
    category = Column(String(80), index=True)
    probability = Column(Integer, default=3, index=True)
    impact = Column(Integer, default=3, index=True)
    risk_score = Column(Integer, default=9, index=True)
    status = Column(String(30), default="open", index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    mitigation_plan = Column(Text)
    contingency_plan = Column(Text)
    due_date = Column(Date, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class PMSClientApproval(Base):
    __tablename__ = "pms_client_approvals"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    milestone_id = Column(Integer, ForeignKey("pms_milestones.id", ondelete="CASCADE"), nullable=True, index=True)
    requested_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    client_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(30), default="Pending", index=True)
    remarks = Column(Text)
    decided_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
