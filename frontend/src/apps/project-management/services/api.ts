/**
 * KaryaFlow API Service
 * All API calls for project management
 */
import { api } from "@/services/api";
import {
  PMSProject,
  PMSTask,
  PMSBoard,
  PMSMilestone,
  PMSComment,
  PMSTimeLog,
  PMSTimesheet,
  PMSFileAsset,
  PMSChecklistItem,
  PMSTag,
  PMSSprint,
  PMSEpic,
  PMSComponent,
  PMSRelease,
  PMSTaskDependency,
  PMSDevIntegration,
  PMSDevLink,
  PMSTaskListItem,
  PMSTaskListQuery,
  PMSTaskListResponse,
  PMSBacklogResponse,
  PMSGanttResponse,
  PMSRoadmapResponse,
  PMSRisk,
  PMSWorkloadHeatmapResponse,
  PMSPortfolioSummary,
  PMSPortfolioProjectsResponse,
  PMSPortfolioHealthTrendResponse,
  PMSCumulativeFlowReport,
  PMSCycleTimeReport,
  PMSProjectHealthReport,
  PMSTaskDistributionReport,
  PMSTeamPerformanceReport,
  PMSTimeInStatusReport,
  PMSSprintReview,
  SprintCompletePayload,
  PMSSavedFilter,
  PMSActivity,
  PMSMentionUser,
  PMSNotification,
  SprintBurndown,
  ProjectVelocity,
  ReleaseReadiness,
  WorkloadResponse,
  CreateTagInput,
  CreateProjectInput,
  CreateProjectIntakeInput,
  PMSProjectIntake,
  CreateRiskInput,
  CreateTaskInput,
  CreateMilestoneInput,
  CreateCommentInput,
  CreateTimeLogInput,
  TimesheetPayload,
  CreateFileAssetInput,
  CreateChecklistItemInput,
  TaskReorderPayload,
  DashboardData,
} from "../types";

const BASE_URL = "/project-management";

// ============= PROJECTS =============
export const projectsAPI = {
  create: async (data: CreateProjectInput) => {
    const response = await api.post<PMSProject>(`${BASE_URL}/projects`, data);
    return response.data;
  },

  list: async (
    skip: number = 0,
    limit: number = 100,
    status?: string
  ) => {
    const params = new URLSearchParams();
    params.append("skip", skip.toString());
    params.append("limit", limit.toString());
    if (status) params.append("status", status);

    const response = await api.get<PMSProject[]>(
      `${BASE_URL}/projects?${params}`
    );
    return response.data;
  },

  get: async (projectId: number) => {
    const response = await api.get<PMSProject>(
      `${BASE_URL}/projects/${projectId}`
    );
    return response.data;
  },

  update: async (projectId: number, data: Partial<CreateProjectInput>) => {
    const response = await api.patch<PMSProject>(
      `${BASE_URL}/projects/${projectId}`,
      data
    );
    return response.data;
  },

  delete: async (projectId: number) => {
    const response = await api.delete(`${BASE_URL}/projects/${projectId}`);
    return response.data;
  },

  getDashboard: async (projectId: number) => {
    const response = await api.get<DashboardData>(
      `${BASE_URL}/dashboard/${projectId}`
    );
    return response.data;
  },
};

// ============= PROJECT INTAKE =============
export const projectIntakeAPI = {
  create: async (data: CreateProjectIntakeInput) => {
    const response = await api.post<PMSProjectIntake>(`${BASE_URL}/intake`, data);
    return response.data;
  },

  list: async (status?: string, skip: number = 0, limit: number = 20) => {
    const params = new URLSearchParams();
    params.append("skip", skip.toString());
    params.append("limit", limit.toString());
    if (status) params.append("status", status);
    const response = await api.get<PMSProjectIntake[]>(`${BASE_URL}/intake?${params}`);
    return response.data;
  },

  review: async (intakeId: number, data: { status: string; review_notes?: string; project_key?: string; manager_user_id?: number }) => {
    const response = await api.post<PMSProjectIntake>(`${BASE_URL}/intake/${intakeId}/review`, data);
    return response.data;
  },
};

// ============= RISKS =============
export const risksAPI = {
  list: async (filters: { projectId?: number | string; status?: string; ownerId?: number | string; severity?: string } = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") params.append(key, String(value));
    });
    const suffix = params.toString() ? `?${params}` : "";
    const response = await api.get<PMSRisk[]>(`${BASE_URL}/risks${suffix}`);
    return response.data;
  },

  create: async (data: CreateRiskInput) => {
    const response = await api.post<PMSRisk>(`${BASE_URL}/risks`, data);
    return response.data;
  },

  update: async (riskId: number, data: Partial<CreateRiskInput>) => {
    const response = await api.patch<PMSRisk>(`${BASE_URL}/risks/${riskId}`, data);
    return response.data;
  },

  delete: async (riskId: number) => {
    const response = await api.delete(`${BASE_URL}/risks/${riskId}`);
    return response.data;
  },
};

// ============= TASKS =============
export const tasksAPI = {
  create: async (projectId: number, data: CreateTaskInput) => {
    const payload = {
      ...data,
      task_key: data.task_key || `${Date.now().toString().slice(-5)}`,
    };
    const response = await api.post<PMSTask>(
      `${BASE_URL}/projects/${projectId}/tasks`,
      payload
    );
    return response.data;
  },

  list: async (
    projectId: number,
    skip: number = 0,
    limit: number = 100,
    filters?: {
      status?: string;
      assignee_id?: number;
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
      sprint_id?: number;
    }
  ) => {
    const params = new URLSearchParams();
    params.append("skip", skip.toString());
    params.append("limit", limit.toString());
    if (filters?.status) params.append("status", filters.status);
    if (filters?.assignee_id)
      params.append("assignee_id", filters.assignee_id.toString());
    if (filters?.epic_id) params.append("epic_id", filters.epic_id.toString());
    if (filters?.component_id)
      params.append("component_id", filters.component_id.toString());
    if (filters?.release_id)
      params.append("release_id", filters.release_id.toString());
    if (filters?.sprint_id)
      params.append("sprint_id", filters.sprint_id.toString());
    if (filters?.work_type) params.append("work_type", filters.work_type);
    if (filters?.epic_key) params.append("epic_key", filters.epic_key);
    if (filters?.component) params.append("component", filters.component);
    if (filters?.severity) params.append("severity", filters.severity);
    if (filters?.fix_version) params.append("fix_version", filters.fix_version);
    if (filters?.release_name) params.append("release_name", filters.release_name);
    if (filters?.security_level) params.append("security_level", filters.security_level);

    const response = await api.get<PMSTask[]>(
      `${BASE_URL}/projects/${projectId}/tasks?${params}`
    );
    return response.data;
  },

  listAll: async (query: PMSTaskListQuery = {}) => {
    const params = new URLSearchParams();
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        params.append(key, String(value));
      }
    });
    const suffix = params.toString() ? `?${params.toString()}` : "";
    const response = await api.get<PMSTaskListResponse>(`${BASE_URL}/tasks${suffix}`);
    return response.data;
  },

  get: async (taskId: number) => {
    const response = await api.get<PMSTask>(`${BASE_URL}/tasks/${taskId}`);
    return response.data;
  },

  update: async (taskId: number, data: Partial<CreateTaskInput>) => {
    const response = await api.patch<PMSTask>(
      `${BASE_URL}/tasks/${taskId}`,
      data
    );
    return response.data;
  },

  delete: async (taskId: number) => {
    const response = await api.delete(`${BASE_URL}/tasks/${taskId}`);
    return response.data;
  },

  updateStatus: async (taskId: number, status: string) => {
    return tasksAPI.update(taskId, { status: status as any });
  },

  bulkUpdate: async (payload: {
    task_ids: number[];
    status?: string;
    assignee_user_id?: number;
    priority?: string;
    sprint_id?: number;
    release_id?: number;
    component_id?: number;
  }) => {
    const response = await api.patch<{ updated_count: number; tasks: PMSTask[] }>(
      `${BASE_URL}/tasks/bulk`,
      payload
    );
    return response.data;
  },

  addDependency: async (taskId: number, dependsOnTaskId: number, dependencyType = "Finish To Start") => {
    const response = await api.post<PMSTaskDependency>(
      `${BASE_URL}/tasks/${taskId}/dependencies`,
      { depends_on_task_id: dependsOnTaskId, dependency_type: dependencyType }
    );
    return response.data;
  },

  listDependencies: async (taskId: number) => {
    const response = await api.get<PMSTaskDependency[]>(
      `${BASE_URL}/tasks/${taskId}/dependencies`
    );
    return response.data;
  },

  listActivity: async (taskId: number) => {
    const response = await api.get<PMSActivity[]>(`${BASE_URL}/tasks/${taskId}/activity`);
    return response.data;
  },

  listAttachments: async (taskId: number) => {
    const response = await api.get<PMSFileAsset[]>(`${BASE_URL}/tasks/${taskId}/attachments`);
    return response.data;
  },

  listTimeLogs: async (taskId: number) => {
    const response = await api.get<PMSTimeLog[]>(`${BASE_URL}/tasks/${taskId}/time-logs`);
    return response.data;
  },

  addTimeLog: async (taskId: number, data: CreateTimeLogInput) => {
    const response = await api.post<PMSTimeLog>(`${BASE_URL}/tasks/${taskId}/time-logs`, data);
    return response.data;
  },

  listChecklists: async (taskId: number) => {
    const response = await api.get<PMSChecklistItem[]>(`${BASE_URL}/tasks/${taskId}/checklists`);
    return response.data;
  },

  addChecklistItem: async (taskId: number, data: CreateChecklistItemInput) => {
    const response = await api.post<PMSChecklistItem>(`${BASE_URL}/tasks/${taskId}/checklists`, data);
    return response.data;
  },

  updateChecklistItem: async (itemId: number, data: Partial<CreateChecklistItemInput & { position: number }>) => {
    const response = await api.patch<PMSChecklistItem>(`${BASE_URL}/checklist/${itemId}`, data);
    return response.data;
  },

  deleteChecklistItem: async (itemId: number) => {
    const response = await api.delete(`${BASE_URL}/checklist/${itemId}`);
    return response.data;
  },

  reorderChecklist: async (taskId: number, itemIds: number[]) => {
    const response = await api.post<PMSChecklistItem[]>(`${BASE_URL}/tasks/${taskId}/checklist/reorder`, { item_ids: itemIds });
    return response.data;
  },

  listSubtasks: async (taskId: number) => {
    const response = await api.get<PMSTask[]>(`${BASE_URL}/tasks/${taskId}/subtasks`);
    return response.data;
  },

  createSubtask: async (taskId: number, data: Partial<CreateTaskInput> & { title: string }) => {
    const response = await api.post<PMSTask>(`${BASE_URL}/tasks/${taskId}/subtasks`, data);
    return response.data;
  },

  listLinks: async (taskId: number) => {
    const response = await api.get<PMSTaskDependency[]>(`${BASE_URL}/tasks/${taskId}/links`);
    return response.data;
  },

  listDevLinks: async (taskId: number) => {
    const response = await api.get<PMSDevLink[]>(`${BASE_URL}/tasks/${taskId}/dev-links`);
    return response.data;
  },

  listTags: async (taskId: number) => {
    const response = await api.get<PMSTag[]>(`${BASE_URL}/tasks/${taskId}/tags`);
    return response.data;
  },

  addTag: async (taskId: number, name: string) => {
    const params = new URLSearchParams({ name });
    const response = await api.post<PMSTag>(`${BASE_URL}/tasks/${taskId}/tags?${params}`);
    return response.data;
  },

  addTagById: async (taskId: number, tagId: number) => {
    const response = await api.post<PMSTag>(`${BASE_URL}/tasks/${taskId}/tags`, { tag_id: tagId });
    return response.data;
  },

  removeTag: async (taskId: number, tagId: number) => {
    const response = await api.delete(`${BASE_URL}/tasks/${taskId}/tags/${tagId}`);
    return response.data;
  },

  moveToSprint: async (taskId: number, sprintId: number, position?: number) => {
    const response = await api.post<PMSTask>(`${BASE_URL}/tasks/${taskId}/move-to-sprint`, { sprint_id: sprintId, position });
    return response.data;
  },

  removeFromSprint: async (taskId: number) => {
    const response = await api.post<PMSTask>(`${BASE_URL}/tasks/${taskId}/remove-from-sprint`);
    return response.data;
  },

  removeDependency: async (taskId: number, dependencyId: number) => {
    const response = await api.delete(`${BASE_URL}/tasks/${taskId}/dependencies/${dependencyId}`);
    return response.data;
  },
};

export const devIntegrationsAPI = {
  list: async (filters?: { projectId?: number | string }) => {
    const params = new URLSearchParams();
    if (filters?.projectId) params.append("projectId", String(filters.projectId));
    const suffix = params.toString() ? `?${params.toString()}` : "";
    const response = await api.get<PMSDevIntegration[]>(`${BASE_URL}/dev-integrations${suffix}`);
    return response.data;
  },

  create: async (data: {
    provider: "github" | "gitlab";
    project_id: number;
    repo_owner: string;
    repo_name: string;
    access_token?: string;
    webhook_secret?: string;
    is_active?: boolean;
  }) => {
    const response = await api.post<PMSDevIntegration>(`${BASE_URL}/dev-integrations`, data);
    return response.data;
  },

  delete: async (integrationId: number) => {
    const response = await api.delete(`${BASE_URL}/dev-integrations/${integrationId}`);
    return response.data;
  },
};

export const backlogAPI = {
  get: async (projectId: number, filters?: { search?: string; sortBy?: string }) => {
    const params = new URLSearchParams({ projectId: String(projectId) });
    if (filters?.search) params.append("search", filters.search);
    if (filters?.sortBy) params.append("sortBy", filters.sortBy);
    const response = await api.get<PMSBacklogResponse>(`${BASE_URL}/backlog?${params}`);
    return response.data;
  },

  reorder: async (projectId: number, taskIds: number[]) => {
    const response = await api.post<PMSTask[]>(`${BASE_URL}/backlog/reorder?projectId=${projectId}`, { task_ids: taskIds });
    return response.data;
  },
};

export const ganttAPI = {
  get: async (query: {
    projectId?: number | string;
    sprintId?: number | string;
    assigneeId?: number | string;
    epicId?: number | string;
    status?: string;
    from?: string;
    to?: string;
  } = {}) => {
    const params = new URLSearchParams();
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") params.append(key, String(value));
    });
    const suffix = params.toString() ? `?${params}` : "";
    const response = await api.get<PMSGanttResponse>(`${BASE_URL}/gantt${suffix}`);
    return response.data;
  },

  updateSchedule: async (taskId: number, data: { start_date?: string; due_date?: string }) => {
    const response = await api.patch<{ task: PMSTask; warnings: PMSGanttResponse["warnings"] }>(`${BASE_URL}/tasks/${taskId}/schedule`, data);
    return response.data;
  },

  createDependency: async (data: { source_task_id: number; target_task_id: number; dependency_type: string; lag_days?: number }) => {
    const response = await api.post<PMSTaskDependency>(`${BASE_URL}/task-dependencies`, data);
    return response.data;
  },

  deleteDependency: async (dependencyId: number) => {
    const response = await api.delete(`${BASE_URL}/task-dependencies/${dependencyId}`);
    return response.data;
  },
};

export const tagsAPI = {
  list: async (q?: string) => {
    const params = new URLSearchParams();
    if (q) params.append("q", q);
    const query = params.toString();
    const response = await api.get<PMSTag[]>(`${BASE_URL}/tags${query ? `?${query}` : ""}`);
    return response.data;
  },

  create: async (data: CreateTagInput) => {
    const response = await api.post<PMSTag>(`${BASE_URL}/tags`, data);
    return response.data;
  },
};

// ============= KANBAN BOARD (DRAG & DROP) =============
export const kanbanAPI = {
  getBoard: async (projectId: number) => {
    const response = await api.get<PMSBoard>(
      `${BASE_URL}/projects/${projectId}/board`
    );
    return response.data;
  },

  reorderTask: async (projectId: number, payload: TaskReorderPayload) => {
    const response = await api.post(
      `${BASE_URL}/projects/${projectId}/board/reorder`,
      payload
    );
    return response.data;
  },
};

// ============= COMMENTS (COLLABORATION) =============
export const commentsAPI = {
  addToTask: async (taskId: number, data: CreateCommentInput) => {
    const response = await api.post<PMSComment>(
      `${BASE_URL}/tasks/${taskId}/comments`,
      data
    );
    return response.data;
  },

  listForTask: async (taskId: number) => {
    const response = await api.get<PMSComment[]>(
      `${BASE_URL}/tasks/${taskId}/comments`
    );
    return response.data;
  },

  update: async (commentId: number, data: Partial<CreateCommentInput>) => {
    const response = await api.patch<PMSComment>(
      `${BASE_URL}/comments/${commentId}`,
      data
    );
    return response.data;
  },

  delete: async (commentId: number) => {
    const response = await api.delete(`${BASE_URL}/comments/${commentId}`);
    return response.data;
  },
};

export const pmsUsersAPI = {
  search: async (query: { q?: string; projectId?: number; taskId?: number; limit?: number }) => {
    const params = new URLSearchParams();
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") params.append(key, String(value));
    });
    const response = await api.get<PMSMentionUser[]>(`${BASE_URL}/users/search?${params}`);
    return response.data;
  },
};

export const pmsNotificationsAPI = {
  list: async (unreadOnly = false) => {
    const response = await api.get<PMSNotification[]>(`${BASE_URL}/notifications?unreadOnly=${unreadOnly}`);
    return response.data;
  },

  markRead: async (notificationId: number) => {
    const response = await api.patch(`${BASE_URL}/notifications/${notificationId}/read`);
    return response.data;
  },
};

// ============= MILESTONES =============
export const milestonesAPI = {
  create: async (projectId: number, data: CreateMilestoneInput) => {
    const response = await api.post<PMSMilestone>(
      `${BASE_URL}/projects/${projectId}/milestones`,
      data
    );
    return response.data;
  },

  list: async (
    projectId: number,
    skip: number = 0,
    limit: number = 100
  ) => {
    const params = new URLSearchParams();
    params.append("skip", skip.toString());
    params.append("limit", limit.toString());

    const response = await api.get<PMSMilestone[]>(
      `${BASE_URL}/projects/${projectId}/milestones?${params}`
    );
    return response.data;
  },

  submitApproval: async (milestoneId: number) => {
    const response = await api.post(`${BASE_URL}/milestones/${milestoneId}/submit-approval`);
    return response.data;
  },

  approve: async (milestoneId: number) => {
    const response = await api.post(`${BASE_URL}/milestones/${milestoneId}/approve`);
    return response.data;
  },

  reject: async (milestoneId: number, remarks: string) => {
    const response = await api.post(`${BASE_URL}/milestones/${milestoneId}/reject`, {
      status: "Rejected",
      remarks,
    });
    return response.data;
  },
};

// ============= PLANNING OBJECTS =============
export const planningAPI = {
  createEpic: async (projectId: number, data: Partial<PMSEpic>) => {
    const response = await api.post<PMSEpic>(
      `${BASE_URL}/projects/${projectId}/epics`,
      data
    );
    return response.data;
  },

  listEpics: async (projectId: number, status?: string) => {
    const params = new URLSearchParams();
    if (status) params.append("status", status);
    const response = await api.get<PMSEpic[]>(
      `${BASE_URL}/projects/${projectId}/epics?${params}`
    );
    return response.data;
  },

  getRoadmap: async (query: { projectId?: string | number; ownerId?: string | number; status?: string; from?: string; to?: string } = {}) => {
    const params = new URLSearchParams();
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") params.append(key, String(value));
    });
    const suffix = params.toString() ? `?${params}` : "";
    const response = await api.get<PMSRoadmapResponse>(`${BASE_URL}/roadmap${suffix}`);
    return response.data;
  },

  updateEpicSchedule: async (epicId: number, data: { start_date?: string; end_date?: string; target_date?: string; status?: string }) => {
    const response = await api.patch<PMSEpic>(`${BASE_URL}/epics/${epicId}/schedule`, data);
    return response.data;
  },

  listEpicTasks: async (epicId: number) => {
    const response = await api.get<PMSTaskListItem[]>(`${BASE_URL}/epics/${epicId}/tasks`);
    return response.data;
  },

  createComponent: async (projectId: number, data: Partial<PMSComponent>) => {
    const response = await api.post<PMSComponent>(
      `${BASE_URL}/projects/${projectId}/components`,
      data
    );
    return response.data;
  },

  listComponents: async (projectId: number, activeOnly: boolean = true) => {
    const response = await api.get<PMSComponent[]>(
      `${BASE_URL}/projects/${projectId}/components?active_only=${activeOnly}`
    );
    return response.data;
  },

  createRelease: async (projectId: number, data: Partial<PMSRelease>) => {
    const response = await api.post<PMSRelease>(
      `${BASE_URL}/projects/${projectId}/releases`,
      data
    );
    return response.data;
  },

  listReleases: async (projectId: number, status?: string) => {
    const params = new URLSearchParams();
    if (status) params.append("status", status);
    const response = await api.get<PMSRelease[]>(
      `${BASE_URL}/projects/${projectId}/releases?${params}`
    );
    return response.data;
  },

  getReleaseReadiness: async (releaseId: number) => {
    const response = await api.get<ReleaseReadiness>(
      `${BASE_URL}/releases/${releaseId}/readiness`
    );
    return response.data;
  },
};

// ============= SPRINTS =============
export const sprintsAPI = {
  create: async (projectId: number, data: Partial<Omit<PMSSprint, "id" | "project_id" | "created_at" | "updated_at">>) => {
    const response = await api.post<PMSSprint>(`${BASE_URL}/projects/${projectId}/sprints`, data);
    return response.data;
  },

  list: async (projectId: number) => {
    const response = await api.get<PMSSprint[]>(`${BASE_URL}/projects/${projectId}/sprints`);
    return response.data;
  },

  start: async (sprintId: number) => {
    const response = await api.post<PMSSprint>(`${BASE_URL}/sprints/${sprintId}/start`);
    return response.data;
  },

  complete: async (sprintId: number, payload?: number | SprintCompletePayload) => {
    const body = typeof payload === "number" ? { carry_forward_sprint_id: payload } : (payload || {});
    const response = await api.post<PMSSprint>(`${BASE_URL}/sprints/${sprintId}/complete`, body);
    return response.data;
  },

  review: async (sprintId: number) => {
    const response = await api.get<PMSSprintReview>(`${BASE_URL}/sprints/${sprintId}/review`);
    return response.data;
  },

  updateReview: async (sprintId: number, payload: SprintCompletePayload) => {
    const response = await api.patch<PMSSprintReview>(`${BASE_URL}/sprints/${sprintId}/review`, payload);
    return response.data;
  },

  burndown: async (sprintId: number) => {
    const response = await api.get<SprintBurndown>(`${BASE_URL}/sprints/${sprintId}/burndown`);
    return response.data;
  },

  reorderTasks: async (sprintId: number, taskIds: number[]) => {
    const response = await api.post<PMSTask[]>(`${BASE_URL}/sprints/${sprintId}/reorder-tasks`, { task_ids: taskIds });
    return response.data;
  },

  velocity: async (projectId: number) => {
    const response = await api.get<ProjectVelocity>(`${BASE_URL}/projects/${projectId}/velocity`);
    return response.data;
  },
};

// ============= SAVED FILTERS, ACTIVITY, REPORTS =============
export const savedFiltersAPI = {
  create: async (projectId: number, data: Partial<PMSSavedFilter>) => {
    const response = await api.post<PMSSavedFilter>(`${BASE_URL}/projects/${projectId}/saved-filters`, data);
    return response.data;
  },

  list: async (projectId: number, viewType?: string) => {
    const params = new URLSearchParams();
    if (viewType) params.append("view_type", viewType);
    const response = await api.get<PMSSavedFilter[]>(`${BASE_URL}/projects/${projectId}/saved-filters?${params}`);
    return response.data;
  },

  update: async (filterId: number, data: Partial<PMSSavedFilter>) => {
    const response = await api.patch<PMSSavedFilter>(`${BASE_URL}/saved-filters/${filterId}`, data);
    return response.data;
  },

  delete: async (filterId: number) => {
    const response = await api.delete(`${BASE_URL}/saved-filters/${filterId}`);
    return response.data;
  },
};

export const savedViewsAPI = {
  list: async (entityType = "task") => {
    const response = await api.get<PMSSavedFilter[]>(`${BASE_URL}/saved-views?entityType=${entityType}`);
    return response.data;
  },

  create: async (data: Partial<PMSSavedFilter>) => {
    const response = await api.post<PMSSavedFilter>(`${BASE_URL}/saved-views`, data);
    return response.data;
  },

  update: async (viewId: number, data: Partial<PMSSavedFilter>) => {
    const response = await api.patch<PMSSavedFilter>(`${BASE_URL}/saved-views/${viewId}`, data);
    return response.data;
  },

  delete: async (viewId: number) => {
    const response = await api.delete(`${BASE_URL}/saved-views/${viewId}`);
    return response.data;
  },
};

export const activityAPI = {
  list: async (projectId: number, filters?: { task_id?: number; limit?: number }) => {
    const params = new URLSearchParams();
    if (filters?.task_id) params.append("task_id", filters.task_id.toString());
    if (filters?.limit) params.append("limit", filters.limit.toString());
    const response = await api.get<PMSActivity[]>(`${BASE_URL}/projects/${projectId}/activity?${params}`);
    return response.data;
  },
};

export const reportsAPI = {
  workload: async (projectId: number, filters?: { group_by?: "user" | "sprint"; sprint_id?: number }) => {
    const params = new URLSearchParams();
    if (filters?.group_by) params.append("group_by", filters.group_by);
    if (filters?.sprint_id) params.append("sprint_id", filters.sprint_id.toString());
    const response = await api.get<WorkloadResponse>(`${BASE_URL}/projects/${projectId}/workload?${params}`);
    return response.data;
  },

  workloadHeatmap: async (filters: { projectId?: string | number; teamId?: string | number; sprintId?: string | number; from?: string; to?: string; basis?: "hours" | "story_points" | "task_count" } = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") params.append(key, String(value));
    });
    const suffix = params.toString() ? `?${params.toString()}` : "";
    const response = await api.get<PMSWorkloadHeatmapResponse>(`${BASE_URL}/workload${suffix}`);
    return response.data;
  },

  taskDistribution: async (filters: ReportFilters = {}) => {
    const response = await api.get(`${BASE_URL}/reports/task-distribution${reportQuery(filters)}`);
    return response.data as PMSTaskDistributionReport;
  },

  burndown: async (sprintId: number) => {
    const response = await api.get<SprintBurndown>(`${BASE_URL}/reports/burndown?sprintId=${sprintId}`);
    return response.data;
  },

  velocity: async (projectId: number) => {
    const response = await api.get<ProjectVelocity>(`${BASE_URL}/reports/velocity?projectId=${projectId}`);
    return response.data;
  },

  cumulativeFlow: async (filters: ReportFilters = {}) => {
    const response = await api.get(`${BASE_URL}/reports/cumulative-flow${reportQuery(filters)}`);
    return response.data as PMSCumulativeFlowReport;
  },

  cycleTime: async (filters: ReportFilters = {}) => {
    const response = await api.get(`${BASE_URL}/reports/cycle-time${reportQuery(filters)}`);
    return response.data as PMSCycleTimeReport;
  },

  timeInStatus: async (filters: ReportFilters = {}) => {
    const response = await api.get(`${BASE_URL}/reports/time-in-status${reportQuery(filters)}`);
    return response.data as PMSTimeInStatusReport;
  },

  projectHealth: async (filters: ReportFilters = {}) => {
    const response = await api.get(`${BASE_URL}/reports/project-health${reportQuery(filters)}`);
    return response.data as PMSProjectHealthReport;
  },

  teamPerformance: async (filters: ReportFilters = {}) => {
    const response = await api.get(`${BASE_URL}/reports/team-performance${reportQuery(filters)}`);
    return response.data as PMSTeamPerformanceReport;
  },

  export: async (filters: ReportFilters & { report: string; format: "csv" | "pdf" | "xlsx" }) => {
    const response = await api.get(`${BASE_URL}/reports/export${reportQuery(filters)}`, { responseType: "blob" });
    return response.data as Blob;
  },
};

type ReportFilters = {
  projectId?: string | number;
  sprintId?: string | number;
  assigneeId?: string | number;
  from?: string;
  to?: string;
  report?: string;
  format?: string;
};

function reportQuery(filters: ReportFilters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") params.append(key, String(value));
  });
  return params.toString() ? `?${params}` : "";
}

export const portfolioAPI = {
  summary: async (filters: { ownerId?: string | number; clientId?: string | number; status?: string } = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") params.append(key, String(value));
    });
    const suffix = params.toString() ? `?${params.toString()}` : "";
    const response = await api.get<PMSPortfolioSummary>(`${BASE_URL}/portfolio/summary${suffix}`);
    return response.data;
  },

  projects: async (filters: { ownerId?: string | number; clientId?: string | number; status?: string; health?: string } = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") params.append(key, String(value));
    });
    const suffix = params.toString() ? `?${params.toString()}` : "";
    const response = await api.get<PMSPortfolioProjectsResponse>(`${BASE_URL}/portfolio/projects${suffix}`);
    return response.data;
  },

  healthTrend: async (filters: { ownerId?: string | number; clientId?: string | number; status?: string } = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") params.append(key, String(value));
    });
    const suffix = params.toString() ? `?${params.toString()}` : "";
    const response = await api.get<PMSPortfolioHealthTrendResponse>(`${BASE_URL}/portfolio/health-trend${suffix}`);
    return response.data;
  },
};

// ============= FILES =============
export const filesAPI = {
  create: async (data: CreateFileAssetInput & { project_id?: number; task_id?: number; milestone_id?: number }) => {
    const response = await api.post<PMSFileAsset>(`${BASE_URL}/files`, data);
    return response.data;
  },

  uploadToTask: async (taskId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await api.post<PMSFileAsset>(`${BASE_URL}/tasks/${taskId}/attachments`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },

  list: async (filters?: { project_id?: number; task_id?: number }) => {
    const params = new URLSearchParams();
    if (filters?.project_id) params.append("project_id", filters.project_id.toString());
    if (filters?.task_id) params.append("task_id", filters.task_id.toString());
    const response = await api.get<PMSFileAsset[]>(`${BASE_URL}/files?${params}`);
    return response.data;
  },

  downloadBlob: async (fileId: number) => {
    const response = await api.get<Blob>(`${BASE_URL}/attachments/${fileId}/download`, { responseType: "blob" });
    return response.data;
  },

  deleteAttachment: async (fileId: number) => {
    const response = await api.delete(`${BASE_URL}/attachments/${fileId}`);
    return response.data;
  },
};

// ============= TIME TRACKING =============
export const timeLogsAPI = {
  create: async (data: CreateTimeLogInput) => {
    const response = await api.post<PMSTimeLog>(`${BASE_URL}/time-logs`, data);
    return response.data;
  },

  update: async (timeLogId: number, data: Partial<CreateTimeLogInput>) => {
    const response = await api.patch<PMSTimeLog>(`${BASE_URL}/time-logs/${timeLogId}`, data);
    return response.data;
  },

  delete: async (timeLogId: number) => {
    const response = await api.delete(`${BASE_URL}/time-logs/${timeLogId}`);
    return response.data;
  },

  list: async (
    skip: number = 0,
    limit: number = 100,
    filters?: { project_id?: number; user_id?: number }
  ) => {
    const params = new URLSearchParams();
    params.append("skip", skip.toString());
    params.append("limit", limit.toString());
    if (filters?.project_id)
      params.append("project_id", filters.project_id.toString());
    if (filters?.user_id) params.append("user_id", filters.user_id.toString());

    const response = await api.get<PMSTimeLog[]>(
      `${BASE_URL}/time-logs?${params}`
    );
    return response.data;
  },
};

export const timesheetsAPI = {
  list: async (filters?: { weekStart?: string; userId?: number; status?: string }) => {
    const params = new URLSearchParams();
    if (filters?.weekStart) params.append("weekStart", filters.weekStart);
    if (filters?.userId) params.append("userId", String(filters.userId));
    if (filters?.status) params.append("status", filters.status);
    const response = await api.get<PMSTimesheet[]>(`${BASE_URL}/timesheets?${params}`);
    return response.data;
  },

  create: async (payload: TimesheetPayload) => {
    const response = await api.post<PMSTimesheet>(`${BASE_URL}/timesheets`, payload);
    return response.data;
  },

  update: async (timesheetId: number, payload: TimesheetPayload) => {
    const response = await api.patch<PMSTimesheet>(`${BASE_URL}/timesheets/${timesheetId}`, payload);
    return response.data;
  },

  submit: async (timesheetId: number) => {
    const response = await api.post<PMSTimesheet>(`${BASE_URL}/timesheets/${timesheetId}/submit`);
    return response.data;
  },

  approve: async (timesheetId: number) => {
    const response = await api.post<PMSTimesheet>(`${BASE_URL}/timesheets/${timesheetId}/approve`);
    return response.data;
  },

  reject: async (timesheetId: number, rejectionReason: string) => {
    const response = await api.post<PMSTimesheet>(`${BASE_URL}/timesheets/${timesheetId}/reject`, { rejection_reason: rejectionReason });
    return response.data;
  },
};

// ============= MODULE INFO =============
export const moduleAPI = {
  getInfo: async () => {
    const response = await api.get(`${BASE_URL}/module-info`);
    return response.data;
  },
};

