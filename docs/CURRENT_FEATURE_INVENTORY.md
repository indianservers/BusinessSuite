# Current Feature Inventory

Date: 2026-06-04

Scope: Business Suite CRM, Project Management System (PMS), HRMS, AI agents, and shared platform surfaces found in backend routers/models, frontend routes, automated certification reports, and readiness reports.

## Executive Summary

The suite has a unusually broad implemented surface for an SME/mid-market business platform. HRMS is the deepest module and is close to market-ready. PMS and CRM are functionally rich enough for controlled pilots and certified automated UI/API/RBAC smoke coverage, but still need cross-module workflow, production integrations, automation depth, scale proof, and mobile/offline polish before being positioned against Zoho One, Dynamics 365, Odoo, Salesforce, HubSpot, Jira, ClickUp, Asana, or monday.com.

| Product Area | Inventory Verdict | Market Readiness | Main Strength | Main Constraint |
|---|---:|---:|---|---|
| HRMS | Very broad | 88/100 | Payroll, attendance, compliance, ESS, workflows | Direct statutory/biometric integrations and mobile polish |
| CRM | Broad core CRM | 72/100 | Leads, deals, quotes, reports, territories, approvals | Marketing automation, email/calendar sync, forecasting, mobile/offline |
| PMS | Broad project/agile/time platform | 74/100 | Projects, tasks, agile, timesheets, risks, reports | Financials, templates, automation, resource planning, large-scale proof |
| AI Agents | Platform foundation | 55/100 | Agent routes, approvals, analytics, config | Need embedded module-specific use cases and trust controls |
| Suite Platform | Solid foundation | 76/100 | RBAC, module registry, shared shell, workflow/notifications | Cross-module business flows and integration marketplace |

## CRM Inventory

### Implemented or Strong

| Area | Current Capability |
|---|---|
| Lead management | Lead CRUD, lead sources, statuses, scoring rules, score recalculation, enrichment preview/apply/history, duplicate scan/merge, conversion to contact/company/deal |
| Account/contact management | Contacts, companies/accounts, account/contact detail pages, relationship context, deal contacts |
| Sales pipeline | Deals, multiple pipelines, stages, pipeline settings, Kanban route, stage/probability/expected revenue fields |
| Activities | Tasks, notes, calls, meetings, activities, calendar aggregation, follow-up and overdue reporting |
| Quotations | Products, quotation items, PDF generation, PDF email endpoint, approval workflows |
| Communication | Email templates/logging/sending endpoint, message templates, SMS/WhatsApp logging/sending surface, webhooks |
| Sales operations | Territories, auto-assignment foundations, roles, audit logs/timelines, custom fields |
| Reporting | Win/loss, funnel, revenue trend, lead source, conversion, pipeline, salesperson performance, overdue follow-up, forecast-style reports |
| Frontend | Dashboard, leads, contacts, accounts, deals, pipeline, activities, calendar, quotations, approvals, duplicates, territories, reports, customer 360, import/export, admin/settings |

### Partial or Not Yet Competitive

| Gap Area | Current State |
|---|---|
| Production email/calendar | Outbound and sync surfaces exist; full Gmail/Outlook two-way inbox/calendar behavior is not proven |
| Marketing journeys | Campaigns exist, but drip journeys, web forms, landing pages, ad/social attribution, and nurture automation are partial |
| Forecasting | Reports exist, but quotas, commit categories, forecast periods, hierarchy rollups, and forecast history are partial |
| Automation | Approvals, scoring, and webhooks exist; no full trigger/condition/action workflow builder yet |
| Enterprise security | RBAC exists; field-level security, sharing rules, export governance, and immutable audit depth need hardening |
| Native mobile/offline | Responsive web exists; no verified native app/offline selling workflow |

## PMS Inventory

### Implemented or Strong

| Area | Current Capability |
|---|---|
| Project management | Projects, clients, members, roles, project intake, project dashboards, portfolio views |
| Task management | Tasks, subtasks, checklists, tags, priorities, dependencies, comments, mentions, files/assets |
| Agile delivery | Boards, backlog, sprints, story points, epics, components, releases, burndown, velocity, cumulative flow, cycle time |
| Planning | Milestones, timeline/Gantt routes, dependency views, workload/capacity surfaces, project calendar |
| Time tracking | Time logs, weekly timesheets, billable/non-billable, submission/approval/rejection |
| Governance | Access checks, saved filters, activity logs, risks, client approvals, reports/export |
| Integrations/realtime | Dev integrations/links, webhooks, authenticated websocket route |
| Frontend | Command center, portfolio, dependency management, resource planning, agile execution, financials, risk register, reports, client portal, admin/settings |

### Partial or Not Yet Competitive

| Gap Area | Current State |
|---|---|
| Project templates/cloning | Routes/surfaces exist, but persistent enterprise template and clone-with-date-offset flow is not proven |
| Financials | Budget, actuals, billable time exist; rate cards, invoicing, profitability, EAC/ETC, and revenue recognition are partial |
| Resource planning | Capacity surfaces exist; skills, leave-calendar integration, allocation calendar, utilization forecasts need work |
| Automation/reminders | Approvals and notification foundations exist; rule builder, scheduled reminders, escalations are partial |
| Gantt maturity | Gantt/timeline exists; baselines, critical path, slack, auto-reschedule are not proven |
| Collaboration workspace | Comments/files exist; docs/wiki/forums/whiteboards/proofing are not competitive yet |

## HRMS Inventory

### Implemented or Strong

| Area | Current Capability |
|---|---|
| Employee core | Employee master, directory, profile, self-service, role workspace, org/company structure |
| Attendance | Punches, biometric CSV import adapter, duplicate detection, reconciliation, missing punch report, month locks, shifts/rosters |
| Leave | Leave requests, balances, accrual/carry-forward foundations, payroll feed |
| Payroll | Payroll runs, components, statutory fields, tax declarations, Form 16, bank advice, FNF, validation |
| Talent | Recruitment, onboarding, probation, performance, LMS, engagement |
| Operations | Helpdesk, documents, assets, exit management, background verification |
| Compliance | Statutory compliance, audit/logging, privacy, security, SSO/MFA surfaces |
| Analytics | Reports, advanced analytics, command-center readiness widgets |
| Communication | Notifications and WhatsApp ESS surfaces |

### Partial or Not Yet Competitive

| Gap Area | Current State |
|---|---|
| Direct device integrations | CSV biometric adapter exists; direct eSSL/ZKTeco/API sync should be added |
| Statutory portal filing | Validations exist; direct EPFO/ESIC/PT/LWF/TDS portal submission integrations remain roadmap |
| Mobile ESS | Web/WhatsApp surfaces exist; mobile-first leave, attendance, payslip, approvals need deeper polish |
| Advanced workforce rules | Split shifts, holiday double pay, comp-off, union/industry rules need configurable depth |

## Shared Suite Inventory

| Shared Area | Current Capability |
|---|---|
| Identity/security | Auth, roles, module permissions, superuser route access, SSO/MFA surfaces |
| Module architecture | Module registry and separate CRM/PMS/HRMS app boundaries |
| Navigation/layout | Shared frontend shell and app route registration |
| Workflow | Approval/workflow foundations across modules |
| Notifications | Common notification surfaces and module events |
| AI | AI agents app with chat/config/approvals/analytics/usage/security/feedback/handoff/logs |
| Audit/reporting | Audit logs, module-specific reports, certification reports |

## Best Current Positioning

1. HRMS can be positioned as the lead wedge for Indian SME/mid-market buyers.
2. CRM can support sales teams in a controlled pilot, especially lead-to-quote use cases.
3. PMS can support software teams, internal projects, and consulting delivery, with billing handled externally for now.
4. The suite should not yet be marketed as a full Zoho One/Dynamics/Odoo replacement until cross-module lead-to-cash, project-to-invoice, integration marketplace, and mobile/offline workflows are implemented.

