# HRMS + Payroll Final Readiness Retest Report

Retest date: 2026-06-03  
Scope: HRMS and Payroll modules only  
Audit role: HRMS Consultant, Payroll Expert, HR Head, QA Auditor  
Benchmark: Zoho People, Zoho Payroll, Keka HR, GreytHR practical readiness

## 1. Executive Verdict

| Area | Score | Verdict | Reason |
|---|---:|---|---|
| HRMS functional readiness | 72% | Partially Ready | Broad module coverage exists, but some important flows are not fully connected in UI/API and live E2E could not be completed. |
| Payroll functional readiness | 68% | Partially Ready | Payroll has strong foundations, lock/readiness concepts, components and reports, but one payroll regression fails and live startup is blocked. |
| UI readiness | 78% | Partially Ready | Frontend lint and production build pass. Menus and routes are mostly aligned, but some advanced pages are unreachable or partially wired. |
| API readiness | 64% | Not Ready | Registered API coverage is broad, but configured database startup fails and one frontend-called endpoint is missing. |
| Security readiness | 70% | Partially Ready | Role/menu segregation and payroll access patterns exist, but live RBAC and locked mutation checks need E2E verification. |
| Go-live score | 5.8 / 10 | Not Ready | Production go-live is blocked by live database schema mismatch and payroll regression. |

Final verdict: **Not Ready for production go-live**.

The product is **partially ready in test/in-memory environments**, but it is not ready for real-world deployment until the database migration issue, payroll regression and missing UI/API connections are fixed and revalidated.

## 2. Test Execution Summary

| Test / Check | Command / Method | Result | Notes |
|---|---|---|---|
| Frontend lint | `npm run lint` in `frontend` | Pass | No lint failures found. |
| Frontend production build | `npm run build` in `frontend` | Pass | Vite build completed and HRMS/Payroll lazy chunks compiled. |
| Backend HRMS/Payroll regression group | `pytest -q backend/tests/test_hrms_market_ready_readiness.py backend/tests/test_payroll_readiness_gate.py backend/tests/test_hrms_readiness_reports.py backend/tests/test_attendance.py backend/tests/test_payroll_components.py backend/tests/test_payroll_inputs_worksheet.py backend/tests/test_payroll_payments_accounting.py backend/tests/test_hrms_leave_payroll_feeds.py backend/tests/test_payroll_real_world_engine.py` | Fail | 23 passed, 1 failed. Failure is in payroll component line/rich payslip test. |
| Backend live startup | `uvicorn app.main:app --host 127.0.0.1 --port 8001` in `backend` | Fail | Startup fails against configured DB because `companies.cin_number` column is missing. |
| Frontend to backend endpoint scan | Static API comparison | Partial | 586 relevant frontend calls, 720 relevant backend routes, 1 frontend-called endpoint missing. |
| Browser route smoke | In-app Browser / Playwright fallback | Blocked | In-app browser returned unavailable and local Playwright package was not installed/resolvable. |

## 3. Critical Go-Live Blockers

| Priority | Issue | Evidence | Business Impact | Required Fix |
|---|---|---|---|---|
| P0 | Backend cannot start on configured database | Startup fails with `Unknown column 'companies.cin_number' in 'field list'` | HRMS/Payroll API is unavailable in the deployed/local DB environment. | Add and run database migration for company fields, especially `cin_number`, then rerun startup and migrations. |
| P0 | Payroll regression in component-line payslip flow | `test_payroll_run_persists_component_lines_and_rich_payslip` expected `201`, got `400` | Payroll run can be blocked when approved reimbursements are not included before run. Rich payslip workflow is not reliable. | Align reimbursement inclusion workflow with pre-run readiness checks or update run/test flow to include approved reimbursements before payroll approval. |
| P1 | Missing backend route called by frontend | Frontend calls `GET /statutory-compliance/portal-submissions`, backend only has POST and PUT submit routes | Statutory compliance portal submissions screen can fail at runtime. | Add list endpoint or update frontend to call an available endpoint. |
| P1 | Route/API live E2E not completed | Backend startup blocked and browser tooling unavailable | User journeys cannot be certified end to end. | Fix backend startup, install/enable browser automation, run full route smoke. |

## 4. Route Audit Table

| Route | Page / Module | Status | Finding |
|---|---|---|---|
| `/hrms` | HRMS entry | Available | Redirect/landing route exists. |
| `/hrms/dashboard` | Dashboard | Available | Main HRMS dashboard route exists. |
| `/hrms/role-home` | Role landing | Available | Internal role-based landing route exists. |
| `/hrms/admin-home` | Admin home | Available | Admin dashboard route exists. |
| `/hrms/hr-home` | HR home | Available | HR dashboard route exists. |
| `/hrms/executive-home` | Executive home | Available | Executive dashboard route exists. |
| `/hrms/manager-dashboard` | Manager dashboard | Available | Manager dashboard route exists. |
| `/hrms/ess` | Employee self-service | Available | ESS route exists. |
| `/hrms/employee-directory` | Employee directory | Available | Directory route exists. |
| `/hrms/employees` | Employee master | Available | Employee listing route exists. |
| `/hrms/employees/new` | Employee onboarding | Available | New employee route exists. |
| `/hrms/employees/:id` | Employee detail | Available | Employee detail route exists. |
| `/hrms/probation` | Probation | Available | Lifecycle route exists. |
| `/hrms/attendance` | Attendance | Available | Core attendance route exists. |
| `/hrms/attendance/shift-roster` | Shift roster | Partially Available | Route exists, but not clearly exposed through role menus/access list. |
| `/hrms/timesheets` | Timesheets | Available | Timesheet route exists. |
| `/hrms/workflow` | Workflow approvals | Available | Workflow route exists. |
| `/hrms/workflow-designer` | Workflow designer | Available | Designer route exists. |
| `/hrms/notifications` | Notifications | Available | Notifications route exists. |
| `/hrms/leave` | Leave management | Available | Leave route exists. |
| `/hrms/payroll` | Payroll | Available | Payroll route exists and compiles. |
| `/hrms/fnf-settlements` | Full and final settlement | Available | F&F route exists. |
| `/hrms/investment-declaration` | Investment declaration | Available | Tax declaration route exists. |
| `/hrms/recruitment` | Recruitment | Available | Recruitment route exists. |
| `/hrms/performance` | Performance | Available | Performance route exists. |
| `/hrms/benefits` | Benefits | Available | Benefits route exists. |
| `/hrms/lms` | Learning management | Available | LMS route exists. |
| `/hrms/statutory-compliance` | Statutory compliance | Partially Available | Route exists, but frontend calls one missing backend endpoint. |
| `/hrms/background-verification` | Background verification | Available | Route exists. |
| `/hrms/whatsapp-ess` | WhatsApp ESS | Available | Route exists. |
| `/hrms/custom-fields` | Custom fields | Available | Route exists. |
| `/hrms/enterprise` | Enterprise HR | Available | Route exists. |
| `/hrms/engagement` | Engagement | Available | Route exists. |
| `/hrms/helpdesk` | Helpdesk | Available | Route exists. |
| `/hrms/reports` | Reports | Available | Reports route exists, but several backend report endpoints appear unused. |
| `/hrms/advanced-analytics` | Advanced analytics | Available | Route exists. |
| `/hrms/logs` | Audit logs | Available | Logs route exists. |
| `/hrms/company` | Company settings | Available | Route exists. Live DB company schema is broken. |
| `/hrms/org-chart` | Org chart | Available | Route exists. |
| `/hrms/settings` | HRMS settings | Available | Route exists. |
| `/hrms/assets` | Asset management | Available | Route exists. |
| `/hrms/onboarding` | Onboarding | Available | Route exists. |
| `/hrms/documents` | Documents | Available | Route exists. |
| `/hrms/exit` | Exit management | Available | Route exists. |
| `/hrms/ai-assistant` | HRMS AI assistant | Available | Route exists. |

Route verdict: **Mostly available**, with live rendering not certified due backend startup and browser automation blockers.

## 5. UI Page Audit Table

| UI Area | Available? | Partial? | Missing? | Risk Level | Finding |
|---|---:|---:|---:|---|---|
| Employee master | Yes | No | No | Medium | Employee create/list/detail routes exist and build successfully. Live save/edit not E2E verified. |
| Departments, branches, designations | Yes | Yes | No | Medium | Company/settings routes exist, but live DB company schema prevents runtime validation. |
| Employee documents | Yes | Yes | No | Medium | Document route exists. Upload/download audit was not live verified. |
| Attendance | Yes | Yes | No | Medium | Attendance page exists. Half-day backend coverage passed in regression group except unrelated payroll regression. |
| Shift roster | Yes | Yes | No | High | Route exists but is not clearly exposed in menus/access config. |
| Timesheets | Yes | Yes | No | Medium | Timesheet route exists. Approval workflow not live E2E verified. |
| Leave management | Yes | Yes | No | Medium | Leave route exists. Leave/payroll feed tests passed in the selected group. |
| Payroll | Yes | Yes | No | High | Payroll page compiles, but payroll run regression exists and live backend is blocked. |
| Payroll payslip | Yes | Yes | No | High | Component-line rich payslip test currently fails because payroll run is blocked by readiness check. |
| F&F settlement | Yes | Yes | No | Medium | F&F route exists. End-to-end settlement calculation not live verified. |
| Investment declarations | Yes | Yes | No | Medium | Route exists. Tax declaration readiness is included conceptually in checks. |
| Recruitment | Yes | Yes | No | High | Route exists. Backend candidate conversion route appears unused by frontend. |
| Performance | Yes | Yes | No | Medium | Route exists. KPI/appraisal depth needs functional UAT. |
| ESS | Yes | Yes | No | High | ESS route exists. Payslip access restriction needs live role-based E2E after backend starts. |
| Reports | Yes | Yes | No | High | Reports route exists, but many backend report endpoints are not called by frontend. |
| Audit logs | Yes | Yes | No | Medium | Logs route exists. Critical payroll mutation audit should be E2E verified. |

## 6. API Audit Table

| API Area | Available? | Partial? | Missing? | Risk Level | Finding |
|---|---:|---:|---:|---|---|
| Employee APIs | Yes | Yes | No | Medium | Broad HRMS employee endpoints are registered. Live DB validation blocked. |
| Attendance APIs | Yes | Yes | No | Medium | Attendance lock, punches, weekly off and team APIs exist, but several appear unused by frontend. |
| Leave APIs | Yes | Yes | No | Medium | Leave/payroll integration tests in selected group passed. |
| Payroll run APIs | Yes | Yes | No | Critical | Readiness gate exists, but current reimbursement path blocks rich payslip regression. |
| Payroll component lines | Yes | Yes | No | Critical | Expected feature exists but regression test fails before run creation. |
| Payroll exports | Yes | Yes | No | Medium | Export/bank advice style endpoints exist. Full UI export flow not live verified. |
| Payroll lock APIs | Yes | Yes | No | High | Lock concept exists. Locked mutation E2E must be rerun after backend starts. |
| Reimbursement APIs | Yes | Yes | No | High | Approved reimbursement inclusion into payroll needs clearer workflow integration. |
| Loan/advance APIs | Yes | Yes | No | Medium | APIs and tests exist in payroll group. Live payroll run E2E not completed. |
| Statutory compliance APIs | Yes | Yes | Yes | High | Frontend calls `GET /statutory-compliance/portal-submissions`, but backend route is missing. |
| Recruitment APIs | Yes | Yes | No | High | Candidate conversion backend route exists but appears not used by frontend. |
| Reports APIs | Yes | Yes | No | High | Many report APIs exist but appear unused or not fully connected in frontend. |
| Audit APIs | Yes | Yes | No | Medium | Logs route exists, but critical change audit coverage needs live validation. |
| Company APIs | Yes | No | No | Critical | Company model/API cannot run against configured DB due missing `cin_number` column. |

Static API scan result:

| Metric | Count |
|---|---:|
| Relevant frontend API calls scanned | 586 |
| Relevant backend routes registered | 720 |
| Frontend-called relevant endpoints missing in backend | 1 |
| Backend relevant endpoints not seen in frontend calls | 135 |

Missing frontend-called endpoint:

| Method | Endpoint | Risk |
|---|---|---|
| GET | `/statutory-compliance/portal-submissions` | Statutory compliance portal submissions list can fail at runtime. |

Examples of backend APIs not clearly wired from frontend:

| API | Business Impact |
|---|---|
| `POST /attendance/locks` | Attendance freeze before payroll may not be reachable from UI. |
| `PUT /attendance/locks/{id}/unlock` | Attendance unlock workflow may be incomplete in UI. |
| `GET /attendance/punches`, `POST /attendance/punches` | Biometric/manual punch management may not be fully exposed. |
| `GET /attendance/weekly-offs`, `POST /attendance/weekly-offs` | Configurable weekly-off setup may not be UI-accessible. |
| `POST /recruitment/candidates/{id}/convert` | Candidate to employee conversion flow may be incomplete. |
| `GET /reports/employee-report` | Employee reporting may exist in API but not UI. |
| `GET /reports/salary-register` | Payroll register may exist in API but not UI. |
| `GET /reports/audit-log-report` | Audit log reporting may exist in API but not UI. |

## 7. HRMS Workflow Test Results

| Workflow | Status | Result | Risk | Notes |
|---|---|---|---|---|
| HR creates employee with branch, department, designation and manager | Partially Tested | Partial | Medium | Route/API coverage exists. Live DB save blocked by backend startup failure. |
| Upload employee documents | Partially Tested | Partial | Medium | Document module route exists. Upload not live verified. |
| Employee status lifecycle | Partially Tested | Partial | Medium | Probation, exit and employee detail routes exist. Full state transition UAT pending. |
| Capture daily attendance | Tested by backend group | Pass | Medium | Attendance tests passed in selected regression group. |
| Half-day attendance counts as 0.5 | Tested by backend group | Pass | High | Mandatory condition covered by regression group. Needs live UI verification. |
| Attendance freeze before payroll | Static verified | Partial | High | Backend APIs exist, but UI wiring appears incomplete. |
| Attendance regularization approval | Static verified | Partial | Medium | Workflow/attendance routes exist. Live approval path pending. |
| Leave request and approval | Tested by backend group | Pass / Partial | Medium | Leave payroll feed tests passed. Full ESS approval UI pending. |
| Leave balance in ESS | Static verified | Partial | Medium | ESS and leave routes exist. Role-based live verification pending. |
| Recruitment candidate management | Static verified | Partial | Medium | Recruitment route exists. Candidate conversion API appears not used. |
| Performance review/KPI | Static verified | Partial | Medium | Route exists. Detailed appraisal readiness not certified. |
| Exit and F&F trigger | Static verified | Partial | High | Exit and F&F routes exist. Full settlement E2E pending. |
| Employee self-service access | Static verified | Partial | High | ESS route exists. Employee-only payslip access needs live RBAC test. |
| HR reports | Static verified | Partial | High | Reports route exists, but report API/UI mapping has gaps. |

## 8. Payroll Workflow Test Results

| Workflow | Status | Result | Risk | Notes |
|---|---|---|---|---|
| Salary assignment and payroll run | Tested by backend group | Partial | High | Core payroll tests mostly pass, but component-line payslip test fails because run is blocked. |
| Payroll readiness/pre-run checks | Tested by backend group | Pass / Strict | High | Checks correctly identify pending reimbursement as critical. Workflow needs better UI/action path. |
| Payroll approval | Static verified | Partial | High | Approval concepts exist. Live maker-checker E2E pending. |
| Payroll lock after approval | Static verified | Partial | High | Lock concepts exist. Locked mutation APIs must be live retested. |
| Payslip with component lines | Tested by backend group | Fail | Critical | Regression fails before payroll record creation. |
| Payslip YTD and grouped components | Tested by backend group | Fail / Partial | Critical | Intended test fails due readiness gate. |
| Reimbursement inclusion in payroll | Tested by backend group | Fail / Partial | High | Approved reimbursement without payroll inclusion blocks run. |
| Loans and advances | Tested by backend group | Pass / Partial | Medium | Payroll inputs/payments/accounting tests passed in selected group. |
| Salary revision and arrears | Static verified | Partial | High | Routes/APIs likely exist, but full backdated revision UAT pending. |
| Statutory deductions | Static verified | Partial | High | Rule/stub coverage exists, but statutory portal list endpoint missing. |
| Bank advice/export | Static verified | Partial | Medium | Export endpoints exist. Live export download not verified. |
| F&F settlement | Static verified | Partial | High | Route exists. Full settlement calculation not certified. |
| Employee payslip self-service | Static verified | Partial | High | Must retest employee cannot access another employee's payslip after backend starts. |

## 9. Payroll Calculation Validation Table

| Case | Expected Validation | Retest Result | Risk | Notes |
|---|---|---|---|---|
| Monthly fixed salary | Gross, deductions and net salary correct | Pass / Partial | Medium | Backend payroll tests mostly passed. Live run blocked. |
| Half-day attendance | Half-day must count as 0.5 present day | Pass | High | Mandatory known bug appears covered by passing attendance/payroll tests. |
| Leave without pay | LOP reduces payable days and salary | Pass / Partial | Medium | Covered through payroll/leave test group. Live UI pending. |
| Paid leave | No salary deduction | Pass / Partial | Medium | Covered conceptually in tests. UI pending. |
| Joining mid-month | Salary prorated from joining date | Pass / Partial | Medium | Included in real-world payroll engine group. |
| Exit mid-month | Salary prorated to last working day | Pass / Partial | High | Included in payroll engine group, but F&F E2E pending. |
| Configurable working calendar | Working days should not default to Monday-Friday for all | Pass / Partial | High | Payroll real-world tests passed, but UI setup reachability needs verification. |
| Overtime as earning component | OT added as earning and not deducted | Pass / Partial | Medium | Variable earning concept exists. UI flow pending. |
| Bonus/incentive | Scheduled or one-time earning added correctly | Pass / Partial | Medium | Manual payroll inputs exist. UI/reporting pending. |
| Reimbursement | Approved reimbursement included or flagged before run | Fail / Partial | Critical | Readiness check blocks run when reimbursement is approved but not included. |
| Loan/advance recovery | EMI/recovery deducted correctly | Pass / Partial | Medium | Payroll input/accounting tests passed. |
| Arrears | Backdated revision calculates arrears | Partial | High | Needs full UAT with salary revision approval. |
| Statutory deductions | PF/ESI/PT/TDS rule driven | Partial | High | Compliance route gap and live DB blocker prevent final certification. |
| Negative net salary | Warning/block before approval | Pass / Partial | High | Readiness gate includes critical checks. Full UI pending. |
| Branch/department/pay schedule scope | Runs and reports respect selected scope | Partial | High | Scoping exists in code/tests, but live UI/report E2E pending. |

## 10. Security Test Results

| Security Area | Result | Risk | Finding |
|---|---|---|---|
| HRMS role menus | Partial | Medium | Role menus exist and map mostly to valid routes. Some advanced routes are not clearly exposed. |
| Employee self-service isolation | Partial | High | ESS route exists. Employee-only payslip access must be live tested after backend startup is fixed. |
| Payroll lock mutation restriction | Partial | High | Lock concepts exist, but live mutation blocking could not be E2E verified. |
| Approval maker-checker | Partial | High | Approval workflow exists in module structure. Self-approval restrictions need explicit UAT. |
| Branch/team visibility | Partial | High | Role/branch fields exist. Live record-level visibility test was blocked. |
| Audit log for critical changes | Partial | Medium | Logs route exists. Assignment, salary, payroll and deletion events need end-to-end audit verification. |
| Export access control | Partial | Medium | Permission patterns exist, but download audit and export authorization need live validation. |

## 11. UI/UX Findings

| Area | Finding | Risk | Recommendation |
|---|---|---|---|
| Payroll page density | Payroll UI is functionally broad and likely action-heavy. | Medium | Split into clear tabs for Run, Inputs, Checks, Payslips, Reports and Settings. |
| Attendance setup discoverability | Shift roster and weekly-off configuration are not clearly visible from menus. | High | Add explicit Attendance Setup / Calendar / Shift Roster navigation. |
| Payroll readiness feedback | Readiness gate is strict, but users need guided remediation. | High | Show failed checks with one-click actions, such as include reimbursements, lock attendance or assign salary. |
| Reports discoverability | Many report APIs are not clearly connected to UI. | High | Add report catalogue with payroll, leave, attendance, employee and audit sections. |
| Mobile readiness | Build passes, but mobile route smoke was not possible. | Medium | Add responsive smoke tests for dashboard, ESS, attendance, leave and payslip pages. |
| Error handling | Live backend schema failure would appear as full API outage. | Critical | Add migration checks and startup health diagnostics before deployment. |

## 12. Bugs Found

| Priority | Bug | Evidence | Impact | Fix |
|---|---|---|---|---|
| P0 | Live backend startup fails due missing DB column | `companies.cin_number` expected by model, absent in DB | Application API cannot start. | Add migration and run it on configured database. |
| P0 | Payroll component-line/rich payslip test fails | `test_payroll_run_persists_component_lines_and_rich_payslip` got `400` instead of `201` | Payslip generation workflow cannot be certified. | Fix reimbursement readiness/inclusion flow or test setup. |
| P1 | Frontend calls missing statutory portal list endpoint | `GET /statutory-compliance/portal-submissions` missing in backend | Statutory UI can fail. | Add GET list route. |
| P1 | Attendance lock/weekly-off APIs appear not fully wired | Backend routes exist but not seen in frontend calls | Payroll calendar/freeze workflows may be incomplete for HR users. | Wire setup pages/actions. |
| P1 | Recruitment candidate conversion API appears not wired | Backend route exists but not seen in frontend calls | Recruitment to employee lifecycle flow incomplete. | Add UI action and audit log. |
| P2 | Many report endpoints appear unused | Static scan shows unused employee/payroll/audit report APIs | Reports may not meet go-live expectations. | Connect reports page to APIs and add export actions. |
| P2 | Pydantic/Jose deprecation warnings | 1595 warnings in backend regression group | Upgrade risk and noisy test signal. | Migrate Pydantic config and timezone-safe datetime usage. |

## 13. Missing Connections

| Connection | Status | Business Risk |
|---|---|---|
| Frontend statutory portal submission list to backend API | Missing | Statutory compliance page may fail. |
| Attendance lock/unlock UI to backend lock APIs | Partial / Unconfirmed | Attendance freeze before payroll may not be operational for HR. |
| Weekly-off/calendar setup UI to backend APIs | Partial / Unconfirmed | Configurable payroll calendar may not be usable by non-technical HR users. |
| Candidate conversion UI to recruitment conversion API | Partial / Unconfirmed | Recruitment lifecycle may stop before employee onboarding. |
| Reports UI to payroll/employee/audit report APIs | Partial | Managers may not get payroll register, audit log and employee report from UI. |
| Payroll reimbursement inclusion action to readiness gate | Broken / Partial | Approved reimbursements can block payroll run without a clear inclusion path. |
| Live DB schema to backend model | Broken | Application cannot start in configured environment. |

## 14. Zoho / Keka / GreytHR Comparison

| Capability | Current Module | Zoho People / Payroll | Keka HR | GreytHR | Gap |
|---|---|---|---|---|---|
| Employee database | Partial / Strong | Strong | Strong | Strong | Needs live DB stability and full document verification. |
| Attendance and shifts | Partial | Strong | Strong | Strong | Shift roster and attendance calendar need better UI connectivity. |
| Leave management | Partial / Strong | Strong | Strong | Strong | ESS balance and approval E2E pending. |
| Payroll processing | Partial | Strong | Strong | Strong | Payroll regression and readiness remediation gap. |
| Payslip | Partial | Strong | Strong | Strong | Rich payslip test failing. |
| Reimbursements | Partial | Strong | Strong | Medium | Payroll inclusion workflow must be fixed. |
| Loans/advances | Partial | Medium | Strong | Strong | Needs live EMI/payroll UAT. |
| Statutory compliance | Partial | Strong | Strong | Strong | Missing portal submission list endpoint and export certification. |
| ESS | Partial | Strong | Strong | Strong | Employee-only access needs live E2E. |
| Reports | Partial | Strong | Strong | Strong | Report API/UI wiring gaps. |
| Audit and controls | Partial | Strong | Strong | Strong | Critical audit events need end-to-end verification. |

## 15. Final Fix Plan

| Priority | Fix | Owner | Validation |
|---|---|---|---|
| P0 | Create and apply DB migration for `companies.cin_number` and any missing company fields | Backend | `uvicorn app.main:app` starts cleanly against configured DB. |
| P0 | Fix payroll reimbursement readiness to rich payslip workflow | Payroll Backend | `test_payroll_run_persists_component_lines_and_rich_payslip` passes. |
| P1 | Add `GET /statutory-compliance/portal-submissions` backend route | Backend | Frontend statutory page loads list without API error. |
| P1 | Wire attendance lock, unlock, weekly-off and shift roster setup in UI | Frontend + HRMS Backend | HR can configure calendar, lock attendance and unlock through approval. |
| P1 | Add payroll readiness remediation actions in UI | Frontend + Payroll Backend | Failed checks show action buttons and payroll approval is blocked only when unresolved. |
| P1 | Add recruitment candidate conversion UI action | Frontend + HRMS Backend | Candidate converts to employee with audit log. |
| P1 | Connect reports UI to employee, salary register and audit report endpoints | Frontend | Reports page shows downloadable HRMS/Payroll reports. |
| P1 | Run full live E2E route smoke after backend starts | QA | Login, HRMS dashboard, employee, attendance, leave, payroll, ESS and reports routes pass. |
| P2 | Add automated browser route smoke tests | QA / Frontend | CI catches broken lazy imports, route crashes and missing API hooks. |
| P2 | Clean Pydantic/Jose warnings | Backend | Backend regression suite runs with materially reduced warnings. |

## 16. Final Certification Decision

| Certification Item | Decision |
|---|---|
| Ready for controlled internal demo | Yes, if demo uses seeded/test backend and avoids failing payroll reimbursement path. |
| Ready for pilot with real HR/payroll data | No |
| Ready for production go-live | No |
| Ready for schools/colleges/SMEs/hospitals/manufacturing/trading/IT | Not yet |

Final verdict: **Not Ready**.

Release can move to go-live retest only after:

1. Backend starts cleanly on the configured database.
2. Payroll component-line/rich payslip regression passes.
3. Missing statutory portal submission list endpoint is added.
4. Attendance calendar/lock and reimbursement inclusion flows are connected in UI.
5. Employee payslip access, payroll lock mutation restriction and branch/department scoping are verified through live E2E tests.
