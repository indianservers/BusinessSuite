# CRM RBAC Verification Report

Date: 2026-06-04

## Status

Overall RBAC status: **Partially Passed**

Reason: Backend CRM API RBAC and record visibility are strong for tested paths. Frontend route RBAC had a high-impact gap for CRM admin/settings pages; it was fixed and verified. Team hierarchy and some manager-vs-admin distinctions still need deeper tests.

## Verified

| Area | Status | Evidence |
|---|---|---|
| Sales executive assigned-record visibility | Passed | `test_crm_sales_executive_visibility_is_limited_to_permitted_records` |
| Organization scoping | Passed | Lead CRUD, approval, duplicate, win/loss, territory tests prevent cross-org records |
| API permission gates | Passed | CRM router uses `RequirePermission("crm_view", "crm_manage", "crm_admin")` and stricter manage/admin gates |
| Frontend CRM admin/settings route block | Passed after fix | `crm_sales_executive` denied `/crm/admin` and `/crm/settings` in Playwright |
| CRM admin route availability for admin role | Passed | `crm_org_admin` opens `/crm/admin` in Playwright |
| CRM nav filtering | Passed after fix | `getCrmNavForRole` filters CRM admin/manager-only routes |
| Manager team hierarchy | Partially Passed | Manager role exists; no dedicated subordinate hierarchy test found |
| Global CRM search permission filtering | Not Implemented | No CRM record-wide global search API found |

## Bug Fixed

Bug: CRM frontend route guard allowed every CRM role to open every `/crm/*` route, including admin/settings pages.

Fix: Updated `frontend/src/lib/roles.ts`:

- Added CRM admin and manager role helpers.
- Added `canAccessCrmPath`.
- Restricted `/crm/admin`, `/crm/settings`, `/crm/approval-settings`, `/crm/webhooks`, `/crm/feature-checklist` to CRM/admin roles.
- Restricted `/crm/import-export`, `/crm/lead-scoring`, `/crm/pipeline-settings`, `/crm/territories` to CRM manager/admin roles.
- Filtered CRM navigation using the same route rules.

Verification:

- `npm run build` passed.
- `pytest -q tests/test_crm_rest_api.py` passed (`26 passed`).
- Playwright RBAC smoke:
  - `crm_sales_executive` allowed `/crm/leads`.
  - `crm_sales_executive` denied `/crm/admin`.
  - `crm_sales_executive` denied `/crm/settings`.
  - `crm_org_admin` allowed `/crm/admin`.

## Pending RBAC Risks

- Add automated frontend tests for CRM route matrix.
- Add backend tests for sales manager subordinate/team visibility.
- Implement and test CRM global search permission filtering.
- Add explicit CRM role matrix documentation for admin, sales manager, sales executive, marketing, support, and viewer roles.

