# CRM and PMS functionality acceptance — 8 November 2026

Implemented in order: advanced project scheduling, PMS automation, then CRM/PMS reporting. Existing manual date editing, task completion/approval rules, automation triggers, report directories and business records remain in place. No deployment, schema migration, provider connection or production data mutation was performed.

## Where to use the changes

- **PMS → Project timeline / Gantt:** select a project, then use **Advanced scheduling** below the manual timeline. Project links carrying `project` or `projectId` now initialize the project filter.
- **PMS → Task automation:** choose **Set due date** as an action. **Recent executions** now supports outcome, rule and UTC date filters, older pages and action details.
- **CRM → Reports and insights:** **Build a deal report** appears alongside the existing report directory. Choose detail columns or currency-separated grouping, save/run, reopen, update, export or delete a private definition.
- **PMS → Advanced scheduling → Baselines and schedule variance:** capture named baselines and compare/export dates using CSV or Excel.

## Advanced scheduling

The planner supports finish-to-start, start-to-start, finish-to-finish and start-to-finish dependencies, positive/negative working-day lag, critical tasks and slack. Zero-lag finish-to-start starts on the next project working day. A project calendar specifies working weekdays and explicit holiday dates.

The calculated plan respects existing start dates as lower bounds. It pushes constrained successors later; it does not automatically pull their commitments earlier. Task durations are scheduled spans in project working days, not estimates of effort or available staffing.

Users can move one task and preview the full project impact before applying. Apply recomputes the plan under the project mutation lock, rechecks project/actor access, rejects stale revisions and changes all affected dates in one transaction. A changed task roster, dates, status, dependency, project scope or calendar invalidates an earlier preview. Completed/cancelled tasks cannot be moved automatically. Archived projects cannot receive scheduling writes.

Named baseline snapshots retain captured task dates rather than replacing prior versions. Baseline variance is **current due date minus captured due date in calendar days**: positive means later. New/undated tasks have no numeric variance. Removed baseline-task counts are explicit. Exports identify the selected baseline and capture timestamp.

Current bounds:

- 1,000 tasks per project and a 20-year planning horizon; input/result dates from 1900 through 2200.
- 20 retained baselines per project/workspace scope.
- All tasks must have both dates before a complete dependency plan can apply. Existing manual scheduling remains available to date incomplete tasks.
- This is project-calendar planning. It does not implement skill/resource leveling, HR leave-aware scheduling, cost/effort baselines or historical financial forecasting.
- PostgreSQL concurrency and authenticated deployed acceptance for these new operations have not been run in this batch.

## Automation

The existing rule engine now supports an **absolute due date** alongside priority and assignment actions. It uses the same event and clock paths. A due date before the task start, or an attempt to reschedule terminal work, produces a skipped action with a reason instead of an invalid mutation. It does not write task status or bypass transition approvals.

Execution reporting includes before/after values, skip reasons, rule IDs, outcome/date filters and cursor pagination. Filters use UTC dates; timestamps retain their UTC offset for local display. Totals count recorded actions matching the filters, not every trigger evaluation. Unchanged no-op evaluations are intentionally not execution records. Existing clock receipts, current-access checks and paused duplication are retained.

This action sets a fixed date; it is not a rolling date shift or automatic dependency cascade. External actions, generalized retry/dead-letter queues, quotas and usage billing remain separate work.

## Reporting

Private CRM definitions reuse `AnalyticsReport` storage and the shared analytics query engine. New domain-owned definitions are hidden from generic analytics routes/catalogs; their CRM endpoints enforce owner and company scope. Report execution reuses current CRM record visibility. A read-only deal user was checked against another rep's records.

The builder supports selected detail columns, exact status/currency/owner filters, and grouping by status, owner or stage. Monetary summaries always include currency as a grouping dimension. Missing/invalid currency labels prevent monetary aggregation rather than producing a mixed/unknown-currency total. No currency conversion is applied.

Definitions have optimistic revisions. Conflicts retain the local draft and offer loading the latest definition, restoring the previous draft, or saving a separate copy. Deleting a definition preserves deal records, and its draft can be restored as a new definition. Current export capabilities remain authoritative. Export requests can bind to a definition revision so a concurrent definition edit cannot silently change the exported report.

CSV/Excel exports cover the complete filtered output, up to 5,000 rows/groups. Larger synchronous exports fail with a narrowing instruction rather than silently truncating. CSV formula-like strings are escaped; Excel string values remain text. The shared workbook writer retains its existing default worksheet name and accepts descriptive names for the new exports.

The current builder covers private deal reports, with up to 100 saved definitions per owner. It does not yet implement other CRM entity sources, shared definitions, date-range/compound filters, scheduled delivery or historical result snapshots. Current live records are queried again on every run/export.

## Verification

### Final focused run

**21 passed, no skipped cases**, comprising 19 new-scope cases and two adjacent existing export-format checks. This includes three disposable real-browser workflows. The runner uses a cloned SQLite fixture database with independent request sessions and a loopback API/Vite server; it does not use a developer or production database. Each preview is smoke-checked with agent-browser before Playwright interaction tests.

- Scheduling: capture baseline → calendar/holiday change → preview → atomic apply → reload → verify persisted variance → reject stale baseline capture → retain draft → reload/retry → retain both baselines. Desktop/mobile layout and critical-path/slack calculations are checked.
- Automation: create a due-date rule in the UI → create real tasks → verify successful/invalid-date outcomes → filter history → edit → duplicate paused → pause → verify subsequent task dates remain unchanged. A separate clock test verifies replay protection; terminal work is not rescheduled.
- CRM reports: save/run → verify separate INR/USD groups → download CSV/Excel → reload/reopen → filter/update → reject stale export/save → retain/recover draft → save a copy → delete/restore a private definition without touching deals. Unauthorized owner access and read-only record visibility are checked.
- Export structure: worksheet XML, descriptive tab names, numeric variance, text-only formula-like values, real XLSX ZIP structure and existing PDF/spreadsheet behavior.

JUnit evidence: `.local/crm-pms-functionality/tests.xml`. Screenshots: `.local/crm-pms-functionality/{scheduling,automation,crm}-{1440,390}.png`.

### Preservation regressions

A separate bounded run passed **64 tests**, with **two existing opt-in workflow browser cases skipped**. It covered PMS planning/reports, automation and schedules, workflow schemes/transition approvals, CRM deal operations, and shared analytics report/build/export/RBAC behavior. The two existing export-format cases were rerun in the final focused pass after the shared workbook-label enhancement.

These are separate runs, not a fresh full-repository certification. The existing workflow browser cases had been exercised in the preceding UI/navigation batch; this batch's three new browser cases ran explicitly.

### Frontend

The production frontend build, including TypeScript, passed after the final feature changes. Existing dependency annotation, mixed import and large-chunk warnings remain. Build output is retained at `.local/crm-pms-functionality/frontend-build.log`. Desktop/mobile screenshots were visually inspected; a narrow-screen export-control overflow was corrected and the scheduling browser journey rerun successfully.

## Repeat the focused acceptance

From `backend` in PowerShell:

```powershell
$env:RUN_CRM_PMS_FUNCTIONALITY_BROWSER='1'
$env:RUN_PMS_SCHEDULING_BROWSER='1'
.\venv\Scripts\python.exe -m pytest tests/test_crm_report_builder.py tests/test_pms_automation_due_dates.py tests/test_pms_advanced_scheduling.py tests/test_pms_planning_reports_workflows.py::test_report_export_mapping_xlsx_format_and_invalid_reports tests/test_pms_planning_reports_workflows.py::test_spreadsheet_cells_are_text_and_pdf_keeps_all_rows -q --disable-warnings --maxfail=1 --tb=short --junitxml=../.local/crm-pms-functionality/tests.xml
```

The frontend/browser dependencies and agent-browser CLI must be available. The existing fixture runner starts and closes its own isolated preview/API services. No provider messages or production workflows are sent by these tests.
