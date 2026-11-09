# Payroll defects and fixes

## PAY-VAL-01 â€” High â€” negative salary values accepted

Root cause: EmployeeSalaryCreate used unconstrained Decimal fields. Negative CTC, basic, HRA, wage rate, default units, commission rate/base and invoice amount passed validation and could feed payroll calculations.

Reproduce: construct EmployeeSalaryCreate(employee_id=1, ctc=-0.01, effective_from='2026-05-01'), or POST that payload to /api/v1/payroll/salary with payroll permissions. Before: accepted by schema. After: validation error / HTTP 422 before mutation. All eight negative-field cases have regressions; five real API cases additionally verify no salary insert.

Fix: nonnegative Field constraints at the existing schema boundary. No records or APIs removed.

## PAY-VAL-02 â€” High â€” invalid attendance totals accepted

Root cause: PayrollAttendanceInputCreate did not constrain negative days/hours or bound payable/present/LOP days by working days. Negative LOP can increase pay when consumed by the engine.

Reproduce: validate period_id=1, employee_id=1, working_days=21, lop_days=-0.5; separately set payable_days=21.5. Before: accepted. After: rejected. Regression coverage includes all nine negative-unit fields and three above-denominator fields.

Fix: nonnegative constraints and shared model validation for the three day bounds. Legitimate zero/fractional nonnegative values remain supported; no unsupported half-day-only policy was imposed.

## PAY-VAL-03 â€” Medium â€” reversed salary dates accepted

Root cause: no relationship check between salary start and effective_to.

Reproduce: EmployeeSalaryCreate(employee_id=1, ctc=360000, effective_from='2026-05-15', effective_to='2026-05-01'). Before: accepted and could create an empty interval. After: rejected by range validation, using effective_date when provided.

Fix: model validator. Existing historical records were not rewritten.

## PAY-COUNT-04 â€” Medium â€” payroll summary showed zero employees

Browser evidence: a run with one calculated payroll record and gross 30,000 showed Employees 0. Root cause: the frontend reads total_employees, but PayrollRunSchema omitted it and the model had no calculated count.

Fix: expose the number of calculated records through a read-only model property and the existing response schema. No new column or data migration. The LOP matrix checks serialization returns one employee; the real browser test checks API count equals the records endpoint. The updated screenshot verifies the summary. Counts use the existing records relationship and may load that collection when serializing a run.

## PAY-PG-05 â€” High â€” concurrent generation created duplicate runs

Two simultaneous PostgreSQL connections produced two run IDs; four produced four IDs for the same period and scope. Root cause: lookup-then-insert had no protection when the row did not yet exist. A row lock alone cannot protect a missing row.

Fix: acquire a deterministic PostgreSQL transaction advisory lock for the established month/year/organization/branch/department/group/category identity before lookup, then lock existing runs. The lock releases on commit/rollback. Approval/locking refreshes and locks the run row. Regression tests verify two/four distinct PostgreSQL backend PIDs yield one run and one employee record, and a waiting generation observes a concurrently locked status and refuses recalculation. No unique-index migration or historical deduplication was applied.

## PAY-RECALC-06 â€” High â€” one-time inputs disappeared during recalculation

Reproduce: approve a 1,250 reimbursement/advance/overtime/encashment item, generate, then generate again before approval. A reimbursement net of 49,450 became 48,200; an advance recovery disappeared from deductions; overtime and encashment gross dropped from 51,250 to 50,000.

Root cause: generation consumed items by marking Paid/Recovered and linking the old record; reruns selected only Approved and unlinked items before replacing that record. Fix: include previously consumed items linked to the same employee/run, relink them to the replacement record, and continue excluding other runs' items. Four PostgreSQL regressions compare exact first/repeated gross, deductions, net, record identity and source linkage.

## PAY-LEAVE-07 â€” High â€” duplicate/deleted leave and absence could double LOP

Reproduce: two approved full-day unpaid requests on one date produced two LOP days; repeated first-half requests produced one instead of 0.5; soft-deleted approvals still contributed. The LWP feed separately summed unpaid leave and absent attendance on the same date.

Fix: shared date/half-day interval union for both reconciliation and LWP feed; exclude soft-deleted leave and subtract approved leave coverage from absent attendance. Distinct first/second halves combine to one day. LOP is capped at the payroll day denominator, so full-month unpaid leave cannot produce more LOP than working days; negative correction adjustments are clamped at zero. Regression cases cover duplicates, full-plus-half overlap, deleted full/half leave, and paid/unpaid full/half leave with absent attendance. Conflicting paid and unpaid approvals for the same interval remain a policy question.

## PAY-LOCK-08 â€” High â€” finalized payroll inputs could still be changed

An Open input period allowed reconciliation/upsert after its payroll run was locked. Manual input review and LWP sync lacked the same run-lock guard. Fix: reuse the existing scoped locked-period check before these mutations. Tests reject reconciliation and pending-input approval after locking; browser tests verify HTTP 400 for input editing/review, then verify the authorized unlock/correction workflow and retained calculation snapshots.

## PAY-LEAVE-09 â€” Medium â€” leave could violate employment and half-day configuration

Requests before joining/after exit and multi-date half-day requests passed the service. The half_day_allowed configuration was not enforced there. Fix: validate employment bounds and configured half-day eligibility in the existing leave service before overlap/balance mutation. Four regression cases exercise these boundaries; existing leave workflow/accrual tests were rerun.

## PAY-PRORATE-10 â€” High â€” salary revision was weighted outside employment

Root cause: salary versions were averaged over the entire payroll period, then multiplied by the employment fraction. For a mid-month joiner whose applicable revision starts on joining, that included a pre-employment salary; a new salary effective on joining could also be prorated twice.

Fix: average salary versions over the employment intersection first, then apply full-period employment proration once. Eight controlled combinations span 28/29/30/31-day months, join/exit boundaries, a 0.5-day LOP, 1,000 bonus and 250 recovery. The independent oracle verifies gross; repeated generation retains the same scoped run. Browser workflows additionally verify a mid-month revision, correction and consistent payslip.

## PAY-LWP-11 â€” High â€” cancelling leave left a stale synced deduction

Root cause: the feed omitted zero-day employees, so sync never revisited an earlier nonzero entry after leave cancellation. Fix: sync includes zero rows internally, updates existing tracked entries/inputs to zero, and leaves unrelated employees without tracked entries untouched. Public preview still excludes zero rows. The regression syncs one unpaid day, cancels it, syncs again and verifies zero LOP.

## PAY-UI-12 — Medium — selected payroll totals stayed stale after recalculation

Browser screenshot review showed the selected run still displaying net 27,810.95 after an authorized correction changed the backend net to 29,801.13. The run list refreshed, but selectedRun and cached records/variance/readiness did not. The old locked action state could remain visible too.

Fix: replace the selected run with the generation response when IDs match and invalidate its records, variance and readiness queries. The browser combination asserts the displayed selected-run total equals the regenerated API total after unlock/correction. TypeScript checking and desktop/phone browser retests cover the change.

## PAY-HIST-13 — High — future pay mode/rate changed historical payroll

An employee changing from monthly to hourly pay in June received hourly pay when May was generated. Daily/hourly historical employees switching to monthly pay showed the reverse problem. Three controlled regressions initially failed.

Root cause: generation selected the latest active salary to choose pay mode and rate, even though CTC averaging used historical versions. Fix: choose the salary whose effective interval overlaps the requested period, including inactive historical versions, and apply that range to salary readiness. Future revisions no longer decide a prior period's wage mode/rate. Three independently expected gross amounts (30,000 monthly, 21,000 daily, 1,000 hourly) are verified, along with related readiness/engine/currency regressions.

## Open policy findings and test limits

The four previously blocked cases and two unsupported options are now resolved; see the configurable policy completion below and the updated CSV/report. PostgreSQL concurrency, locking, rollback, final settlement and browser correction workflows have now been tested locally. Production providers, live payment/filing and legal statutory certification remain outside this safe local run.

Initial failures attributable to test fixtures: incomplete company setup in the browser fixture; an unflushed controlled salary caused ensure_payroll_ready to add a second salary; a half-up statutory oracle conflicted with actual half-even code. These were corrected in tests and are not application defect counts. Existing payslip browser tests were updated to expand mobile history/grouped rows before interacting.

The final execution report and JUnit evidence give the definitive retest counts. All test data is synthetic and isolated; no employee salary/history migration was performed.

PostgreSQL fixture repairs: use real seeded actor IDs instead of assuming ID 1; assign the audit fixture's actual person/tenant identity; isolate committed concurrency fixtures in their own cluster; preserve explicit company/branch run scope when a fixture helper later attaches branch ownership. These repairs are not counted as product defects. Earlier failed runs are preserved as evidence, with later outcomes superseding them.


## Configurable policy completion

POL-01..04 and NA-01..02 are resolved through effective-dated pay-group configuration. See Payroll_Policy_Implementation.md. Added shared day evaluation for payroll/reconciliation/LWP, component-level proration/LOP, fixed 26/30 divisors, optional sandwich charging, manual-resolution audit notes, hard approval gates and stale-calculation detection. Run policy/component snapshots preserve history; additive migration pg_20261109_091_payroll_policies supplies storage. Basic/HRA statutory summaries recognize component codes and names; monthly nonworking-day charging cannot create daily/hourly wage units. All targeted policy assertions and real browser earnings comparisons are included in final evidence.

QA harness fixes: random server ports and per-run Vite cache avoid collisions; Windows selector event loop avoids local Proactor accept resets. Browser component assertions use the actual earnings payload. Existing unrelated workspace edits were preserved.
