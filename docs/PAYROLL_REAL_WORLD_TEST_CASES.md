# Payroll Real-World Test Cases

Validated against the current Payroll implementation on 2026-06-03 by reading the payroll models, API, CRUD calculation engine, and running the payroll-focused automated tests listed at the end.

## Calculation Baseline

Use these formulas unless a case overrides them:

- Monthly prorated pay: `monthly_ctc * employed_calendar_days / period_calendar_days`
- LOP deduction: `prorated_monthly_ctc / working_days * lop_days`
- Gross salary: `basic + hra + other_allowances - lop_deduction + approved overtime + approved encashment + approved taxable earnings`
- Total deductions: `PF employee + ESI employee + PT + LWF employee + salary advance or loan recovery + other approved deductions`
- Net salary: `gross_salary - total_deductions + approved reimbursements`
- Statutory defaults/expected examples: PF 12 percent on capped basic, ESI if gross is under threshold and rule/profile exists, PT/LWF by state slab, TDS by tax worksheet where configured.

## Test Matrix

| ID | Business type | Employee category | Payroll scenario | Inputs required | Expected payroll calculation / output | Edge cases to check | Pass / Fail validation points |
|---|---|---|---|---|---|---|---|
| PR-01 | Engineering college | Full-time teaching faculty | Fixed monthly salary | CTC 12,00,000; basic 40,000; HRA 20,000; 22 working days; full attendance; PF/PT profile | Gross 1,00,000 before statutory deductions; PF/PT deducted as configured; net = gross - deductions | Semester vacation treated as paid; arrears from pay revision | Payslip shows Basic, HRA, Other Allowances, PF/PT, net; payroll can run department-wise for CSE/ECE |
| PR-02 | Engineering college | Lab assistants | Overtime after practical sessions | Monthly CTC 4,80,000; 22 working days; 8 OT hours; OT rate 150; multiplier 1.5 | OT earning 1,800; gross = monthly pay + 1,800 - LOP; net applies statutory deductions | OT above max hours; unapproved OT excluded | Approved OT line becomes paid and appears in payslip; unapproved line is not paid |
| PR-03 | Engineering college | Visiting faculty | Per lecture/hour payout | 24 lectures; rate 1,200; TDS rule if consultant; no monthly salary | Gross 28,800; TDS/contract deduction if applicable; net = gross - TDS | Cancelled lecture; duplicate lecture entry; no bank/PAN | Fails today unless represented through off-cycle/manual earning because payroll engine requires active salary for readiness |
| PR-04 | Engineering college | Administrative staff | Attendance-based salary | CTC 3,60,000; working days 22; payable days 20.5; LOP 1.5 | Monthly 30,000; LOP 2,045.45; gross 27,954.55 before statutory | Half-day; late mark conversion to LOP | Attendance input approved and locked; approval blocked if not locked |
| PR-05 | Engineering college | Hostel wardens | Fixed salary plus hostel allowance | Monthly CTC 45,000; hostel allowance 5,000; full attendance | Gross includes allowance; allowance taxable/exempt per component setup | Allowance only for resident wardens; mid-month assignment | Payslip separates allowance; allowance is not treated as deduction |
| PR-06 | School | Permanent teachers | Annual increment | Old CTC 6,00,000 until 15 Apr; new CTC 6,60,000 from 16 Apr | April salary prorated across both salary segments; arrears if revision entered later | Backdated increment; inactive salary records | Salary revision and arrear lines reconcile to revised effective date |
| PR-07 | School | Temporary/substitute teachers | Paid per day | 12 days; daily rate 1,500 | Gross 18,000; deductions only if applicable | Half day substitute; cancelled day | Missing as first-class wage type; can be modeled with manual/off-cycle earning but readiness needs salary assignment |
| PR-08 | School | Bus drivers | Fixed salary plus trip allowance | Monthly 28,000; 42 trips; trip allowance 80 | Gross 31,360 before statutory | Missed trips; fuel advance offset | Trip allowance must be a component/manual input and must not reduce salary |
| PR-09 | School | Non-teaching staff | Leave deduction | Monthly 24,000; working days 22; paid leave 1; LOP 2 | Paid leave has no deduction; LOP 2,181.82; gross 21,818.18 | Leave spans holiday/weekend; unpaid leave approved late | Payroll attendance input reflects paid_leave_days and lop_days separately |
| PR-10 | School | Exam invigilators | Separate exam duty payment | 6 sessions; rate 700 | Separate earning 4,200, preferably off-cycle or one-time component | Faculty already paid salary; tax treatment | Payment appears as separate component and does not alter base salary |
| PR-11 | SME trading company | Sales staff | Fixed plus commission | Monthly 35,000; sales 8,00,000; commission 2 percent | Commission 16,000; gross 51,000 before deductions | Returned invoices; commission cap | Requires approved incentive/manual component; payslip shows commission clearly |
| PR-12 | SME trading company | Warehouse staff | Overtime | Monthly 26,000; 12 OT hours; rate 100; multiplier 2 | OT 2,400; gross 28,400 before deductions | Weekend OT; holiday OT | OT policy multipliers applied; max hours enforced |
| PR-13 | SME trading company | Accountant | Fixed salary | CTC 7,20,000; full attendance; PT/TDS profile | Gross 60,000; deductions as configured; net correct | PAN missing; bank invalid | Readiness blocks missing salary/bank, warns for missing PAN |
| PR-14 | SME trading company | Part-time employee | Hourly/monthly partial salary | 80 hours; rate 300 | Gross 24,000; deductions per profile | Hours above contract; unpaid holiday | Missing first-class hourly wage support; use manual earning or salary proration workaround |
| PR-15 | SME trading company | New employee | Joining mid-month | DOJ 16 May; monthly CTC 60,000; May has 31 days | Monthly pay prorated 16/31 = 30,967.74 before LOP/statutory | Joining on holiday; no attendance rows | Current engine prorates by calendar employment days |
| PR-16 | SME trading company | Exiting employee | Resigning mid-month | Exit 12 May; monthly CTC 60,000; May has 31 days | Regular salary prorated 12/31 = 23,225.81 plus FnF items | Recovery, leave encashment, notice pay | Current engine handles exit proration; FnF endpoint should validate settlement separately |
| PR-17 | Manufacturing company | Daily wage workers | Daily wage payroll | 24 present days; daily wage 750 | Gross 18,000; ESI/PF if applicable | Absent day; weekly off pay | Missing first-class daily wage salary type; can be approximated with attendance input and manual monthly amount |
| PR-18 | Manufacturing company | Shift workers | Shift allowance | 10 second shifts at 150 | Allowance 1,500 added to gross | Shift change after approval | Needs shift allowance component/manual input; roster itself is not directly converted to pay line by observed engine |
| PR-19 | Manufacturing company | Night shift workers | Night shift payroll | 8 night shifts; allowance 250; normal salary 32,000 | Night allowance 2,000; gross 34,000 before deductions | Night crosses month; public holiday night | Requires approved earning input; no first-class night-shift calculation observed |
| PR-20 | Manufacturing company | Production workers | Production incentive | Base 25,000; 1,200 units; rate 3 per unit | Incentive 3,600; gross 28,600 | Defective units; incentive cap | Requires approved incentive/manual component; reports should show production incentive separately |
| PR-21 | Construction company | Site workers | Project-wise payroll | Worker mapped to Project A; 20 days; daily 900 | Gross 18,000 allocated to project cost center | Worked at two projects; transfer mid-month | Missing first-class project-wise payroll allocation in core run; use department/branch/manual tags if available |
| PR-22 | Construction company | Labour | Biometric/manual attendance | 18 biometric days; 2 manual approved days; daily 850 | Payable 20 days; gross 17,000 | Duplicate punches; manual override after lock | Attendance reconciliation must exclude draft/unapproved inputs and audit overrides |
| PR-23 | Construction company | Site labour | Accommodation and food deduction | Gross 22,000; food 1,500; accommodation 2,000 | Deductions 3,500 plus statutory; net reduced correctly | Deduction cap; free accommodation category | Deduction components appear separately and do not reduce gross |
| PR-24 | IT company | Salaried employees | Remote attendance | CTC 12,00,000; WFH all month; no LOP | Gross 1,00,000; WFH counted as present | Missing remote punch proof; timezone | Current raw attendance treats WFH as present |
| PR-25 | IT company | Employees | Performance bonus | Monthly 90,000; bonus 25,000 | Gross 1,15,000; taxable bonus line; net after deductions/TDS | Bonus paid off-cycle; bonus withheld | Off-cycle/manual earning supported as foundation; must show in reports |
| PR-26 | IT company | Consultant/contract staff | Invoice-based payout | Invoice 1,50,000; TDS 10 percent | Gross 1,50,000; TDS 15,000; net 1,35,000 | GST reimbursement; partial invoice approval | Missing first-class invoice-based contractor payroll; can be off-cycle/manual, not normal run |
| PR-27 | Hospital | Doctors | Fixed plus consultation incentive | Monthly 1,50,000; 120 consults; rate 100 | Incentive 12,000; gross 1,62,000 | Cancelled/refunded consults; department split | Needs approved incentive component and medical department reporting |
| PR-28 | Hospital | Nurses | Shift allowance | Monthly 40,000; 12 night/rotational shifts at 200 | Shift allowance 2,400; gross 42,400 | Shift swap; double shift | Needs shift-derived earning input; attendance lock required |
| PR-29 | Hospital | Medical staff | Emergency duty allowance | 4 emergency duties at 1,000 | Allowance 4,000 added to gross | Emergency on public holiday; multiple approvals | Requires allowance component with approval and audit trail |
| PR-30 | Retail business | Store staff | Weekly off and overtime | Monthly 24,000; working days 26; OT 6 hours at 1.5x | OT added; weekly off treated paid if policy says so | Work on weekly off; holiday shift | Generic OT supported; weekly-off pay policy needs explicit attendance input |
| PR-31 | Retail business | Cashier | Cash shortage deduction | Gross 28,000; shortage 750 approved | Net reduced by 750; deduction line visible | Shortage disputed; cap by policy | Requires approved deduction/manual input; should be locked after approval |
| PR-32 | Restaurant | Waiters | Service charge distribution | Pool 60,000; waiter share 5,500 | Service charge earning 5,500; gross/net updated | Absent employee share; allocation rounding | Missing first-class pool distribution; manual earning can represent result |
| PR-33 | Restaurant | Kitchen staff | Meal deduction | Gross 25,000; meals 22 days at 40 | Deduction 880; net reduced | Free meal day; max deduction | Deduction line appears separately; not subtracted from allowance accidentally |
| PR-34 | Logistics company | Drivers | Trip allowance and fuel advance | Salary 30,000; 12 trips at 500; fuel advance 4,000 | Gross 36,000; advance deduction 4,000; net after statutory | Unsettled fuel bills; trip cancellation | SalaryAdvance is supported; trip allowance needs approved earning input |
| PR-35 | Logistics company | Delivery staff | Per-delivery incentive | Base 18,000; 320 deliveries at 12 | Incentive 3,840; gross 21,840 | Failed delivery; COD shortage | Incentive line separate; shortage as deduction if approved |
| PR-36 | Security agency | Guards | 12-hour shift calculation | 26 shifts; rate 800 per 12-hour shift | Gross 20,800 plus statutory if applicable | 8-hour vs 12-hour site contracts; OT after 12 hours | Missing first-class shift-rate wage basis; manual/attendance input workaround needed |
| PR-37 | Security agency | Guards | Client-location-wise payroll | Same guard works Client A 15 shifts, Client B 10 shifts | Gross split by client cost center; payslip total sum | Client billing dispute; location transfer | Missing first-class client-location payroll allocation in core run |
| PR-38 | Cleaning company | Cleaners | Multiple customer sites | 12 days Site A, 10 days Site B; daily 650 | Gross 14,300 with site split | Two sites same day; travel allowance | Missing first-class multi-site allocation; can only approximate with manual earning lines |
| PR-39 | Real estate company | Agents | Commission-based payroll | No fixed salary; sales commission 1,20,000; TDS if contract | Gross 1,20,000; net after TDS/deductions | Clawback on cancelled deal; split commission | Missing first-class commission-only employee support due readiness active salary expectation |
| PR-40 | Professional services firm | Partners/directors | Salary or fixed remuneration | Monthly remuneration 2,00,000; TDS/PT by category | Gross 2,00,000; director tax treatment applied | Profit share vs salary; no PF | Can be modeled if statutory profile disables PF/ESI; partner distribution needs custom component/reporting |

## Cross-Cutting Validation Checklist

Run each applicable case through these checks:

| Condition | Validation expected |
|---|---|
| Monthly fixed salary | Active salary exists; gross equals monthly/prorated CTC less LOP plus approved earnings |
| Daily wage salary | Dedicated daily wage setup should calculate present days x day rate; current module needs workaround |
| Hourly wage salary | Dedicated hourly setup should calculate approved hours x rate; current module needs workaround |
| Per lecture payment | Lecture count x rate; current module needs workaround/off-cycle earning |
| Overtime calculation | Approved OT line amount = hours x hourly rate x multiplier; unapproved OT excluded |
| Night shift allowance | Approved night shifts generate allowance line; current engine does not auto-create from roster |
| Leave without pay | LOP days reduce gross by per-day salary |
| Paid leave | Paid leave contributes to payable days and does not reduce gross |
| Half-day attendance | Payable days should add 0.5; raw attendance path currently counts `Half-day` as one present day unless reconciled input provides 0.5 |
| Late coming / early leaving | Approved policy should convert to LOP or deduction; no direct payroll conversion observed |
| Week-off and holiday | Should be policy-driven; current run uses Mon-Fri default unless attendance input overrides working days |
| Public holiday pay | Paid holiday should not reduce salary; holiday OT should use holiday multiplier |
| Joining during month | Calendar-day employment proration is applied |
| Exit/final settlement | Calendar-day exit proration plus FnF settlement validation |
| Advance salary / loan deduction | Approved SalaryAdvance recovered in selected payroll month |
| Bonus / incentive / commission | Must appear as approved earning component or off-cycle/manual line |
| Reimbursement | Added after deductions; not part of taxable gross unless configured separately |
| Allowance calculation | Allowance appears as earning and must not be deducted |
| Deduction calculation | Deduction appears separately and reduces net, not gross unless LOP |
| Arrears / backdated revision | Arrear run line should reconcile historical effective dates |
| Branch / department / company processing | Reports and runs should be filterable/scoped; core run is currently month/year-wide in observed engine |
| Approval workflow | Run cannot approve unless attendance inputs are approved and locked unless force approval is audited |
| Payslip generation | Payslip lists component heads and PDF URL after generation |
| Export Excel/PDF | CSV/payroll exports and bank advice PDF/XLSX/CSV should generate for approved/locked/paid runs |
| Bank transfer file | Bank advice validates IFSC/account and total net amount |
| Role-based access control | Employee cannot view another employee payslip; payroll permissions gate run/approve/view |
| Audit log | Lock, unlock, export, forced approval, payslip generation, and bank advice actions are logged |

## Current Module Verdict

Supported well:

- Monthly salary, mid-month joining/exiting, salary revision proration, PF/ESI/PT/LWF deductions, advances, reimbursements, overtime lines, leave encashment, payroll approval/lock states, payslip payload/PDF, bank advice exports, payroll exports, RBAC, audit logs, and readiness checks.

Supported through configuration/workarounds:

- Allowances, bonuses, incentives, commissions, one-time exam duty, cash shortage, food/accommodation deduction, fuel advance, service charge distribution, consultant payout, and partner/director remuneration can be represented with generic salary/manual/off-cycle components, but not all have dedicated workflows.

Missing or weak for "any type of business":

- First-class daily wage, hourly wage, per-lecture, per-delivery, per-trip, per-shift, piece-rate, commission-only, invoice-based consultant, project-wise, client-location-wise, and multi-site payroll workflows.
- Automatic conversion from shift roster/night shift/holiday/week-off/late coming/early leaving into payroll earning or deduction lines.
- Department-wise/branch-wise/company-wise payroll run selection in the core observed `run_payroll` path. It processes month/year employees broadly.
- Pool allocation engines, such as restaurant service charge distribution or real estate split commission/clawback.
- Strong contractor/vendor invoice payroll with GST/TDS section handling.

Likely bugs or risks found by code review:

- Raw attendance counts `Half-day` as one present day in the fallback path. Correct half-day payroll requires an approved `PayrollAttendanceInput` with `payable_days` set to 0.5 increments.
- `total_working_days` is mutated inside the employee loop when an attendance input exists. A custom working-day value for one employee can leak into later employees without attendance input in the same run.
- The default fallback uses Monday-Friday working days, which can be wrong for schools, retail, hospitals, security, restaurants, and manufacturing unless attendance inputs override it.
- Payroll readiness is month/year wide and not obviously scoped by pay group, branch, department, or company in the current CRUD path.
- `force_run` can bypass critical readiness checks. It is audited, but production policy should restrict who can force run and require reason/approver separation.

## Validation Performed

Automated subset executed from `backend`:

```powershell
pytest -q tests/test_payroll_run_state_machine.py tests/test_payroll_inputs_worksheet.py tests/test_payroll_trust.py tests/test_payroll_bank_advice_exports.py
```

Result: `10 passed` in 35.41 seconds. Warnings were deprecation warnings from Pydantic and pytest-asyncio, not payroll assertion failures.

