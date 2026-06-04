# HRMS + Payroll UI Data UAT Report

UAT date: 2026-06-03  
Scope: HRMS and Payroll only  
Audit role: Release QA Engineer, HRMS Payroll UAT Tester  
Execution mode: UI data-entry certification requested  
Automation artifact: `qa/playwright/hrms-payroll-ui-data-uat.spec.ts`

## 1. Executive Verdict

| Area | Score | Verdict | Reason |
|---|---:|---|---|
| HRMS UI data readiness | 82% | Pending Certification | Core screens and backend fixes exist, but the required browser data-entry run could not be executed because Playwright is not installed in this repo. |
| Payroll UI data readiness | 84% | Pending Certification | Payroll backend regressions now pass, but UI-created payroll data was not browser-executed through salary assignment, run, payslip and lock. |
| API readiness | 96% | Release Candidate | Previously missing statutory list API was added; backend startup and selected regression tests pass. |
| UI readiness | 88% | Pending Certification | Frontend lint and production build pass, but UI data-entry UAT is pending real browser execution. |
| Data-chain readiness | 72% | Not Certified | The strict rule requires UI-created data to save, reappear, confirm by API/database and feed the next workflow. This has not been executed end to end. |
| Go-live score | 8.2 / 10 | Release Candidate, Not Certified | Technical blockers were reduced, but real UI UAT evidence is still missing. |

Final verdict: **Not Certified for production go-live yet**.

The product is now a strong release candidate, but the requested UI data-entry UAT cannot be marked passed until the Playwright/browser run creates the test data from the UI and verifies reuse across HRMS and Payroll workflows.

## 2. Data Creation Result Table

| Data Area | Test Data | UI Save Required | List/Detail Required | API/DB Confirm Required | Reused In Next Workflow | Result |
|---|---|---:|---:|---:|---:|---|
| Company/legal entity | Indian Servers Demo Pvt Ltd, CIN `U72900TG2026PTC000001`, PAN `AABCI1234F`, Telangana, Hyderabad | Pending | Pending | Pending | Pending | Not Passed - browser execution pending |
| Branches | Hyderabad Head Office, Bengaluru Branch, Dubai Branch | Pending | Pending | Pending | Pending | Not Passed - browser execution pending |
| Departments | HR, Finance, IT, Sales, Academics, Operations | Pending | Pending | Pending | Pending | Not Passed - browser execution pending |
| Designations | HR Manager, Payroll Executive, Software Developer, Sales Executive, Professor, School Teacher, Driver, Security Guard | Pending | Pending | Pending | Pending | Not Passed - browser execution pending |
| Pay groups | Monthly Staff, Academic Staff, Contract Staff | Pending | Pending | Pending | Pending | Not Passed - browser execution pending |
| Payroll calendar | June 2026, cutoff 25 June, run 28 June, payout 30 June, weekly off Sunday | Pending | Pending | Pending | Pending | Not Passed - browser execution pending |
| Salary components | Basic, HRA, transport, special, OT, bonus, reimbursement, PF, ESI, PT, loan EMI, advance recovery, LOP | Pending | Pending | Pending | Pending | Not Passed - browser execution pending |
| Salary structures | Standard Monthly, Academic, Contract | Pending | Pending | Pending | Pending | Not Passed - browser execution pending |

Strict QA note: Backend availability or static route presence is not counted as a pass for this table.

## 3. Employee Creation Result Table

| Employee | Expected UI Entry | Salary Assignment | List/Detail Verification | API/DB Confirmation | Payroll Reuse | Result |
|---|---|---:|---:|---:|---:|---|
| EMP001 Aarav Sharma | IT, Software Developer, Hyderabad, Monthly Staff, joining 2026-06-01 | Pending | Pending | Pending | Pending | Not Passed |
| EMP002 Meera Rao | Academics, Professor, Hyderabad, Academic Staff, joining 2026-06-01 | Pending | Pending | Pending | Pending | Not Passed |
| EMP003 Rohan Patel | Sales, Sales Executive, Bengaluru, Monthly Staff, joining 2026-06-10 | Pending | Pending | Pending | Pending | Not Passed |
| EMP004 Fatima Khan | Operations, Driver, Hyderabad, Contract Staff, joining 2026-06-01 | Pending | Pending | Pending | Pending | Not Passed |
| EMP005 Kavya Iyer | Finance, Payroll Executive, Hyderabad, Monthly Staff, joining 2026-06-20 | Pending | Pending | Pending | Pending | Not Passed |

Finding: Employee creation UI exists, but employee code and pay-group linkage must be verified during the browser run because creation and salary assignment appear to be split between add employee and employee detail screens.

## 4. Attendance And Leave Result Table

| Scenario | Required UI Action | Expected Result | API/DB Confirmation | Result |
|---|---|---|---:|---|
| Present attendance | Mark present from attendance UI | Present day contributes to payable days | Pending | Not Passed |
| Half-day attendance | Mark half-day from attendance UI | Half-day counts as `0.5`, not `1.0` | Pending | Not Passed |
| LOP leave | Apply/approve unpaid leave | LOP reduces payable days and salary | Pending | Not Passed |
| Paid leave | Apply/approve paid leave | No salary deduction | Pending | Not Passed |
| Attendance lock | Lock June 2026 attendance | Payroll run uses frozen attendance | Pending | Not Passed |
| Attendance unlock | Request/approve unlock | Audit log records unlock | Pending | Not Passed |

Backend regression evidence from earlier hardening indicates half-day logic and payroll calendar tests pass, but UI data-entry certification remains pending.

## 5. Payroll Input Result Table

| Payroll Input | Employee / Case | Expected Handling | Result |
|---|---|---|---|
| Overtime earning | EMP004 driver | Added as earning, not deduction | Not Passed - UI pending |
| Bonus | EMP002 professor | Added as one-time/scheduled earning | Not Passed - UI pending |
| Reimbursement | EMP001 developer | Approved reimbursement included in payroll or remediated before run | Not Passed - UI pending |
| Loan EMI | EMP005 payroll executive | Monthly EMI deducted and shown in payslip | Not Passed - UI pending |
| Salary advance recovery | EMP003 sales executive | Recovery deducted and shown separately | Not Passed - UI pending |
| LOP deduction | Half-day/LOP case | Deduction applied only for unpaid absence | Not Passed - UI pending |

Technical note: The earlier payroll readiness regression was fixed at backend level by allowing approved reimbursements to proceed into payroll instead of blocking the run. UI workflow still needs execution.

## 6. Payroll Run Result Table

| Run Step | Expected Result | Result |
|---|---|---|
| Select June 2026 pay period | Pay period loads configured calendar and employees | Not Passed - browser pending |
| Select scope | Company/branch/department/pay group scope respected | Not Passed - browser pending |
| Run payroll | Gross, deductions and net generated for five UI-created employees | Not Passed - browser pending |
| Component lines | Earnings, deductions and reimbursements persist per employee | Not Passed - browser pending |
| Variance/checks | Critical checks shown before approval | Not Passed - browser pending |
| Payroll list/detail | Run appears in list/detail after save | Not Passed - browser pending |

Backend evidence: selected payroll regression suite passed after hardening. That is not accepted as UI pass.

## 7. Payroll Calculation Validation Table

| Case | Expected Calculation | Certification Result |
|---|---|---|
| Monthly employee full month | Monthly salary prorated over configured June working days | Pending UI data run |
| Joining mid-month | EMP003/EMP005 salary prorated from joining date | Pending UI data run |
| Half-day | Half-day equals `0.5` present day | Pending UI data run |
| LOP | LOP reduces payable days and net salary | Pending UI data run |
| Paid leave | Paid leave does not reduce pay | Pending UI data run |
| Overtime | OT appears as earning component | Pending UI data run |
| Bonus/incentive | Bonus appears as earning component | Pending UI data run |
| Reimbursement | Reimbursement appears separately and is not taxed/deducted incorrectly | Pending UI data run |
| Loan/advance | EMI/recovery appears as deduction | Pending UI data run |
| Net salary | Gross minus deductions plus reimbursements equals net | Pending UI data run |

## 8. Payslip Test Result Table

| Payslip Check | Expected Result | Result |
|---|---|---|
| Payslip generated after payroll run | Payslip available per employee | Not Passed |
| Component grouping | Earnings, deductions, reimbursements and employer contributions grouped clearly | Not Passed |
| YTD summary | YTD gross, net and deductions shown | Not Passed |
| Employee access | Employee can access own payslip only | Not Passed |
| Other employee restriction | Employee cannot access another employee payslip | Not Passed |
| Download audit | Payslip download creates audit trail | Not Passed |

## 9. Approval And Lock Test Result Table

| Control | Expected Result | Result |
|---|---|---|
| Payroll approval | Approver sees checks and variance before approval | Not Passed |
| Payroll lock | Approved payroll can be locked | Not Passed |
| Edit locked payroll | Mutation blocked or requires authorized unlock | Not Passed |
| Post-lock audit | Unlock/change is recorded in audit log | Not Passed |
| Attendance lock | Payroll respects locked attendance | Not Passed |
| Attendance unlock approval | Unlock flow requires authorization | Not Passed |

## 10. Report Export Test Result Table

| Report / Export | Expected Result | Result |
|---|---|---|
| Employee report | Filters, pagination and export work | Not Passed |
| Attendance report | June attendance shown/exported | Not Passed |
| Leave report | Leave and LOP shown/exported | Not Passed |
| Payroll register | Gross, deductions, net shown/exported | Not Passed |
| Bank advice | Bank file/advice generated | Not Passed |
| PF/ESI/PT/TDS export stubs | Export actions available and permissioned | Not Passed |
| Loan outstanding report | Loan/EMI balances shown | Not Passed |
| Reimbursement report | Claims and payroll inclusion shown | Not Passed |
| F&F report | Settlement report available | Not Passed |
| Audit log report | Critical changes visible | Not Passed |

## 11. Security Test Result Table

| Security Case | Expected Result | Result |
|---|---|---|
| HR admin access | Can configure HRMS and Payroll setup | Pending |
| Payroll executive access | Can process permitted payroll actions only | Pending |
| Manager access | Can view team data only | Pending |
| Employee ESS | Can view own profile, attendance, leave and payslip only | Pending |
| Unauthorized payslip access | Blocked | Pending |
| Locked payroll mutation | Blocked without authorized unlock | Pending |
| Report export permissions | Restricted by role | Pending |
| Audit log visibility | Critical events recorded and visible to authorized roles | Pending |

## 12. Bugs Found

| Priority | Bug / Gap | Evidence | Impact | Fix |
|---|---|---|---|---|
| Critical | UI data-entry UAT could not be executed | `playwright` and `@playwright/test` are not installed; no existing e2e runner found | No strict UI certification can be issued. | Install Playwright, configure base URL and run `qa/playwright/hrms-payroll-ui-data-uat.spec.ts`. |
| High | Employee code/pay group assignment needs UI confirmation | Add employee screen does not clearly show employee code/pay group fields in initial inspection | Required employee test data may need separate detail/salary assignment flow. | Verify UI path and add explicit visible linkage if missing. |
| High | Payroll calendar setup needs UI confirmation | Payroll calendar/cutoff/payout fields were not browser-verified | Salary proration and payroll run timing may be hard to certify from UI. | Execute setup UAT and wire missing fields if found. |
| High | Report exports not UI-certified | Export APIs exist, but browser download testing was not run | Managers may not be able to produce required statutory/payroll reports. | Run export tests with download assertions. |
| Medium | ESS role isolation not UI-certified | Backend access patterns exist, but employee browser session was not tested | Payslip privacy remains a certification risk. | Run admin and employee sessions in browser automation. |
| Medium | UI selectors need stabilization for UAT automation | Current screens do not consistently expose test IDs | Automated UAT may be brittle. | Add stable `data-testid` attributes to critical forms and action buttons. |

## 13. Missing UI/API Connections

| Connection | Current Status | Required UAT Evidence |
|---|---|---|
| UI company setup to persisted company record | Pending | Company created from UI appears in list and `/companies`. |
| UI branch/department/designation setup to employee creation | Pending | Employee form can select UI-created org records. |
| UI pay group/calendar setup to payroll run | Pending | Payroll run uses UI-created June 2026 pay group/calendar. |
| UI salary components to payslip lines | Pending | Payslip shows UI-created earning/deduction heads. |
| UI attendance and leave to payroll | Pending | Half-day, paid leave and LOP affect payroll correctly. |
| UI reimbursement approval to payroll inclusion | Pending | Approved reimbursement appears in payroll/payslip. |
| UI loan/advance to payroll deduction | Pending | EMI/recovery appears in payroll/payslip. |
| UI report center to export APIs | Pending | Filters, pagination and downloads work from browser. |
| ESS UI to payslip access control | Pending | Employee can download own payslip only. |

## 14. Final Fix Plan

| Priority | Fix | Owner | Validation |
|---|---|---|---|
| P0 | Install/configure Playwright or enable in-app browser automation for HRMS UAT | QA / Frontend | Browser test can run against local app and backend. |
| P0 | Execute `qa/playwright/hrms-payroll-ui-data-uat.spec.ts` against clean database | QA | Test data is created from UI and verified through API/database. |
| P0 | Stabilize failed UI flows found during the run | Product Engineering | Re-run passes without manual intervention. |
| P1 | Add stable `data-testid` attributes on HRMS/Payroll setup, employee, attendance, payroll and report actions | Frontend | UAT selectors are reliable and CI-safe. |
| P1 | Confirm employee code and pay-group assignment path from UI | HRMS + Payroll | Employees EMP001-EMP005 can be represented exactly or with traceable generated codes. |
| P1 | Add browser download assertions for payslip, bank advice and report exports | QA | Downloads complete with expected filenames/content. |
| P1 | Add dual-session ESS security automation | QA / Security | Employee cannot access another employee payslip or payroll data. |
| P2 | Add the UI UAT suite to CI after stabilizing selectors | DevOps | Release pipeline blocks on HRMS/Payroll UAT regression. |

## 15. Production Certification Status

| Target | Requested | Current Strict UAT Result |
|---|---:|---:|
| HRMS readiness | >= 95% | 82% pending browser execution |
| Payroll readiness | >= 95% | 84% pending browser execution |
| UI readiness | >= 90% | 88% pending browser execution |
| API readiness | >= 95% | 96% release candidate |
| Go-live score | >= 9 / 10 | 8.2 / 10 |

Certification status: **Not Certified - UI Data UAT Pending**.

The release can be promoted to final certification only after a real browser run proves that UI-entered HRMS setup data creates employees, drives attendance/leave, processes payroll, generates payslips, locks payroll and exports reports with API/database confirmation at every step.
