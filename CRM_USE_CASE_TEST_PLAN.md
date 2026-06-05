# CRM Use Case Test Plan

Date: 2026-06-04

Scope: CRM sales, manager, admin, and owner workflows across UI routes, REST APIs, database writes, RBAC, validation, audit logs, notifications, error handling, and mobile/responsive rendering.

## Verification Rules

- Mark `Passed` only when verified through code, API tests, database-impact assertions, and UI route evidence where applicable.
- Mark `Partially Passed` when a workflow exists but is incomplete, mocked, static, or lacks one required verification dimension.
- Mark `Failed` when implemented behavior is wrong.
- Mark `Not Implemented` when no credible implementation path was found.
- Critical/high bugs found during verification are fixed when safely scoped.

## Execution Evidence Sources

- Backend focused CRM regression: `pytest -q tests/test_crm_rest_api.py` in `backend` -> `26 passed`.
- Frontend build regression: `npm run build` in `frontend` -> passed after CRM RBAC patch.
- Browser UI smoke with Playwright against `http://127.0.0.1:5173`:
  - Desktop routes: `/crm/leads`, `/crm/pipeline`, `/crm/quotations`, `/crm/approval-settings`, `/crm/duplicates`, `/crm/customer-360`, `/crm/import-export`, `/crm/calendar-integrations`.
  - Mobile routes: `/crm/leads`, `/crm/customer-360`, `/crm/quotations` at `390x844`.
  - Result: meaningful content rendered, no Vite overlay, no console errors after corrected notification mock.
- Browser RBAC smoke:
  - `crm_sales_executive` can open `/crm/leads`.
  - `crm_sales_executive` is denied `/crm/admin` and `/crm/settings` after fix.
  - `crm_org_admin` can open `/crm/admin`.
- Code/API/database inspection:
  - `backend/app/apps/crm/api/router.py`
  - `backend/app/apps/crm/models.py`
  - `backend/app/apps/crm/schema.py`
  - `backend/tests/test_crm_rest_api.py`
  - `frontend/src/apps/crm/routes.tsx`
  - `frontend/src/apps/crm/CRMWorkspacePage.tsx`
  - `frontend/src/apps/crm/CRMRecordDetailPage.tsx`
  - `frontend/src/apps/crm/api.ts`
  - `frontend/src/lib/roles.ts`

## CRM Database Tables Checked

`crm_leads`, `crm_contacts`, `crm_companies`, `crm_deals`, `crm_deal_contacts`, `crm_pipelines`, `crm_pipeline_stages`, `crm_products`, `crm_deal_products`, `crm_quotations`, `crm_quotation_items`, `crm_activities`, `crm_tasks`, `crm_notes`, `crm_note_mentions`, `crm_email_logs`, `crm_email_templates`, `crm_messages`, `crm_message_templates`, `crm_call_logs`, `crm_meetings`, `crm_tickets`, `crm_campaigns`, `crm_file_assets`, `crm_custom_fields`, `crm_custom_field_values`, `crm_territories`, `crm_territory_users`, `crm_approval_workflows`, `crm_approval_steps`, `crm_approval_requests`, `crm_approval_request_steps`, `crm_audit_logs`, `crm_webhooks`, `crm_webhook_deliveries`, `crm_enrichment_logs`, `calendar_integrations`, `notifications`.

## Use Case Matrix

| # | Use Case | Primary Role | UI Route | Primary API | Planned Status Criteria |
|---|---|---|---|---|---|
| 1 | Admin creates lead manually | CRM Admin | `/crm/leads` | `POST /api/v1/crm/leads` | Required fields, source, owner, status, duplicate behavior, save feedback |
| 2 | Sales user views assigned leads | Sales Executive | `/crm/leads` | `GET /api/v1/crm/leads` | Assigned-only records, hidden peer records |
| 3 | Manager views team leads | Sales Manager | `/crm/leads` | `GET /api/v1/crm/leads` | Team visibility and hierarchy |
| 4 | Admin imports leads from CSV | CRM Admin | `/crm/import-export`, `/crm/leads` | `POST /api/v1/crm/leads/import` | Duplicates, invalid rows, rollback/export |
| 5 | Website lead captured | Anonymous/customer | Public web form | Web-to-lead API | Source, assignment, notification |
| 6 | Lead assignment rule | CRM Admin/Sales Ops | `/crm/territories` | `POST /api/v1/crm/territories/auto-assign` | Territory/source owner assignment |
| 7 | Lead status update | Sales Executive | `/crm/leads/:id` | `PATCH /api/v1/crm/leads/{id}` | Timeline, audit, follow-up prompt |
| 8 | Call note and follow-up | Sales Executive | `/crm/leads/:id` | `POST /api/v1/crm/notes`, `POST /api/v1/crm/tasks` | Timeline and reminders |
| 9 | Send email/WhatsApp/SMS | Sales Executive | `/crm/leads/:id` | `POST /api/v1/crm/emails/send`, `POST /api/v1/crm/messages/send` | Message log and delivery state |
| 10 | Duplicate detection/merge | Sales Ops/Admin | `/crm/duplicates` | `GET /api/v1/crm/duplicates`, `POST /api/v1/crm/duplicates/merge` | Merge, relink, audit |
| 11 | Lead conversion | Sales Executive | `/crm/leads/:id` | `POST /api/v1/crm/leads/{id}/convert` | Contact/company/deal mapping |
| 12 | Manual deal creation | Sales Executive | `/crm/deals` | `POST /api/v1/crm/deals` | Required links, value, probability, close date |
| 13 | Pipeline movement | Sales Executive | `/crm/pipeline` | `GET /api/v1/crm/deals/kanban`, `PATCH /api/v1/crm/deals/{id}` | Stage/probability/history/stale warning |
| 14 | Pipeline dashboard | Sales Manager | `/crm`, `/crm/reports` | CRM report APIs | Pipeline value, forecast, overdue |
| 15 | Quotation from deal | Sales Executive | `/crm/quotations`, `/crm/deals/:id` | `POST /api/v1/crm/quotations`, `GET /pdf` | Items, tax, discount, terms, PDF |
| 16 | Discount approval | Sales Manager/CFO | `/crm/approval-settings`, `/crm/my-approvals` | CRM approval APIs | Approval/rejection gate |
| 17 | Email approved quotation | Sales Executive | `/crm/quotations/:id` | `POST /api/v1/crm/quotations/{id}/send-pdf-email` | Attachment/log/timeline/status |
| 18 | Closed Won deal | Sales Executive | `/crm/deals/:id` | `PATCH /api/v1/crm/deals/{id}` | Mandatory handoff fields and trigger |
| 19 | Closed Won creates PMS project | Sales/PMS | CRM/PMS | CRM-to-PMS API | Project template, budget, milestones |
| 20 | Closed Lost deal | Sales Executive | `/crm/deals/:id`, `/crm/reports` | `PATCH /api/v1/crm/deals/{id}`, win/loss report | Lost reason, competitor, report |
| 21 | Sales sequence/cadence | Sales Executive | `/crm/automation` | Cadence APIs | Scheduled follow-up/email/reminder |
| 22 | Monthly quota | Sales Manager | `/crm/forecasting` | Quota API | Quota vs achieved |
| 23 | Forecast rollup | Manager/Owner | `/crm/forecasting`, `/crm/reports` | Forecast/report APIs | User/team/branch forecast |
| 24 | Customer 360 | Sales/Support/Owner | `/crm/customer-360` | CRM list/detail APIs | Related CRM/cross-module data |
| 25 | Global search | All CRM roles | Global search | Record search API | Permission-filtered CRM records |
| 26 | Restricted admin/settings | Sales Executive | `/crm/admin`, `/crm/settings` | Admin CRM APIs | UI and API blocked |
| 27 | Custom field | CRM Admin | `/crm/settings` | `POST /api/v1/crm/custom-fields`, value upsert | Validation/save/reporting |
| 28 | CRM report export | Manager/Admin | `/crm/reports` | Report/export APIs | Filters, accuracy, permissions |
| 29 | Email/calendar sync | Sales/Admin | `/crm/calendar-integrations` | Calendar/email APIs | Connector status/log/failures |
| 30 | Mobile CRM | Sales Executive | `/crm/leads`, `/crm/quotations`, `/crm/customer-360` | Same CRM APIs | Lead list/detail/actions/mobile |

