# Competitor gap closure

Started 6 November 2026. Close gaps in priority order by checking current code first, reusing authoritative services and testing each changed flow.

## Batch 1: product inventory and project transition policies

The capability inventory now acknowledges the implemented dashboard builder, versioned conditional forms, organization task types and leave-aware dated capacity. It no longer describes these as absent. The dashboard link opens the dashboard builder. Availability remains partial where operational acceptance or advanced functionality is outstanding.

Project workflows are accessible from **PMS management home â†’ Project workflows** (`/pms/workflow-schemes`). A project editor can select a workspace project, define allowed transitions between the six standard statuses, require an assignee, due date or nonempty description, and publish the policy. Publishing records activity and rejects stale revisions. Disabling a policy restores standard transitions. Existing projects start with no policy.

The implementation reuses workspace-entry storage, project authorization, task completion guards, audit activity and existing task mutation services. No schema migration is needed. The UI supports adding/removing transitions, reload/discard, unsaved-change protection on project switching and page unload, and mobile layout.

Policies are checked during direct updates, bulk updates, management actions, board moves, assignment-derived status rollups and recovery. A merged development link is retained when an automatic completion fails its guards; activity records the skipped transition instead of losing the development evidence or forcing completion. Existing checklist, blocker, evidence and work-submission completion rules remain in place on the normal mutation paths.

Scope is deliberately explicit: these are transition policies for existing tasks, not a complete Jira workflow designer. At the end of Batch 1, work-type-specific schemes and configurable approval routing remained open; Batch 2 below implements those flows. New custom statuses, task-creation initial-state rules and a draft/approval/publish lifecycle remain open. The existing shared approval engine should be assessed before adding approval logic.

## Validation

- Baseline: 48 API tests passed across dashboards, forms, shared forms, capacity/management, planning/reports and automations on disposable SQLite.
- Initial workflow and adjacent API regression pass: 21 tests passed.
- Final workflow/browser and adjacent regression pass: 65 tests passed across workflow policies, workspace recovery, workspace operations, project access and intern execution. This includes the real browser flow against the disposable API.
- Frontend TypeScript check and full production build passed.
- The opt-in browser runner uses the real workflow editor against an ephemeral API backed by the test fixture database. It publishes, reloads, checks real task-transition enforcement, discards edits and checks mobile overflow. Run with `RUN_PMS_WORKFLOW_BROWSER=1` and the workflow test module.
- PostgreSQL locking behavior and production/provider rollout are not established by SQLite tests or the frontend build.

## Batch 2: work-type workflows and approval routing

The workflow editor now supports per-work-type transition overrides and a project default fallback. It validates built-in and organization-defined types and each transition graph. Removing an override restores inheritance. Type changes must happen separately in Backlog or To Do while a workflow is enabled, preventing a mid-transition switch to less restrictive rules.

Each transition can name an ordered sequence of up to ten reviewers. Requests create shared `WorkflowDefinition`, `WorkflowStepDefinition`, `WorkflowInstance` and `WorkflowTask` records. The shared engine resolves assignments and delegation, advances steps, records decisions and emits audit events. PMS adds project-access and self-review checks rather than creating a second approval engine. The shared decision endpoints and aliases enforce those checks too.

Reviewers use **Transition approval inbox** (`/pms/transition-approvals`) and the task's **Transition approvals** panel. The task editor requests a transition, reviewers approve or reject it in order, and an authorized task editor explicitly applies it after all approvals. Approval alone does not update status. Rejection permits a fresh request. Duplicate pending requests reuse the existing instance.

Approval is bound to the saved task fields, selected rule and policy revision. Editing those fields or changing the workflow invalidates the request. Old pending requests are cancelled when a replacement is requested. Approved grants are single-use, require real shared-engine review audit events, and cannot be replayed after a task cycles back to an earlier status. Revoked reviewers cannot decide or supply a valid grant. Invalid delegation and delegated self-review fail safely. Failed completion or bulk operations roll back grant consumption. Checklist, attachment and other related records remain subject to their own completion/authorization controls; they are not all included in the task-field snapshot.

Storage and schema are reused; no migration is needed. PostgreSQL concurrency and production rollout remain separate acceptance work.

Batch 2 validation:

- 20 workflow/type/approval tests passed, including both real-browser journeys against disposable databases with independent request sessions.
- Browser coverage includes publishing and reloading type overrides, fallback restoration, approval-route persistence, request/reject/retry/approve/apply and mobile layout.
- API coverage includes sequential reviews, delegation, self-review and access rejection, stale task/policy snapshots, invalid approvers, revoked reviewers, single-use grants, board moves and failed bulk/completion rollback.
- 80 adjacent regression tests passed across PMS management/access, workspace recovery/operations, intern execution, the shared engine, workflow inboxes and Approval OS. The separate opt-in browser case was skipped in that regression run and exercised in the 20-test pass above.
- TypeScript check and full production frontend build passed. Existing dependency/chunk-size build warnings remain.

## Batch 3: PostgreSQL concurrency and production acceptance (6–7 November 2026)

The workflow acceptance suite now runs against a freshly migrated local PostgreSQL 17.11 database. Each concurrency case uses a separate disposable database cloned from that migrated test baseline, with independently committed request sessions. Tests wait for a real PostgreSQL lock before releasing the competing editor transaction; they do not simulate concurrency with a shared SQLite session.

Four reproduced lock-wait failures were fixed:

- A review could approve task fields loaded before another editor committed a change. Review decisions now refresh the task after acquiring their mutation locks.
- Bulk transitions could consume approval using stale pre-lock task fields. Bulk updates now reload task state after project locks, reject tasks moved/deleted while waiting and acquire project locks in a stable order.
- Reviewer suspension during a lock wait was not reflected in the cached actor. Decisions now refresh the actor and reuse project authorization after the wait.
- A suspended requester could still apply a grant after waiting. Shared actor revalidation now also protects direct updates, bulk updates, board moves, approval requests and workflow publication. The tests verify all five write paths.

Tests also cover first-publication/update conflicts, duplicate request deduplication, competing approve/reject decisions, single-use grant consumption and rollback. The PostgreSQL browser tests use committed data and independent sessions. Vite hot reload and filesystem watching are disabled in browser harnesses, and each run has its own cache so unrelated workspace edits cannot reload the page mid-flow.

The production-configured API process is started with its actual startup lifecycle on a cloned test database, with debug, demo seeding and automatic migrations disabled. Acceptance verifies production health, unauthenticated inbox rejection, reviewer inbox visibility and request → review → apply. Public URLs and CORS use explicit HTTPS origins; remote tenant provisioning is disabled for these tests.

Validation:

- **40 passed, 2 skipped** in the full PostgreSQL acceptance run. The two savepoint-fixture browser cases are intentionally skipped on PostgreSQL and replaced by the two passing committed-data browser cases.
- **66 passed, 2 skipped** in the SQLite regression run across workflow/type/approval, management, project access, intern execution and the shared engine.
- A further production-runtime recheck passed using a database-owner login with `NOSUPERUSER`, `NOCREATEDB` and `NOCREATEROLE`; startup and the full request → review → apply flow worked with those restrictions. [Runtime test evidence](../outputs/workflow-production-mode.xml).
- All **829 model tables** were checked against migrated PostgreSQL with no missing model columns, at migration head `pg_20261106_085_accounting_sync`.
- The readiness sweep found incomplete schema-coverage snapshots for accounting sync, payment batches and Form 16 records. Their snapshots were completed from the actual migrated columns; no application-table migration or frozen-baseline change was required. All six schema-configuration checks pass.

The latest localhost rerun recorded **40 passed, 2 skipped** plus one schema-manifest failure caused by newly added accounting customer links and CRM templates. The three affected table snapshots were verified against actual PostgreSQL columns and updated. The targeted schema suite then passed **all six checks**; a separate actual-schema sweep verified **831 model tables**, no missing columns, at `pg_20261107_087_crm_templates`. The workflow and browser cases all passed; the original failed report is retained alongside the successful [schema recheck](../outputs/workflow-schema-recheck.xml) and [current actual-schema verification](../outputs/workflow-localhost-schema-acceptance.json). TypeScript passed after the default task workspace panel was added.

Repeat the local acceptance run from the repository root with `backend/venv/Scripts/python.exe qa/run_workflow_postgresql_acceptance.py`, supplying `DATABASE_URL` for a loopback PostgreSQL server whose dedicated test administration role can create databases and temporary runtime roles. The runner creates randomly named test databases and removes them afterward; it does not reuse the configured application database. The app database role's existing restrictions were preserved. The private PostgreSQL server was subsequently reused for the requested localhost sandbox and remains running. Automatic approval review previously blocked recursive deletion of its temporary files; the ignored `.local/workflow-acceptance-pg-path.txt` records their location.

Evidence: [PostgreSQL test report](../outputs/workflow-postgresql-acceptance.xml), [SQLite regression report](../outputs/workflow-sqlite-regression.xml), [actual model-schema verification](../outputs/workflow-schema-acceptance.json).

### Localhost and live acceptance

Both production hosts subsequently reported release `b4bb3552a139110236cf4bef8f50bf579c972413`, healthy databases and an authenticated workflow inbox route (unauthenticated requests return 403). This chat did not deploy that release. Authenticated production testing on app.dsbchartered.com reached the company setup gate: the official company email is blank. No company identity was fabricated. The two QA accounts were suspended and their workspace memberships removed; the labeled QA branch remains because the API refuses to trash the last active branch. Production end-to-end acceptance remains open.

At the user's request, acceptance moved to an isolated localhost database. The frontend is available at http://127.0.0.1:5198 and proxies the current API on port 1538. It uses synthetic test accounts and no production data. The permission catalog is seeded from the existing system catalog. The isolated sandbox remains available for manual review.

The managed-access check exposed an Automation entitlement dependency in the shared workflow engine. PMS now exposes a task-bound decision adapter that calls the existing engine. The request's model scope permits only PMS transition definitions/instances and their authorized parents; it does not grant the Automation module. The focused reviewer regression and the broader managed-access suite passed (37 passed, 2 intentional browser skips).

The localhost HTTP acceptance passed all 48 checks: PMS-only requester and two ordered reviewers, rejection/retry, deduplication, self-review denial, partial-review enforcement, explicit apply, single-use replay rejection, stale edit rejection, and the Bug-specific override. All eight QA cleanup actions passed. The full browser also logged in and loaded the saved workflow editor successfully. A default-task-workspace check exposed the missing transition panel; the existing panel is now reused on the Reviews tab, and inbox links open that tab directly. The resulting full-page request → inbox review → ordered final review → explicit apply browser flow passed. [Browser evidence](../outputs/workflow-localhost-browser.json). [Localhost acceptance evidence](../outputs/workflow-localhost-acceptance.json), [managed access regression](../outputs/workflow-managed-access-regression.xml).

Repeat read-only availability checks with `backend/venv/Scripts/python.exe qa/check_workflow_production.py`. [Live probe evidence](../outputs/workflow-production-probes.json). Production company setup and authenticated deployed acceptance remain pending.

## Batch 4: PMS compound conditions and clock triggers (7 November 2026)

PMS automation now reuses the shared runtime's nested `all`/`any` condition evaluator. The rule editor supports AND/OR groups over task status, priority, work type, title, due date and primary assignee. Payload validation bounds the tree to 40 nodes, restricts fields/operators and validates values. Existing status filters and event rules remain compatible. Editing, reloading and paused duplication preserve the condition tree and schedule.

Two clock triggers reuse the PMS action path: a daily local-time schedule and a due-date trigger with an offset from -365 to +365 days. Due-date rules catch up eligible overdue tasks and recognize a changed due date as a new occurrence. Daily rules run at most once per matching open task per local calendar day. Completed/deleted tasks and archived/deleted projects do not run. Daily schedules do not replay every missed historical day.

The existing authenticated cron mechanism calls `/api/v1/internal/pms-automations`; the Vercel configuration checks it every five minutes when deployed. The adapter uses the existing scheduler ledger, workspace-entry storage, branch/tenant authorization and PMS execution history. It scans at most 25 rules and 50 tasks per rule per tick by default, rotating persisted cursors. Delivery is after the selected local time, with latency depending on polling and backlog. There is no new application table or migration.

A rule runs under its author's current company, branch, module and workspace/project access, resolved after acquiring mutation locks. Task mutations, per-task occurrence receipts and scan progress commit together. A failed rule rolls back its changes and receipts and can retry on a later tick. Overlapping ticks cannot duplicate an occurrence. Editing a rule starts a new revision; pausing/resuming preserves receipts. These guarantees cover the existing deterministic priority/assignee actions; arbitrary external actions and general-purpose queues remain separate work.

Local acceptance completed each flow before proceeding. The nested-condition browser journey passed first, followed by the daily clock journey and then due-date offset/catch-up/reschedule. The browser found that adding clock fields caused the generic form wrapper to hide fields behind newly activated tabs; this already-sectioned editor now keeps its fields visible. Mobile checks and actual task mutations pass.

Validation and repeatability:

- 11 initial compound/shared-condition tests passed.
- 28 regression tests passed with one opt-in approval browser case skipped; the dedicated localhost browser checks exercised the changed UI.
- All 18 PMS automation tests passed on freshly migrated, disposable PostgreSQL. A further nine clock/access checks passed on SQLite, including PMS-only managed authors and revoked workspace membership.
- Two committed PostgreSQL concurrency tests passed: overlapping ticks apply once, and author suspension during a project-lock wait prevents execution.
- TypeScript checks passed. Full localhost browser runs passed for nested conditions and both clock triggers, including persistence and mobile layout.
- Evidence: [compound checks](../outputs/pms-compound-conditions.xml), [regression](../outputs/pms-automation-regression.xml), [PostgreSQL](../outputs/pms-automation-postgresql.xml), [clock access](../outputs/pms-clock-access-recheck.xml), [concurrency](../outputs/pms-clock-concurrency.xml), [compound browser](../outputs/pms-automation-localhost-browser.json), [clock browser](../outputs/pms-clock-localhost-browser.json).

The localhost preview remains at http://127.0.0.1:5198/pms/automation. `qa/serve_workflow_acceptance.py --reuse` preserves its isolated test database across code restarts. `qa/run_pms_localhost_scheduler.py` checks the sandbox every minute; production uses authenticated cron. Re-run browser acceptance with `node qa/check_pms_automation_localhost.cjs` and `node qa/check_pms_clock_localhost.cjs`. These helpers accept only the labeled loopback sandbox. No production deployment or live-company setup changes were made in this batch.

## Batch 5: scheduling, automation diagnostics and CRM reports (8 November 2026)

The Gantt page now exposes opt-in project-calendar scheduling: all four dependency types with working-day lag, critical-path/slack analysis, preview before atomic apply, and stale-plan rejection. Existing start dates remain lower bounds. Named baseline snapshots are retained for comparison and CSV/Excel variance exports. Existing manual editing is preserved. This is not resource leveling or HR leave-aware planning; complete application requires every task to have both dates. Completed/cancelled tasks are not moved automatically.

PMS rules now support an absolute due-date action through the existing event/clock action path. Invalid date ranges and completed work are skipped with recorded reasons. Execution reporting adds outcome/rule/date filters, cursor pagination and before/after values. Unchanged no-op evaluations are not counted as executions. Existing daily/due-date receipts and pause/edit/duplicate behavior are reused.

CRM reports now include private deal-report definitions using the existing analytics query engine. Users can choose detail columns, exact filters and grouping; monetary summaries always group by currency. Current CRM record visibility and export capabilities remain authoritative. Definitions have optimistic revisions, with retained drafts and copy-based conflict recovery. CSV/Excel exports include the complete matching result up to an explicit 5,000-row/group limit. Domain-owned private definitions are hidden from the generic analytics catalog and routes.

See [scope, repeat commands and acceptance evidence](qa/crm-pms-functionality-2026-11-08.md). Local tests and disposable real-browser flows do not establish deployed or PostgreSQL concurrency acceptance for these new scheduling/reporting operations.

## Remaining order

1. Finish production company setup with its official email and complete authenticated deployed acceptance. Local PostgreSQL concurrency and production-mode checks now pass. Custom statuses, task-creation rules and draft publication remain separate enhancements.
2. Continue PMS automation depth: broader connector/action coverage, usage accounting and reconciliation tooling. Batch 6 adds bounded PMS signed-webhook queues, retries, dead letters and cancellation; legacy CRM webhook transport is unchanged.
3. Scheduling and commercial depth: cross-project resource reservations/optimization, expense billing and commercial acceptance. Batch 6 adds opt-in project-only effort/capacity leveling with the existing HR calendar/leave capacity service. Deployed and PostgreSQL scheduling acceptance remain separate.
4. Knowledge capture and collaboration: clipping, OCR/attachment search, offline sync and live document editing.
5. Enterprise identity, governance and external connected-search acceptance.
6. Broader CRM reporting sources, shared definitions, range filters, attachments and historical snapshots. Batch 6 adds owner-only daily/weekly sign-in link delivery for private CRM deal reports and PMS baseline variance.

Each item remains open until its complete supported flow is implemented and validated. Existing vendor connector code must be exercised before being labeled absent or complete.


## Batch 6: project resource leveling, external action queues and report links (8 November 2026)

Resource leveling is opt-in in Advanced scheduling. A deterministic project-only planner allocates remaining estimated effort against assignee working hours, dated weekly capacity, applicable holidays and approved leave. Multi-assignee effort is split equally. It retains dependency constraints and existing date lower bounds; completed/cancelled tasks cannot be moved. Preview includes daily hour allocations, and apply rejects changed estimates, assignments or availability. Bounds are 200 tasks, 50 assignees and 366 calendar days. Other projects are not reserved; this is not organization-wide optimal leveling. Resource-constrained plans do not present dependency-only slack or critical-path labels as resource-aware metrics.

PMS automation adds a signed webhook action with workspace connections. Secrets use the shared encrypted credential helper; HTTPS uses shared public-address validation and pinned TLS transport. Task saves enqueue into existing durable automation jobs without network IO. Receivers must acknowledge delivery-ID deduplication. Confirmed 429/500/502/503/504 rejections retry with bounded backoff, up to five attempts; permanent rejection or exhausted retries goes to dead letter. A committed unconfirmed state precedes network IO, so timeouts/crashes are held for reconciliation. Owners/admins can inspect deliveries, retry confirmed failures, cancel pending failures and disable connections. Current author/company/branch/project/workspace rights and paused sources are checked before sending. Legacy CRM webhook transport remains unchanged.

CRM private saved deal reports and PMS baseline variance reports can deliver daily/weekly authenticated links to the schedule owner's company email, with local time and IANA timezone. Preparation executes the existing scoped export, queues through the shared email outbox and advances the occurrence atomically. Duplicate occurrences use stable outbox keys. Paused/deleted/revoked sources are blocked or suppressed, including a final permission check before provider dispatch. The UI distinguishes queued from provider accepted. Links open current authorized data; there are no attachments, historical snapshots or arbitrary recipients. Existing cron and long-running email worker paths are reused; no migration or deployment was performed.

Local validation and precise limitations are recorded in [Batch 6 QA](qa/crm-pms-resource-delivery-2026-11-08.md). PostgreSQL overlap/crash tests, real provider delivery and production rollout remain unverified for this batch.
