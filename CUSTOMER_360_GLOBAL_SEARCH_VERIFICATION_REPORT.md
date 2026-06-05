# Customer 360 and Global Search Verification Report

Verification date: 2026-06-04

## Final Status

Overall: **Partially Passed UI surface, Failed transformation depth**

Go-live status: **Not approved** for Customer 360 / Global Search transformation claims.

## Evidence

- Code reviewed:
  - `frontend/src/apps/crm/CRMWorkspacePage.tsx`
  - `frontend/src/components/app/GlobalSearch.tsx`
  - `backend/app/api/v1/reports.py`
  - `backend/app/apps/crm/api/router.py`
- Tests run:
  - Full backend suite: **225 passed**
  - Focused CRM/PMS suite: **60 passed**
- Relevant facts:
  - CRM `Customer360Page` exists, but builds customer views from companies and frontend helper `customer360For`.
  - Global Search backend route is `/api/v1/reports/global-search`.
  - Global Search backend searches employees, jobs, company policies, and helpdesk tickets only.
  - CRM/PMS contexts use static page links, not true global backend record search.

## Tested Routes / APIs

- Frontend:
  - `/crm/customer-360`
  - Global search component in app topbar
- Backend:
  - `GET /api/v1/reports/global-search?q=...`
  - CRM generic record routes:
    - `GET /api/v1/crm/{entity}`
    - `GET /api/v1/crm/{entity}/{id}`
    - `GET /api/v1/crm/{entity}/{id}/related`

## Database Tables Checked

- HRMS global search: `employees`, `jobs`, `company_policies`, `helpdesk_tickets`
- CRM related data: `crm_companies`, `crm_contacts`, `crm_deals`, `crm_tasks`, `crm_activities`, `crm_quotations`, `crm_files`

## Feature Status

| Feature | Status | Evidence |
|---|---|---|
| Customer 360 shows CRM data | **Partially Passed** | UI route exists and loads CRM company-derived cards. It does not fetch a verified backend Customer 360 aggregate. |
| Customer 360 shows PMS data | **Not Implemented** | No verified customer-linked PMS project/task data in Customer 360 route. |
| Customer 360 shows invoice data | **Not Implemented** | Invoice module/draft data not found. |
| Customer 360 shows tasks/communication/documents | **Partially Passed** | CRM detail/timeline can show CRM tasks, activities, emails, meetings, files. Customer 360 aggregate itself is frontend-derived. |
| Customer 360 shows approval data | **Not Implemented** | No Approval OS integration found in Customer 360. |
| Customer 360 permissions respected | **Partially Passed** | CRM APIs have organization scoping tests. Customer 360 frontend helper itself has no separate cross-module permission proof. |
| No cross-customer data leakage | **Partially Passed** | CRM org scoping tests pass; no cross-module Customer 360 leakage test exists. |
| Performance acceptable | **Not Verified** | No load/performance test for Customer 360 aggregate found. |
| Global Search searches customers | **Failed** | Backend global search does not search CRM companies/contacts/customers. |
| Global Search searches employees | **Passed** | `/reports/global-search` searches employees. |
| Global Search searches projects/tasks/documents/approvals | **Not Implemented** | Backend route does not search PMS projects/tasks, documents, or approvals. |
| Results permission-filtered | **Partially Passed** | Backend uses `reports_view`; frontend filters static route results by route access. Record-level permission filtering for all modules is not implemented. |
| Quick actions work | **Not Implemented** | Global Search returns navigation results only; no verified quick actions. |
| Unauthorized records hidden | **Partially Passed** | Some CRM/PMS org/access tests pass; global search itself is not cross-module and lacks full record-level permission tests. |

## Bugs Found

- Customer 360 is not a backend-backed cross-module aggregate.
- Global Search is HRMS-focused and does not search CRM/PMS/documents/approvals.
- No quick actions in global search.

## Bugs Fixed

None during this verification pass.

## Pending Blockers

- Create backend Customer 360 aggregate API with CRM/PMS/invoice/document/approval joins.
- Add permission-scoped global search index across modules.
- Add quick action result types with permission checks.
- Add leakage and performance tests.

