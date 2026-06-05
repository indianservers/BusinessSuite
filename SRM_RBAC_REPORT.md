# SRM RBAC Report

Date: 2026-06-04

## Permissions Added
`srm_view`, `srm_manage`, `srm_admin`, `srm_invoice_view`, `srm_invoice_create`, `srm_invoice_approve`, `srm_collection_view`, `srm_collection_create`, `srm_profitability_view`, `srm_settings_manage`.

## Roles Added
| Role | Status | Permissions |
|---|---|---|
| SRM Admin | Passed | Full SRM access and settings. |
| Sales Manager | Passed | Sales/revenue visibility and manage access. |
| Sales Executive | Passed | SRM view/manage; backend assigned-user filtering implemented. |
| Finance Manager | Passed | Invoice, approval, collection, profitability access. |
| Revenue Manager | Passed | Revenue/profitability/report visibility. |
| Collection Executive | Passed | Collection view/create only. |
| Business Owner | Passed | Dashboards, reports, profitability, invoices, collections. |
| Viewer | Passed | Read-only SRM/invoice/collection/report visibility. |

## Enforcement Evidence
- Backend APIs use `RequirePermission`.
- SRM access helper restricts non-manager sales users to assigned sales orders and engagements.
- Frontend route guards restrict finance, collections, settings, and sales-only views.
- Test `test_srm_role_without_permission_is_api_blocked`: Passed with HTTP 403.

## Pending
- Team hierarchy scoping for Sales Manager is coarse org-level at present; a real team hierarchy service should be connected.

