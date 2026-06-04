# Employee Lifecycle Role-Based UAT Report

Test date: 2026-06-04  
Scope: Employee lifecycle across Admin, HR, Manager and Employee roles  
Method: UI-first testing. API and database checks were performed only after UI actions.  
Environment: Frontend `http://127.0.0.1:5173`, Backend `http://127.0.0.1:8001`

## 1. Executive Verdict

| Area | Result | Finding |
|---|---|---|
| Role login | PASS | Admin, HR, Manager and Employee demo role logins opened their expected home pages. |
| HR employee creation | PASS | HR created `Lifecycle Test Employee` from the UI. Record persisted after refresh and appeared in the employee list. |
| Employee login mapping | PASS after fix | Employee detail page did not expose account creation. Fixed by wiring the existing create-user-account API into the Account tab. |
| Employee first login | PASS | Created employee logged in with the linked account and opened ESS. |
| Employee isolation | PASS | Operational HRMS routes showed explicit `403 ACCESS DENIED` with role, requested page and required permission. |
| Attendance entry | PASS | HR manually saved half-day attendance with OT from the Attendance Register. UI, API and DB confirmed persistence. |
| Manager workflow | FAIL | Created employee was not linked to a reporting manager because the employee creation wizard did not expose manager assignment. |
| Leave cycle | FAIL / Not certified | Employee ESS showed no leave balances assigned. End-to-end apply, approve, reject and cancel flow was not completed. |
| Payroll cycle | FAIL / Not certified | Salary assignment, bank details, payroll run, approval, lock and payslip cycle were not completed for the new lifecycle employee. |
| Exit lifecycle | FAIL / Not certified | Resignation, F&F, after-exit access and exit reports were not completed in this UAT run. |

Final decision: **EMPLOYEE LIFECYCLE NOT CERTIFIED**.

The core employee onboarding and attendance entry flows are now working from UI through API and database. The complete lifecycle is not certified because manager assignment, leave balance/application, payroll processing and exit stages were not completed for the created employee.

## 2. Test Data

| Data Item | Value |
|---|---|
| Employee name | Lifecycle Test Employee |
| Employee code | EMP00031 |
| Employee ID | 31 |
| Login email | lifecycle.employee@test.com |
| Temporary password | Employee@123456 |
| Branch | Head Office |
| Department | People Operations |
| Designation | HRMS User / designation ID 1 |
| Joining date | 2026-07-01 |
| Attendance test date | 2026-07-02 |

Note: The intended IT/developer department path could not be used with `Head Office` because the wizard filtered departments by selected branch. This filtering worked, but it also made branch/department selection dependent on available seeded mappings.

## 3. Role-Wise Login Result

| Role | UI Login Result | Landing Page | Result |
|---|---|---|---|
| Admin | Demo role login succeeded | `/hrms/admin-home` | PASS |
| HR | Demo role login succeeded | `/hrms/hr-home` | PASS |
| Manager | Demo role login succeeded | `/hrms/manager-dashboard` | PASS |
| Employee | Demo role login succeeded | `/hrms/ess` | PASS |
| Lifecycle employee | Email/password login succeeded | `/hrms/ess` | PASS |

## 4. Admin Setup Result

| Check | UI Tested? | Result | Notes |
|---|---:|---|---|
| Admin home | Yes | PASS | Admin dashboard opened. |
| Admin menus | Yes | PASS | Company, Workflow Designer, Settings, Logs, Custom Fields, Enterprise and Payroll were visible to Admin. |
| Full setup edit cycle | No | Not certified | The test did not edit company/branch/department/designation master data because master-data chain was already certified separately. |

## 5. HR Employee Creation Result

| Step | UI Result | API Result | DB Result | Retest Result |
|---|---|---|---|---|
| Create employee | Toast showed `Employee created successfully!` | `GET /api/v1/employees/31` returned employee data | `employees` row existed with ID 31 and code `EMP00031` | PASS |
| Refresh detail page | Employee detail still showed Lifecycle Test Employee | API still returned same employee | DB row persisted | PASS |
| Employee list | Employee appeared in `/hrms/employees` grid | List data included employee | DB row active | PASS |
| Field verification | Name, code, email, phone, branch, department and status visible | API returned branch ID 2, department ID 1, designation ID 1, status Active | DB matched API | PASS |

Verified API response highlights:

| Field | Value |
|---|---|
| `id` | 31 |
| `employee_id` | EMP00031 |
| `personal_email` | lifecycle.employee@test.com |
| `phone` | 9999999999 |
| `date_of_joining` | 2026-07-01 |
| `status` | Active |
| `user_id` before fix | null |

## 6. Employee Account Mapping Fix

| Item | Finding |
|---|---|
| Issue | Employee detail Account tab allowed linking an existing user but did not expose creating a new login account for the employee. |
| Affected screen | `/hrms/employees/31`, Account tab |
| Existing backend API | `POST /api/v1/employees/{employee_id}/user-account` |
| Fix applied | Added a Create Login form to the Account tab when `emp.user_id` is missing. |
| File changed | `frontend/src/apps/hrms/pages/employees/EmployeeDetailPage.tsx` |
| UI retest | Create Login button posted successfully and refreshed the linked account state. |
| API retest | Login with `lifecycle.employee@test.com` returned role `employee`, user ID 19 and employee ID 31. |
| DB retest | `employees.user_id = 19`, linked to `users.email = lifecycle.employee@test.com`, role `employee`. |
| Result | PASS |

## 7. Employee First Login Result

| Check | Result | Notes |
|---|---|---|
| Login with created account | PASS | Employee logged in using `lifecycle.employee@test.com`. |
| ESS dashboard | PASS | ESS opened successfully. |
| My Profile access | PASS | Self-service profile area available. |
| My Attendance access | PASS | `/hrms/my-attendance` opened without 403. |
| My Leave access | PASS | Leave page opened without 403. |
| My Payslips access | PASS / Empty | ESS showed no payslips yet, which is expected before payroll run. |
| Leave balances | FAIL / Missing data | ESS showed no leave balances assigned. |

## 8. Manager Approval Result

| Check | Result | Issue |
|---|---|---|
| Manager login | PASS | Manager dashboard opened. |
| Manager team context | PASS / Existing data | Dashboard showed one team member from existing data. |
| Lifecycle employee assigned to manager | FAIL | Employee creation wizard did not expose a reporting-manager field in the tested flow. |
| Leave approval by manager | Not certified | Blocked by no manager mapping and no leave balance/application completion. |

## 9. Attendance Cycle Result

| Step | UI Result | API Result | DB Result | Final |
|---|---|---|---|---|
| Open attendance register | PASS | N/A | N/A | PASS |
| Search employee | PASS | N/A | N/A | PASS |
| Save half-day attendance with OT | PASS | `POST /api/v1/attendance/bulk-entry` returned 200 and saved 1 row | `attendances` row ID 27 persisted | PASS |
| Refresh/register read | PASS | `GET /api/v1/attendance/register?date=2026-07-02&search=Lifecycle` returned row | DB row persisted | PASS |
| Half-day calculation | PASS | Summary returned `present: 0.5`, `half_day: 1`, `overtime_hours: 2.00` | `status=Half-day`, `total_hours=4.00`, `overtime_hours=2.00` | PASS |

Attendance evidence:

| Field | Value |
|---|---|
| Attendance ID | 27 |
| Employee ID | 31 |
| Date | 2026-07-02 |
| Status | Half-day |
| Hours worked | 4.00 |
| OT hours | 2.00 |
| Remarks | Lifecycle UAT half day with OT |

## 10. Leave Cycle Result

| Flow | Result | Issue |
|---|---|---|
| Employee leave page access | PASS | Page accessible to employee. |
| Leave balance visibility | FAIL | No leave balances assigned to lifecycle employee. |
| Apply paid leave | Not certified | Not completed. |
| Apply sick leave | Not certified | Not completed. |
| Apply LOP | Not certified | Not completed. |
| Approve/reject/cancel leave | Not certified | Blocked by missing completed application path. |
| Payroll leave feed | Not certified | No leave transaction was created for payroll feed. |

## 11. Payroll Cycle Result

| Flow | Result | Issue |
|---|---|---|
| Salary setup for lifecycle employee | Not certified | Not completed in this UAT pass. |
| Bank details | FAIL / Missing data | Created employee has no bank details from the onboarding wizard. |
| Payroll inputs | Not certified | Bonus, incentive, reimbursement, loan EMI, advance and arrears were not completed for this employee. |
| Payroll run | Not certified | Payroll was not run for this lifecycle employee. |
| Payroll approval and lock | Not certified | Not completed. |
| Payslip | Not certified | No lifecycle-employee payslip generated. |

## 12. Employee Change History Result

| Change | Result | Notes |
|---|---|---|
| Edit employee | Not certified | Creation was verified, but lifecycle edit history was not completed. |
| Transfer | Not certified | Not completed. |
| Promotion | Not certified | Not completed. |
| Salary revision | Not certified | Not completed. |
| Document upload | Not certified | Not completed for this employee. |

## 13. Exit Process Result

| Exit Flow | Result | Notes |
|---|---|---|
| Resignation request | Not certified | Not completed. |
| Exit approval | Not certified | Not completed. |
| Full and final settlement | Not certified | Not completed. |
| Post-exit employee login block | Not certified | Employee remains active. |
| Post-exit reports | Not certified | No exit record created. |

## 14. Role Permission Matrix

| Route / Function | Admin | HR | Manager | Employee | Result |
|---|---|---|---|---|---|
| Admin home | Allowed | Denied / not primary | Denied / not primary | Denied | PASS |
| HR home | Allowed | Allowed | Denied / not primary | Denied | PASS |
| Manager dashboard | Allowed | Allowed / operational context | Allowed | Denied | PASS |
| ESS dashboard | Allowed / not primary | Allowed / not primary | Allowed / not primary | Allowed | PASS |
| Employee master | Allowed | Allowed | Denied | Denied with 403 | PASS |
| Attendance register | Allowed | Allowed | Denied | Denied with 403 | PASS |
| My Attendance | Allowed | Allowed | Allowed | Allowed | PASS |
| Payroll operations | Allowed | Allowed | Denied | Denied with 403 | PASS |
| Reports | Allowed | Allowed | Denied / scoped | Denied with 403 | PASS |
| Company setup | Allowed | Denied unless delegated | Denied | Denied with 403 | PASS |
| Logs | Allowed | Denied by regular HR policy | Denied | Denied with 403 | PASS |

## 15. Unauthorized Access Tests

Lifecycle employee direct URL tests:

| URL | Expected | Observed | Result |
|---|---|---|---|
| `/hrms/employees` | 403 | `403 ACCESS DENIED` with role, requested page and required permission | PASS |
| `/hrms/payroll` | 403 | `403 ACCESS DENIED` with role, requested page and required permission | PASS |
| `/hrms/attendance` | 403 | `403 ACCESS DENIED` with role, requested page and required permission | PASS |
| `/hrms/reports` | 403 | `403 ACCESS DENIED` with role, requested page and required permission | PASS |
| `/hrms/company` | 403 | `403 ACCESS DENIED` with role, requested page and required permission | PASS |
| `/hrms/settings` | 403 | `403 ACCESS DENIED` with role, requested page and required permission | PASS |
| `/hrms/logs` | 403 | `403 ACCESS DENIED` with role, requested page and required permission | PASS |

## 16. Bugs Found

| Priority | Bug / Gap | Evidence | Fix Applied | Retest |
|---|---|---|---|---|
| P0 | Employee account creation missing from employee detail UI | Account tab had only existing-user mapping, while new employee had `user_id = null`. | Added Create Login form using existing `employeeApi.createUserAccount`. | PASS |
| P1 | Reporting manager not captured in employee wizard | Tested wizard did not expose manager selection in the visible job step. | Not fixed in this pass. | FAIL |
| P1 | Leave balance not available for new lifecycle employee | ESS showed no leave balances assigned after account login. | Not fixed in this pass. | FAIL |
| P1 | Bank/payroll prerequisites missing for lifecycle employee | Employee API/DB showed bank details null and no payroll setup completed. | Not fixed in this pass. | FAIL |
| P2 | Branch/department selection depends on seeded mapping | Selecting Head Office filtered out intended IT department. | No code change; behavior documented. | Partial |

## 17. Fixes Applied

| Fix | File | Status |
|---|---|---|
| Added employee login account creation form to employee Account tab. | `frontend/src/apps/hrms/pages/employees/EmployeeDetailPage.tsx` | Completed |
| Invalidated employee and user-option queries after account creation. | `frontend/src/apps/hrms/pages/employees/EmployeeDetailPage.tsx` | Completed |
| Defaulted account email from employee work/personal email. | `frontend/src/apps/hrms/pages/employees/EmployeeDetailPage.tsx` | Completed |

## 18. Retest Result

| Retest | Result |
|---|---|
| Create login account from UI | PASS |
| Login as lifecycle employee | PASS |
| Employee API `/auth/me` and `/employees/me` | PASS |
| DB user mapping | PASS |
| HR manual attendance save | PASS |
| Attendance register API read | PASS |
| Attendance DB read | PASS |
| Half-day equals 0.5 present day | PASS |

## 19. Final Scores

| Area | Score | Reason |
|---|---:|---|
| Admin setup | 70% | Login and menu access verified; setup CRUD not repeated. |
| HR employee creation | 90% | Create, refresh, list, API and DB verified. Manager/bank fields remain incomplete. |
| Employee self-service | 78% | Login and access isolation passed; leave balance and payslip data missing. |
| Manager workflow | 35% | Manager login passed, but lifecycle employee was not manager-linked. |
| Attendance lifecycle | 95% | Manual entry, half-day, OT, API and DB persistence passed. |
| Leave lifecycle | 25% | Page access only; balance/application/approval not certified. |
| Payroll lifecycle | 20% | Not completed for lifecycle employee. |
| Exit lifecycle | 10% | Not completed. |
| RBAC/security | 92% | Employee operational routes correctly returned 403; backend API isolation for every operation not retested here. |
| Overall lifecycle | 58% | Onboarding and attendance work; leave, payroll, manager and exit lifecycle remain uncertified. |

## 20. Final Decision

**EMPLOYEE LIFECYCLE NOT CERTIFIED**

Certification can move forward only after:

1. Employee creation captures or assigns a reporting manager.
2. New employee leave balances are initialized or visibly assignable from HR.
3. Lifecycle employee bank details and salary assignment are completed from UI.
4. Leave application, manager approval, payroll feed and payslip generation pass for the same employee.
5. Transfer, promotion, salary revision and exit/F&F are completed and verified through UI, API and DB.
