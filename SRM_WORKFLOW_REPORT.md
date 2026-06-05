# SRM Workflow Report

Date: 2026-06-04

## Workflow Coverage
| Workflow | Status | Evidence |
|---|---|---|
| CRM Won to SRM Sales Order | Passed | `POST /api/v1/srm/handoff/crm-won/{deal_id}` creates sales order and engagement. |
| Quote/deal line copy | Partially Passed | Quote lines copied when CRM quotation exists; test covers deal fallback without quotation. |
| Sales order approval threshold | Passed | Submit creates Approval OS request when amount exceeds configured/default threshold. |
| Sales order confirmation | Passed | Confirm creates/links engagement. |
| Engagement to PMS project | Passed | Creates PMS project, member, kickoff milestone, engagement link, notification. |
| Billing plan creation | Passed | Billing plan and milestones persist. |
| Invoice from sales order | Passed | Draft invoice created and duplicate source blocked. |
| Invoice approval/send | Passed | Status history and revenue event created. |
| Receipt allocation | Passed | Receipt allocation updates invoice paid/balance/status and revenue event. |
| Profitability snapshot | Passed | Snapshot calculates order, billing, invoice, collected, cost, margin, cash margin. |
| Recurring billing automation | Partially Passed | Recurrence field exists; scheduler not implemented. |
| External delivery/accounting workflows | Not Implemented | No production accounting export or payment reconciliation connector. |

## Regression Evidence
- SRM lifecycle tests passed.
- Existing `test_auth.py` and `test_approval_os.py` passed.

