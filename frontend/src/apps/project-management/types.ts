/**
 * KaryaFlow - Project Management Types
 * Complete TypeScript interfaces for all project management entities
 */

// ============= ENUMS & LITERALS =============
export type ProjectStatus = "Draft" | "Planned" | "Active" | "On Hold" | "Completed" | "Cancelled" | "Archived";
export type ProjectPriority = "Low" | "Medium" | "High" | "Critical";
export type ProjectHealth = "Good" | "At Risk" | "Critical" | "Blocked";

export type TaskStatus = "Backlog" | "To Do" | "In Progress" | "In Review" | "Blocked" | "Done" | "Cancelled";
export type TaskPriority = "Low" | "Medium" | "High" | "Urgent";

export type MilestoneStatus = "Not Started" | "In Progress" | "At Risk" | "Completed" | "Delayed" | "Cancelled";
export type ApprovalStatus = "Not Required" | "Pending" | "Approved" | "Rejected";

export type FileVisibility = "Internal" | "Project Team" | "Client Visible" | "Private";
export type TimeApprovalStatus = "Pending" | "Approved" | "Rejected";

// ============= CLIENT TYPES =============
export interface PMSClient {
  id: number;
  organization_id?: number;
  name: string;
  company_name?: string;
  email?: string;
  phone?: string;
  website?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface CreateClientInput {
  name: string;
  company_name?: string;
  email?: string;
  phone?: string;
  website?: string;
  notes?: string;
}

// ============= PROJECT TYPES =============
export interface PMSProject {
  id: number;
  organization_id?: number;
  name: string;
  project_key: string;
  description?: string;
  client_id?: number;
  manager_user_id?: number;
  status: ProjectStatus;
  priority: ProjectPriority;
  health: ProjectHealth;
  start_date?: string;
  due_date?: string;
  completed_at?: string;
  budget_amount?: number;
  actual_cost?: number;
  progress_percent: number;
  is_client_visible: boolean;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateProjectInput {
  name: string;
  project_key: string;
  description?: string;
  client_id?: number;
  manager_user_id?: number;
  status?: ProjectStatus;
  priority?: ProjectPriority;
  start_date?: string;
  due_date?: string;
  budget_amount?: number;
}

export interface PMSProjectIntake {
  id: number;
  organization_id?: number;
  requester_user_id?: number;
  title: string;
  description?: string;
  requester_name?: string;
  requester_email?: string;
  client_id?: number;
  client_name?: string;
  priority: ProjectPriority | string;
  desired_start_date?: string;
  desired_due_date?: string;
  budget_amount?: number;
  status: string;
  review_notes?: string;
  reviewed_by_user_id?: number;
  reviewed_at?: string;
  created_project_id?: number;
  created_at: string;
  updated_at?: string;
}

export interface CreateProjectIntakeInput {
  title: string;
  description?: string;
  requester_name?: string;
  requester_email?: string;
  client_id?: number;
  client_name?: string;
  priority?: ProjectPriority | string;
  desired_start_date?: string;
  desired_due_date?: string;
  budget_amount?: number;
}

// ============= TASK TYPES =============
export interface PMSChecklistItem {
  id: number;
  task_id: number;
  title: string;
  is_completed: boolean;
  position: number;
  created_at: string;
  updated_at: string;
}

export interface CreateChecklistItemInput {
  title: string;
  is_completed?: boolean;
  position?: number;
}

export interface PMSTask {
  id: number;
  project_id: number;
  board_id?: number;
  column_id?: number;
  milestone_id?: number;
  sprint_id?: number;
  epic_id?: number;
  component_id?: number;
  release_id?: number;
  parent_task_id?: number;
  title: string;
  description?: string;
  task_key: string;
  work_type: "Epic" | "Story" | "Task" | "Bug" | "Sub-task" | string;
  epic_key?: string;
  initiative?: string;
  component?: string;
  severity?: "S1" | "S2" | "S3" | "S4" | string;
  environment?: string;
  affected_version?: string;
  fix_version?: string;
  release_name?: string;
  status: TaskStatus;
  priority: TaskPriority;
  assignee_user_id?: number;
  reporter_user_id?: number;
  start_date?: string;
  due_date?: string;
  completed_at?: string;
  estimated_hours?: number;
  actual_hours?: number;
  original_estimate_hours?: number;
  remaining_estimate_hours?: number;
  story_points?: number;
  subtask_count?: number;
  completed_subtask_count?: number;
  attachment_count?: number;
  rank?: number;
  security_level: "Internal" | "Client Visible" | "Private" | string;
  development_branch?: string;
  development_commits: number;
  development_prs: number;
  development_deployments: number;
  development_build: "Passing" | "Failing" | "Pending" | string;
  position: number;
  is_client_visible: boolean;
  is_blocking: boolean;
  tags?: Array<string | PMSTag>;
  created_at: string;
  updated_at: string;
}

export interface PMSTaskListItem extends PMSTask {
  project_name?: string;
  project_key?: string;
  epic_name?: string;
  sprint_name?: string;
  assignee_name?: string;
  reporter_name?: string;
}

export interface PMSTaskListOption {
  id: number;
  name: string;
  project_id?: number;
  project_key?: string;
  epic_key?: string;
}

export interface PMSTaskListFilters {
  projects: PMSTaskListOption[];
  sprints: PMSTaskListOption[];
  epics: PMSTaskListOption[];
  statuses: string[];
  priorities: string[];
  assignees: PMSTaskListOption[];
  reporters: PMSTaskListOption[];
  tags: string[];
}

export interface PMSTaskListResponse {
  items: PMSTaskListItem[];
  total: number;
  page: number;
  pageSize: number;
  pages: number;
  filters: PMSTaskListFilters;
}

export interface PMSBacklogSprint extends PMSSprint {
  tasks: PMSTaskListItem[];
}

export interface PMSBacklogResponse {
  project: { id: number; name: string; project_key?: string };
  backlog: PMSTaskListItem[];
  sprints: PMSBacklogSprint[];
}

export interface PMSTaskListQuery {
  projectId?: number | string;
  sprintId?: number | string;
  epicId?: number | string;
  status?: string;
  priority?: string;
  assigneeId?: number | string;
  reporterId?: number | string;
  tag?: string;
  search?: string;
  dueFrom?: string;
  dueTo?: string;
  createdFrom?: string;
  createdTo?: string;
  updatedFrom?: string;
  updatedTo?: string;
  storyPointsMin?: number | string;
  storyPointsMax?: number | string;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
  page?: number;
  pageSize?: number;
}

export interface CreateTaskInput {
  title: string;
  description?: string;
  task_key: string;
  work_type?: "Epic" | "Story" | "Task" | "Bug" | "Sub-task" | string;
  epic_key?: string;
  initiative?: string;
  component?: string;
  severity?: "S1" | "S2" | "S3" | "S4" | string;
  environment?: string;
  affected_version?: string;
  fix_version?: string;
  release_name?: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  assignee_user_id?: number;
  reporter_user_id?: number;
  parent_task_id?: number;
  epic_id?: number;
  component_id?: number;
  release_id?: number;
  start_date?: string;
  due_date?: string;
  estimated_hours?: number;
  original_estimate_hours?: number;
  remaining_estimate_hours?: number;
  story_points?: number;
  rank?: number;
  security_level?: "Internal" | "Client Visible" | "Private" | string;
  development_branch?: string;
  development_commits?: number;
  development_prs?: number;
  development_deployments?: number;
  development_build?: "Passing" | "Failing" | "Pending" | string;
  is_client_visible?: boolean;
}

// ============= KANBAN TYPES =============
export interface PMSBoardColumn {
  id: number;
  board_id: number;
  name: string;
  status_key: string;
  position: number;
  wip_limit?: number;
  is_collapsed: boolean;
  color?: string;
  tasks?: PMSTask[];
  task_count: number;
}

export interface PMSBoard {
  id: number;
  project_id: number;
  name: string;
  board_type: string; // "Kanban", "Scrum", etc.
  created_at: string;
  columns?: PMSBoardColumn[];
}

export interface TaskReorderPayload {
  task_id: number;
  column_id: number;
  position: number;
}

// ============= MILESTONE TYPES =============
export interface PMSMilestone {
  id: number;
  project_id: number;
  name: string;
  description?: string;
  status: MilestoneStatus;
  owner_user_id?: number;
  start_date?: string;
  due_date?: string;
  completed_at?: string;
  progress_percent: number;
  client_approval_status: ApprovalStatus;
  client_approved_at?: string;
  client_rejected_reason?: string;
  created_at: string;
  updated_at: string;
}

export interface CreateMilestoneInput {
  name: string;
  description?: string;
  status?: MilestoneStatus;
  owner_user_id?: number;
  start_date?: string;
  due_date?: string;
  progress_percent?: number;
}

// ============= COMMENT TYPES (COLLABORATION) =============
export interface PMSComment {
  id: number;
  author_user_id?: number;
  project_id?: number;
  task_id?: number;
  milestone_id?: number;
  parent_comment_id?: number;
  body: string;
  body_format: "markdown" | "plain" | string;
  is_internal: boolean;
  is_edited: boolean;
  created_at: string;
  updated_at: string;
  mentions?: Array<{
    id: number;
    mentioned_user_id: number;
    mentioned_by_user_id?: number;
    task_id: number;
    project_id: number;
    comment_id?: number;
    read_at?: string;
    created_at: string;
    user?: PMSMentionUser;
  }>;
  author?: {
    id: number;
    name: string;
    avatar_url?: string;
  };
}

export interface CreateCommentInput {
  body: string;
  body_format?: "markdown" | "plain";
  is_internal?: boolean;
  parent_comment_id?: number;
  mentioned_user_ids?: number[];
}

export interface PMSMentionUser {
  id: number;
  email: string;
  name: string;
}

export interface PMSNotification {
  id: number;
  title: string;
  message: string;
  event_type?: string;
  related_entity_type?: string;
  related_entity_id?: number;
  action_url?: string;
  is_read: boolean;
  read_at?: string;
  created_at: string;
}

// ============= FILE TYPES =============
export interface PMSFileAsset {
  id: number;
  uploaded_by_user_id?: number;
  uploaded_by_name?: string;
  project_id?: number;
  task_id?: number;
  milestone_id?: number;
  file_name: string;
  original_name: string;
  mime_type?: string;
  size_bytes: number;
  storage_path: string;
  version_number: number;
  visibility: FileVisibility;
  download_url?: string;
  preview_url?: string;
  created_at: string;
  updated_at: string;
}

export interface CreateFileAssetInput {
  file_name: string;
  original_name: string;
  mime_type?: string;
  size_bytes: number;
  storage_path: string;
  visibility?: FileVisibility;
}

// ============= TIME LOG TYPES =============
export interface PMSTimeLog {
  id: number;
  timesheet_id?: number;
  user_id: number;
  project_id: number;
  task_id?: number;
  log_date: string;
  start_time?: string;
  end_time?: string;
  duration_minutes: number;
  description?: string;
  is_billable: boolean;
  approval_status: TimeApprovalStatus;
  approved_by_user_id?: number;
  approved_at?: string;
  created_at: string;
  updated_at: string;
}

export interface CreateTimeLogInput {
  project_id: number;
  task_id?: number;
  log_date: string;
  start_time?: string;
  end_time?: string;
  duration_minutes: number;
  description?: string;
  is_billable?: boolean;
  approval_status?: TimeApprovalStatus;
}

export interface PMSTimesheetEntry {
  id?: number;
  time_log_id?: number;
  project_id: number;
  project_name?: string;
  task_id?: number;
  task_key?: string;
  task_title?: string;
  log_date: string;
  duration_minutes: number;
  description?: string;
  is_billable: boolean;
  approval_status?: TimeApprovalStatus;
}

export interface PMSTimesheet {
  id: number;
  organization_id?: number;
  user_id: number;
  week_start_date: string;
  status: "draft" | "submitted" | "approved" | "rejected";
  submitted_at?: string;
  approved_by_user_id?: number;
  approved_at?: string;
  rejection_reason?: string;
  total_minutes: number;
  billable_minutes: number;
  non_billable_minutes: number;
  daily_totals: Record<string, number>;
  entries: PMSTimesheetEntry[];
  created_at: string;
  updated_at?: string;
}

export interface TimesheetEntryInput {
  time_log_id?: number;
  project_id: number;
  task_id?: number;
  log_date: string;
  duration_minutes: number;
  description?: string;
  is_billable?: boolean;
}

export interface TimesheetPayload {
  week_start_date?: string;
  user_id?: number;
  entries?: TimesheetEntryInput[];
}

// ============= TAG TYPES =============
export interface PMSTag {
  id: number;
  organization_id?: number;
  name: string;
  color?: string;
  created_at: string;
}

export interface CreateTagInput {
  name: string;
  color?: string;
}

// ============= SPRINT TYPES =============
export interface PMSSprint {
  id: number;
  project_id: number;
  name: string;
  goal?: string;
  status: "Planned" | "Active" | "Completed" | "Cancelled";
  start_date: string;
  end_date: string;
  capacity_hours?: number;
  velocity_points?: number;
  committed_task_count: number;
  committed_story_points: number;
  completed_story_points: number;
  scope_change_count: number;
  carry_forward_task_count: number;
  started_at?: string;
  completed_at?: string;
  completed_by_user_id?: number;
  commitment_snapshot?: string;
  completion_summary?: string;
  review_notes?: string;
  retrospective_notes?: string;
  what_went_well?: string;
  what_did_not_go_well?: string;
  outcome?: string;
  created_at: string;
  updated_at: string;
}

export interface PMSSprintActionItem {
  id?: number;
  sprint_id?: number;
  title: string;
  owner_user_id?: number | null;
  due_date?: string | null;
  created_task_id?: number | null;
  status?: string;
  created_at?: string;
  updated_at?: string;
}

export interface PMSSprintReview {
  sprint: PMSSprint;
  action_items: PMSSprintActionItem[];
  completed_tasks: Array<Pick<PMSTaskListItem, "id" | "task_key" | "title" | "status" | "priority" | "story_points" | "assignee_user_id" | "due_date">>;
  incomplete_tasks: Array<Pick<PMSTaskListItem, "id" | "task_key" | "title" | "status" | "priority" | "story_points" | "assignee_user_id" | "due_date">>;
}

export interface SprintCompletePayload {
  carry_forward_sprint_id?: number;
  incomplete_action?: "move_to_backlog" | "move_to_next_sprint" | "keep_in_sprint";
  review_notes?: string;
  retrospective_notes?: string;
  what_went_well?: string;
  what_did_not_go_well?: string;
  outcome?: string;
  action_items?: Array<Partial<PMSSprintActionItem> & { title: string }>;
  create_action_item_tasks?: boolean;
}

// ============= PROJECT MEMBER TYPES =============
export interface PMSProjectMember {
  id: number;
  project_id: number;
  user_id: number;
  role: "Manager" | "Lead" | "Member" | "Viewer" | "Client";
  created_at: string;
}

// ============= PLANNING OBJECT TYPES =============
export interface PMSEpic {
  id: number;
  organization_id?: number;
  project_id: number;
  epic_key: string;
  name: string;
  description?: string;
  status: string;
  owner_user_id?: number;
  owner_name?: string;
  project_name?: string;
  project_key?: string;
  color?: string;
  start_date?: string;
  end_date?: string;
  target_date?: string;
  progress_percent?: number;
  task_count?: number;
  completed_task_count?: number;
  story_points?: number;
  completed_story_points?: number;
  tasks?: PMSTaskListItem[];
  dependencies?: PMSTaskDependency[];
  created_at: string;
  updated_at?: string;
}

// ============= RISK TYPES =============
export interface PMSRisk {
  id: number;
  organization_id?: number;
  project_id: number;
  linked_task_id?: number | null;
  title: string;
  description?: string | null;
  category?: string | null;
  probability: number;
  impact: number;
  risk_score: number;
  status: "open" | "mitigating" | "closed" | string;
  owner_user_id?: number | null;
  mitigation_plan?: string | null;
  contingency_plan?: string | null;
  due_date?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface CreateRiskInput {
  project_id: number;
  linked_task_id?: number | null;
  title: string;
  description?: string;
  category?: string;
  probability?: number;
  impact?: number;
  status?: string;
  owner_user_id?: number | null;
  mitigation_plan?: string;
  contingency_plan?: string;
  due_date?: string | null;
}

export interface PMSRoadmapSprint {
  id: number;
  project_id: number;
  project_name?: string;
  name: string;
  status: string;
  start_date: string;
  end_date: string;
}

export interface PMSRoadmapResponse {
  projects: PMSTaskListOption[];
  owners: PMSTaskListOption[];
  statuses: string[];
  sprints: PMSRoadmapSprint[];
  epics: PMSEpic[];
}

export interface PMSComponent {
  id: number;
  project_id: number;
  name: string;
  description?: string;
  lead_user_id?: number;
  default_assignee_user_id?: number;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export interface PMSRelease {
  id: number;
  project_id: number;
  name: string;
  description?: string;
  status: string;
  release_date?: string;
  owner_user_id?: number;
  readiness_percent: number;
  launch_notes?: string;
  created_at: string;
  updated_at?: string;
}

export interface PMSTaskDependency {
  id: number;
  task_id: number;
  depends_on_task_id: number;
  source_task_id?: number;
  target_task_id?: number;
  dependency_type: string;
  lag_days?: number;
  created_at: string;
  task_key?: string;
  depends_on_task_key?: string;
  task_title?: string;
  depends_on_task_title?: string;
  source_task_key?: string;
  target_task_key?: string;
  source_task_title?: string;
  target_task_title?: string;
}

export interface PMSDevIntegration {
  id: number;
  organization_id?: number;
  project_id: number;
  project_name?: string;
  provider: "github" | "gitlab";
  repo_owner: string;
  repo_name: string;
  is_active: boolean;
  has_access_token: boolean;
  has_webhook_secret: boolean;
  created_at: string;
  updated_at?: string;
}

export interface PMSDevLink {
  id: number;
  organization_id?: number;
  task_id: number;
  provider: "github" | "gitlab";
  link_type: "branch" | "commit" | "pr" | "mr";
  external_id: string;
  title?: string;
  url?: string;
  status?: string;
  author?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
}

export interface PMSGanttWarning {
  dependency_id: number;
  source_task_id: number;
  target_task_id: number;
  dependency_type: string;
  message: string;
}

export interface PMSGanttResponse {
  tasks: PMSTaskListItem[];
  dependencies: PMSTaskDependency[];
  warnings: PMSGanttWarning[];
  filters: {
    projects: PMSTaskListOption[];
    sprints: Array<PMSTaskListOption & { status?: string }>;
    epics: PMSTaskListOption[];
    assignees: PMSTaskListOption[];
    statuses: string[];
  };
}

export interface PMSSavedFilter {
  id: number;
  organization_id?: number;
  project_id?: number;
  user_id?: number;
  name: string;
  view_type: string;
  entity_type?: string;
  query?: string;
  filters?: Record<string, unknown>;
  sort?: Record<string, unknown>;
  columns?: unknown;
  visibility?: "private" | "team" | "workspace" | string;
  is_default?: boolean;
  is_shared: boolean;
  created_at: string;
  updated_at?: string;
}

export interface PMSActivity {
  id: number;
  project_id: number;
  task_id?: number;
  sprint_id?: number;
  actor_user_id?: number;
  action: string;
  entity_type: string;
  entity_id?: number;
  summary: string;
  metadata_json?: string;
  created_at: string;
}

export interface SprintBurndown {
  sprint_id: number;
  committed_story_points: number;
  completed_story_points: number;
  remaining_story_points: number;
  points: Array<{
    date: string;
    ideal_remaining_points: number;
    actual_remaining_points: number;
    completed_points: number;
  }>;
}

export interface ProjectVelocity {
  project_id: number;
  average_velocity_points: number;
  sprints: Array<{ id: number; name: string; end_date: string; velocity_points: number }>;
}

export interface ReleaseReadiness {
  release_id: number;
  release_name: string;
  readiness_percent: number;
  health: string;
  total_tasks: number;
  done_tasks: number;
  open_blockers: number;
  overdue_tasks: number;
  severity_counts: Record<string, number>;
}

export interface WorkloadResponse {
  project_id: number;
  group_by: string;
  items: Array<{
    user_id?: number;
    sprint_id?: number;
    task_count: number;
    story_points: number;
    estimated_hours: number;
    overdue_tasks: number;
    capacity_hours?: number;
    load_percent?: number;
  }>;
}

export interface PMSTaskDistributionReport {
  total_tasks: number;
  total_story_points: number;
  by_status: Array<{ name: string; tasks: number; story_points: number }>;
  by_priority: Array<{ name: string; tasks: number; story_points: number }>;
  by_assignee: Array<{ assignee_id?: number; name: string; tasks: number; story_points: number }>;
}

export interface PMSCumulativeFlowReport {
  statuses: string[];
  points: Array<Record<string, string | number>>;
}

export interface PMSCycleTimeReport {
  average_lead_time_hours: number;
  average_cycle_time_hours: number;
  items: Array<{
    task_id: number;
    task_key: string;
    title: string;
    assignee_id?: number;
    story_points: number;
    started_at?: string;
    completed_at?: string;
    lead_time_hours: number;
    cycle_time_hours: number;
  }>;
}

export interface PMSTimeInStatusReport {
  statuses: Array<{ status: string; hours: number; days: number }>;
  items: Array<{ task_id: number; task_key: string; statuses: Record<string, number> }>;
}

export interface PMSProjectHealthReport {
  points: Array<Record<string, string | number>>;
}

export interface PMSTeamPerformanceReport {
  items: Array<{
    assignee_id?: number;
    name: string;
    assigned_tasks: number;
    completed_tasks: number;
    assigned_points: number;
    completed_points: number;
    completion_rate: number;
    avg_cycle_time_hours: number;
  }>;
}

export interface PMSWorkloadHeatmapResponse {
  basis: "hours" | "story_points" | "task_count";
  from: string;
  to: string;
  weeks: Array<{ week_start: string; label: string }>;
  projects: Array<{ id: number; name: string; project_key?: string }>;
  sprints: Array<{ id: number; project_id: number; name: string; status: string; start_date: string; end_date: string }>;
  users: Array<{ id: number; name: string }>;
  rows: Array<{
    user_id: number;
    user_name: string;
    email?: string;
    totals: {
      planned_hours: number;
      story_points: number;
      task_count: number;
      capacity_hours: number;
      utilization_percent: number;
    };
    cells: Array<{
      week_start: string;
      planned_hours: number;
      story_points: number;
      task_count: number;
      capacity_hours: number;
      load_value: number;
      load_unit: string;
      utilization_percent: number;
      status: "under" | "near" | "over";
      tasks: Array<{
        id: number;
        task_key: string;
        title: string;
        project_id: number;
        sprint_id?: number;
        status: string;
        priority: string;
        start_date?: string;
        due_date?: string;
        planned_hours: number;
        story_points: number;
      }>;
    }>;
  }>;
  summary: {
    over_capacity: number;
    near_capacity: number;
    under_capacity: number;
  };
}

export interface PMSPortfolioSummary {
  total_projects: number;
  active_projects: number;
  overdue_projects: number;
  at_risk_projects: number;
  completed_projects: number;
  total_open_tasks: number;
  team_workload_summary: {
    open_estimated_hours: number;
    active_assignees: number;
    avg_open_hours_per_assignee: number;
  };
  upcoming_milestones: number;
  health_distribution: Array<{ name: string; value: number }>;
  tasks_by_status: Array<{ name: string; value: number }>;
  filters: {
    owners: PMSTaskListOption[];
    clients: PMSTaskListOption[];
    statuses: string[];
    health: string[];
  };
}

export interface PMSPortfolioProject {
  id: number;
  name: string;
  project_key: string;
  owner_id?: number;
  owner_name?: string;
  client_id?: number;
  client_name?: string;
  status: string;
  health: string;
  stored_health?: string;
  progress_percent: number;
  open_tasks: number;
  overdue_tasks: number;
  blocked_tasks: number;
  risk_count?: number;
  open_high_risks?: number;
  total_tasks: number;
  sprint_status: string;
  active_sprint_name?: string;
  upcoming_milestones: number;
  start_date?: string;
  due_date?: string;
  budget_amount?: number;
  actual_cost?: number;
}

export interface PMSPortfolioProjectsResponse {
  items: PMSPortfolioProject[];
}

export interface PMSPortfolioHealthTrendResponse {
  items: Array<{
    month: string;
    project_count: number;
    at_risk: number;
    avg_progress: number;
    open_tasks: number;
    overdue_tasks: number;
  }>;
}

// ============= DASHBOARD TYPES =============
export interface ProjectMetrics {
  total_projects: number;
  active_projects: number;
  completed_projects: number;
  overdue_projects: number;
  total_tasks: number;
  completed_tasks: number;
  overdue_tasks: number;
  high_risks: number;
  pending_approvals: number;
  team_utilization: number;
  hours_logged_this_week: number;
  upcoming_milestones: number;
  recent_activities: number;
}

export interface DashboardData {
  project: PMSProject;
  metrics: ProjectMetrics;
}

// ============= API RESPONSE TYPES =============
export interface ApiResponse<T> {
  data?: T;
  error?: string;
  message?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

// ============= FILTER & SORT TYPES =============
export interface TaskFilters {
  status?: TaskStatus;
  priority?: TaskPriority;
  assignee_id?: number;
  milestone_id?: number;
  sprint_id?: number;
  epic_id?: number;
  component_id?: number;
  release_id?: number;
  work_type?: string;
  epic_key?: string;
  component?: string;
  severity?: string;
  fix_version?: string;
  release_name?: string;
  security_level?: string;
  tags?: number[];
}

export interface ProjectFilters {
  status?: ProjectStatus;
  priority?: ProjectPriority;
  client_id?: number;
  manager_id?: number;
}

export interface SortOption {
  field: string;
  direction: "asc" | "desc";
}

