# Suite Workflow Audit

Date: 2026-06-04

## Executive Verdict

The suite has strong individual modules, but the next growth step is cross-module workflow. Right now the product looks like HRMS + CRM + PMS + AI in one shell. To compete with Zoho One, Odoo, Dynamics 365, or NetSuite-style suites, it must behave like one operating system: shared customers, employees, projects, approvals, files, notifications, invoices, and analytics moving through one business lifecycle.

Suite workflow score: 76/100

## Current Cross-Module Strengths

| Workflow Foundation | Status | Evidence |
|---|---|---|
| Shared authentication/RBAC | Strong | Common roles, permissions, superuser route access, module guards |
| Module registry | Strong | CRM/PMS/HRMS can be enabled and routed independently |
| Shared shell/navigation | Strong | App route registration and sidebar layout |
| Shared users/employees | Good | HRMS employee/user foundation can support module ownership and capacity |
| Notifications | Good foundation | Notification surfaces and mention flows exist |
| Workflows/approvals | Good foundation | CRM approvals, PMS timesheet/client approvals, HRMS workflows |
| AI agents app | Good foundation | Agent chat/config/approvals/analytics/log surfaces |
| Reports/audit | Good foundation | Module reports and certification artifacts exist |

## End-To-End Workflow Assessment

| Workflow | Current Readiness | Market Expectation | Gap |
|---|---:|---|---|
| Lead to quote | Good | Capture, qualify, quote, approve, send | Add forms, inbox, quote pricing/tax/discount controls |
| Quote to project | Weak/partial | Won deal automatically creates delivery project, team, milestones, budget | Build CRM-to-PMS project handoff |
| Project to invoice | Weak/partial | Billable time, milestones, expenses, invoices, revenue/margin | Build invoicing or accounting integration |
| Employee capacity to project staffing | Partial | HR leave/skills/capacity influence PMS assignment | Connect HRMS roster/leave/skills to PMS allocation |
| Ticket/customer support to project/task | Partial | Support issues become tasks/projects and update customer 360 | Formalize ticket-to-task and support status sync |
| Approval inbox across modules | Partial | One inbox for CRM quotes, PMS timesheets, HR leave/payroll/actions | Build suite-wide approval inbox and delegation |
| Customer 360 | Partial | CRM, projects, tickets, invoices, contacts, communications in one view | Add cross-module customer graph |
| Executive suite dashboard | Partial | Revenue, delivery, payroll, utilization, risk, receivables | Build suite-wide BI dashboard |
| Suite-wide search | Partial | Search people, customers, projects, documents, tasks | Add global search index |
| Integration marketplace | Weak | OAuth apps, webhooks, API docs, connector health | Build marketplace/admin connector layer |

## Workflow Risk Register

| Risk | Severity | Impact | Recommended Control |
|---|---:|---|---|
| Modules feel adjacent, not integrated | High | Buyers compare against mature suites and see workflow breaks | Build top 5 cross-module workflows before broad marketing |
| Duplicate entities across modules | High | Customer/project/account data drift | Shared customer/account graph and canonical IDs |
| Approval fragmentation | Medium | Managers miss approvals across CRM/PMS/HRMS | One approval inbox with filters and delegation |
| Notifications become noisy | Medium | Users ignore system signals | Preference center, digest, severity, ownership routing |
| AI lacks workflow authority | Medium | AI feels cosmetic | Agent approvals, traceability, suggested actions tied to module records |
| Integration setup is opaque | Medium | Production readiness confusion | Connector status, credential validation, delivery logs |

## Recommended Suite Workflows

### 1. Lead Won to Delivery Project

Trigger: CRM deal moves to Closed Won.

Actions:

- Create PMS project from selected template.
- Link CRM account, contact, deal, quotation, and PMS client/project.
- Copy quote lines into project budget and milestone plan.
- Suggest team from HRMS skills/capacity.
- Notify project manager and sales owner.

### 2. Project Work to Invoice

Trigger: Approved milestone or approved billable timesheets.

Actions:

- Generate invoice draft or export payload.
- Include approved time, milestone amount, tax, and discounts.
- Update CRM customer 360 with billing status.
- Update PMS profitability and budget variance.

### 3. One Approval Inbox

Trigger: Any approval event from CRM, PMS, or HRMS.

Actions:

- Display approval by module, amount, SLA, priority, requester, and delegation.
- Allow approve/reject/comment from one place.
- Record immutable audit event.

### 4. HR Capacity to PMS Resource Planning

Trigger: Task/project staffing or leave approval.

Actions:

- Show leave/holidays/shift schedules inside PMS allocation.
- Warn on over-allocation.
- Recommend available employees by skill and capacity.

### 5. Customer 360

Trigger: Open account/customer record.

Actions:

- Show CRM deals/quotes, PMS projects/tasks/risks, support tickets, invoices, documents, contacts, communication timeline.
- Allow module-specific drilldowns without losing customer context.

## Priority Actions

| Rank | Action | Impact |
|---:|---|---|
| 1 | Build CRM Closed Won -> PMS Project workflow | Turns modules into a suite and supports services businesses |
| 2 | Build PMS time/milestone -> invoice draft/export | Unlocks revenue workflow |
| 3 | Build suite-wide approval inbox | Immediate manager productivity |
| 4 | Build customer/account canonical graph | Prevents data duplication |
| 5 | Build HR capacity to PMS allocation | Differentiates against standalone PMS |
| 6 | Build global search | Makes suite feel integrated |
| 7 | Build connector status/admin page | Reduces deployment confusion |
| 8 | Build suite BI dashboard | Enables leadership buying decision |

