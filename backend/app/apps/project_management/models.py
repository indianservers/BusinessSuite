from sqlalchemy import JSON, Boolean, Column, Date, DateTime, ForeignKey, Integer, LargeBinary, Numeric, String, Text, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import deferred, relationship

from app.db.base_class import Base


class PMSNoteFolder(Base):
    __tablename__ = "pms_note_folders"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("pms_note_folders.id", ondelete="SET NULL"), nullable=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="SET NULL"), nullable=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(120), nullable=False)
    color = Column(String(7), nullable=False, default="#8b5cf6")
    icon = Column(String(24), nullable=False, default="folder")
    position = Column(Integer, nullable=False, default=0)
    version = Column(Integer, nullable=False, default=1)
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class PMSNote(Base):
    __tablename__ = "pms_private_notes"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    folder_id = Column(Integer, ForeignKey("pms_note_folders.id", ondelete="SET NULL"), nullable=True, index=True)
    favorite = Column(Boolean, nullable=False, default=False)
    title = Column(String(180), nullable=False, default="Untitled note")
    content = Column(Text, nullable=False, default="")
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="SET NULL"), nullable=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="SET NULL"), nullable=True)
    tags = Column(JSON, nullable=False, default=list)
    pinned = Column(Boolean, nullable=False, default=False)
    archived = Column(Boolean, nullable=False, default=False)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class PMSNoteRevision(Base):
    __tablename__ = "pms_private_note_revisions"
    __table_args__ = (UniqueConstraint("note_id", "version", name="uq_private_note_revision"),)
    id = Column(Integer, primary_key=True)
    note_id = Column(Integer, ForeignKey("pms_private_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    title = Column(String(180), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PMSNoteShare(Base):
    __tablename__ = "pms_note_shares"
    __table_args__ = (UniqueConstraint("note_id", "user_id", name="uq_pms_note_share"),)
    id = Column(Integer, primary_key=True)
    note_id = Column(Integer, ForeignKey("pms_private_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)


class PMSNoteEvent(Base):
    __tablename__ = "pms_note_events"
    id = Column(Integer, primary_key=True)
    note_id = Column(Integer, ForeignKey("pms_private_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(40), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PMSNoteAttachment(Base):
    __tablename__ = "pms_private_note_attachments"
    id = Column(Integer, primary_key=True)
    note_id = Column(Integer, ForeignKey("pms_private_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    media_type = Column(String(100), nullable=False)
    size = Column(Integer, nullable=False)
    # Bytes never enter public /uploads or bearer-link storage. Listing metadata doesn't load them.
    body = deferred(Column(LargeBinary, nullable=False))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class PMSNoteTaskLink(Base):
    __tablename__ = "pms_private_note_task_links"
    __table_args__ = (UniqueConstraint("note_id", "request_key", name="uq_private_note_task_request"),)
    id = Column(Integer, primary_key=True)
    note_id = Column(Integer, ForeignKey("pms_private_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="CASCADE"), nullable=False)
    request_key = Column(String(36), nullable=False)
    request_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PMSClient(Base):
    __tablename__ = "pms_clients"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(180), nullable=False, index=True)
    company_name = Column(String(180))
    email = Column(String(150), index=True)
    phone = Column(String(40))
    phone_country_code = Column(String(5), nullable=True)
    website = Column(String(200))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class PMSWorkspace(Base):
    __tablename__ = "pms_workspaces"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(180), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class PMSWorkspaceMember(Base):
    __tablename__ = "pms_workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_pms_workspace_member"),)
    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)


class PMSWorkspaceInvitation(Base):
    __tablename__ = "pms_workspace_invitations"
    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(100), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default="pending")
    expires_at = Column(DateTime, nullable=False)


class PMSProject(Base):
    __tablename__ = "pms_projects"
    __table_args__ = (UniqueConstraint("organization_id", "project_key", name="uq_pms_project_org_key"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id", ondelete="RESTRICT"), nullable=True, index=True)
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
    assignments = relationship("PMSTaskAssignee", cascade="all, delete-orphan", lazy="selectin", order_by="PMSTaskAssignee.user_id")

    @property
    def assignee_user_ids(self):
        return sorted({a.user_id for a in self.assignments} | ({self.assignee_user_id} if self.assignee_user_id else set()))

    @assignee_user_ids.setter
    def assignee_user_ids(self, ids):
        existing = {a.user_id: a for a in self.assignments}
        retained = set(ids or []) | {a.user_id for a in self.assignments if a.source_key}
        self.assignments = [existing.get(user_id) or PMSTaskAssignee(user_id=user_id) for user_id in sorted(retained)]
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


class PMSTaskAssignee(Base):
    __tablename__ = "pms_task_assignees"
    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    execution_status = Column(String(30), nullable=False, default="To Do", server_default="To Do", index=True)
    due_date = Column(Date, index=True)
    reviewer_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    maximum_score = Column(Integer, nullable=False, default=100, server_default="100")
    progress_percent = Column(Integer, nullable=False, default=0, server_default="0")
    work_notes = Column(Text)
    cancelled_at = Column(DateTime(timezone=True))
    source_key = Column(String(80), index=True)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PMSWorkSubmission(Base):
    __tablename__ = "pms_work_submissions"
    __table_args__ = (UniqueConstraint("task_id", "user_id", "version", name="uq_pms_work_version"),)
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    notes = Column(Text, nullable=False)
    links = Column(JSON, nullable=False, default=list)
    files = Column(JSON, nullable=False, default=list)
    revision_note = Column(Text)
    status = Column(String(30), nullable=False, default="Pending Review", index=True)
    legacy_submission_id = Column(Integer, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class PMSWorkReview(Base):
    __tablename__ = "pms_work_reviews"
    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey("pms_work_submissions.id", ondelete="CASCADE"), nullable=False, unique=True)
    reviewer_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    decision = Column(String(30), nullable=False)
    score = Column(Integer, nullable=False)
    maximum_score = Column(Integer, nullable=False)
    communication_score = Column(Integer)
    rubric = Column(JSON, default=dict)
    feedback = Column(Text, nullable=False)
    strengths = Column(Text)
    improvements = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


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


class PMSWorkspaceEntry(Base):
    __tablename__ = "pms_workspace_entries"
    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    kind = Column(String(12), nullable=False)
    body = Column(Text, nullable=False)
    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class PMSCustomField(Base):
    __tablename__ = "pms_custom_fields"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_pms_custom_field_name"),)
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    task_type = Column(String(40), nullable=False, default="", server_default="")
    field_type = Column(String(20), nullable=False)
    options_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PMSCustomFieldValue(Base):
    __tablename__ = "pms_custom_field_values"
    field_id = Column(Integer, ForeignKey("pms_custom_fields.id", ondelete="CASCADE"), primary_key=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="CASCADE"), primary_key=True)
    value_json = Column(Text, nullable=False)


class PMSWorkspaceTeam(Base):
    __tablename__ = "pms_workspace_teams"
    __table_args__ = (UniqueConstraint("workspace_id", "alias", name="uq_pms_team_alias"),)
    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    alias = Column(String(60), nullable=False)
    member_ids_json = Column(Text, nullable=False, default="[]")


class PMSDirectConversation(Base):
    __tablename__ = "pms_direct_conversations"
    __table_args__ = (UniqueConstraint("workspace_id", "first_user_id", "second_user_id", name="uq_pms_direct_pair"),)
    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    first_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    second_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class PMSDirectMessage(Base):
    __tablename__ = "pms_direct_messages"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("pms_direct_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    client_id = Column(String(36), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    __table_args__ = (UniqueConstraint("conversation_id", "author_id", "client_id", name="uq_pms_dm_client"),)


class PMSTaskType(Base):
    __tablename__ = "pms_task_types"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_pms_task_type_name"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=True, index=True)
    name = Column(String(40), nullable=False)
    plural_name = Column(String(60), nullable=False, default="", server_default="")
    description = Column(String(1000), nullable=False, default="")
    category = Column(String(60), nullable=False, default="General")
    icon = Column(String(30), nullable=False, default="task")
    color = Column(String(7), nullable=False, default="#7c3aed")
    default_priority = Column(String(30), nullable=False, default="Medium")
    archived = Column(Boolean, nullable=False, default=False)


class PMSRunningTimer(Base):
    __tablename__ = "pms_running_timers"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="SET NULL"), nullable=True)
    session_key = Column(String(36), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    timezone = Column(String(80), nullable=False, default="UTC")
    description = Column(Text, nullable=False, default="")
    is_billable = Column(Boolean, nullable=False, default=False)
    active = Column(Boolean, nullable=False, default=True)
    log_id = Column(Integer, ForeignKey("pms_time_logs.id", ondelete="SET NULL"), nullable=True)


class PMSDocument(Base):
    __tablename__ = "pms_documents"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(180), nullable=False)
    content = Column(Text, nullable=False, default="")
    version = Column(Integer, nullable=False, default=1)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class PMSDocumentRevision(Base):
    __tablename__ = "pms_document_revisions"
    __table_args__ = (UniqueConstraint("document_id", "version", name="uq_pms_doc_revision"),)
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("pms_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    title = Column(String(180), nullable=False)
    content = Column(Text, nullable=False)
    task_id = Column(Integer, nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PMSPlannerPreference(Base):
    __tablename__ = "pms_planner_preferences"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    revision = Column(Integer, nullable=False, default=1)
    payload = Column(JSON, nullable=False, default=dict)


class PMSCalendarEvent(Base):
    __tablename__ = "pms_calendar_events"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id", ondelete="CASCADE"), nullable=True, index=True)
    task_id = Column(Integer, ForeignKey("pms_tasks.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(220), nullable=False)
    description = Column(Text, nullable=False, default="")
    start_at = Column(DateTime(timezone=True), nullable=False, index=True)
    end_at = Column(DateTime(timezone=True), nullable=False)
    timezone = Column(String(80), nullable=False, default="UTC")
    kind = Column(String(20), nullable=False, default="meeting")
    visibility = Column(String(20), nullable=False, default="private")
    meeting_url = Column(String(2000), nullable=False, default="")
    revision = Column(Integer, nullable=False, default=1)

# Register additive messaging tables for module metadata / migration discovery.
from .chat_models import ChatConversation, ChatMember, ChatMessage, ChatAttachment  # noqa: E402,F401

# Register recovery tables with both migration chains.
from .recovery_models import RecoveryChange, RecoveryPoint, RecoveryPolicy  # noqa: E402, F401

from .workspace_lifecycle import WorkspaceArchive  # noqa: E402, F401
