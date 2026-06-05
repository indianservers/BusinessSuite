# PMS Use Case Execution Report

Execution date: 2026-06-04

Overall counts:
- Passed: 18
- Partially Passed: 11
- Failed: 0
- Not Implemented: 1

Commands executed:
- `pytest -q tests/test_pms_project_access.py tests/test_pms_readiness_features.py` -> 24 passed.
- `npm run build` -> production build passed.
- Browser smoke against `http://127.0.0.1:5173/` with mocked PMS APIs -> route rendering and RBAC checks completed; some slow/lazy PMS routes stayed in loading state under mocks and TaskList showed a mock-shape error, so UI certification is partial for those pages.

Bug fixed:
- PMS frontend route/nav RBAC was too broad. Before the fix, any PMS role could open PMS admin/settings/security routes. Fixed in `frontend/src/lib/roles.ts` by adding PMS admin, manager, delivery, viewer, and client route filtering.

## Use Cases

Use Case Number: 1
Use Case Name: Project Manager creates a new project manually
User Role: Project Manager
Business Scenario: A project manager starts a new client delivery project after kickoff.
Steps to Test: Open `/pms/projects/new`; submit project fields; verify project appears in list and creator becomes manager/member.
Expected Result: Project saved, required fields validated, creator gets project access, activity is recorded.
Actual Result: Backend test verified project creation and creator membership. UI route rendered in browser smoke. API and table paths exist.
Status: Passed
Bugs Found: None for backend/API. UI route access depended on broad PMS role guard before fix.
Fix Applied: PMS route guard tightened in `frontend/src/lib/roles.ts`.
Evidence: `test_project_creator_becomes_manager_and_can_add_member`; `POST /project-management/projects`; `pms_projects`, `pms_project_members`, `pms_activities`; browser `/pms/projects/new`.

Use Case Number: 2
Use Case Name: Project Director submits and reviews project intake
User Role: Project Director
Business Scenario: A director receives a new internal project request and reviews it before project creation.
Steps to Test: Submit intake from `/pms`; review via intake API; verify accepted intake can create/link project.
Expected Result: Intake saved, reviewed, status updated, project linkage recorded when approved.
Actual Result: UI intake form and APIs exist. Backend inspection shows intake create/review endpoints and `created_project_id`. No focused automated test covered full director intake-to-project path.
Status: Partially Passed
Bugs Found: None fixed.
Fix Applied: None.
Evidence: `/pms`; `POST /project-management/intake`; `POST /project-management/intake/{id}/review`; `pms_project_intakes`.

Use Case Number: 3
Use Case Name: Project Manager creates a project from a template
User Role: Project Manager
Business Scenario: A PM starts a standard implementation using a reusable template.
Steps to Test: Retrieve templates; clone template/project; verify copied milestones, tasks, and dependencies.
Expected Result: Template clone creates a new project and copies selected work structure safely.
Actual Result: Backend test verified clone/archive/template/report behavior.
Status: Passed
Bugs Found: None.
Fix Applied: None.
Evidence: `test_pms_project_clone_archive_template_and_reports`; `GET /project-management/project-templates`; `POST /project-management/projects/{id}/clone`; `pms_projects`, `pms_tasks`, `pms_milestones`, `pms_task_dependencies`.

Use Case Number: 4
Use Case Name: Project Manager manages members and allocation
User Role: Project Manager
Business Scenario: PM allocates a team member at a percentage of weekly capacity.
Steps to Test: Add member to project; set allocation percent; verify member access.
Expected Result: Member record created, duplicate members blocked, allocation stored, member can access project.
Actual Result: Backend test verified manager can add member and project access is member-scoped.
Status: Passed
Bugs Found: None.
Fix Applied: None.
Evidence: `test_project_creator_becomes_manager_and_can_add_member`; `POST /project-management/projects/{id}/members`; `pms_project_members`.

Use Case Number: 5
Use Case Name: Project Manager defines milestones and approval requirement
User Role: Project Manager
Business Scenario: PM defines UAT and go-live milestones that need client approval.
Steps to Test: Create milestone; mark approval status; verify milestone appears on project and reports.
Expected Result: Milestone stores due date/status/client approval status and affects progress reports.
Actual Result: Milestone model, schema, endpoints, and progress report APIs exist. Automated tests cover milestone progress indirectly, but not full UI create/edit approval setup.
Status: Partially Passed
Bugs Found: None.
Fix Applied: None.
Evidence: `pms_milestones`; milestone APIs in router; `/pms/projects/{id}/milestones`.

Use Case Number: 6
Use Case Name: Client approves or rejects milestone
User Role: Client
Business Scenario: Client reviews submitted deliverable and approves/rejects with comment.
Steps to Test: Open `/pms/client-portal`; review submitted milestone; approve/reject; check activity/audit.
Expected Result: Client decision updates milestone/client approval and is auditable.
Actual Result: Client portal route exists and rendered on desktop/mobile smoke. `pms_client_approvals` model exists. Full client decision end-to-end was not covered by tests.
Status: Partially Passed
Bugs Found: Client portal rendered with React key warning under mock data; no critical failure found.
Fix Applied: None.
Evidence: `/pms/client-portal`; `pms_client_approvals`; browser route smoke.

Use Case Number: 7
Use Case Name: Team Lead creates task with priority, owner, and points
User Role: Team Lead
Business Scenario: Team lead breaks milestone scope into assigned tasks.
Steps to Test: Create task with assignee, priority, story points, tags; verify validation/activity.
Expected Result: Task saved with fields, invalid values rejected, activity recorded.
Actual Result: Backend tests verified task creation fields, tags, story points, validation, and activity events.
Status: Passed
Bugs Found: None.
Fix Applied: None.
Evidence: `test_task_story_points_and_tags_have_validation_and_activity`; `POST /project-management/projects/{id}/tasks`; `pms_tasks`, `pms_tags`, `pms_task_tags`, `pms_activities`.

Use Case Number: 8
Use Case Name: Developer views accessible project tasks
User Role: Developer
Business Scenario: Developer opens only the projects/tasks where they are a member.
Steps to Test: Compare member and non-member access to project task APIs and task list UI.
Expected Result: Member can view; non-member receives access denied; no cross-project leakage.
Actual Result: Backend tests verified non-member cannot view/create project tasks and task list is organization/access scoped. Browser `/pms/tasks` route rendered but showed a mock-shape error during smoke, so UI route certification is partial.
Status: Partially Passed
Bugs Found: TaskList error occurred under mocked response shape: `Cannot read properties of undefined (reading 'length')`.
Fix Applied: None; backend contract remains covered by tests.
Evidence: `test_non_member_cannot_view_or_create_project_tasks`; `test_all_tasks_endpoint_scopes_by_accessible_organization`; `/pms/tasks`.

Use Case Number: 9
Use Case Name: Developer updates checklist and subtasks
User Role: Developer
Business Scenario: Developer breaks task work into checklist items and subtasks.
Steps to Test: Create/reorder checklist, create subtasks, update progress, attempt cyclic subtask relation.
Expected Result: Items persist, progress rolls up, cycles blocked, activity recorded.
Actual Result: Backend tests verified checklist CRUD/reorder and subtask CRUD/progress/cycle guard.
Status: Passed
Bugs Found: None.
Fix Applied: None.
Evidence: `test_task_checklist_crud_reorder_and_activity_events`; `test_task_subtasks_crud_progress_and_cycle_guard`; `pms_checklist_items`, `pms_tasks`, `pms_activities`.

Use Case Number: 10
Use Case Name: Developer adds comment with mention notification
User Role: Developer
Business Scenario: Developer comments on a blocked task and mentions a teammate.
Steps to Test: Add comment with mention; verify comment timeline, mention record, notification.
Expected Result: Comment saved, mention linked, notification queued, activity visible.
Actual Result: Comment, mention, notification APIs/models exist. Full mention notification end-to-end test was not present.
Status: Partially Passed
Bugs Found: None.
Fix Applied: None.
Evidence: `pms_comments`, `pms_mentions`, `notifications`; comment APIs; `/pms/projects/{id}/tasks/{taskId}`.

Use Case Number: 11
Use Case Name: Team Lead moves work on Kanban board
User Role: Team Lead
Business Scenario: Team lead moves tasks across delivery stages.
Steps to Test: Open board; drag task between columns; verify task status and board order.
Expected Result: Status/order changes persist and activity is recorded.
Actual Result: Board route rendered in browser smoke. Board and reorder APIs exist. No focused automated Kanban drag/drop test was found.
Status: Partially Passed
Bugs Found: None.
Fix Applied: None.
Evidence: `/pms/projects/{id}/board`; `GET /project-management/projects/{id}/board`; board reorder APIs; `pms_boards`, `pms_board_columns`, `pms_tasks`.

Use Case Number: 12
Use Case Name: Project Manager creates dependency and prevents cycles
User Role: Project Manager
Business Scenario: PM links predecessor/successor tasks and prevents invalid loops.
Steps to Test: Add dependency; view Gantt; attempt circular dependency.
Expected Result: Dependency saved, Gantt reflects schedule, circular dependency rejected.
Actual Result: Backend test verified Gantt dependencies, schedule handling, and cycle validation.
Status: Passed
Bugs Found: None.
Fix Applied: None.
Evidence: `test_gantt_dependencies_schedule_and_cycle_validation`; `pms_task_dependencies`; `/pms/gantt`, `/pms/dependencies`.

Use Case Number: 13
Use Case Name: Team Lead plans sprint with capacity
User Role: Team Lead
Business Scenario: Team lead creates upcoming sprint and commits scope/capacity.
Steps to Test: Create sprint with dates/capacity; verify status and workload metrics.
Expected Result: Sprint persists with capacity and is available in backlog/report views.
Actual Result: Backend tests verified sprint API additions, capacity, burndown, velocity, and workload integration.
Status: Passed
Bugs Found: None.
Fix Applied: None.
Evidence: `test_market_gap_api_additions_for_sprints_dependencies_filters_and_reports`; `pms_sprints`, `pms_user_capacity`; `/pms/sprints`.

Use Case Number: 14
Use Case Name: Team Lead moves backlog item into sprint
User Role: Team Lead
Business Scenario: Team lead pulls prioritized backlog into planned sprint.
Steps to Test: Open backlog; move task into sprint; reorder tasks; verify sprint assignment.
Expected Result: Sprint assignment and rank persist without duplicate execution.
Actual Result: Backend test verified backlog move-to-sprint and reorder behavior.
Status: Passed
Bugs Found: Browser route stayed loading under mock data, so UI smoke was inconclusive for this screen.
Fix Applied: None.
Evidence: `test_backlog_move_to_sprint_and_reorder`; `pms_tasks`, `pms_sprints`; `/pms/backlog`.

Use Case Number: 15
Use Case Name: Project Manager starts/completes sprint with retro items
User Role: Project Manager
Business Scenario: PM starts delivery sprint, completes it, carries forward unfinished work, and creates retro actions.
Steps to Test: Start sprint; complete sprint; choose incomplete task action; create action items.
Expected Result: Sprint lifecycle fields update, completed velocity captured, retro actions optionally create tasks.
Actual Result: Backend test verified sprint review, retro, completion, carry-forward, and action items.
Status: Passed
Bugs Found: None.
Fix Applied: None.
Evidence: `test_sprint_review_retro_completion_and_action_items`; `pms_sprints`, `pms_sprint_retro_action_items`, `pms_tasks`.

Use Case Number: 16
Use Case Name: Team Lead saves advanced task filters/views
User Role: Team Lead
Business Scenario: Team lead saves a custom issue navigator view for sprint triage.
Steps to Test: Apply filters/columns; save view; verify only owner/project scope can access.
Expected Result: Saved view persists and respects permissions.
Actual Result: Backend test verified saved filters store filters/columns and permissions.
Status: Passed
Bugs Found: None.
Fix Applied: None.
Evidence: `test_task_saved_views_store_filters_columns_and_permissions`; `pms_saved_filters`.

Use Case Number: 17
Use Case Name: Developer logs task time
User Role: Developer
Business Scenario: Developer logs billable hours against a task.
Steps to Test: Add time log; edit/delete; verify task activity and approval status.
Expected Result: Hours persist, billable flag captured, activity recorded.
Actual Result: Backend tests verified time log CRUD and activity events.
Status: Passed
Bugs Found: None.
Fix Applied: None.
Evidence: `test_task_time_logs_crud_and_activity_events`; `pms_time_logs`; `/pms/time-tracking`.

Use Case Number: 18
Use Case Name: Developer submits weekly timesheet
User Role: Developer
Business Scenario: Developer submits week hours for approval.
Steps to Test: Create weekly sheet, add entries, submit, attempt invalid date/outside week.
Expected Result: Draft transitions to submitted and entries link to logs.
Actual Result: Backend test verified weekly timesheet submit flow and validation.
Status: Passed
Bugs Found: Browser `/pms/timesheets` stayed loading under mock data; backend remains verified.
Fix Applied: None.
Evidence: `test_pms_weekly_timesheet_submit_approve_reject_flow`; `pms_timesheets`, `pms_time_logs`.

Use Case Number: 19
Use Case Name: Project Manager approves/rejects team timesheet
User Role: Project Manager
Business Scenario: PM reviews submitted timesheets and approves or rejects with reason.
Steps to Test: List submitted team sheets; approve; reject with reason; verify status and timestamps.
Expected Result: Manager-only approval, approved/rejected state persists, reason captured.
Actual Result: Backend test verified submit, approve, reject, and access checks.
Status: Passed
Bugs Found: None.
Fix Applied: None.
Evidence: `test_pms_weekly_timesheet_submit_approve_reject_flow`; approve/reject APIs; `pms_timesheets`.

Use Case Number: 20
Use Case Name: Project Manager maintains risk register
User Role: Project Manager
Business Scenario: PM tracks high risk and project health impact.
Steps to Test: Create risk; update severity/status; verify project health and scoped access.
Expected Result: Risk persists, is project scoped, and affects portfolio health.
Actual Result: Backend test verified scoped risk register and health impact. Browser `/pms/risks` route rendered; warning appeared under mock data for NaN metric.
Status: Partially Passed
Bugs Found: UI warning under mocked risk data: NaN metric render in Risks page.
Fix Applied: None.
Evidence: `test_pms_risk_register_is_project_scoped_and_affects_health`; `pms_risks`; `/pms/risks`.

Use Case Number: 21
Use Case Name: Developer uploads project/task file
User Role: Developer
Business Scenario: Developer uploads deliverable evidence to a task/project.
Steps to Test: Upload file; verify project/task scoping; delete file; verify activity.
Expected Result: File is scoped to project/task and non-member cannot access it.
Actual Result: Backend test verified task attachments are project scoped and log activity.
Status: Passed
Bugs Found: Browser `/pms/files` stayed loading under mock data.
Fix Applied: None.
Evidence: `test_task_attachments_are_project_scoped_and_log_activity`; `pms_file_assets`.

Use Case Number: 22
Use Case Name: Client views portal deliverables
User Role: Client
Business Scenario: Client checks project status, files, and approvals.
Steps to Test: Open client portal desktop/mobile; attempt admin route; verify portal-only access.
Expected Result: Client portal renders, admin route blocked, no internal admin links visible.
Actual Result: Desktop and mobile `/pms/client-portal` rendered. `/pms/admin` blocked for `pms_client` after RBAC fix.
Status: Partially Passed
Bugs Found: Client portal React key warning under mock data.
Fix Applied: PMS route guard fixed for client/admin block.
Evidence: Browser smoke; `pms_client_approvals`; `frontend/src/lib/roles.ts`.

Use Case Number: 23
Use Case Name: Project Director reviews portfolio
User Role: Project Director
Business Scenario: Director reviews all accessible projects and health rollup.
Steps to Test: Open portfolio; verify project counts, risk health, overdue indicators, scoped access.
Expected Result: Portfolio summary shows only accessible projects and calculates health.
Actual Result: Backend test verified portfolio dashboard access scoping and health calculations.
Status: Passed
Bugs Found: None.
Fix Applied: None.
Evidence: `test_portfolio_dashboard_is_accessible_scoped_and_calculates_health`; `pms_projects`, `pms_tasks`, `pms_sprints`, `pms_risks`.

Use Case Number: 24
Use Case Name: Project Director reviews resource utilization and capacity
User Role: Project Director
Business Scenario: Director checks overloaded resources across sprint/project work.
Steps to Test: Open workload/capacity; verify planned hours, capacity hours, over-capacity flags.
Expected Result: Workload heatmap respects access and compares assignment load to capacity.
Actual Result: Backend test verified workload heatmap is project scoped and uses capacity.
Status: Passed
Bugs Found: None.
Fix Applied: None.
Evidence: `test_workload_heatmap_is_accessible_project_scoped_and_uses_capacity`; `pms_user_capacity`, `pms_project_members`, `pms_tasks`.

Use Case Number: 25
Use Case Name: Finance Manager reviews project profitability
User Role: Finance Manager
Business Scenario: Finance reviews margin based on project budget and actual/timesheet cost.
Steps to Test: Open project financials/report; verify profitability amount and percent.
Expected Result: Budget, actual cost, timesheet cost, and profitability are calculated.
Actual Result: Backend test verified profitability amount/percent in reports.
Status: Passed
Bugs Found: None.
Fix Applied: None.
Evidence: `test_pms_project_clone_archive_template_and_reports`; report APIs; `pms_projects`, `pms_time_logs`.

Use Case Number: 26
Use Case Name: Finance Manager reviews budget vs actual report
User Role: Finance Manager
Business Scenario: Finance compares planned budget to actual cost.
Steps to Test: Open reports; run budget-vs-actual; verify data accuracy and permissions.
Expected Result: Report uses real project/time data and is access scoped.
Actual Result: Backend tests verified PMS reports are real-data and access scoped.
Status: Passed
Bugs Found: Browser `/pms/reports` stayed loading under mock data.
Fix Applied: None.
Evidence: `test_pms_reports_are_real_data_and_access_scoped`; report APIs.

Use Case Number: 27
Use Case Name: Finance Manager creates invoice draft from approved timesheets
User Role: Finance Manager
Business Scenario: Finance turns approved billable timesheets into customer invoice draft/export.
Steps to Test: Approve timesheet; generate invoice draft; export invoice; verify links to project/customer.
Expected Result: Invoice draft/export exists and links approved billable time to project/customer.
Actual Result: No real PMS invoice draft/export table or API was found. `enterpriseEngine.ts` contains inactive/static invoice draft demo data only.
Status: Not Implemented
Bugs Found: Missing invoice workflow implementation.
Fix Applied: None; this is a product gap, not a small safe patch.
Evidence: Code search found static `invoiceDrafts` in frontend demo data and no PMS invoice model/API.

Use Case Number: 28
Use Case Name: Finance Manager exports PMS report
User Role: Finance Manager
Business Scenario: Finance exports project/budget/timesheet report for billing review.
Steps to Test: Run report; export; verify file/data and permission filtering.
Expected Result: Export endpoint returns permission-filtered report data.
Actual Result: Report export endpoint exists; automated tests cover report data/scoping but not actual download/export in UI.
Status: Partially Passed
Bugs Found: None.
Fix Applied: None.
Evidence: report/export API in router; `test_pms_reports_are_real_data_and_access_scoped`.

Use Case Number: 29
Use Case Name: Team Lead links GitHub PRs safely
User Role: Team Lead
Business Scenario: Lead links repository PRs to PMS tasks without exposing tokens.
Steps to Test: Configure integration; link PR; verify token not returned; verify task link.
Expected Result: PR link persists and stored token is hidden from API responses.
Actual Result: Backend test verified GitHub PR linking and token hiding.
Status: Passed
Bugs Found: None.
Fix Applied: None.
Evidence: `test_dev_integrations_link_github_prs_and_hide_tokens`; `pms_dev_integrations`, `pms_dev_links`.

Use Case Number: 30
Use Case Name: Mobile PMS execution workflow
User Role: Developer, Client
Business Scenario: Developer and client use PMS from mobile for task/client portal work.
Steps to Test: Open mobile viewport for project list, tasks, client portal; verify no access leakage.
Expected Result: Mobile routes render and RBAC still applies.
Actual Result: Mobile project list and client portal rendered. Mobile task route hit the same mocked TaskList error as desktop. No offline queue found.
Status: Partially Passed
Bugs Found: TaskList mock-shape error during mobile route smoke; no PMS offline queue implementation found.
Fix Applied: PMS route guard applies equally on mobile.
Evidence: Browser smoke for `/pms/projects`, `/pms/tasks`, `/pms/client-portal` at 390x844.

## Critical Blockers

- PMS invoice workflow is not implemented.
- Full UI certification for backlog/sprint/timesheet/report/file/task screens needs a seeded backend or stronger contract fixtures; browser smoke with mocks left several lazy routes loading and surfaced TaskList mock-shape errors.

## Final PMS Go-Live Status

Not certified for full PMS go-live. Core project/task/sprint/timesheet/risk/report/portfolio/resource/profitability APIs are strong enough for controlled pilot use, but invoice workflow is missing and several UI flows need seeded end-to-end UI verification before production release.

