# Payroll local execution report — configurable policies, 9 November 2026

400 distinct automated cases across all phases; 6 grouped policy requirements tracked separately. Final register: 406 PASS, 0 FAIL, 0 BLOCKED, 0 NOT APPLICABLE. Repeated runs and grouped requirements are not additional automated executions.

PostgreSQL 17.11: 382 distinct backend cases and 6 real-API desktop/phone browser workflows. SQLite regression coverage: 325 distinct cases. Environment-specific outcomes and exact test sources are retained in Payroll_Test_Cases.csv. Earlier phase evidence remains available.

All four blocked cases and both previously unsupported options are implemented as effective-dated pay-group policies. See Payroll_Policy_Implementation.md for recommendations, formulas, configuration and history protection. The additive migration creates payroll_policy_versions and policy snapshots/traces. Existing unpublished pay groups keep legacy behavior; publishing a policy activates these rules for eligible future periods. No historical payroll is rewritten.

The policy matrix covers holidays/weekends/sandwich boundaries, full/half-day conflicts, missing attendance and approval gates, 28/29/30/31-day months, fixed 26/30 divisors, joining/exit proration, component metadata/overrides, one-time earnings, daily/hourly safeguards, tenant boundaries, stale-input detection and frozen historical policy versions. Existing calculation, concurrency, leave, final-settlement and payslip regressions remain covered.

Browser workflows publish policies, reload controls, generate payroll, verify missing-attendance rejection even with force approval, resolve attendance with audited notes, compare independent amounts (30,000 monthly, fixed-30 LOP, HRA exempt: gross 29,200), publish a future version, regenerate with the frozen earlier policy, approve/lock and reject historical policy edits. Desktop and phone evidence includes screenshots, calculation JSON and traces. Frontend TypeScript checks passed.

The first new browser attempt asserted fields absent from the payslip API payload; the test now reads actual earnings components. A Windows Proactor accept-loop failure was isolated to the local QA server; the harness uses the selector loop and random server ports/cache directories. HTTP failures remain asserted. Product fixes and policy safeguards are documented in Payroll_Bugs_and_Fixes.md.

Isolation: every PostgreSQL runner migrates a fresh random-port loopback cluster and synthetic bs_payroll_*_test database and stops it in finally. Existing databases and .env files are not used. No real payment, external employee message or statutory filing was executed. This verifies configured behavior, not legal statutory certification.

Rerun from the repository root:

```powershell
& ./backend/scripts/run_payroll_policies_qa.ps1
```

Evidence is retained under evidence/. Latest passing results supersede earlier attempts; numeric actuals are only reported where asserted. No failing executed cases remain.
