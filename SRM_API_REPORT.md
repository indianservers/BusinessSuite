# SRM API Report

Date: 2026-06-04

## API Coverage
| API Area | Status | Tested APIs |
|---|---|---|
| Module info | Passed | `GET /api/v1/srm/module-info` |
| Sales orders | Passed | `GET/POST/PATCH /api/v1/srm/sales-orders`, `POST /submit`, `POST /approve`, `POST /confirm` |
| CRM Won handoff | Passed | `POST /api/v1/srm/handoff/crm-won/{deal_id}` |
| Contracts | Passed | `GET/POST /api/v1/srm/contracts` |
| Engagements | Passed | `GET/POST /api/v1/srm/engagements`, `GET /engagements/{id}` |
| PMS project creation | Passed | `POST /api/v1/srm/engagements/{id}/create-pms-project` |
| Billing plans | Partially Passed | `GET/POST /api/v1/srm/billing-plans`; no advanced recurring invoice scheduler yet. |
| Invoice drafts | Passed | `GET /api/v1/srm/invoice-drafts` |
| Invoice engine | Passed | `POST /invoices/draft-from-sales-order/{id}`, `POST /draft-from-engagement/{id}`, `POST /draft-from-timesheets`, `PATCH /invoices/{id}`, `POST /approve`, `POST /send`, `GET /pdf` |
| Collections | Passed | `POST /receipts`, `POST /receipts/{id}/allocate`, `GET /collections/aging`, `GET /collections/customer/{customer_id}`, `POST /collections/reminders/send` |
| Profitability | Passed | `GET /api/v1/srm/profitability?engagement_id={id}` |
| Customer 360 | Passed API, Partial UI | `GET /api/v1/srm/customer-360/{customer_id}` implemented; frontend route currently shows workspace shell without customer selector. |
| Reports | Passed | `GET /api/v1/srm/reports/dashboard`, `GET /reports/lead-to-cash` |
| Settings | Passed | `GET /api/v1/srm/settings`, `PUT /settings/{key}` |

## Bugs Fixed
- Duplicate invoice source prevention verified with HTTP 409.
- SRM app loading fixed through `backend/.env` installed app list.

## Pending
- Full production PDF rendering is a minimal PDF response, not a branded invoice document engine.
- External accounting export and payment gateway reconciliation are not implemented.

