# CRM/PMS resource leveling and delivery QA — 8 November 2026

## Implemented scope

PMS Advanced scheduling now offers an opt-in resource plan. It reuses the existing capacity service for working hours, dated weekly capacity, applicable holidays and approved leave. Open tasks require assignees and positive remaining effort, using remaining estimates or estimated minus actual hours. Effort is split equally across multiple assignees. The deterministic planner obeys the four dependency relationships and retains current date lower bounds, with a bounded 366-day horizon, 200 tasks and 50 assignees. Daily allocations are included in the preview response. Preview does not mutate tasks; apply is atomic and rejects changes to dates, dependencies, status, estimates, assignees or calculated availability. Terminal tasks cannot be moved.

Resource scope is the selected project. Other projects are not reserved and no global optimum is claimed. Dependency-only planning remains available without estimates. Resource-constrained previews omit critical-path/slack values instead of presenting dependency-only float as a resource-aware result. Existing baselines and variance exports remain available.

PMS automation now supports queued signed webhooks. Workspace owners/admins can register an HTTPS destination and an encrypted signing secret, choose it in a rule, inspect queue state, retry dead letters, cancel pending/failed deliveries and disable a connection. Paused duplication and rule editing preserve the connection. Registration requires the receiver's delivery-ID deduplication contract. URLs use the existing public-address validation and pinned TLS transport; credentials, query strings, private addresses and redirects are rejected.

Enqueue commits with the task/rule occurrence. No external network call runs in a task-save transaction. The durable worker rechecks current owner, company, branch, workspace, project and source availability. It commits an unconfirmed state before network IO; a timeout/crash therefore cannot cause a blind automatic replay. Confirmed transient receiver rejections (429/500/502/503/504) retry with 60/120/240/480-second backoff, up to five attempts. Exhaustion/permanent rejection goes to dead letter. Accepted means an HTTP success response; it does not assert completion inside the receiving service. Ambiguous outcomes remain held for operator reconciliation. Legacy CRM webhook transport and arbitrary connector operations are unchanged.

Scheduled report delivery covers private CRM saved deal reports and PMS baseline variance. The owner can configure daily or weekly delivery, local time, IANA timezone and pause/resume. Preparation executes the current scoped export and atomically queues an owner-only email through the existing outbox, using a stable occurrence key. Current access is checked again before provider dispatch. Deleted/revoked sources are blocked; paused/revoked deliveries are suppressed. The UI distinguishes schedule state, queued email and provider acceptance. Existing authenticated email cron and long-running email worker both run preparation.

Emails contain authenticated sign-in links to current authorized reports. Attachments, retained historical report snapshots, arbitrary recipient sharing and broader report sources remain open. Missed ticks coalesce into one current run rather than sending every missed historical period. Schedule preparation is bounded to ten reports per tick. No migration, deployment, real webhook request or provider message was performed.

## Validation

- Focused scheduling/report/automation suite: **32 passed**, zero skips/failures, including the three prior browser journeys. Evidence: `.local/crm-pms-resource-delivery/tests.xml`.
- Final feature suite after UI refinements: **17 passed**, zero skips/failures, including the new combined real-browser journey. Evidence: `.local/crm-pms-resource-delivery/resource-delivery-final.xml`.
- Separate preservation regression run: **103 passed**, two pre-existing opt-in workflow browser cases skipped. Covered planning/export mapping, automations and clock triggers, workflow schemes/approvals, CRM deals/integrations, shared analytics export/RBAC, capacity management, email and connector runtime. Evidence: `.local/crm-pms-resource-delivery/regressions.xml`.
- Final API recheck after restricting each module's report-delivery adapter: see `.local/crm-pms-resource-delivery/final-api.xml`.
- Full frontend TypeScript/production build passed. Existing dependency annotation, mixed import and chunk-size warnings remain. Evidence: `.local/crm-pms-resource-delivery/frontend-build.log`.

These runs overlap; counts must not be added as unique tests. All backend test data was disposable. Browser requests used a disposable SQLite-backed API and the real React components. The harness first smoked each newly started Vite preview with agent-browser, then exercised workflows with Playwright. No production/company data or provider configuration was changed. PostgreSQL locking/concurrency, process-crash injection and deployed delivery are not certified by these tests.

### Workflow coverage

- Competing assignments: preview, unchanged stored dates, reduced weekly capacity, stale rejection, guest denial and atomic apply.
- Approved half-day leave and holidays: exact daily hour allocation; assignment changes invalidate preview.
- Four dependency types and multiple assignees: allocated effort is conserved and no user's daily capacity is exceeded.
- Webhook action: connection encryption/redaction, enqueue without sending, explicit transient rejection/backoff, eventual acceptance with stable delivery ID, exhaustion, manual retry, cancellation and pause/revocation guards.
- Timeout: unconfirmed state persists, subsequent worker ticks do not resend, manual blind retry is rejected.
- Public HTTPS validation: HTTP, loopback and query-string destinations are rejected.
- Report delivery: daily/weekly local occurrence calculation, private CRM ownership, PMS baseline requirement at execution, durable outbox, mocked provider acceptance, duplicate occurrence suppression, pause/revocation suppression and deleted-source blocking.
- Browser: resource preview/apply; baseline capture; PMS schedule save/pause; webhook connection/rule creation; real task-triggered enqueue; queue cancellation; edit/copy preservation; CRM weekly schedule reload persistence. Desktop (1440px) and mobile (390px) checks passed with no page errors or document-wide horizontal overflow.

Screenshots are `.local/crm-pms-resource-delivery/{resource,external,report}-{1440,390}.png`. They were visually inspected. Mobile tables retain their own horizontal scroll. Inspection found and corrected an incorrect webhook summary label; resource actions now have explicit resource-plan button labels.

## Repeat acceptance

From `backend` in PowerShell:

```powershell
$env:RUN_CRM_PMS_RESOURCE_BROWSER='1'
$env:RUN_CRM_PMS_FUNCTIONALITY_BROWSER='1'
$env:RUN_PMS_SCHEDULING_BROWSER='1'
.\venv\Scripts\python.exe -m pytest tests/test_crm_pms_resource_delivery.py tests/test_pms_advanced_scheduling.py tests/test_pms_automation_due_dates.py tests/test_crm_report_builder.py -q --disable-warnings --maxfail=1
```

The browser runner needs frontend dependencies, Playwright Chromium and agent-browser. It starts and closes its own API/preview processes and mocks outbound transport. The shared checkout also contains unrelated HRMS work; those changes were preserved and were not included in this feature assessment.
