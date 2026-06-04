# HRMS RBAC UI All Roles Test Report

Date: 2026-06-04  
Scope: HRMS frontend RBAC verification for Admin, HR, Employee and delegated HR roles  
Mode: UI route/menu/search verification only; no HRMS or Payroll feature expansion

## Executive Result

| Area | Result | Notes |
|---|---|---|
| Admin UI access | PASS | Admin can access registered HRMS route inventory and administrative pages. |
| Regular HR UI access | PASS | HR can access operational HR routes and is blocked from system administration defaults. |
| Employee UI isolation | PASS | Employee sees ESS/self-service surfaces only and receives 403 for operational/admin routes. |
| Delegated HR access | PASS | Each delegated HR role receives only its specific optional admin route. |
| Global Search RBAC | PASS | Forbidden pages are filtered from search results for Employee and regular HR. |
| Direct URL protection | PASS | Unauthorized direct URLs render explicit 403. |
| Mobile navigation | PASS | Employee mobile navigation exposes only ESS/self-service links. |
| Frontend build health | PASS | Lint and production build pass. |

Final frontend RBAC decision: **RBAC UI CERTIFIED**.

## Fixes Applied

| Issue | Fix |
|---|---|
| Employee could inherit `/hrms/workflow/admin` through the broad `/workflow` permission. | Added explicit `/workflow/admin` route guard requiring HR/Manager/Admin level access and `Approval Administration` permission label. |
| Employee topbar notification button could expose `/hrms/notifications`. | Notification action is now hidden unless the active role can access the notifications route. |
| Optional delegated HR roles could directly access delegated pages but did not receive matching menu entries. | Added delegated menu entries for `hr_company_admin`, `hr_workflow_admin` and `hr_custom_field_admin`. |
| RBAC suite had no dedicated Playwright config/script. | Added `frontend/playwright.config.ts` and `npm run test:rbac`. |
| Playwright RBAC suite depended on live backend token validity and could be logged out by 401 API responses. | Updated the test harness to seed the frontend auth store and stub non-authorization data APIs, keeping this suite scoped to frontend route/menu/search RBAC. |

## Role Verification

| Role | Sidebar / menu | Dashboard / cards | Global search | Direct URLs | 403 page | Result |
|---|---|---|---|---|---|---|
| Admin | Full HRMS administrative menu visible | Admin route inventory reachable | Admin pages searchable when configured | Registered routes allowed | No 403 for allowed inventory | PASS |
| HR | Operational HR menu visible | HR Home opens | Payroll and Talent exposed; Company hierarchy hidden | Company, Workflow Designer, Custom Fields, Enterprise, Settings, Logs, Security denied | Shows role, route and required permission | PASS |
| Employee | ESS Dashboard, My Profile, My Attendance, My Leave, My Payslips, My Documents, My Requests, My Roster only | ESS cards only | ESS Profile visible; Payroll, Talent and Org Chart hidden | Payroll, attendance register, shift roster, reports, company, workflow designer, custom fields, settings, logs, recruitment, employee master and bulk routes denied | Shows role, route and required permission | PASS |
| `hr_company_admin` | HR operational menu plus Company only | HR Home opens | No broad admin escalation tested | Company allowed; Workflow Designer, Custom Fields, Enterprise, Settings, Logs, Security denied | Correct 403 for forbidden routes | PASS |
| `hr_workflow_admin` | HR operational menu plus Workflow Designer only | HR Home opens | No broad admin escalation tested | Workflow Designer allowed; Company, Custom Fields, Enterprise, Settings, Logs, Security denied | Correct 403 for forbidden routes | PASS |
| `hr_custom_field_admin` | HR operational menu plus Custom Fields only | HR Home opens | No broad admin escalation tested | Custom Fields allowed; Company, Workflow Designer, Enterprise, Settings, Logs, Security denied | Correct 403 for forbidden routes | PASS |

## Employee Forbidden Route Coverage

| Route / Pattern | Expected | Result |
|---|---|---|
| `/hrms/payroll` | 403 | PASS |
| `/hrms/attendance` | 403 | PASS |
| `/hrms/attendance/shift-roster` | 403 | PASS |
| `/hrms/reports` | 403 | PASS |
| `/hrms/company` | 403 | PASS |
| `/hrms/workflow-designer` | 403 | PASS |
| `/hrms/custom-fields` | 403 | PASS |
| `/hrms/settings` | 403 | PASS |
| `/hrms/security` | 403 | PASS |
| `/hrms/logs` | 403 | PASS |
| `/hrms/recruitment` | 403 | PASS |
| `/hrms/employees` | 403 | PASS |
| `/hrms/employee-master` | 403 | PASS |
| `/hrms/payroll/setup`, `/run`, `/tools`, `/reports`, `/bulk-publish`, `/bulk-export` | 403 | PASS |
| `/hrms/employees/bulk-import` | 403 | PASS |
| `/hrms/attendance/bulk-import` | 403 | PASS |
| `/hrms/workflow/admin` | 403 | PASS |
| `/hrms/audit-log` | 403 | PASS |

## Validation Commands

| Command | Result |
|---|---|
| `npm run test:rbac` | PASS, 6 passed in 41.7s |
| `npm run lint` | PASS |
| `npm run build` | PASS, production build completed |

Note: The Playwright run uses frontend seeded auth state and stubs read-only data APIs that are not part of authorization. This prevents fake UI-test tokens from triggering Axios logout on backend 401 responses. Backend/API authorization is not certified by this report.

## Required Output Files

| File | Status |
|---|---|
| `docs/RBAC_ROUTE_MATRIX.md` | Created |
| `docs/RBAC_MISSING_ROUTE_REVIEW.md` | Created |
| `docs/RBAC_UI_ALL_ROLES_TEST_REPORT.md` | Created |
| `playwright/rbac-all-roles.spec.ts` | Created |

## Final Certification Boundary

Frontend RBAC is certified for menu visibility, route guards, direct URL denial, global search filtering, mobile navigation and delegated HR UI access.

Backend/API authorization remains a separate control plane and must be validated with API-level RBAC, object ownership and ESS isolation tests before production security sign-off.
