# SRM Phase 3 CRM-SRM-PMS Flow Report

Date: 2026-06-04

Final Phase Status: Passed

## Scope Verified

Commercial handoff verified and implemented:

CRM Deal Won -> SRM Sales Order -> SRM Contract / Engagement -> Billing Plan -> PMS Project.

CRM no longer owns the PMS project creation path. CRM won/deal handoff creates SRM commercial records first. PMS project creation is exposed from SRM engagement and is blocked until the linked sales order is confirmed.

## Implemented Files

- `backend/app/apps/srm/api/router.py`
- `backend/app/apps/crm/api/router.py`
- `backend/app/apps/project_management/api/router.py`
- `frontend/src/apps/srm/api.ts`
- `frontend/src/apps/crm/CRMRecordDetailPage.tsx`
- `frontend/src/apps/project-management/pages/ProjectDashboard.tsx`
- `frontend/src/apps/project-management/types.ts`
- `playwright/srm-test-utils.ts`
- `playwright/srm-crm-handoff.spec.ts`
- `playwright/srm-engagement-lifecycle.spec.ts`
- `playwright/crm-deal-srm-link.spec.ts`
- `playwright/pms-project-srm-link.spec.ts`
- `backend/tests/test_srm_crm_won_handoff.py`
- `backend/tests/test_srm_sales_order_from_crm.py`
- `backend/tests/test_srm_engagement_creation.py`
- `backend/tests/test_srm_pms_project_creation.py`
- `backend/tests/test_srm_handoff_idempotency.py`
- `backend/tests/test_srm_billing_plan_from_sales_order.py`

## API Verification

| API | Status | Evidence |
| --- | --- | --- |
| `POST /api/v1/srm/from-crm/deals/{deal_id}/create-sales-order` | Passed | Backend and Playwright tests verified SRM sales order, engagement, contract, billing plan, audit, notification payload path. |
| `POST /api/v1/srm/sales-orders/{id}/approve` | Passed | Backend API already implemented; Phase 3 tests use confirmed SO path after approval-capable flow. |
| `POST /api/v1/srm/sales-orders/{id}/confirm` | Passed | Confirm creates or returns billing plan idempotently. |
| `POST /api/v1/srm/engagements/{id}/create-pms-project` | Passed | Backend tests verify PMS project creation, milestone/task copy, link-back, and idempotency. |
| `GET /api/v1/srm/engagements/{id}/lifecycle` | Passed | Playwright and backend tests verify CRM/SRM/PMS links plus audit evidence. |
| `GET /api/v1/srm/by-crm-deal/{deal_id}` | Passed | Backend and frontend API tests verify handoff lookup by CRM deal. |

## Flow Status

| Stage | Status | Evidence |
| --- | --- | --- |
| CRM Won trigger | Passed | CRM create/update routes now call SRM handoff when deal status is `Won` or stage is marked won. |
| Sales order creation | Passed | `test_srm_crm_won_handoff.py` and `test_srm_sales_order_from_crm.py` verify SO creation from CRM deal/quote. |
| Sales order line copy | Passed | Quote lines are copied to `srm_sales_order_lines`, including amount and source quote line references. |
| Engagement creation | Passed | Engagement is created with CRM deal/quote references and linked to sales order/contract. |
| Contract creation/linking | Passed | Contract is created and linked to the SRM engagement. |
| Billing plan creation | Passed | Billing plan and milestones are created from sales order lines; endpoint also supports idempotent creation. |
| PMS project creation | Passed | SRM engagement creates PMS project only after confirmed sales order. |
| PMS link-back | Passed | Engagement stores `pms_project_id`; PMS project API returns `srm_links`. |
| CRM link display | Passed | CRM deal detail shows Commercial Handoff card with SRM and PMS links. |
| SRM lifecycle view/API | Passed | Lifecycle endpoint returns CRM, SRM, PMS, invoice, link, and audit sections. |

## Idempotency Verification

Status: Passed

- Existing CRM deal handoff returns the existing sales order and engagement instead of creating duplicates.
- Existing PMS project on an engagement returns the linked project instead of creating a duplicate.
- Safe idempotent events are audit logged.

## Audit And Notifications

Status: Passed

Verified records/events:

- SRM audit logs for `crm_won_handoff`, `created_from_crm_won`, `created_from_sales_order`, and idempotent paths.
- SRM revenue event `crm_won_handoff`.
- CRM timeline event `srm_handoff`.
- Notifications for sales owner and project manager.

## Database Impact Verified

Status: Passed

Tables verified through backend tests:

- `srm_sales_orders`
- `srm_sales_order_lines`
- `srm_contracts`
- `srm_engagements`
- `srm_engagement_links`
- `srm_billing_plans`
- `srm_billing_milestones`
- `srm_revenue_events`
- `srm_audit_logs`
- PMS project, milestone, and task tables through SRM project creation tests.
- CRM timeline/activity table through won-deal handoff trigger test.

## UI Link Status

Status: Passed

- CRM deal detail route `/crm/deals/501` renders Commercial Handoff with:
  - SRM Sales Order
  - SRM Engagement
  - SRM Contract
  - Billing Plan
  - PMS Project
- PMS project route `/pms/projects/301` renders SRM Engagement Link with:
  - Engagement
  - Sales Order
  - Contract
  - Billing Plan

## Tests Executed

Backend:

```text
pytest tests/test_srm_crm_won_handoff.py tests/test_srm_sales_order_from_crm.py tests/test_srm_engagement_creation.py tests/test_srm_pms_project_creation.py tests/test_srm_handoff_idempotency.py tests/test_srm_billing_plan_from_sales_order.py -q
Result: 10 passed
```

Frontend:

```text
npx playwright test --config=playwright.config.ts ../playwright/srm-crm-handoff.spec.ts ../playwright/srm-engagement-lifecycle.spec.ts ../playwright/crm-deal-srm-link.spec.ts ../playwright/pms-project-srm-link.spec.ts
Result: 4 passed
```

Build:

```text
npm run build
Result: Passed
```

## Bugs Found

1. CRM generic update route changed deal status to Won but did not invoke SRM handoff.
2. Frontend Playwright link tests initially authenticated as SRM Admin, which is correctly blocked from CRM/PMS routes by RBAC.

## Bugs Fixed

1. Added CRM update-route handoff trigger for won deals.
2. Added authorized admin test user for cross-module UI verification.
3. Added missing SRM frontend API client methods for handoff, CRM deal lookup, lifecycle, and billing plan creation.

## Pending Issues

None blocking Phase 3.

Residual notes:

- Backend test run emits existing Pydantic deprecation warnings; not introduced by this phase.
- Frontend production build emits normal Vite chunk output only.

## Go-Live Certification

Phase 3 is certified as Passed for the verified CRM Won -> SRM -> PMS commercial handoff.

Go-live status: Ready for controlled rollout.
