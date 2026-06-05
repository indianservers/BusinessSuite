# SRM Phase 2 Database, Models, Schemas And Core APIs Report

## Final Phase Status

**Passed**

SRM now has its own operational database model set, schema compatibility helper, Alembic migration, expanded CRUD/status APIs, audit logging, validation, RBAC checks, and backend tests for the requested Phase 2 coverage. SRM records reference CRM/PMS/customer/user identifiers where needed, but the operating records are stored in SRM-owned `srm_*` tables.

## Tables Created And Verified

The required SRM operational tables are implemented in `backend/app/apps/srm/models.py` and verified through database inspection in `backend/tests/test_srm_database_integrity.py`.

- `srm_sales_orders`
- `srm_sales_order_lines`
- `srm_contracts`
- `srm_engagements`
- `srm_engagement_links`
- `srm_billing_plans`
- `srm_billing_milestones`
- `srm_invoice_drafts`
- `srm_invoices`
- `srm_invoice_lines`
- `srm_invoice_history`
- `srm_receipts`
- `srm_receipt_allocations`
- `srm_collection_reminders`
- `srm_customer_aging`
- `srm_profitability_snapshots`
- `srm_revenue_events`
- `srm_audit_logs`
- `srm_settings`

Status: **Passed**

## Migrations Created And Verified

Created migration:

- `backend/alembic/versions/20260604_002_srm_database_core.py`

Migration sanity check:

```text
alembic heads
20260604_002 (head)
```

The SRM dev compatibility helper is also implemented:

- `backend/app/apps/srm/schema.py`
- `ensure_srm_schema(db)`

Status: **Passed**

## Models Created And Verified

Implemented/verified model classes:

- `SRMSalesOrder`
- `SRMSalesOrderLine`
- `SRMContract`
- `SRMEngagement`
- `SRMEngagementLink`
- `SRMBillingPlan`
- `SRMBillingMilestone`
- `SRMInvoiceDraft`
- `SRMInvoice`
- `SRMInvoiceLine`
- `SRMInvoiceHistory`
- `SRMReceipt`
- `SRMReceiptAllocation`
- `SRMCollectionReminder`
- `SRMCustomerAging`
- `SRMProfitabilitySnapshot`
- `SRMRevenueEvent`
- `SRMAuditLog`
- `SRMSetting`

Status: **Passed**

## Schemas Created And Verified

Implemented/expanded SRM request schemas include:

- Sales order create/update
- Sales order line create/update
- Contract create/update
- Engagement create/update/link
- Billing plan create/update
- Billing milestone create
- Invoice patch
- Invoice line create
- Timesheet invoice request
- Receipt create/allocation
- Collection reminder
- Setting upsert

Status: **Passed**

## APIs Created And Verified

API prefix:

- `/api/v1/srm`

Verified API areas:

- Sales orders: create, view, list, update, submit, approve, confirm, cancel, close
- Sales order lines: add, edit, delete, recalculate totals
- Contracts: create, view, update, activate, expire, terminate, renew
- Engagements: create, view, update, link CRM/PMS records, lifecycle status, timeline
- Billing plans: create fixed/milestone/T&M/recurring/hybrid plan, add milestones, activate, pause, complete, cancel
- Invoices: create draft, add invoice lines, approve, send/export, generate PDF, track status/history
- Receipts: create, confirm, allocate to invoice, partial/full allocation tracking
- Collections: aging, reminders, customer outstanding, persisted customer aging rows
- Profitability: engagement profitability snapshots, customer/project-linked profitability inputs
- Settings: list/upsert SRM settings

Status: **Passed**

## Status Transitions Verified

The required status catalogs are explicitly defined and tested:

- Sales Order: `draft`, `pending_approval`, `approved`, `confirmed`, `cancelled`, `closed`
- Contract: `draft`, `under_review`, `active`, `expired`, `terminated`, `renewed`
- Engagement: `created`, `project_pending`, `project_created`, `delivery_in_progress`, `billing_in_progress`, `completed`, `closed`
- Billing Plan: `draft`, `active`, `paused`, `completed`, `cancelled`
- Invoice: `draft`, `pending_approval`, `approved`, `sent`, `partially_paid`, `paid`, `overdue`, `cancelled`
- Receipt: `draft`, `confirmed`, `allocated`, `partially_allocated`, `cancelled`
- Collection: `not_due`, `due`, `overdue`, `escalated`, `collected`, `written_off`

Transition validation is enforced for sales orders, contracts, billing plans, invoices, and receipts.

Status: **Passed**

## RBAC Verified

SRM APIs continue to use `RequirePermission(...)` checks and SRM-specific access helpers:

- Sales order/engagement assigned-record visibility
- SRM management permissions
- Invoice permissions
- Collection permissions
- Profitability permissions
- Settings/admin permissions

Verified by:

- `backend/tests/test_srm_rbac.py`
- Required backend suite run

Status: **Passed**

## Audit Logging Verified

Audit logging is implemented through `srm_audit_logs` for:

- Sales order create/update/submit/approve/confirm/cancel/close
- Sales order line create/update/delete
- Contract create/update/status changes
- Engagement create/update/link/status changes/PMS project creation
- Billing plan create/update/status changes
- Billing milestone create
- Invoice draft/create/update/approve/send/line create
- Receipt create/confirm/allocation
- Collection reminder send
- Setting upsert

Status: **Passed**

## Tests Executed

Command:

```bash
pytest tests/test_srm_sales_order.py tests/test_srm_contracts.py tests/test_srm_engagements.py tests/test_srm_billing_plans.py tests/test_srm_invoice_engine.py tests/test_srm_collection_engine.py tests/test_srm_profitability.py tests/test_srm_database_integrity.py tests/test_srm_rbac.py -q
```

Result:

```text
15 passed
```

Additional migration check:

```bash
alembic heads
```

Result:

```text
20260604_002 (head)
```

Status: **Passed**

## Bugs Found

1. `ensure_srm_schema` was only a placeholder.
   - Severity: High
   - Status: Fixed

2. Required Phase 2 migration did not exist.
   - Severity: High
   - Status: Fixed

3. Required `test_srm_billing_plans.py` and `test_srm_database_integrity.py` were missing.
   - Severity: High
   - Status: Fixed

4. Sales order line CRUD APIs were missing.
   - Severity: High
   - Status: Fixed

5. Contract lifecycle APIs were incomplete.
   - Severity: High
   - Status: Fixed

6. Engagement linking/status/timeline APIs were incomplete.
   - Severity: High
   - Status: Fixed

7. Billing plan lifecycle APIs and billing milestone add API were incomplete.
   - Severity: High
   - Status: Fixed

8. Invoice line add API and receipt confirmation API were missing.
   - Severity: Medium
   - Status: Fixed

9. Collection aging calculated response data but did not persist `srm_customer_aging`.
   - Severity: Medium
   - Status: Fixed

10. Status defaults were inconsistent during implementation:
    - Sales orders temporarily started as `created`.
    - Contracts temporarily started as `created`.
    - Engagements temporarily started as `draft`.
    - Severity: Medium
    - Status: Fixed and verified by tests

## Bugs Fixed

- Added SRM Alembic migration `20260604_002_srm_database_core.py`.
- Implemented `ensure_srm_schema(db)` with table inspection and SRM table creation for dev compatibility.
- Added missing schemas for line CRUD, contract updates, engagement updates/links, billing plan updates, invoice lines.
- Added sales order line add/edit/delete APIs with total recalculation.
- Added sales order cancel/close APIs and transition validation.
- Added contract get/update/activate/expire/terminate/renew APIs.
- Added engagement update/link/status/timeline APIs.
- Added billing plan get/update/milestone/status lifecycle APIs.
- Added invoice get/line add APIs and invoice status validation.
- Added receipt confirm API and receipt allocation status tracking.
- Persisted customer aging rows during collections aging calculation.
- Added and expanded backend tests for CRUD, DB rows, RBAC, validation, audit logs, duplicate prevention, and status catalogs.

## Pending Issues

No Phase 2 blocker remains.

Non-blocking follow-up items:

- The test database is SQLite in-memory; production rollout should run Alembic against the target MySQL/Postgres environment before go-live.
- Some tests emit existing dependency deprecation warnings from Pydantic, pytest-asyncio, jose, and passlib/bcrypt. These do not fail the SRM Phase 2 verification.
- Collection escalation and write-off are represented in the status catalog, but richer escalation workflows can be expanded in a later SRM workflow phase.

## Final Certification

SRM Phase 2 Database, Models, Schemas, And Core APIs is certified as:

**Passed**

The module has SRM-owned operational tables, migration coverage, schemas, CRUD/status APIs, access checks, audit logging, validation, duplicate prevention, and passing backend verification for the required Phase 2 scope.
