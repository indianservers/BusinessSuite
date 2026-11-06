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

Repeat the local acceptance run from the repository root with `backend/venv/Scripts/python.exe qa/run_workflow_postgresql_acceptance.py`, supplying `DATABASE_URL` for a loopback PostgreSQL server whose dedicated test administration role can create databases and temporary runtime roles. The runner creates randomly named test databases and removes them afterward; it does not reuse the configured application database. The app database role's existing restrictions were preserved. The temporary PostgreSQL server was stopped after validation. Automatic approval review blocked recursive deletion of its temporary files, so the test data and logs were retained; the ignored `.local/workflow-acceptance-pg-path.txt` records their location.

Evidence: [PostgreSQL test report](../outputs/workflow-postgresql-acceptance.xml), [SQLite regression report](../outputs/workflow-sqlite-regression.xml), [actual model-schema verification](../outputs/workflow-schema-acceptance.json).

### Live rollout remains open

Read-only probes of `app.dsbchartered.com` and `app.indianservers.com` report healthy databases and release `cab74ac32a11ee114190fd83ad02752f11a7a6f1`. Both return **404** for `/api/v1/project-management/transition-approvals/inbox`. Therefore local production-mode acceptance is established, but authenticated live workflow acceptance is not. No live user records were changed and no deployment was performed.

Repeat availability checks with `backend/venv/Scripts/python.exe qa/check_workflow_production.py`. [Live probe evidence](../outputs/workflow-production-probes.json) records timestamps and limits; an OpenAPI transport error on one site is retained in that evidence rather than treated as a passing workflow check. The remaining acceptance step is a reviewed workflow release followed by authenticated verification on the deployed environment.

## Remaining order

1. Deploy the reviewed workflow release and finish authenticated live acceptance. Local PostgreSQL concurrency and production-mode checks now pass. Custom statuses, task-creation rules and draft publication remain separate enhancements.
2. Expand PMS automation using existing automation infrastructure: compound conditions, scheduled/due-date triggers, more actions, durable execution/retry/idempotency and usage accounting.
3. Scheduling and commercial depth: critical path, baselines, calendar-aware dependency propagation, expense billing and commercial acceptance.
4. Knowledge capture and collaboration: clipping, OCR/attachment search, offline sync and live document editing.
5. Enterprise identity, governance and external connected-search acceptance.

Each item remains open until its complete supported flow is implemented and validated. Existing vendor connector code must be exercised before being labeled absent or complete.
