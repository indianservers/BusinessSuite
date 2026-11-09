# Configurable payroll policies — 9 November 2026

All six remaining requirements are implemented. The user authorized the recommended defaults and configurable alternatives. Configure them under HRMS → Payroll → Payroll Policies, select a pay group, enter a first-of-month effective date and reason, then publish. Select that pay group when running payroll.

## Recommended defaults and alternatives

- POL-01: charge scheduled working days only. Explicit approved unpaid leave on weekly offs and holidays can be charged through independent toggles. The employee calendar and employment dates bound the calculation.
- POL-02: missing attendance blocks approval and locking, including Force Approve. Alternatives are payable (with warning) or LOP. HR can resolve missing attendance through an approved attendance input with a nonempty resolution note; leave conflicts still require resolution.
- POL-03: use assigned salary-structure component proration and LOP metadata. Without a structure, Basic, HRA and Other Allowances prorate and incur LOP; incentives and reimbursements do neither by default. Disable metadata use to apply explicit per-code mappings. Missing/unsupported metadata blocks approval; fixing metadata and regenerating an errored draft is supported.
- POL-04: overlapping paid and unpaid leave for the same half-day blocks approval. Paid-wins and unpaid-wins alternatives are available and emit warnings. Complementary half-days remain distinct; duplicate intervals count once.
- NA-01 (now supported): LOP and joining/exit divisors independently support working days, calendar days, fixed 26 and fixed 30. Calendar-day employment proration is recommended; working-day employment basis is configurable.
- NA-02 (now supported): sandwich charging is disabled by default. When enabled, intervening nonworking dates are charged only between full-day approved unpaid scheduled days. Half-day endpoints do not trigger it. Month/year boundaries and holidays are covered.

## Equations and examples

Employment proration is 1 for full-month employment. For partial employment, factor = min(1, eligible calendar/working days ÷ configured denominator). Assigned component Calendar Days/Working Days metadata selects that component's variable basis; a fixed configured divisor selects the denominator. Components exempt from proration retain their monthly amount.

Working-day LOP reduces an eligible prorated component by its LOP fraction over employed scheduled days. Calendar/fixed LOP uses full monthly component amount × LOP days ÷ selected denominator, capped at the prorated component amount. Each component rounds to two decimals using existing half-even Decimal rounding. A component exempt from LOP receives no reduction. Amounts never become negative.

Example: monthly 30,000 = Basic 12,000 + HRA 6,000 + Other 12,000; one LOP day with fixed 30, HRA exempt → Basic 11,600 + HRA 6,000 + Other 11,600 = gross 29,200. This independent result is asserted in both browser viewports.

Daily, hourly and unit wages retain existing unit-rate formulas. Monthly divisor and extra weekly-off/holiday charging must not invent paid units for these wages. Statutory calculations and rounding retain existing configured behavior.

## Activation, audit and history

Policies are append-only, scoped to the pay group and effective from the first of a month. Publishing requires payroll-run permission; viewing requires payroll-view permission and tenant/branch access. Dates must increase and cannot rewrite already-generated applicable periods. Migration pg_20261109_091_payroll_policies adds policy versions, run snapshots and attendance policy traces. It does not backfill or rewrite historical pay.

Unpublished groups retain legacy behavior. A generated run freezes its policy and valid component treatment. Publishing a future version or regenerating does not replace the frozen version. Reconciliation, LWP feeds and calculation use the shared policy evaluator when a policy is active. Relevant input changes invalidate approval until regeneration; approved manual missing-attendance resolution requires a note. Approval gates cannot be bypassed with Force Approve.

## Verification

See Payroll_Test_Execution_Report.md and Payroll_Test_Cases.csv for final counts and environment results. The 75-case configurable policy suite covers rule combinations and boundaries. Real PostgreSQL desktop/phone workflows additionally verify configuration persistence, audited attendance correction, monetary output, version preservation, approval/locking and historical-edit rejection. Synthetic data runs in disposable local databases; no production policy or provider transfer was changed.
