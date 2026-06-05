# PMS Use Case Test Plan

Verification date: 2026-06-04

Scope: Project Management Suite verification using real delivery personas: Project Manager, Project Director, Team Lead, Developer, Client, and Finance Manager.

Evidence sources:
- Code/API inspection: `frontend/src/apps/project-management/routes.tsx`, `frontend/src/apps/project-management/services/api.ts`, `backend/app/apps/project_management/api/router.py`, `backend/app/apps/project_management/models.py`, `backend/app/apps/project_management/access.py`.
- Backend tests: `pytest -q tests/test_pms_project_access.py tests/test_pms_readiness_features.py`.
- Frontend build: `npm run build`.
- Browser smoke: local Vite app at `http://127.0.0.1:5173/` with PMS API mocks for route rendering, mobile shell checks, and route-level RBAC.
- Fix applied during verification: PMS frontend route/nav RBAC tightened in `frontend/src/lib/roles.ts`.

Database tables checked:
`pms_clients`, `pms_projects`, `pms_project_intakes`, `pms_project_members`, `pms_epics`, `pms_components`, `pms_releases`, `pms_boards`, `pms_board_columns`, `pms_sprints`, `pms_sprint_retro_action_items`, `pms_milestones`, `pms_tasks`, `pms_task_dependencies`, `pms_dev_integrations`, `pms_dev_links`, `pms_saved_filters`, `pms_activities`, `pms_checklist_items`, `pms_tags`, `pms_task_tags`, `pms_file_assets`, `pms_comments`, `pms_mentions`, `pms_time_logs`, `pms_timesheets`, `pms_user_capacity`, `pms_risks`, `pms_client_approvals`, `notifications`.

Status definitions:
- Passed: verified through actual code/API/tests/UI.
- Partially Passed: implemented but not fully verified end-to-end, or UI/API has incomplete behavior.
- Failed: implemented but verified as broken.
- Not Implemented: no real implementation found.

## Use Case Inventory

| # | Use case | Role | Primary UI routes | Primary APIs | Tables | Verification focus |
|---|---|---|---|---|---|---|
| 1 | Create a project manually | Project Manager | `/pms/projects/new`, `/pms/projects` | `POST /project-management/projects`, `GET /project-management/projects` | `pms_projects`, `pms_project_members`, `pms_activities` | Required fields, manager membership, validation, RBAC |
| 2 | Submit and review project intake | Project Director | `/pms`, `/pms/command-center` | `POST /project-management/intake`, `POST /project-management/intake/{id}/review` | `pms_project_intakes`, `pms_projects` | Intake queue, approval/rejection, project creation |
| 3 | Create a project from a template | Project Manager | `/pms/templates`, `/pms/projects/{id}` | `GET /project-management/project-templates`, `POST /project-management/projects/{id}/clone` | `pms_projects`, `pms_milestones`, `pms_tasks`, `pms_task_dependencies` | Template cloning and copied work structure |
| 4 | Manage project members and allocation | Project Manager | `/pms/resource-planning`, `/pms/projects/{id}` | `POST /project-management/projects/{id}/members` | `pms_project_members` | Resource assignment, allocation percent, project access |
| 5 | Define milestones and client approval requirement | Project Manager | `/pms/projects/{id}/milestones` | `POST /project-management/projects/{id}/milestones` | `pms_milestones`, `pms_client_approvals` | Milestone dates, approval status, validation |
| 6 | Approve or reject a submitted milestone | Client | `/pms/client-portal`, `/pms/projects/{id}/milestones` | milestone submit/approve/reject APIs | `pms_milestones`, `pms_client_approvals`, `pms_activities` | Client review, comments, audit trail |
| 7 | Create task with priority, owner, points | Team Lead | `/pms/tasks`, `/pms/projects/{id}/board` | `POST /project-management/projects/{id}/tasks` | `pms_tasks`, `pms_tags`, `pms_task_tags`, `pms_activities` | Field validation and activity trail |
| 8 | Developer views accessible project tasks | Developer | `/pms/tasks`, `/pms/projects/{id}/tasks/{taskId}` | `GET /project-management/tasks`, `GET /project-management/projects/{id}/tasks` | `pms_tasks`, `pms_project_members` | Project membership access and non-member block |
| 9 | Update task checklist and subtasks | Developer | `/pms/projects/{id}/tasks/{taskId}` | checklist/subtask APIs | `pms_checklist_items`, `pms_tasks`, `pms_activities` | Progress, reorder, cycle guard |
| 10 | Add task comment with mention notification | Developer | `/pms/projects/{id}/tasks/{taskId}` | comment and notification APIs | `pms_comments`, `pms_mentions`, `notifications`, `pms_activities` | Timeline and mention notification |
| 11 | Kanban stage move and board reorder | Team Lead | `/pms/projects/{id}/board` | `GET /project-management/projects/{id}/board`, reorder APIs | `pms_boards`, `pms_board_columns`, `pms_tasks`, `pms_activities` | Drag/drop, status history |
| 12 | Create task dependency and prevent cycles | Project Manager | `/pms/gantt`, `/pms/dependencies` | dependency and Gantt APIs | `pms_task_dependencies`, `pms_tasks`, `pms_activities` | Schedule logic, cycle prevention |
| 13 | Plan sprint and commit capacity | Team Lead | `/pms/sprints` | `POST /project-management/projects/{id}/sprints` | `pms_sprints`, `pms_user_capacity` | Sprint dates, capacity, validation |
| 14 | Move backlog work into sprint | Team Lead | `/pms/backlog` | backlog, move-to-sprint, reorder APIs | `pms_tasks`, `pms_sprints`, `pms_activities` | Backlog rank and sprint assignment |
| 15 | Start and complete sprint with retro items | Project Manager | `/pms/sprints` | sprint start/complete/review APIs | `pms_sprints`, `pms_sprint_retro_action_items`, `pms_tasks` | Lifecycle and carry-forward rules |
| 16 | Save advanced task filters and views | Team Lead | `/pms/tasks`, `/pms/issue-navigator-pro` | saved filter APIs | `pms_saved_filters` | User-scoped saved view access |
| 17 | Developer logs task time | Developer | `/pms/time-tracking`, task detail | time log APIs | `pms_time_logs`, `pms_activities` | Billable hours and approval status |
| 18 | Submit weekly timesheet | Developer | `/pms/timesheets` | `POST /project-management/timesheets`, submit API | `pms_timesheets`, `pms_time_logs` | Week validation, ownership, submit status |
| 19 | Approve or reject team timesheet | Project Manager | `/pms/timesheets` | timesheet approve/reject APIs | `pms_timesheets`, `pms_time_logs`, `pms_activities` | Manager approval and rejection reason |
| 20 | Maintain risk register | Project Manager | `/pms/risks`, `/pms/risk-register` | risk APIs | `pms_risks`, `pms_activities` | Severity, mitigation, health impact |
| 21 | Upload and scope project/task files | Developer | `/pms/files`, task detail files | file APIs | `pms_file_assets`, `pms_tasks`, `pms_milestones` | Project scoping, delete, audit |
| 22 | Client views portal deliverables | Client | `/pms/client-portal` | client-facing project/milestone/file APIs | `pms_projects`, `pms_milestones`, `pms_file_assets`, `pms_client_approvals` | Client-only route and visibility |
| 23 | Project Director reviews portfolio | Project Director | `/pms/portfolio`, `/pms/command-center` | portfolio APIs | `pms_projects`, `pms_tasks`, `pms_sprints`, `pms_risks` | Health, summary, access scoping |
| 24 | Resource utilization and capacity planning | Project Director | `/pms/workload`, `/pms/capacity`, `/pms/resource-utilization` | workload/capacity APIs | `pms_user_capacity`, `pms_project_members`, `pms_tasks` | Load vs capacity |
| 25 | Project profitability report | Finance Manager | `/pms/project-financials`, `/pms/reports` | profitability/report APIs | `pms_projects`, `pms_time_logs` | Budget, cost, profitability amount |
| 26 | Budget vs actual report | Finance Manager | `/pms/reports` | budget/report APIs | `pms_projects`, `pms_time_logs` | Planned vs actual cost |
| 27 | Invoice workflow from approved timesheets | Finance Manager | `/pms/project-financials` | invoice workflow expected | None found for PMS invoice draft | Invoice draft/export handoff |
| 28 | Export PMS report | Finance Manager | `/pms/reports` | `GET /project-management/reports/export` | report source tables | Export availability and permissions |
| 29 | Dev integration links GitHub PRs safely | Team Lead | `/pms/settings`, task detail | dev integration APIs | `pms_dev_integrations`, `pms_dev_links` | Token secrecy, PR linking |
| 30 | Mobile PMS execution workflow | Developer, Client | `/pms/projects`, `/pms/tasks`, `/pms/client-portal` | same APIs as desktop | same tables as relevant workflow | Responsive rendering and route access |

