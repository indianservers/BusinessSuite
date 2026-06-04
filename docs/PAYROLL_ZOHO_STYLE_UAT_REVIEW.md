# Payroll UAT Review: Zoho-Style Practical Payroll Features

Scope: Review of the current Payroll module against practical configurable payroll flows similar to Zoho Payroll: employee profile, department/designation, branch/work location, pay schedule, salary structure, earnings, deductions, reimbursements, loans/advances, attendance, LOP, statutory deductions, approvals, lock, payslip, bank advice, reports, and audit logs.

This UAT set intentionally avoids creating unlimited hardcoded payroll options. Bonus, incentive, overtime, allowances, reimbursements, recoveries, and deductions should be handled through salary components, variable earnings, manual payroll inputs, reimbursement records, salary advances, loans, and configurable pay heads.

## UAT Table

| # | Scenario Name | Business Type | Employee Details | Payroll Configuration Required | User Testing Steps | Expected Result | Possible? | Current Gap / Bug / Risk | Suggested Fix |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Monthly salaried employee | SME/IT/School | Full-time employee, branch + department + designation, active salary | Monthly pay schedule, salary structure with Basic/HRA/Allowance, statutory profile | Create salary, lock attendance, run payroll | Gross, deductions, net, components and payslip are correct | Yes | Needs valid salary/bank/readiness setup | Keep readiness checks mandatory |
| 2 | Employee joining mid-month | Any | DOJ 16th of month | Monthly salary, active employee profile | Run payroll for joining month | Salary prorated by employment days; payslip shows prorated salary | Yes | Calendar-day proration may differ from company policy | Add configurable proration rule: calendar/working days |
| 3 | Employee resigning mid-month | Any | Exit date 12th of month | Exit date in employee profile; salary active until exit | Run payroll for exit month | Salary paid only until exit date; employee included in payroll | Yes | FnF items must be processed separately | Link regular exit payroll with FnF workflow |
| 4 | Leave without pay deduction | Any | Employee with approved unpaid leave | Leave/attendance input with LOP days | Reconcile attendance, approve/lock input, run payroll | LOP deduction reduces gross by per-day salary | Yes | Raw leave-to-payroll mapping depends on input reconciliation | Keep payroll input reconciliation auditable |
| 5 | Paid leave without deduction | Any | Employee with approved paid leave | Leave policy and paid leave entry | Run payroll after attendance reconciliation | Paid leave counts as payable day; no LOP deduction | Yes | Incorrect leave type setup can create false LOP | Add leave type validation in pre-run checks |
| 6 | Half-day attendance as 0.5 | Any | Employee with one half-day | Raw attendance status Half-day | Run payroll without manual payroll attendance input | Half-day counts 0.5 present/payable, LOP reflects 0.5 | Yes | Fixed in current engine; regression risk | Keep automated regression test |
| 7 | Overtime earning component | College/Factory/Retail | Employee with approved OT | OT policy/OT pay line mapped to earning component | Approve OT line, run payroll | OT amount appears as earning; net increases | Yes | OT must be approved before run | Add OT policy caps and alerts |
| 8 | One-time bonus | Any | Eligible employee | Bonus as approved manual earning/off-cycle component | Add approved bonus input and run payroll | Bonus appears separately in payslip and reports | Yes | Tax handling depends on component setup | Add taxable/exempt validation per component |
| 9 | Performance incentive | Sales/IT/Hospital | Employee eligible for incentive | Incentive as variable earning/manual payroll input | Add approved incentive, run payroll | Incentive added to gross, not deducted | Yes | No dedicated incentive approval screen in core run | Add variable pay batch upload/review |
| 10 | Salary advance recovery | Any | Employee with approved salary advance | SalaryAdvance with deduction month/year | Run payroll for recovery month | Advance recovered as deduction; status becomes recovered | Yes | Recovery can make net negative | Add negative net warning/approval gate |
| 11 | Employee loan monthly deduction | Any | Employee with loan installment | Loan account/installment or deduction component | Run payroll with due installment | Installment deducted monthly and visible on payslip | Partially | Loan model exists in broader payroll, but regular run mainly recovers advances | Integrate loan installments into run engine |
| 12 | Reimbursement claim | Any | Employee with approved claim | Approved reimbursement in period | Run payroll | Reimbursement added after deductions and shown separately | Yes | Reimbursement cutoff rules need enforcement | Add cutoff validation in readiness |
| 13 | Mobile allowance | IT/SME | Employee eligible for allowance | Mobile allowance earning component | Assign salary/component or manual earning | Allowance appears under earnings; net increases | Yes | Component must be configured correctly | Provide standard allowance templates |
| 14 | Travel allowance | Sales/Logistics | Field employee | Travel allowance earning component | Add allowance and run payroll | Travel allowance appears as earning; not deducted | Yes | Taxability may vary by policy | Add component tax treatment checklist |
| 15 | Housing allowance | School/Hospital/Company | Employee with housing benefit | HRA/housing allowance component | Assign structure and run payroll | Housing allowance included as earning | Yes | Exemption logic may need richer tax rules | Improve HRA exemption calculation workflow |
| 16 | Transport allowance | Retail/School/SME | Employee with transport benefit | Transport allowance component | Add component, run payroll | Transport allowance appears clearly in payslip | Yes | No issue if configured as earning | Add default transport allowance head |
| 17 | Meal deduction | Restaurant/Factory | Employee using meal facility | Meal deduction component/manual deduction | Add approved deduction, run payroll | Net reduced; gross unchanged except LOP rules | Yes | Requires manual/custom deduction setup | Add recurring deduction schedule |
| 18 | Accommodation deduction | Construction/Hospital | Employee with company accommodation | Accommodation deduction component | Add approved deduction, run payroll | Net reduced; payslip shows deduction | Yes | No cap/policy validation | Add deduction cap rules |
| 19 | Department-wise payroll | Any | Employees in multiple departments | Department scope in payroll run | Run payroll for one department | Only scoped department employees included | Yes | Reports/export must consistently use run records | Keep exports tied to run_id records |
| 20 | Branch-wise payroll | Multi-branch business | Employees across branches | Branch scope/pay group branch | Run payroll for selected branch | Only selected branch employees processed | Yes | Requires branch on employee profile | Add pre-run warning for unassigned branch |
| 21 | Pay schedule-wise payroll | Any | Employees under pay group/pay schedule | Pay group/payroll period/pay schedule | Run payroll with pay_group_id | Payroll uses pay schedule and calendar settings | Yes | UI must expose pay schedule selection | Add pay schedule selector in run screen |
| 22 | Employee category-wise payroll | College/Hospital/Factory | Full-time, contract, trainee, visiting | Employee category scope via employment/worker category | Run payroll for selected category | Only matching category employees processed | Yes | Category matching uses existing employee fields | Add canonical employee category field |
| 23 | Payroll approval workflow | Any | Payroll manager and approver | Run status flow: draft to calculated to approved | Run payroll, approve | Approval updates status and approver metadata | Yes | Force approval can bypass blockers | Restrict force approval with maker-checker |
| 24 | Payroll lock after approval | Any | Approved payroll run | Lock action after approval | Approve then lock payroll | Run becomes locked; sensitive changes blocked | Yes | Unlock must be controlled | Keep unlock request approval workflow |
| 25 | Attempt to edit locked payroll | Any | Locked payroll period | Locked payroll exists | Try salary/component/reimbursement mutation | Mutation rejected | Yes | Generic lock protection may be broad | Make lock checks scope-aware where safe |
| 26 | Payslip generation | Any | Employee with payroll record | Payroll run with components | Generate payslip/PDF | Payslip shows earnings, deductions, reimbursements, net | Yes | PDF formatting should be visually tested | Add PDF render QA |
| 27 | Bank advice generation | Any | Employees with valid bank details | Approved/locked/paid payroll; bank format | Generate bank advice | CSV/XLSX/PDF bank advice with totals | Yes | Invalid/duplicate bank accounts must block/warn | Strengthen bank validation before export |
| 28 | Payroll export to Excel/PDF | Any | Payroll run completed | Export configuration | Export pay register/statutory/bank files | Payroll export generated and downloadable | Partially | Core export is CSV; bank advice supports XLSX/PDF | Add pay register XLSX/PDF export |
| 29 | Payroll reports | Any | Payroll runs over periods | Reports module/payroll analytics | View salary register/payroll summary | Reports show gross, deductions, net, trends | Yes | Scope filters must be consistent | Add branch/pay group/category filters everywhere |
| 30 | Audit log for salary change | Any | Salary changed by payroll admin | Sensitive salary audit | Change salary/revision | Audit entry captures actor/action/masked values | Yes | Ensure all salary mutation paths audit | Add audit assertion for every salary endpoint |
| 31 | Backdated salary revision | Any | Employee revision effective previous month | Salary revision request/arrear run | Approve revision, process arrear | Revised salary effective date respected; arrear generated | Partially | Arrear creation exists but automatic delta calculation is limited | Add automatic backdated arrear calculator |
| 32 | Arrears calculation | Any | Employee owed past earning | Arrear run and arrear line | Add/approve arrear, process payroll | Arrear appears as earning line and reportable | Partially | Arrear line exists; integration into current regular run is limited | Attach approved arrears to payroll record during run |
| 33 | Bonus outside regular salary | Any | Employee eligible for off-cycle bonus | Off-cycle run or approved bonus input | Create off-cycle bonus/payment | Bonus processed separately from salary | Yes | Off-cycle payment and payslip/reporting depth may be limited | Expand off-cycle payslip and bank advice |
| 34 | Final settlement | Any | Exiting employee | FnF settlement setup | Create and approve FnF settlement | Notice pay, recovery, leave encashment handled | Yes | Needs end-to-end UI validation | Add full FnF UAT workflow |
| 35 | Leave encashment | Any | Employee encashing leave | Encashment policy/line/request | Approve encashment and run payroll | Encashment appears as earning and request becomes paid | Yes | Tax treatment configurable but needs validation | Add tax treatment tests |
| 36 | Statutory deduction calculation | India payroll | Employee with PF/ESI/PT/LWF profile | Statutory rules and employee profile | Run payroll | PF/ESI/PT/LWF calculated and contribution lines saved | Yes | TDS in regular run appears limited to tax worksheet/export flows | Integrate monthly TDS into run |
| 37 | ESS payslip access | Any | Employee user | Employee login and payroll record | Employee opens own payslip | Employee can see own payslip, not others | Yes | Access must remain role-scoped | Keep RBAC regression tests |
| 38 | Missing attendance warning | Any | Employee without locked attendance period/input | Payroll period not locked | Attempt run without force | Readiness fails or warns on attendance not locked | Yes | Force run bypass is possible | Require reason and approver for force run |
| 39 | Negative net pay warning | Any | High deduction/advance employee | Large deduction exceeding gross | Run payroll | Negative net flagged as anomaly/warning | Yes | Current engine flags negative net but approval gate can improve | Add hard approval blocker for negative net |
| 40 | Large payroll run with multiple employees | Manufacturing/Retail/IT | 500+ employees across branches/departments | Pay groups, attendance, salary structures, bank data | Run payroll, approve, export reports/bank advice | Batch completes with correct totals and scoped reports | Partially | Needs scale/performance UAT and pagination/export validation | Add load tests and async payroll job processing |

## Feature-Wise Pass/Fail Summary

| Feature | Status | Notes |
|---|---|---|
| Employee profile, department, designation, branch | Pass | Employee model supports department, branch, designation, employment/worker categories. |
| Pay schedule/pay group | Pass | Pay groups and periods exist; payroll run can now scope by pay_group_id. |
| Salary structure | Pass | Salary components, structures, templates, assignments and revisions exist. |
| Earnings and allowances | Pass | Fixed components and manual/variable earnings can handle standard allowances, bonus, incentive and OT. |
| Deductions | Pass | Statutory, LOP, advances and manual deductions are supported. Recurring non-loan deductions need polish. |
| Reimbursements | Pass | Approved reimbursements are added after deductions and shown separately. |
| Loans/advances | Partial | Advances are recovered in regular payroll; loan installment integration needs strengthening. |
| Leave and attendance | Pass | Attendance inputs, LOP, paid leave and raw half-day handling are supported. |
| Configurable working days | Pass | Pay group/company/branch-style calendar behavior is now supported; UI should expose it clearly. |
| Payroll run scoping | Pass | Company, branch, department, pay group and employee category scoping supported in run path. |
| Variable earnings | Pass | Standard variable pay should use approved manual inputs/components, not hardcoded pay types. |
| Approvals and lock | Pass | State machine supports approval, lock and paid states. |
| Payslip | Pass | Payslip payload/PDF support exists with component grouping. |
| Bank advice | Pass | Bank advice supports CSV/XLSX/PDF. |
| Payroll exports | Partial | CSV exports exist; pay register PDF/XLSX should be added. |
| Reports | Pass | Payroll reports/analytics exist; all reports should be checked for new scope filters. |
| Audit logs | Pass | Payroll run audit and sensitive salary audit exist. |

## Bugs Found / Known Issues

| Issue | Current Status | Risk |
|---|---|---|
| Half-day attendance counted as 1 day | Fixed | Keep regression coverage so it does not return. |
| total_working_days mutated inside employee loop | Fixed | One employee's custom calendar should no longer affect the next employee. |
| Fixed Monday-Friday fallback | Fixed/Improved | Pay schedule/company/branch working pattern should be configured before payroll. |
| Payroll run scope missing | Fixed/Improved | Run supports company, branch, department, pay group and employee category scope. |
| Variable earnings could drift into hardcoded payroll types | Controlled | Use configurable salary components/manual inputs/off-cycle runs instead of new special payroll engines. |
| Negative net only flagged as anomaly | Open | Should block approval or require special approval. |
| Loan installment integration incomplete | Open | Salary advances work; loan amortization should feed payroll automatically. |
| XLSX/PDF pay-register export missing | Open | Bank advice has XLSX/PDF, but general payroll export is mostly CSV. |

## Zoho-Style Missing Features

- Pay schedule UI that clearly assigns employees to schedules and calendars.
- Standard earning/deduction templates: mobile allowance, travel allowance, meal deduction, accommodation deduction, recurring deductions.
- Variable pay batch workflow for bonus, incentive and overtime with approval before payroll.
- Automatic backdated salary revision arrears.
- Loan installment schedule linked directly to monthly payroll.
- Negative net pay approval blocker.
- Pay register export in XLSX/PDF, not only CSV.
- Stronger report filters for branch, department, pay group, employee category and work location.
- Payroll pre-run dashboard that clearly shows missing attendance, missing bank, invalid statutory profile, missing salary and negative net risks.
- End-to-end UI UAT for payslip PDF formatting and employee self-service access.

## Priority Development Fixes

| Priority | Fix | Reason |
|---|---|---|
| P0 | Add negative net pay approval blocker | Prevents accidental invalid payroll payouts. |
| P0 | Integrate loan installments into regular payroll | Zoho-style payroll expects loans to recover automatically each month. |
| P1 | Add UI for pay schedule calendar patterns | The engine supports it; users need safe configuration. |
| P1 | Add variable pay batch workflow | Bonus, incentive and OT should be uploaded/reviewed/approved cleanly. |
| P1 | Add automatic arrear calculation for backdated salary revisions | Reduces manual payroll errors. |
| P1 | Add XLSX/PDF pay-register exports | Common payroll operations need non-CSV exports. |
| P2 | Add standard earning/deduction templates | Reduces setup mistakes for allowances and recoveries. |
| P2 | Extend payroll report filters to every report | Ensures scoped payroll is visible and auditable. |
| P2 | Add full large-payroll performance/load UAT | Confirms reliability for 500+ employee runs. |

