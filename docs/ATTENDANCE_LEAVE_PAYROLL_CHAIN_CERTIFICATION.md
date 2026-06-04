# Attendance, Leave and Payroll Chain Certification

Certification date: 2026-06-03  
Role used: HR Executive and Payroll Officer  
Scope: Employee -> Attendance -> Leave -> Payroll Inputs -> Payroll Run -> Approval -> Lock -> Payslip -> Reports  
Master data: Company, Branch, Department, Designation and Employee creation were not retested. The certification used the 20 previously certified employees EMP00010 to EMP00029.

## 1. Executive Result

| Area | Result | Certification Finding |
|---|---|---|
| Attendance | FAIL | Attendance APIs, database persistence and attendance lock work, but HR manual attendance entry for the 20 employees could not be completed from the UI as a customer workflow. |
| Leave | FAIL | Leave types and balances can be prepared, but the certified employees do not have linked ESS user accounts, so leave application and approval could not be completed for them through the customer UI/API flow. |
| Payroll | PASS | Salary assignments, payroll inputs, payroll run, worksheet, approval and lock completed for all 20 employees after fixing the component type schema issue. |
| Payslip | FAIL | Payslip API and protected PDF generation work, but the Payroll UI payslip viewer did not show the generated payslip and ESS own-payslip access could not be completed for the certified employees. |
| Reports | PASS | Report APIs and the Reports UI rendered after fixing the KPI rendering crash. Payroll exports, bank advice and statutory export stubs were generated. |
| Overall Payroll Chain | FAIL | The backend payroll chain is operational, but the real customer chain is not fully certified because Attendance UI entry, Leave ESS flow and Payslip UI/ESS flow remain broken or incomplete. |

Final status: **Overall Payroll Chain FAIL**.

## 2. Fixes Applied During Certification

| Issue | Root Cause | Fix Applied | Retest Result |
|---|---|---|---|
| Payroll run failed with 500 during component persistence | `payroll_components.component_type` was too short for `Employer Contribution`. | Widened `PayrollComponent.component_type` from `String(20)` to `String(50)` and added Alembic migration `20260603_006_widen_payroll_component_type.py`. | Payroll run, worksheet, approval, lock and component lines completed. |
| Reports page crashed with error boundary | KPI component attempted to render object values directly in React. | Hardened the Reports KPI renderer to display strings, numbers, array counts or JSON fallback values. | `/hrms/reports` rendered after refresh with Attendance Trend, Leave Trend and Payroll Summary visible. |

## 3. Certified Test Data

| Data Area | Values Used |
|---|---|
| Employees | EMP00010 to EMP00029, employee IDs 10 to 29 |
| Branch | Certified branch ID 3 |
| Department | Certified department ID 2 |
| Designation | Certified designation ID 2 |
| Payroll Period | June 2026 |
| Payroll Run | Run ID 6 |
| Pay Group | Recovery Payroll Group, ID 2 |
| Bank | HDFC Bank |

## 4. Workflow Certification Table

| Workflow Step | UI Save | Refresh Verification | API Verification | Database Verification | Used in Next Workflow | Result |
|---|---|---|---|---|---|---|
| Attendance Entry - Present, Absent, Half Day, Holiday, Weekly Off, Overtime | FAIL - HR manual entry for the 20 employees was not available as a complete UI save flow. | Partial - Attendance page refreshed and showed Attendance Lock / Locked state, but did not show HR-entered employee attendance grid for the 20 employees. | PASS - attendance punches/compute APIs created Present, Absent, Half-day, Holiday, Weekly Off and OT outcomes. | PASS - attendance rows persisted for employees 10 to 15 with expected statuses and hours. | PASS - attendance data was reconciled into payroll attendance inputs. | FAIL |
| Attendance Lock | PASS - Attendance UI showed lock state. | PASS - refreshed page retained Locked state. | PASS - `POST /attendance/locks` returned 201. | PASS - `attendance_month_locks` has June 2026 status Locked. | PASS - payroll was processed against the locked month. | PASS |
| Leave Application - Paid, Sick, LOP | FAIL - certified employees could not apply leave through ESS because they do not have linked user accounts. | FAIL - no UI-created leave applications for the certified employees were available after refresh. | FAIL - `POST /leave/apply` as admin returned `400 No employee profile`. | FAIL - no customer-flow leave requests for the certified employees were inserted. | FAIL - leave approval and payroll leave feed could not use UI-created leave records. | FAIL |
| Leave Approval | FAIL - blocked by missing employee leave applications. | FAIL | FAIL | FAIL | FAIL | FAIL |
| Payroll Inputs - Bonus, Reimbursement, Loan EMI, Salary Advance, Incentive | Partial - Payroll UI has payroll action areas, but input entry was completed through API because the certification-critical UI input path was not fully usable. | PASS - payroll run remained visible after refresh. | PASS - manual inputs were created and approved; employee loan was created. | PASS - approved manual inputs and active loan persisted. | PASS - inputs were included in worksheet/run calculations. | PASS |
| Payroll Run | PASS - Payroll UI showed June 2026 run after refresh in the Run Payroll area. | PASS - run remained visible and locked after page refresh. | PASS - `POST /payroll/run` returned 201 after schema fix. | PASS - payroll run ID 6 persisted for 20 employees. | PASS - worksheet, approval, lock, payslip and reports used the run. | PASS |
| Payroll Calculation Validation | PASS - totals were visible through payroll run context. | PASS | PASS - payroll records endpoint returned 20 records. | PASS - gross 1,001,200.00, deductions 36,000.00, net 965,200.00; component lines persisted. | PASS | PASS |
| Payroll Approval | Partial - completed through API; UI showed locked run afterward. | PASS | PASS - approval endpoint returned 200 with approved status. | PASS - run moved to approved before lock. | PASS | PASS |
| Payroll Lock | PASS - Payroll UI displayed Locked for June 2026. | PASS | PASS - lock endpoint returned 200. | PASS - run ID 6 status Locked with `locked_at` set. | PASS - payslip and reports used locked payroll data. | PASS |
| Payslip Generation and Download | FAIL - Payroll UI payslip viewer showed no payslip available for June 2026 even though API generated one. | FAIL - refreshed UI still did not show the generated payslip. | PASS - payslip endpoint returned 200 and protected PDF generation returned 200. | PASS - payslip PDF URL persisted for employee ID 10. | Partial - reports and exports used payroll records, but ESS payslip flow failed. | FAIL |
| ESS Payslip Access | FAIL - no linked ESS login exists for the 20 certified employees. | FAIL | Partial - unrelated employee login was correctly denied access to employee 10 payslip with 403. | PASS for access denial evidence; own access not testable. | FAIL | FAIL |
| Reports | PASS - Reports UI rendered after fix and refresh. | PASS | PASS - attendance, leave, payroll summary, employee, salary register and audit report APIs responded; salary register required month/year filters. | PASS - report source data exists in payroll, attendance, export and audit tables. | PASS | PASS |
| Bank Advice | PASS through payroll export action path. | PASS | PASS - bank advice preview returned 200 and generation returned 201. | PASS - bank export batch persisted for 20 employees totaling 965,200.00. | PASS | PASS |
| Statutory Reports | PASS through export APIs. | PASS | PASS - PF, ESI, PT and TDS export stubs returned 201; file validation returned 201. | PASS - statutory export batches persisted as Generated. | PASS | PASS |

## 5. API and Database Evidence

| Area | Evidence |
|---|---|
| Attendance statuses | Employee 10 Present 8.00 hours; employee 11 Absent; employee 12 Half-day 3.00 hours; employee 13 Present 10.00 hours with 2.00 OT hours; employee 14 Holiday; employee 15 Weekly Off. |
| Attendance lock | June 2026 lock row exists with status Locked and reason `Certification payroll input freeze`. |
| Salary assignment | 20 active salary assignments exist for employees 10 to 29. |
| Payroll run | Payroll run ID 6 exists with status Locked. |
| Payroll totals | Gross 1,001,200.00; deductions 36,000.00; net 965,200.00. |
| Component lines | Earnings: 61 lines totaling 1,001,200.00; Deductions: 20 lines totaling 36,000.00; Employer Contributions: 20 lines totaling 36,000.00. |
| Payroll inputs | Bonus 5,000.00, Performance Incentive 3,000.00, Salary Advance Recovery 1,000.00 and Travel Reimbursement 2,200.00 persisted as Approved. |
| Loan | Employee 15 loan persisted as Active with 12,000.00 payable and 1,000.00 EMI. |
| Payslip | Employee 10 protected PDF generated at `/uploads/payslips/2026/6/payslip_10_2026_6_protected.pdf`. |
| Bank advice | HDFC Bank advice export generated for 20 employees totaling 965,200.00. |
| Statutory exports | Bank advice, pay register, PF ECR, ESI, PT and TDS 24Q export batches persisted as Generated. |

## 6. Root Cause Findings

| Gap | Root Cause | Impact | Required Fix |
|---|---|---|---|
| HR attendance entry cannot be certified from UI | Attendance UI exposes lock/self-service style views, but not a complete HR manual attendance grid for selecting certified employees, dates, status and OT in one customer workflow. | Attendance data can be created by API, but real HR user entry is not certified. | Wire an HR attendance entry screen to existing attendance punch/compute APIs with employee search, status, hours, OT and refreshable grid. |
| Leave application fails for certified employees | The leave application endpoint depends on the logged-in user's employee profile; the 20 certified employees do not have linked user accounts. | Paid leave, sick leave, LOP and approval cannot be certified for those employees through ESS. | Link employees to user accounts or provide HR-on-behalf leave creation with approval audit. |
| Payslip UI does not show generated payroll payslip | Payslip API and PDF generation work, but the Payroll UI viewer is not resolving the generated employee/run payslip for the admin context. | Users cannot rely on the UI to download generated payslips even though backend data exists. | Connect payslip viewer to locked run records and employee selector; show generated PDF status and download action. |
| ESS own-payslip access cannot be certified | Certified employees lack ESS logins. | Security denial for another employee passes, but own access remains unverified. | Create ESS accounts for certified employees and bind user ID to employee ID. |
| Reports UI had runtime crash | KPI displayed object values directly. | Reports page entered error boundary. | Fixed. Keep regression coverage for report value shapes. |
| Payroll component persistence failed before fix | Component type column was too narrow for employer contribution labels. | Payroll run crashed with 500. | Fixed by widening column and applying migration. |

## 7. Retest Commands

| Check | Result |
|---|---|
| `alembic upgrade head` | PASS |
| `pytest -q backend/tests/test_payroll_components.py backend/tests/test_payroll_inputs_worksheet.py backend/tests/test_payroll_payments_accounting.py` | PASS - 4 passed |
| `npm run lint` | PASS |
| `npm run build` | PASS |

## 8. Final Certification

| Module | Final Result |
|---|---|
| Attendance | FAIL |
| Leave | FAIL |
| Payroll | PASS |
| Payslip | FAIL |
| Reports | PASS |
| Overall Payroll Chain | FAIL |

Certification verdict: **Not production certified as a complete real-user payroll chain**.

The backend payroll engine is now operational for the 20 certified employees, but the customer-facing workflow still fails strict certification because HR attendance entry, leave application/approval for the certified employees and payslip UI/ESS access are not fully connected end to end.
