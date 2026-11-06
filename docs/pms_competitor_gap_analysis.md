# PMS Competitor Gap Analysis

Current implementation follow-up: [Competitor gap closure](competitor-gap-closure.md). This May baseline contains historical gaps; check that ledger and current code before treating an item below as missing.

Date: 2026-05-07

This compares the current Project Management app, **KaryaFlow**, with leading market PMS/work-management tools and separates what belongs to PMS from shared platform capabilities.

## Product Boundary

| Area | Belongs here | Do not mix with |
| --- | --- | --- |
| Common platform | Auth, users, roles, audit, logs, workflow engine, notifications, files foundation, integrations foundation, AI service layer, app registry, deployment controls | App-specific HR records, CRM sales pipeline, PMS delivery objects |
| HRMS | Employees, payroll, attendance, leave, performance, recruitment, onboarding, statutory compliance, benefits, ESS | Project boards, client deliverables, CRM leads/deals |
| CRM | Leads, contacts, companies, deals, quotations, campaigns, support tickets, sales activities | Payroll/employee records, sprint backlog, project time approval |
| PMS / KaryaFlow | Clients, projects, members, boards, tasks, sprints, milestones, dependencies, files, comments, time logs, client approvals, project reporting, delivery planning | HR employment lifecycle, CRM pipeline ownership |

Shared entities should remain common only when all three apps need them. For example, `users`, `organizations`, `audit`, `notifications`, `workflow_engine`, and future `common_people/profiles` are common. `pms_tasks`, `crm_deals`, and `hrms_payroll_runs` should stay app-owned.

## Reference Market Products

- **Jira**: agile backlog, sprints, issue tracking, workflows, automation, dashboards, reports, app integrations.
- **Asana**: projects, portfolios, goals, workload, cross-team work tracking, automation, reporting.
- **monday.com**: boards, views, dashboards, automations, workload, timelines/Gantt, AI-assisted work management.
- **ClickUp**: tasks, dashboards, docs, goals, whiteboards, automations, chat, AI, reports.
- **Wrike**: customizable workspaces, dashboards, resource planning, workflow automation, AI, time/resource management.
- **Smartsheet**: spreadsheet-like project plans, portfolio dashboards, resource management, automation, enterprise controls.
- **Microsoft Planner / Project**: Microsoft 365 project planning, goals, task history, premium scheduling, portfolio/project planning.
- **Zoho Projects**: tasks, issues, Gantt, timesheets, timers, Blueprints automation, document versioning, integrations.

Sources checked:
- Atlassian Jira features: https://www.atlassian.com/software/jira/features/
- Asana features: https://asana.com/en-gb/features
- monday work management support: https://support.monday.com/hc/en-us/p/work-management
- ClickUp dashboards: https://help.clickup.com/hc/en-us/articles/6312197753239-Dashboards-overview
- Wrike features: https://www.wrike.com/features
- Smartsheet project management: https://www.smartsheet.com/project-management
- Microsoft Planner: https://www.microsoft.com/en-us/microsoft-365/planner/microsoft-planner
- Zoho Projects features: https://www.zoho.com/projects/features.html
- Capterra PM software buyer trend page: https://www.capterra.com/project-management-software/

## Current KaryaFlow Position

### Database-Backed PMS Core

Already present in backend models/API:

- Clients with soft delete.
- Projects with key, manager, client, status, priority, health, dates, budget, actual cost, progress, client visibility, archive flag.
- Project members with role.
- Kanban boards and columns with WIP limit fields.
- Tasks with key, status, priority, assignee, reporter, parent task, sprint, milestone, estimates, actual hours, story points, blocking flag, client visibility, soft delete.
- Task dependencies.
- Checklists.
- Tags and task-tag mapping.
- File metadata with version number and visibility.
- Comments with internal/client visibility and threaded parent field.
- Time logs with billable flag and approval status.
- Client milestone approvals.
- Project dashboard metrics for tasks, overdue work, approvals, milestones.

### Frontend PMS Surface

Already present in routes/pages:

- PMS home, project list, project creation, project dashboard.
- Kanban board with drag/drop behavior.
- Task detail, milestones, time tracking, reports, calendar, Gantt, sprints, files, client portal, settings, admin.
- Software planning views for backlog, issues, roadmap, releases.
- Live work management, impact/work hub, dependency timeline, automation/AI, command center, enterprise engine, product launch workspace.

### Important Caveat

The backend has a solid operational core, but several advanced frontend experiences are currently powered by local/sample datasets. Market-grade PMS needs those surfaces backed by persistent models, APIs, permissions, automation execution, reporting exports, and integrations.

## Competitive Scorecard

| Capability | Current KaryaFlow | Market benchmark | Gap |
| --- | --- | --- | --- |
| Project/task CRUD | Strong foundation | All products | Low |
| Kanban | Foundation complete | Jira, monday, ClickUp, Asana, Zoho | Low/medium: needs configurable workflows and board policies |
| Scrum/backlog/sprints | Foundation | Jira, ClickUp, Zoho Sprints | Medium/high: sprint lifecycle, backlog ranking, burndown persistence missing |
| Gantt/timeline | UI foundation | monday, Smartsheet, Wrike, MS Planner, Zoho | High: critical path, baseline, lag, resource-aware scheduling missing |
| Dependencies | Model + UI demo | Jira Advanced Roadmaps, Smartsheet, Wrike | High: dependency validation/rescheduling not persisted end-to-end |
| Resource management | UI/sample foundation | Wrike, Smartsheet, monday Workload, MS Project | Very high: allocation, capacity, holidays, skills, utilization engine missing |
| Portfolio/program management | UI/sample foundation | Asana Portfolios, Smartsheet PPM, Wrike, monday | Very high: portfolio rollups, OKR/goal rollups, cross-project risk missing |
| Reports/dashboards | Basic dashboard + UI samples | Jira reports, ClickUp dashboards, Smartsheet dashboards | High: saved reports, scheduled exports, custom widgets, drilldowns missing |
| Time tracking | Model/API foundation | Zoho, ClickUp, Wrike, Jira apps | Medium: approvals, timers, billing export, invoice linkage incomplete |
| Budget/cost tracking | Project fields + sample forecasts | MS Project, Smartsheet, Wrike | High: rate cards, cost baselines, EAC/ETC, margin, invoice integration missing |
| Client portal/approvals | Foundation | Wrike proofing/client workspaces, Zoho client users | Medium/high: external identity, permission model, approval audit, file proofing missing |
| Automations | UI/sample foundation | Jira, monday, ClickUp, Wrike, Zoho Blueprint | Very high: no persistent rule builder/execution engine for PMS events |
| Forms/intake | UI/sample foundation | Asana forms, monday forms, Jira forms, Zoho Blueprint | High: form definitions, routing, task creation, SLAs missing for PMS |
| Docs/wiki/knowledge | Sample wiki rows only | ClickUp Docs, Confluence/Jira, Notion-like competitors | Very high: pages, versioning, mentions, task linking missing |
| Files/proofing | Metadata foundation | Wrike proofing, Smartsheet attachments, Zoho documents | High: binary upload flow, preview, comments-on-file, approvals missing |
| Notifications | Common foundation | All products | Medium: PMS-specific event preferences and digests need implementation |
| Integrations | Common foundation | GitHub, Slack/Teams, Figma, Google/Microsoft calendar, email | Very high: PMS connectors and webhooks not wired to work items |
| AI | UI/sample foundation | monday AI, Asana AI, ClickUp AI, MS Copilot | High: planning assistant, risk summary, auto status, meeting/action extraction missing |
| Enterprise security | Common foundation | Jira/monday/Smartsheet enterprise controls | Medium/high: project permission schemes and external client roles need enforcement |
| Mobile/PWA | Suite PWA foundation | All leading tools | High: mobile-first PMS flows, offline-safe updates, push notifications missing |

## Top Gaps To Close

### P0 - Product Viability

| Gap | Why it matters | Recommended build |
| --- | --- | --- |
| Real PMS permission model | Client-visible work, private issues, project roles, and admin controls need enforcement before production rollout | Foundation implemented: reusable PMS access helper, project roles, member endpoints, project creator auto-manager membership, and backend enforcement across core project/task/comment/file/time/milestone flows. Next: route-level frontend guards and external client identity. |
| Persist advanced work item fields | Frontend software planning has issue type, epic, release, component, severity, versions, rank, security, development data; backend task model lacked many of these | Foundation implemented: tasks now persist work type, epic, initiative, component, severity, environment, affected/fix version, release, estimates, rank, security, and development metadata with API filters and frontend types. Epics, components, and releases are now first-class project objects with task links. Next: build rollup reports and roadmap UI on these objects. |
| Workflow/status schemes | Market tools let teams define statuses, transitions, validators, and approvals by work type | Add PMS workflow schemes using the common workflow engine for statuses, transition rules, validators, and post-functions. |
| Backlog and sprint lifecycle | Jira-level software teams expect ranked backlog, sprint planning, sprint start/complete, burndown, velocity | Add backlog rank, sprint commitment snapshot, scope-change log, sprint completion flow, burndown/velocity tables. |
| Project reports backed by data | Current dashboard is basic and many rich reports are sample-driven | Persist report snapshots for burndown, burnup, cumulative flow, cycle time, workload, release readiness, overdue risk. |

### P1 - Market Catch-Up

| Gap | Why it matters | Recommended build |
| --- | --- | --- |
| Resource and capacity planning | Wrike, Smartsheet, monday, and MS Project compete heavily here | Add capacity calendars, allocation records, holidays, role/skill demand, over-allocation alerts, utilization reports. |
| Gantt and dependency engine | Visual timeline is not enough; buyers expect schedule impact and critical path | Add dependency lag, dependency validation, baseline dates, critical path, auto-shift options, schedule conflict warnings. |
| Automation engine for PMS | No-code automations are table stakes | Add rule model: trigger, condition, action, active flag, execution log. Support status changes, due dates, assignments, dependencies, comments, file approvals. |
| Intake forms | Asana/monday/Jira/Zoho use forms to standardize work intake | Add PMS form definitions, field schema, routing rules, SLA target, task/project creation mapping. |
| Client portal hardening | Client approvals are a differentiator but need trust controls | Add external client users, invite flow, scoped token access, approval evidence, file preview, comments, rejection reasons, email notifications. |
| Time-to-billing flow | Current time logs stop before commercial workflows | Add timer UI, weekly timesheet submission/approval, rate cards, billable exports, invoice draft handoff to CRM/accounting. |

### P2 - Differentiation

| Gap | Why it matters | Recommended build |
| --- | --- | --- |
| AI delivery copilot | Market is moving toward AI-assisted planning and status updates | Add AI risk summary, auto status report, blocker detection, sprint planning suggestions, release note generation with human review. |
| Cross-app delivery to CRM | Suite advantage over standalone PMS | Link CRM deals/quotations to PMS projects, client approvals to invoice triggers, support tickets to project tasks. |
| Cross-app resource/HRMS integration | Suite advantage over standalone PMS | Link HRMS holidays, employee cost rates, skills, attendance, and timesheets into PMS capacity and cost plans. |
| Docs/wiki workspace | ClickUp/Notion/Confluence-style planning improves stickiness | Add pages, version history, task links, mentions, decision records, meeting notes. |
| Marketplace/connectors | Mature PMS wins by fitting into the toolchain | GitHub, GitLab, Slack, Teams, Figma, Google Calendar, Outlook Calendar, Drive/SharePoint, email ingestion. |

## Clearly Separated Roadmap For All 3 Apps

### Common Platform - Build Once

1. Common `people/profiles` table so HRMS employees are not required for CRM-only or PMS-only deployments.
2. Permission framework with app/module/object scopes.
3. Notification preferences and digest scheduler.
4. Integration credentials, webhook delivery, retry worker, event audit.
5. File storage service with preview metadata and virus-scan hook.
6. Shared workflow engine UI components, but app-owned workflow definitions.
7. AI audit log, prompt/version tracking, human-review queue.

### HRMS - Keep Separate

1. Payroll/statutory depth.
2. Attendance/leave/ESS.
3. Recruitment, onboarding, performance, LMS, benefits.
4. Employee document governance.
5. HR-specific analytics and compliance.

### CRM - Keep Separate

1. Leads, contacts, accounts, deals, quotations.
2. Sales pipeline, activities, campaigns.
3. Customer support/tickets.
4. Sales forecasts, revenue analytics.
5. CRM-to-PMS handoff when a deal becomes a delivery project.

### PMS / KaryaFlow - Build Next

1. PMS permission model and project roles.
2. Rich issue model: work types, epics, releases, components, rank, security, severity.
3. Workflow/status schemes and transition rules.
4. Sprint lifecycle and agile reports.
5. Resource/capacity planning.
6. Gantt dependency engine.
7. Automation rules and intake forms.
8. Client portal hardening.
9. Time-to-billing and budget forecasting.
10. PMS integrations and AI delivery copilot.

## Best Positioning

KaryaFlow should not try to clone every tool at once. The strongest suite-native positioning is:

> India-first delivery management for service businesses, connecting CRM sales promises, PMS execution, client approvals, billable time, and HRMS capacity in one suite.

The practical winning sequence:

1. **Trust core**: permissions, workflows, audit, client access.
2. **Software delivery depth**: backlog, sprints, releases, reports, GitHub/GitLab links.
3. **Service delivery depth**: client approvals, files, time billing, invoices.
4. **Portfolio/resource depth**: capacity, budgets, risk, cross-project dashboards.
5. **AI and automation**: status summaries, risk detection, no-code rules, intake routing.
