# Lead-to-Cash Verification Test Plan

Verification date: 2026-06-04

Lifecycle under test:
Lead -> Deal -> Quote -> Approval -> Closed Won -> Project -> Sprint -> Task -> Timesheet -> Client Approval -> Invoice -> Collection -> Profitability

Personas:
- Sales Executive
- Sales Manager
- Project Manager
- Developer
- Client
- Finance Manager
- CEO

Status definitions:
- Passed: verified from actual code, API, tests, UI route/build evidence, and database models.
- Partially Passed: implemented in one module or visible in UI, but not verified as a complete lifecycle handoff.
- Failed: implemented but verified broken.
- Not Implemented: no real implementation found.

## Evidence Sources

Commands executed:
- `pytest -q tests/test_crm_rest_api.py tests/test_approval_os.py tests/test_pms_project_access.py tests/test_pms_readiness_features.py` -> 52 passed.
- `npm run build` in `frontend` -> passed.
- Code/API inspection with `rg` across CRM, PMS, Approval OS, reports, payroll/payment terms, invoice/collection/payment terms.

UI routes checked by code/build:
- CRM: `/crm/leads`, `/crm/deals`, `/crm/quotations`, `/crm/approval-settings`, `/crm/my-approvals`, `/crm/lead-to-cash`, `/crm/reports`, `/crm/customer-360`.
- PMS: `/pms/projects`, `/pms/projects/new`, `/pms/projects/:projectId`, `/pms/sprints`, `/pms/tasks`, `/pms/timesheets`, `/pms/client-portal`, `/pms/reports`, `/pms/project-financials`.
- Approval OS: `/approval-os`.

Primary APIs to verify:
- Lead: `POST/GET/PATCH /api/v1/crm/leads`, `POST /api/v1/crm/leads/{id}/convert`.
- Deal: `POST/GET/PATCH /api/v1/crm/deals`, `GET /api/v1/crm/deals/kanban`.
- Quote: `POST/PATCH /api/v1/crm/quotations`, `GET /api/v1/crm/quotations/{id}/pdf`, `POST /api/v1/crm/quotations/{id}/send-pdf-email`.
- Approval: `POST /api/v1/crm/approval-workflows`, `POST /api/v1/crm/approvals/submit`, `POST /api/v1/crm/approvals/{id}/approve`, `GET /api/v1/crm/approvals/my-pending`, Approval OS inbox APIs.
- Closed Won: `PATCH /api/v1/crm/deals/{id}` with `status: Won`.
- Project: `POST /api/v1/project-management/projects`, `GET /api/v1/project-management/projects`.
- Sprint: PMS sprint APIs.
- Task: PMS task APIs.
- Timesheet: PMS time log/timesheet APIs.
- Client Approval: PMS milestone/client approval APIs and `pms_client_approvals`.
- Invoice: expected customer invoice draft/export APIs were searched but not found.
- Collection: expected payment collection/receipt APIs were searched but not found for customer A/R.
- Profitability: PMS budget/client profitability report APIs.

Database tables checked:
- CRM: `crm_leads`, `crm_contacts`, `crm_companies`, `crm_deals`, `crm_quotations`, `crm_quotation_items`, `crm_approval_workflows`, `crm_approval_steps`, `crm_approval_requests`, `crm_approval_request_steps`, CRM timeline/activity/audit tables.
- Approval OS: `approval_requests`, `approval_comments`, `approval_history`, `notifications`.
- PMS: `pms_clients`, `pms_projects`, `pms_project_members`, `pms_sprints`, `pms_tasks`, `pms_milestones`, `pms_client_approvals`, `pms_time_logs`, `pms_timesheets`, `pms_activities`, `pms_risks`, `pms_file_assets`, `pms_user_capacity`.
- Finance search result: payroll payment tables exist (`payroll_payment_batches`, `payroll_payment_lines`) but these are payroll disbursement objects, not customer invoice/collection objects for Lead-to-Cash.

## Stage Test Matrix

| Stage | Persona | UI | API | DB | RBAC | Audit | Notifications | Reports | Expected status |
|---|---|---|---|---|---|---|---|---|---|
| Lead | Sales Executive | `/crm/leads`, `/crm/lead-to-cash` | CRM leads + convert | `crm_leads` | Sales record scope | timeline/audit | note/mention supported | lead source/conversion | Passed |
| Deal | Sales Executive, Sales Manager | `/crm/deals`, `/crm/pipeline` | CRM deals/kanban | `crm_deals` | owner/team scope | timeline/audit | activity reminders | pipeline/win-loss | Passed |
| Quote | Sales Executive | `/crm/quotations` | quotation/PDF/send | `crm_quotations`, items | CRM role scope | PDF timeline | email send log | quote data in customer timeline | Passed |
| Approval | Sales Manager, CEO | `/crm/approval-settings`, `/crm/my-approvals`, `/approval-os` | CRM approvals + Approval OS | approval tables | approver/org scope | approval timeline/history | pending approval notifications | approval status in detail | Passed |
| Closed Won | Sales Manager | `/crm/deals` | deal status update | `crm_deals` | approval final gate | closed fields/timeline | not verified for handoff | win/loss reports | Passed for CRM only |
| Project | Project Manager | `/pms/projects` | PMS project create/list | `pms_projects` | PMS access | `pms_activities` | PMS notifications | portfolio reports | Partially Passed |
| Sprint | Project Manager | `/pms/sprints` | sprint lifecycle APIs | `pms_sprints` | PMS access | sprint activity | not fully verified | burndown/velocity | Partially Passed |
| Task | Team Lead, Developer | `/pms/tasks`, board | task APIs | `pms_tasks` | member scope | `pms_activities` | mentions supported | task reports | Partially Passed |
| Timesheet | Developer, Project Manager | `/pms/timesheets` | timesheet/time-log APIs | `pms_timesheets`, `pms_time_logs` | owner/manager scope | activities/status | workflow/Approval OS aggregation exists | timesheet/utilization reports | Partially Passed |
| Client Approval | Client, Project Manager | `/pms/client-portal` | milestone approval APIs | `pms_client_approvals`, `pms_milestones` | client portal role | expected in PMS activity | not fully verified | pending approval metrics | Partially Passed |
| Invoice | Finance Manager | CRM handoff queue, PMS financials demo | No real customer invoice API found | No customer invoice tables found | not enforceable | not available | not available | not available | Not Implemented |
| Collection | Finance Manager | none found for customer A/R collection | No collection/receipt API found | No collection/receipt tables found | not enforceable | not available | not available | not available | Not Implemented |
| Profitability | Finance Manager, CEO | `/pms/project-financials`, `/pms/reports` | profitability/report APIs | `pms_projects`, `pms_time_logs` | PMS report scope | report source activity | not applicable | profitability reports | Partially Passed |

