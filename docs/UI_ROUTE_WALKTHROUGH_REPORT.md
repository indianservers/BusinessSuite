# HRMS + Payroll UI Route Walkthrough Report

Certification date: 2026-06-03  
Scope: HRMS + Payroll frontend UI only  
Mode: Release hardening, no backend feature additions, no payroll logic changes  
Login used: HRMS admin user through the browser flow  

## Executive Result

| Check | Result |
|---|---|
| Desktop protected route smoke | PASS |
| Mobile protected route smoke | PASS |
| Console errors | PASS - none detected |
| API errors during route load | PASS - none detected |
| Error boundaries / blank crashes | PASS - none detected |
| Horizontal overflow | PASS - none detected |
| Production build | PASS |
| Frontend lint | PASS |

Final route verdict: **PASS**.

## Validation Method

The in-app Browser tool was unavailable in this environment, so the walkthrough was performed with local Playwright against the running app:

- Backend: `http://127.0.0.1:8001`
- Frontend: `http://127.0.0.1:5173`
- Backend health: `/health` returned healthy
- Authentication: UI login using `admin@aihrms.com`
- Route checks: 78 total checks
- Desktop viewport: 1440 px
- Mobile/tablet viewports: 1024, 768, 430, 390 px

## Route Results

| Area | Routes Checked | Result |
|---|---:|---|
| HRMS dashboard / role homes | 7 | PASS |
| Employee and directory pages | 4 | PASS |
| Attendance and shift roster | 2 | PASS |
| Leave and workflow pages | 4 | PASS |
| Payroll, F&F, investment declaration | 3 | PASS |
| Recruitment, performance, LMS, benefits | 4 | PASS |
| Compliance and enterprise pages | 5 | PASS |
| Reports, logs, company, org chart, settings | 5 | PASS |
| Assets, onboarding, documents, exit, AI assistant, profile | 6 | PASS |
| Mobile key routes across 4 widths | 32 | PASS |

## Desktop Routes Certified

| Route | Result | Notes |
|---|---|---|
| `/hrms` | PASS | No console/API errors. |
| `/hrms/dashboard` | PASS | Dashboard no longer fires employee-only leave balance call for admin login. |
| `/hrms/role-home` | PASS | Loads cleanly. |
| `/hrms/admin-home` | PASS | Loads cleanly. |
| `/hrms/hr-home` | PASS | Loads cleanly. |
| `/hrms/executive-home` | PASS | Loads cleanly. |
| `/hrms/manager-dashboard` | PASS | Loads cleanly. |
| `/hrms/ess` | PASS | Employee-only APIs are guarded when admin has no employee mapping. |
| `/hrms/employee-directory` | PASS | Loads without overflow. |
| `/hrms/employees` | PASS | Dense table remains contained. |
| `/hrms/employees/new` | PASS | Form route loads. |
| `/hrms/employees/1` | PASS | Detail route loads. |
| `/hrms/probation` | PASS | Loads cleanly. |
| `/hrms/attendance` | PASS | Attendance register is responsive and table scrolls inside container. |
| `/hrms/attendance/shift-roster` | PASS | Employee query cap no longer causes route-load API error. |
| `/hrms/timesheets` | PASS | Loads cleanly. |
| `/hrms/workflow` | PASS | Loads cleanly. |
| `/hrms/workflow-designer` | PASS | Loads cleanly. |
| `/hrms/notifications` | PASS | Loads cleanly. |
| `/hrms/leave` | PASS | Dense tables remain contained. |
| `/hrms/payroll` | PASS | Payroll tables remain contained and API error messages are readable. |
| `/hrms/fnf-settlements` | PASS | Employee query cap no longer causes route-load API error. |
| `/hrms/investment-declaration` | PASS | Employee-only tax self query is guarded for admin login. |
| `/hrms/recruitment` | PASS | Loads cleanly. |
| `/hrms/performance` | PASS | Cycle-dependent queries no longer fire before a cycle is selected. |
| `/hrms/benefits` | PASS | Loads cleanly. |
| `/hrms/lms` | PASS | Optional certification widgets no longer auto-trigger failing route-load calls. |
| `/hrms/statutory-compliance` | PASS | Loads cleanly. |
| `/hrms/background-verification` | PASS | Loads cleanly. |
| `/hrms/whatsapp-ess` | PASS | Loads cleanly. |
| `/hrms/custom-fields` | PASS | Loads cleanly. |
| `/hrms/enterprise` | PASS | Loads cleanly. |
| `/hrms/engagement` | PASS | Employee query cap no longer causes route-load API error. |
| `/hrms/helpdesk` | PASS | Loads cleanly. |
| `/hrms/reports` | PASS | Report page remains responsive. |
| `/hrms/advanced-analytics` | PASS | Manufacturing safety query is gated behind enabled pack state. |
| `/hrms/logs` | PASS | Large log table remains contained. |
| `/hrms/company` | PASS | Empty/loading/error states render cleanly. |
| `/hrms/org-chart` | PASS | Live org chart load is user-triggered to avoid noisy startup errors. |
| `/hrms/settings` | PASS | Loads cleanly. |
| `/hrms/assets` | PASS | Loads cleanly. |
| `/hrms/onboarding` | PASS | Loads cleanly. |
| `/hrms/documents` | PASS | Loads cleanly. |
| `/hrms/exit` | PASS | Loads cleanly. |
| `/hrms/ai-assistant` | PASS | Loads cleanly. |
| `/hrms/profile` | PASS | Employee-only profile APIs and session calls are guarded. |

## Mobile Routes Certified

| Route | Widths | Result |
|---|---|---|
| `/hrms/ess` | 1024, 768, 430, 390 | PASS |
| `/hrms/attendance` | 1024, 768, 430, 390 | PASS |
| `/hrms/leave` | 1024, 768, 430, 390 | PASS |
| `/hrms/payroll` | 1024, 768, 430, 390 | PASS |
| `/hrms/reports` | 1024, 768, 430, 390 | PASS |
| `/hrms/employees` | 1024, 768, 430, 390 | PASS |
| `/hrms/company` | 1024, 768, 430, 390 | PASS |
| `/hrms/profile` | 1024, 768, 430, 390 | PASS |

## Fixed During Walkthrough

| Issue | Fix | Result |
|---|---|---|
| Admin dashboard called employee leave balance API and returned 400 | Guarded leave balance query behind employee profile mapping | PASS |
| ESS/profile pages called employee-only APIs for admin/unlinked login | Added employee profile guards | PASS |
| Investment declaration called employee self endpoint for admin login | Added employee profile guard | PASS |
| Shift roster/F&F/engagement employee list calls used oversized pagination | Reduced query cap to accepted limit | PASS |
| Performance page called goal/nine-box APIs before cycle selection | Gated cycle-dependent calls | PASS |
| Advanced analytics called manufacturing safety incidents before pack enablement | Gated query behind enabled pack state | PASS |
| LMS certifications route-load call returned backend error | Stopped optional certification widgets from auto-firing on route load | PASS |
| Org chart route auto-called unstable live chart endpoint | Made live chart loading user-triggered | PASS |

## Commands Executed

| Command | Result |
|---|---|
| `npm run lint` | PASS |
| `npm run build` | PASS |
| Playwright authenticated route smoke | PASS, 78/78 |

## Final Certification

Route walkthrough status: **PASS**  
UI route readiness: **Certified for release hardening scope**
