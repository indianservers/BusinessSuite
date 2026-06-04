# HRMS + Payroll Real User Acceptance Test Report

Test date: 2026-06-03  
Tester role: HR Executive and Payroll Officer  
Execution method: Live browser UI against local application  
Frontend: `http://127.0.0.1:5173`  
Backend: `http://127.0.0.1:8001`  
Rule applied: No item is marked Pass unless UI entry/save was completed, success was visible, refresh retained the data, and API/database verification supported the result.

## Executive Verdict

| Area | Verdict | Reason |
|---|---|---|
| Company setup | Fail | UI save showed success, but company listing API returned 500 and the company disappeared after refresh. |
| Organization setup | Fail | Branch creation was blocked because Company dropdown had no company options; save returned 422 and crashed the UI toast. |
| Employee lifecycle | Fail | Required 20-employee creation could not proceed because organization setup failed; attempted first employee did not save. |
| Attendance | Partial Pass | Attendance lock and unlock worked from UI, refreshed correctly, and were confirmed by API/database. Manual employee attendance entry was not available on the tested screen. |
| Leave | Fail | Admin leave application failed with `No employee profile`; request did not save or appear after refresh. |
| Payroll setup | Partial Pass | Payroll legal entity and pay group were created from UI, visible after refresh, and confirmed in database. Full salary structure/components/run were not completed. |
| Payroll run | Fail | June payroll run was blocked by readiness checks: missing salary, missing bank, invalid bank, attendance not locked and tax declaration issues. |
| Payslip | Fail | No June payslip could be generated because payroll run did not complete. |
| Reports | Fail | Reports page rendered `Something went wrong`; no report/export could be tested. |
| Security | Partial Pass | Employee login redirected to ESS; direct payroll URL showed only payslip viewer, not setup/run controls. Full role matrix was not completed. |

Final status: **Not Ready for production UAT sign-off**.

## Test Flow 1 - Company Setup

| Screen Name | Data Entered | Saved Successfully? | Visible After Refresh? | Editable? | Used In Next Workflow? | API/DB Verification | Pass/Fail |
|---|---|---:|---:|---:|---:|---|---|
| Company Settings | Indian Servers Demo Pvt Ltd, CIN `U72900TG2026PTC000001`, PAN `AABCI1234F`, Hyderabad, Telangana | Yes, toast showed `Company details saved` | No | Not verified because listing failed | No | UI API `GET /api/v1/company/` returned 500. DB row existed, but `city/state` mapping was incorrect: city stored as `Telangana`, state empty. | Fail |
| Settings > Companies | Indian Servers Demo Pvt Ltd duplicate attempt | No, duplicate prevention returned conflict | No | No | No | UI showed `Could not save` and `Company name already exists`, confirming duplicate prevention but not list usability. | Fail |

Customer-impact finding: Company save and list are inconsistent. A customer sees success, refreshes, and the company is gone from the UI.

## Test Flow 2 - Organization Setup

| Screen Name | Data Entered | Saved Successfully? | Visible After Refresh? | Editable? | Used In Next Workflow? | API/DB Verification | Pass/Fail |
|---|---|---:|---:|---:|---:|---|---|
| Settings > Branches | Hyderabad Head Office, code `HYD-HO` | No | No | No | No | Company dropdown only showed `Select`; save returned 422. Frontend crashed while rendering validation object in toast. | Fail |
| Settings > Departments | HR, Finance, IT, Sales, Academics, Operations | Not executed | No | No | No | Blocked because branch/company setup failed. Existing UI count/list also inconsistent. | Fail |
| Settings > Designations | HR Manager, Payroll Executive, Software Developer, Sales Executive, Professor, School Teacher, Driver, Security Guard | Not executed | No | No | No | Blocked because department setup failed. | Fail |
| Payroll > Pay Groups | Monthly Staff, code `MONTHLY-STAFF` | Yes | Yes | Not verified | Yes, visible in Payroll Setup | DB row exists in `payroll_pay_groups`. | Pass |

Bug observed: Branch save failure caused React error `Objects are not valid as a React child`, leaving a blank/broken page until refresh.

## Test Flow 3 - Employee Lifecycle

| Screen Name | Data Entered | Saved Successfully? | Visible After Refresh? | Editable? | Used In Next Workflow? | API/DB Verification | Pass/Fail |
|---|---|---:|---:|---:|---:|---|---|
| Add Employee | Attempted Aarav Sharma, Head Office, People Operations, HRMS User | No confirmed save | No | No | No | Employee list after reconnect still showed only existing 6 employees; Aarav Sharma was not present. | Fail |
| Employee List | Required 20 employees | No | No | No | No | Could not create required 20 employees because branch/department/designation setup failed. | Fail |
| Documents | Required employee documents | Not executed | No | No | No | Blocked by employee creation failure. | Fail |
| Status / Transfer / Promotion | Required lifecycle changes | Not executed | No | No | No | Blocked by employee creation failure. | Fail |

Customer-impact finding: The employee wizard can open, but the requested business setup chain cannot be completed from UI-created organization data.

## Test Flow 4 - Attendance

| Screen Name | Data Entered | Saved Successfully? | Visible After Refresh? | Editable? | Used In Next Workflow? | API/DB Verification | Pass/Fail |
|---|---|---:|---:|---:|---:|---|---|
| Attendance | Present / Absent / Half Day / Holiday / Weekly Off manual entries | No | No | No | No | Screen only showed self check-in and calendar; no visible HR manual attendance grid for employees. | Fail |
| Attendance Lock | June 2026 lock | Yes, toast showed `Attendance month locked` | Yes, status remained `Locked` after refresh | Yes, unlock available | Potentially payroll readiness | API `GET /attendance/locks?month=6&year=2026` returned `Locked`; DB row in `attendance_month_locks` confirmed. | Pass |
| Attendance Unlock | June 2026 unlock | Yes, toast showed `Attendance month unlocked` | Yes, status remained `Unlocked` after refresh | Yes | Yes | DB row updated to `Unlocked`, with `unlocked_by=1`. | Pass |

## Test Flow 5 - Leave

| Screen Name | Data Entered | Saved Successfully? | Visible After Refresh? | Editable? | Used In Next Workflow? | API/DB Verification | Pass/Fail |
|---|---|---:|---:|---:|---:|---|---|
| Leave > Apply Leave | Casual Leave, 2026-06-05, reason `Personal work UAT` | No | No | No | No | UI returned `Error` and `No employee profile`; request did not appear after refresh. | Fail |
| Leave Approval | Approve / reject / cancel leave | Not executed | No | No | No | Blocked because leave request could not be created as HR Admin. | Fail |
| Leave Balances | Balance verification | Not executed | No | No | No | No submitted/approved leave available. | Fail |

## Test Flow 6 - Payroll

| Screen Name | Data Entered | Saved Successfully? | Visible After Refresh? | Editable? | Used In Next Workflow? | API/DB Verification | Pass/Fail |
|---|---|---:|---:|---:|---:|---|---|
| Payroll Setup > Legal Entity | Indian Servers Demo Pvt Ltd, Telangana, PAN `AABCI1234F`, TAN `TANA12345B` | Yes | Yes | Not verified | Yes | DB row exists in `payroll_legal_entities`. | Pass |
| Payroll Setup > Pay Group | Monthly Staff, `MONTHLY-STAFF` | Yes | Yes | Not verified | Yes | DB row exists in `payroll_pay_groups`. | Pass |
| Payroll Setup > Salary Components | Basic, HRA, Transport, Special, OT, Bonus, Reimbursement, PF, ESI, PT, Loan EMI, Advance Recovery, LOP | Not completed | No | No | No | Component setup was not completed before payroll run because core org/employee setup failed. | Fail |
| Payroll Setup > Salary Structure | Standard Monthly / Academic / Contract | Not completed | No | No | No | Blocked by missing component/employee chain. | Fail |
| Employee Salary Assignment | Salary assignment for UI-created employees | Not executed | No | No | No | Blocked by employee creation failure. | Fail |
| Run Payroll | June 2026 | No | No | No | No | UI blocked run with readiness checks: 16 critical issues, 10 warnings. | Fail |

## Test Flow 7 - Advanced Payroll

| Screen Name | Data Entered | Saved Successfully? | Visible After Refresh? | Editable? | Used In Next Workflow? | API/DB Verification | Pass/Fail |
|---|---|---:|---:|---:|---:|---|---|
| Bonus | Not completed | No | No | No | No | Payroll run prerequisites failed. | Fail |
| Overtime | Not completed | No | No | No | No | No manual attendance/OT employee chain completed. | Fail |
| Reimbursement | Not completed | No | No | No | No | No employee/payroll chain completed. | Fail |
| Loan | Not completed | No | No | No | No | No employee/payroll chain completed. | Fail |
| Advance | Not completed | No | No | No | No | No employee/payroll chain completed. | Fail |
| Arrears | Not completed | No | No | No | No | No salary revision/payroll chain completed. | Fail |

## Test Flow 8 - Payslip

| Screen Name | Data Entered | Saved Successfully? | Visible After Refresh? | Editable? | Used In Next Workflow? | API/DB Verification | Pass/Fail |
|---|---|---:|---:|---:|---:|---|---|
| Payslip Viewer | June 2026 | No | No | No | No | Employee login showed `No payslips available yet`; payroll run did not complete. | Fail |
| Payslip PDF / Download | Not completed | No | No | No | No | No generated payslip. | Fail |
| Component Lines / YTD | Not completed | No | No | No | No | No generated payslip. | Fail |

## Test Flow 9 - Approval Workflow

| Screen Name | Data Entered | Saved Successfully? | Visible After Refresh? | Editable? | Used In Next Workflow? | API/DB Verification | Pass/Fail |
|---|---|---:|---:|---:|---:|---|---|
| Attendance Lock | June 2026 | Yes | Yes | Yes | Yes | API and DB confirmed lock. | Pass |
| Attendance Unlock | June 2026 | Yes | Yes | Yes | Yes | DB confirmed unlock. | Pass |
| Payroll Approval | June 2026 | No | No | No | No | Payroll run was blocked before approval by readiness checks. | Fail |
| Payroll Lock | June 2026 | No | No | No | No | No completed payroll run available. | Fail |

## Test Flow 10 - Security

| Screen Name | Login / Action | Saved Successfully? | Visible After Refresh? | Editable? | Used In Next Workflow? | API/DB Verification | Pass/Fail |
|---|---|---:|---:|---:|---:|---|---|
| HR Admin | `admin@aihrms.com` | Login success | Yes | Yes | Yes | UI redirected to Admin Console. | Pass |
| Employee ESS | `employee@aihrms.com` | Login success | Yes | Own ESS visible | Yes | UI redirected to ESS. | Pass |
| Employee direct Payroll URL | `/hrms/payroll` as employee | No mutation attempted | Yes | Setup/run controls hidden | Limited | Employee saw only Payslip Viewer and no setup/run controls. | Partial Pass |
| Payroll Processor / Approver | Required roles | Not executed | No | No | No | No provided credentials/path verified during this run. | Fail |
| Unauthorized mutations | Attempt setup/run as employee | Not executed | No | No | No | Setup controls were hidden, but mutation API restriction was not tested. | Partial |

## Test Flow 11 - Reports

| Screen Name | Data Entered | Saved Successfully? | Visible After Refresh? | Editable? | Used In Next Workflow? | API/DB Verification | Pass/Fail |
|---|---|---:|---:|---:|---:|---|---|
| HRMS Reports | Open Reports page | No | No | No | No | Page rendered `Something went wrong`; no report/filter/export could be tested. | Fail |
| Employee Report | Not completed | No | No | No | No | Blocked by Reports page crash. | Fail |
| Attendance Report | Not completed | No | No | No | No | Blocked by Reports page crash. | Fail |
| Leave Report | Not completed | No | No | No | No | Blocked by Reports page crash. | Fail |
| Payroll Report | Not completed | No | No | No | No | Blocked by Reports page crash. | Fail |
| Export | Not completed | No | No | No | No | Blocked by Reports page crash. | Fail |

## Bugs Found

| Priority | Bug | Evidence | Business Impact |
|---|---|---|---|
| Critical | Company listing API fails | Company page and Settings show `Could not load companies`; `GET /api/v1/company/` returns 500 | Customer cannot reliably manage legal entities or proceed with org setup. |
| Critical | Company save/list inconsistency | UI shows `Company details saved`, DB row exists, but record disappears after refresh | Customer believes setup is saved but cannot use it. |
| Critical | Branch creation blocked by empty Company dropdown | Branch form required Company, but dropdown had only `Select` | Branch, department, designation, employee and payroll setup chain is blocked. |
| Critical | Branch validation error crashes UI | 422 response led to React error: object rendered as child in toast | User hits a broken screen during normal setup. |
| Critical | Reports page crashes | `/hrms/reports` shows `Something went wrong` | Reports and exports cannot be certified. |
| High | Company city/state values saved incorrectly | DB row showed city `Telangana`, state empty for company entered as Hyderabad/Telangana | Statutory/payslip/company documents may show wrong address. |
| High | Employee lifecycle cannot complete from requested setup | Required organization data cannot be created/selected | 20-employee onboarding UAT is blocked. |
| High | Leave application as HR Admin fails with `No employee profile` | UI submit returns 400 and no request appears | Admin cannot validate leave workflow from the tested role. |
| High | Payroll run blocked by prerequisites | Run shows 16 critical issues and 10 warnings | Payroll cannot complete until employee/salary/bank/tax/attendance setup is fixed. |
| Medium | Manual employee attendance entry not visible | Attendance screen shows self check-in and calendar only | HR cannot enter Present/Absent/Half-day/Holiday/Weekly off manually from tested screen. |
| Medium | Accessibility issue: labels not bound to inputs | Company forms required positional filling because labels did not resolve | Real users with assistive tech and automated UAT struggle with forms. |

## Final UAT Decision

| Certification Item | Decision |
|---|---|
| Ready for HRMS customer setup | No |
| Ready for organization master setup | No |
| Ready for employee onboarding | No |
| Ready for attendance lock/unlock | Yes |
| Ready for full attendance entry | No |
| Ready for leave workflow | No |
| Ready for payroll setup | Partial |
| Ready for payroll run | No |
| Ready for payslip generation | No |
| Ready for reports/export | No |
| Ready for role/security go-live | Partial |

Final verdict: **Not Ready**.

The first production-blocking fix should be the Company/Organization setup chain. Until a customer can create a company, create branches/departments/designations, refresh, edit, search and reuse those records in Employee creation, all downstream HRMS and Payroll readiness remains blocked.
