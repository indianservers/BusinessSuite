# CRM daily workflow and collaboration

Open **CRM → Leads → Board view**. Group by **Current status**, **Team member**, or **Follow-up date**. The selected grouping is stored in the URL and survives saves and refreshes. Boards display the current filtered page; paging and scope limits remain visible.

## Daily actions

- Drag a card's grip between status lanes. Only allowed transitions accept a drop. Required qualification or loss fields open the existing editor when missing; conversion still uses the dedicated customer conversion flow.
- Group by team member to hand off leads. Ownership changes retain the existing employee/account validation, pending task transfer, history and assignment notifications. Assignment beyond self remains permission-controlled.
- Group by follow-up date to see overdue, today, tomorrow, later and unscheduled work. Drop on Today, Tomorrow or Later to review a proposed due time before saving.
- Use **Follow up** on a board card or table row, or **Activities → Schedule or reschedule follow-up** in a lead. Create a new pending task or reschedule an existing one; choose a title, type, due time and responsible teammate. The earliest pending task determines the lead's next follow-up.
- Use **Team** inside the lead to record updates and select colleagues to notify. Discussions retain author, timestamp and mention recipients in the lead history. Mention recipients must already have access; a mention does not grant record access.
- Team discussions refresh every 30 seconds while no draft or other edit is in progress; editing pauses polling to preserve the draft.
- Dragging has pointer, touch and keyboard support. Every editable card also has a **Move to…** menu. Read-only users have no mutation controls.
- Version checks prevent stale updates. Scheduling errors preserve form entries; **Refresh lead, keep draft** loads the latest version before retrying. Unsaved team updates prompt before leaving the tab or closing the lead.

## Reminders and deployment

Due pending tasks produce in-app notifications through the existing protected scheduled-jobs entry point. Reminders are deduplicated per task and reset when the task is rescheduled. Lost, converted, archived, inaccessible and inactive-assignee records are excluded. The scheduled endpoint must already be invoked by the deployment's scheduler; this change does not provision hosting or external email delivery.

No new database migration or external service is required. Existing CRM activity, timeline, notification and operating-state tables store these changes. Existing Excel import/export, saved views, scoring, sequences, workflows, SLA escalation and conversion remain available.

## Reference products reviewed (2026-10-26)

These are workflow references, not a claim of complete product parity or a ranking:

- [Salesforce Path and Kanban](https://trailhead.salesforce.com/content/learn/modules/leads_opportunities_lightning_experience/visualize-success-with-path-and-kanban): visual stages and record movement. BusinessSuite now supports lead stage drag-and-drop with its existing validation gates.
- [Salesforce activity management](https://trailhead.salesforce.com/content/learn/modules/sales_admin_maximize_productivity/sales_admin_maximize_productivity_unit_1): open tasks and interaction history. BusinessSuite adds faster scheduling and retains completed activities and timeline history.
- [HubSpot task management](https://www.hubspot.com/products/task-management): assigned tasks alongside prospect records. BusinessSuite exposes follow-up ownership, due dates, queues and reminders.
- [Pipedrive CRM features](https://www.pipedrive.com/en/crm/features): visual pipeline and activity-focused sales work. BusinessSuite adds status, employee and due-date groupings with clear next actions.
- [Zoho assignment rules](https://help.zoho.com/portal/en/kb/crm/faqs/automation/assignment-rules/articles/faqs-assignment) and [Blueprint](https://help.zoho.com/portal/en/kb/crm/process-management/blueprint/articles/blueprint-an-overview): rule-based routing and controlled process transitions. BusinessSuite retains its configured assignment rules, round robin, stage prerequisites and workflows.

Product-level gaps remain: provider-backed two-way email/calendar synchronization, telephony recording/transcription, advanced territory and availability-based routing, visual branching workflow design, cross-record real-time presence, and broader enterprise forecasting. These require separate integration and data-model work; the workflow changes here do not claim to implement them.

## Validation

Regression coverage includes actual pointer drag persistence, accessible assignment, follow-up scheduling, selected mention recipients, viewer restrictions and existing import/export/conversion/workflow controls. Backend checks cover pending task creation, rescheduling without duplication, earliest due date, stale versions, foreign task IDs, protected recipients, and deduplicated reminders. Evidence is under `docs/qa/crm-workflow/`.

Verified locally: 34 PostgreSQL regression tests, 18 browser checks (16 main checks and two additional draft/mobile checks), and the production frontend build passed. The disposable PostgreSQL test database is separate from the development database. No deployment was performed.
