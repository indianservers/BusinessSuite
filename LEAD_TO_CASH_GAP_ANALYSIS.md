# Lead-to-Cash Gap Analysis

Verification date: 2026-06-04

## Executive Gap Summary

The system has strong CRM and PMS islands, but it does not yet have a complete Lead-to-Cash business lifecycle.

Working:
- CRM lead creation, conversion, deal, quote, approval, Closed Won, audit, reports.
- PMS project/task/sprint/timesheet/resource/profitability foundations.
- Approval OS foundation.

Missing:
- CRM Closed Won -> PMS Project automation.
- CRM/PMS cross-module record graph.
- Invoice generation.
- Collection/receipt/payment allocation.
- Cash-aware profitability.

## Gap Matrix

| Area | Current state | Business impact | Severity | Required fix |
|---|---|---|---|---|
| Closed Won -> Project | CRM can mark Won after approval; PMS can create projects independently. No automatic handoff found. | Sales win does not start delivery automatically; manual duplicate data entry. | Critical | Add deal-won event handler/workflow to create PMS project. |
| Cross-links | CRM links lead/contact/company/deal/quote internally; PMS links client/project internally. No durable CRM-to-PMS link found. | Customer 360/CEO view cannot prove one record chain. | Critical | Add fields/tables for `crm_deal_id`, `crm_quote_id`, `crm_company_id`, `pms_project_id`, external references. |
| Template application | PMS templates/clones exist. No CRM-triggered template selection. | Delivery setup cannot be standardized from sold scope. | High | Map quote/deal products/services to PMS template. |
| Budget/milestones | PMS project budget/profitability exists. CRM quote values do not flow into PMS budget/milestones. | Delivery budget may diverge from sold quote. | High | Copy quote amount, scope, terms, milestones into PMS project at handoff. |
| Approval integration | CRM approvals and Approval OS exist. PMS client approvals exist. | Approval stages are separate; billing gate not enforced. | High | Define lifecycle approvals: quote approval, Closed Won approval, client milestone approval, invoice approval. |
| Invoice | Only demo/static invoice draft UI data found. | Finance cannot bill from the system. | Critical | Implement invoice model, lines, draft generation, status, PDF/export/send. |
| Timesheet -> invoice | PMS timesheets pass, but no invoice draft line generation. | Approved billable time cannot become revenue. | Critical | Generate invoice draft lines from approved billable PMS time logs/timesheets. |
| Collection | No customer A/R collection object found. | CEO cannot track cash received or overdue receivables. | Critical | Implement receipts, allocations, outstanding balances, aging, reminders. |
| Profitability | PMS profitability is based on project/time cost, not invoice/collection. | Margin can be planned/estimated but not actual cash margin. | High | Connect quoted, invoiced, collected, and delivery cost facts. |
| UI | CRM Lead-to-Cash page exists as dashboard/handoff queue. | Users may believe invoice handoff is complete when it is not. | High | Label placeholder/handoff clearly or wire real actions. |
| RBAC | CRM/PMS module RBAC mostly tested; PMS frontend route RBAC recently fixed. Finance Manager role mapping not found. | Finance lifecycle permissions cannot be certified. | High | Add Finance Manager role/permissions for invoice, collection, profitability. |
| Audit | CRM/PMS/Approval audit exists per module. | Cross-stage lifecycle audit missing. | High | Add lifecycle event log spanning CRM, PMS, invoice, collection. |
| Notifications | CRM/Approval/PMS notifications exist in parts. | Handoff notifications cannot be relied on end-to-end. | Medium | Emit notifications for project creation, invoice draft, overdue collection. |
| Reports | CRM and PMS reports pass independently. | CEO cannot see true Lead-to-Cash conversion/cash cycle. | Critical | Build lifecycle report: lead age, quote value, won value, delivery cost, invoice amount, collected amount, margin. |

## Recommended Implementation Order

1. Add canonical lifecycle/cross-link model.
2. Add Closed Won event handler and PMS project creation.
3. Add quote/deal-to-project template and budget/milestone mapping.
4. Add invoice draft model and invoice line generation from approved quote/milestone/timesheets.
5. Add collection receipts/payment allocation and aging.
6. Add Finance Manager RBAC.
7. Add unified lifecycle audit and notifications.
8. Add CEO Lead-to-Cash dashboard/report.
9. Add E2E test: lead -> deal -> quote -> approval -> won -> project -> sprint -> task -> timesheet -> client approval -> invoice -> collection -> profitability.

## Minimum Go-Live Blockers

The following must be fixed before this can be certified as Lead-to-Cash:
- Invoice implementation.
- Collection implementation.
- Closed Won -> PMS project handoff.
- Cross-module entity linking.
- Invoice-aware/cash-aware profitability report.
- Finance Manager RBAC.

