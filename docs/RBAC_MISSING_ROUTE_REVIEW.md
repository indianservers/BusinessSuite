# RBAC Missing Route Review

Date: 2026-06-04  
Baseline: Existing `RBAC_RECERTIFICATION_REPORT.md` plus current HRMS route scan  
Scope: Frontend route coverage gaps and UI exposure risk

## Summary

The prior recertification table covered the major employee/HR/admin routes but did not explicitly list several self-service, operational, advanced and pattern/deep-link routes. The current pass adds those routes to `RBAC_ROUTE_MATRIX.md` and validates the critical direct URL cases in `playwright/rbac-all-roles.spec.ts`.

One protection gap was found and fixed:

| Missing route / pattern | Severity | Protection before | Protection after | UI exposure | Result |
|---|---|---|---|---|---|
| `/hrms/workflow/admin` | Critical | Inherited `/workflow`, so Employee could reach the route shell | Explicit `Approval Administration` route guard added | Not visible | Employee now receives 403. |

## Missing From Prior Recertification Table

| Route / Pattern | Severity | Protection exists now? | UI exposure exists? | Notes |
|---|---|---:|---:|---|
| `/hrms/profile` | Medium | Yes | Yes, profile menu and ESS | Employee self-service route. |
| `/hrms/my-attendance` | Medium | Yes | Yes, Employee | Employee attendance route split from HR attendance register. |
| `/hrms/my-roster` | Medium | Yes | Yes, Employee | Employee roster route split from shift roster admin. |
| `/hrms/my-payslips` | High | Yes | Yes, Employee | Employee payslip route split from payroll operations. |
| `/hrms/notifications` | Medium | Yes | Admin/HR only | Employee notification bell hidden. |
| `/hrms/workflow/admin` | Critical | Yes | No | Fixed in this pass. |
| `/hrms/employees/new` | High | Yes | HR/Admin | Employee direct URL gets 403. |
| `/hrms/employees/:id` | High | Yes | HR/Admin | Employee direct URL gets 403. |
| `/hrms/employees/bulk-import` | Critical | Yes | No | Covered as pattern route. |
| `/hrms/employee-master` | High | Yes | No | Legacy pattern falls back to Admin-only. |
| `/hrms/attendance/bulk-import` | Critical | Yes | No | Covered as pattern route. |
| `/hrms/payroll/setup` | Critical | Yes | No | Covered as payroll operations pattern. |
| `/hrms/payroll/run` | Critical | Yes | No | Covered as payroll operations pattern. |
| `/hrms/payroll/tools` | Critical | Yes | No | Covered as payroll operations pattern. |
| `/hrms/payroll/reports` | Critical | Yes | No | Covered as payroll operations pattern. |
| `/hrms/payroll/bulk-publish` | Critical | Yes | No | Covered as payroll operations pattern. |
| `/hrms/payroll/bulk-export` | Critical | Yes | No | Covered as payroll operations pattern. |
| `/hrms/investment-declaration` | High | Yes | HR/Admin | Employee direct URL gets 403. |
| `/hrms/fnf-settlements` | High | Yes | HR/Admin | Employee direct URL gets 403. |
| `/hrms/benefits` | Medium | Yes | HR/Admin | Employee direct URL gets 403. |
| `/hrms/performance` | Medium | Yes | HR/Admin | Employee direct URL gets 403. |
| `/hrms/lms` | Medium | Yes | HR/Admin | Employee direct URL gets 403. |
| `/hrms/engagement` | Medium | Yes | HR/Admin | Employee direct URL gets 403. |
| `/hrms/statutory-compliance` | High | Yes | HR/Admin | Employee direct URL gets 403. |
| `/hrms/background-verification` | High | Yes | HR/Admin | Employee direct URL gets 403. |
| `/hrms/whatsapp-ess` | Medium | Yes | HR/Admin | Employee direct URL gets 403. |
| `/hrms/helpdesk` | Medium | Yes | HR/Admin | Employee direct URL gets 403. |
| `/hrms/advanced-analytics` | High | Yes | HR/Admin | Employee direct URL gets 403. |
| `/hrms/org-chart` | Medium | Yes | HR/Admin | Employee direct URL gets 403. |
| `/hrms/assets` | Medium | Yes | HR/Admin | Employee direct URL gets 403. |
| `/hrms/onboarding` | High | Yes | HR/Admin | Employee direct URL gets 403. |
| `/hrms/exit` | High | Yes | HR/Admin | Employee direct URL gets 403. |
| `/hrms/ai-assistant` | Low | Yes | HR/Admin | Employee direct URL gets 403. |
| `/hrms/security` | Critical | Yes | No | Admin-only fallback; regular HR and Employee get 403. |
| `/hrms/audit-log` | Critical | Yes | No | Admin-only fallback; Employee gets 403. |

## Remaining Watch Items

| Item | Severity | Recommendation |
|---|---|---|
| Backend/API authorization not covered by this UI suite | Critical | Keep backend RBAC and object-level authorization tests separate from frontend visibility tests. |
| Broad route fallback grants unknown HRMS paths to Admin only | Medium | Continue documenting every new HRMS route in the matrix during feature work. |
| Search dynamic API results depend on backend filtering plus frontend route filtering | High | Backend global search should also enforce role permissions server-side. |

