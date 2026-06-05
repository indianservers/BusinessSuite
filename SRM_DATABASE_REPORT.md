# SRM Database Report

Date: 2026-06-04

## Tables Added
| Table | Status | Notes |
|---|---|---|
| `srm_sales_orders` | Passed | Core order header with CRM/customer/user references and approval metadata. |
| `srm_sales_order_lines` | Passed | Order line details copied from quote lines or created manually. |
| `srm_contracts` | Passed | Contract number, value, dates, status, customer and sales order links. |
| `srm_engagements` | Passed | CRM/SRM/PMS bridge with sales order, contract, project, customer, and owner fields. |
| `srm_engagement_links` | Passed | Generic cross-module link table for CRM, SRM, PMS entities. |
| `srm_billing_plans` | Passed | Billing type, recurrence, total amount, engagement link. |
| `srm_billing_milestones` | Passed | Milestone amount/status/due date under billing plans. |
| `srm_invoice_drafts` | Passed | Draft source tracking for sales orders, engagements, and timesheets. |
| `srm_invoices` | Passed | Invoice header, status, totals, paid and balance amounts. |
| `srm_invoice_lines` | Passed | Invoice lines with duplicate-source guard. |
| `srm_invoice_history` | Passed | Invoice status history. |
| `srm_receipts` | Passed | Receipt header and unallocated amount. |
| `srm_receipt_allocations` | Passed | Receipt-to-invoice allocations. |
| `srm_collection_reminders` | Passed | Reminder tracking. |
| `srm_customer_aging` | Partially Passed | Table exists; live aging endpoint computes from invoices rather than persisting every request. |
| `srm_profitability_snapshots` | Passed | Margin, cash, outstanding, cost, and status snapshots. |
| `srm_revenue_events` | Passed | Invoice sent and cash collected revenue events. |
| `srm_audit_logs` | Passed | SRM mutation audit log. |
| `srm_settings` | Passed | Org-scoped configurable settings. |

## Database Evidence
- SQLAlchemy models added in `backend/app/apps/srm/models.py`.
- Test database created tables through `Base.metadata.create_all`.
- Tests verified persistence for sales orders, lines, contracts, engagements, invoices, invoice history, receipt allocations, PMS project creation, audit logs.

## Pending
- Alembic migration file was not added because this repository currently creates enabled app tables through metadata/startup. Production migration generation remains a deployment blocker.

