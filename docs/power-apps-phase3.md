# Power Apps — Phase 3: durable automation execution

Phase 3 extends the existing standalone Power Apps Studio with real database-backed execution. It preserves graph schema 2, the 48-node design catalog, 39 templates, existing drafts, immutable version snapshots, authoring tools and tenant/environment/ownership boundaries. No PMS, CRM, HRMS or InternHub event provider, action or UI integration was activated. No production migration, deployment, workflow activation or external action was performed.

## Architecture decision and audit

The repository already has PostgreSQL-backed leased jobs in `app/ai_operator/jobs.py`, bounded scheduled batches in `app/services/scheduled_jobs.py`, and legacy native/shared workflows in `app/shared/runtime.py`. These establish the deployment's database-queue pattern. The native engine uses a different graph and native action contracts; silently routing the standalone visual graph through those adapters would change its permissions and activate integrations outside this phase.

The Power Apps runtime therefore uses the same SQLAlchemy/PostgreSQL transaction, compare-and-swap and fenced-lease approach, attached directly to the existing `PowerResource`, `PowerVersion`, `PowerExecution` and authentication infrastructure. It does not add another definition format, Redis, RabbitMQ, Kafka, Celery or Temporal. The central service is `app/apps/power_apps/runtime.py`; the worker is an independently supervised process. An HTTP request creates a run and its first durable job, then returns 202. The browser does not keep it alive.

The Phase 2.B pure transformation and constrained mapping functions are reused as real local executor handlers. Runtime dispatch uses a server-owned capability registry, not frontend flags or simulator fixtures. Simulation stays separate and does not create production run history.

## Definition lifecycle and immutable runs

Editable resources retain their existing draft table/constraint. `power_automation_deployments` tracks validated draft version, immutable published `PowerVersion` ID, runtime lifecycle and policy. This separates editable drafts from the active publication without rewriting saved resources. Runtime states are draft, validated, published, active, paused and archived. Validation is bound to an exact draft version; publication checks that binding under the resource lock. Publication and activation are separate explicit authorized requests. Pause stops new triggers while already accepted runs continue. Archived runtimes cannot transition; create a draft copy when needed.

Runs reuse `power_apps_executions` and reference an immutable saved version through `power_automation_run_states`. Their statuses are queued, running, waiting, retry_scheduled, completed, failed and cancelled. Draft edits, policy edits and later publications do not change a running version or identity. ORM hooks reject updates/deletes of published or used snapshots, and resource deletion is blocked once a publication or run exists.

The legacy graph identity field is retained for serialization compatibility; the explicitly reviewed deployment identity policy controls actual authority. An old owner placeholder never silently delegates execution.

The editor's **Publish & runs** control opens the runtime review page. It does not publish, activate or execute by itself. All these actions are enforced again on the server.

## Persistence and additive migration

Both migration trees include revision `20261027_035_power_runtime` (PostgreSQL prefix `pg_`). The DDL is frozen in the migration files. Upgrade creates only new runtime tables and indexes. It does not rewrite existing resource, version, user, company or execution records. The isolated migration test checks preservation, repeated upgrade and explicit downgrade. Runtime startup never runs downgrade or deletes production history.

New tables:

- `power_automation_deployments`: publication lifecycle and policy.
- `power_automation_run_states`: immutable version reference, effective identity, correlation ID, bounded input, variables, execution plan, deadline and timestamps.
- `power_automation_steps`: durable node instances, loop scope, attempts, input/output, selected ports, errors and timestamps.
- `power_automation_jobs`: availability, status, fenced token, lease expiry, heartbeat and claim count.
- `power_automation_waits`: timed wakeups, authorized event waits and loop deadlines.
- `power_automation_triggers`: explicit schedule, signed-webhook or registered-event configuration.
- `power_automation_events`: execution and administrative audit timeline.
- `power_automation_dead_letters`: exhausted/permanent job failures and resolution stamps.
- `power_automation_replays`: hashed webhook nonces, scoped to a trigger.
- `power_automation_workers`: system-owned liveness and scheduler timestamps.

Run idempotency uses the existing unique organization/environment/resource/request-key constraint. The same key and input returns the existing run; using it with different input is rejected. Webhook replay nonces are separate from run idempotency.

## Queue, concurrency and recovery

Workers claim eligible jobs with PostgreSQL locks, `SKIP LOCKED` and a conditional update. Every claim has a new fencing token and a 30-second lease. Stale workers cannot commit a replacement claim's job. A run lock serializes its checkpoints; each supported local action, persisted output, audit events and successor enqueue commit together. A savepoint rolls back failed action/checkpoint mutations before recording failure or retry.

Leasing is committed before executing the action. This makes the current step and reserved attempt visible in history. A crash can leave a running lease, but not an uncommitted output. After expiry another worker can reclaim it. Interrupted claims remain visible in attempt/claim counts. Attempts are at least once; this does not claim exactly-once external effects.

Quota reservations use a short company lock across environments. Local execution does not hold that company mutex for the duration of an action. The scheduler prioritizes the least recently dispatched eligible tenant and, within that tenant, continuation jobs of admitted runs. This prevents both tenant starvation and a backlog of new runs blocking existing runs from finishing. Capacity is checked transactionally.

Defaults:

- Per workflow: 4 admitted runs, configurable 1–20; queue up to 1,000. Overflow can queue or reject. Duplicate event/request keys are ignored through idempotency; the `ignore` overflow setting still rejects a new unique request when full.
- Per tenant: 20 admitted runs/leases and 2,000 pending runs.
- Per environment within a tenant: 10 admitted runs/leases.
- Workflow duration: 24 hours by default, explicitly configurable up to seven days.
- One process handles one bounded action at a time. Run multiple supervised processes for worker concurrency.

Tenant/environment defaults are configurable through `POWER_RUNTIME_TENANT_ACTIVE`, `POWER_RUNTIME_ENVIRONMENT_ACTIVE` and `POWER_RUNTIME_TENANT_QUEUE`, with validated bounds. Module administrators can adjust a workflow's capacity without changing its execution identity. Pausing/archiving a publication does not cancel accepted runs; cancellation is explicit.

Unexpected worker failures leave a recoverable lease, log only the exception type, and do not acknowledge the job. Repeated interrupted claims are bounded and dead-lettered. SIGINT/SIGTERM drain the current bounded step before stopping. `--once` exits unsuccessfully on an operational error.

## Executors, branching and expressions

The authoritative registry is `runtime_executors.py`; `/automations/runtime/capabilities` exposes its version, fields/output schemas, permissions, timeout, idempotency and retry capability. Supported nodes include manual/schedule/webhook and registered internal-event trigger contracts; If/Else, Switch, AND/OR, Filter, Compare Values, Check Empty, Route by Priority, Parallel Branch, Merge, Set Variable, Transform Data, Map Fields, Build/Parse JSON, Format Date/Number, Aggregate Values, restricted Evaluate Expression, Delay, Wait Until, Stop Workflow, Structured Log Event and Error Handler. Loop/For Each orchestration uses the same registry and durable step instances.

External HTTP, email, native record mutations, approval actions, credentials and sub-workflow recursion remain unsupported and prevent publication. Importing a graph or changing a frontend flag cannot register a handler.

Branch routing persists selected ports; skipped paths become skipped steps. Merge supports all active required inputs, keyed inputs, first completed and first successful. First-successful joins can tolerate a failed sibling; if none succeeds, the join fails. First selection uses committed completion timestamps, rather than the order of edges in JSON. A winning early join does not silently erase other accepted branch histories. Local checkpoints within a run are serialized for consistent shared state; this phase does not measure parallel connector throughput.

Loops expand bounded acyclic body regions into durable instance IDs, with continuation through the done port only. Sequential and bounded-parallel iteration modes enforce count, concurrency (up to 10), maximum nested depth (2), total expanded steps (5,000), plan size (2 MB), node timeout and workflow deadline. Publishing rejects excessive declared expansion. Loop graphs use IDs of at most 40 characters so generated instance IDs remain valid. Loop bodies must terminate independently; they cannot accept outside branch inputs or connect into the done continuation. Unordered branches cannot read/write the same mutable workflow variable. Parallel loop bodies use isolated step outputs; named shared-variable writes require sequential iteration.

Expressions remain safe property paths and the Phase 2.B allowlisted transformations. There is no eval, dynamic JavaScript/Python, arbitrary filesystem access, reflection or URL/API dispatcher. Inputs are limited to 32 KB, local values/outputs and the variable dictionary to 64 KB with depth/complexity limits, aggregate run outputs to 4 MB, and published definitions to 1 MB. Variable names are literal so parallel conflicts can be checked. Legacy flat comparisons retain their compatibility behavior; typed condition groups provide strict comparisons. Secrets and unsafe property names are rejected by the existing parser; recognizable secret-shaped literals are also rejected/redacted. No credential material is resolved into expressions or history.

## Triggers and durable waits

Manual starts require current view/execute access, an active publication, the correct trigger type, enabled environment and optional published input schema. A caller cannot supply a different execution identity.

Schedules support once, every N minutes, hourly, daily, weekly, monthly, numeric five-field cron, IANA timezones and start/end timestamps. Cron accepts ranges, lists and steps; it has a five-year search horizon. A nonexistent DST local time is skipped; a repeated local time fires on the first fold only. Interval schedules use UTC elapsed time. Missed occurrences coalesce to one durable run rather than creating an unlimited catch-up storm. Resource/trigger locking and occurrence idempotency prevent duplicate scheduler claims.

Signed webhooks use unique opaque endpoint IDs and an encrypted secret, shown only when created or rotated. Send:

```
X-Power-Timestamp: Unix seconds
X-Power-Nonce: unique event/request identifier (8–180 characters)
X-Power-Signature: hex HMAC-SHA256(secret, timestamp + "." + nonce + "." + exact raw body)
Content-Type: application/json
```

The signature must be within five minutes. A replay is rejected with 409; rotation invalidates the old secret. Ingress enforces 32 KB, an explicit bounded JSON-schema subset, per-trigger successful-ingress limits, shared IP request throttling and optional CIDR allowlisting using the suite's trusted-proxy rules. Authentication runs before enqueue. The exact route has an explicit capability exception to default user authentication; it always requires HMAC plus a configured effective identity. Rich-text middleware preserves signed request bytes. No anonymous privileged execution policy exists.

Internal events require a deployment-code provider registration with its own authorization callback, a matching configured subscription, company/environment match and input schema. No native Business Suite provider is installed. JSON cannot register a provider.

Delay and Wait Until persist wakeups and release the worker. Optional event keys allow an authorized user to request resume; possession of a key alone grants no access. Event waits time out if no authorized resume occurs. Loop deadlines use separate durable timeout waits. These contracts prepare for Phase 5 without implementing an approval engine.

## Identity, retries, audit and retention

Identity policies are initiating user, explicitly delegated workflow owner, or a centrally managed scoped service user. Only the owner may delegate owner execution; choosing a service identity additionally requires environment administration and an active non-admin central access policy. Background triggers require owner delegation or the approved service policy.

Every action and resume rechecks company membership, active account, environment, module entitlement/governance, view/execute permissions, applicable record scope and current central execution-request action. Revocation affects future actions, including scheduled work. Shared identities do not bypass tenant checks. All run/detail/control queries are scoped to the current company, environment and authorized ownership.

Transient timeouts retry with bounded exponential backoff and deterministic bounded jitter. Invalid configurations and authorization failures are permanent. Error branches and explicit continue policies can handle failures. Failed steps and lease exhaustion create dead-letter records. Manual retry is available only for transactionally idempotent handlers, before the run deadline and before downstream failure routing has committed; otherwise explicitly re-run/reconcile. Retrying a failed sibling preserves an already persisted wait. Re-run requires confirmation and explicitly uses the current active publication, which may differ from the inspected version.

Final failures create a real in-app notification/delivery record for an active owner who still belongs to the company. No email or external notification is sent. Ordinary worker logs contain job/result/worker metadata, not payloads or raw database errors. Correlation IDs, identity, errors, attempts and state transitions are persisted in the execution audit timeline. History APIs are read-only; administrative retry/cancel actions append events. Both runtime export controls revalidate the current module export action through a server endpoint, including after revocation; view access alone does not grant export.

The existing workflow retention setting controls payload purging (1–365 days, default 30). The worker clears expired run inputs, variables, expanded plans, step input/output/local context and structured-log payloads while preserving metadata and audit events. Retention queries select eligible records by their own saved-version policy so long-retention runs do not block shorter policies. Old webhook replay records are removed only after their signature timestamps can no longer be accepted.

## Operational UI and API

Routes inside Power Apps:

- `/power-apps/automations/:resourceId/runtime`: saved-version review, validation, publication, activation/pause/archive, identity/capacity policy, manual input and explicit trigger configuration/rotation.
- `/power-apps/automations/executions`: persisted counts, running/waiting/completed/failed/cancelled, duration/failure rate/queue depth, filters and pagination.
- `/power-apps/automations/executions/:runId`: immutable version graph, current/executed/skipped/failed nodes, loop instances, attempts, input/output inspection, audit timeline, correlation ID, cancellation, safe retry, confirmed re-run and sanitized export.

The Phase 2.B `WorkflowDebugger` is reused in runtime mode. It shows real history, never simulator fixtures. Desktop and mobile layouts were exercised in a real authenticated browser with an isolated API and actual worker loop.

API families (under `/api/v1/power-apps`):

- `automations/{id}/runtime` and POST `runtime/{validate|publish|activate|pause|archive}`.
- POST `automations/{id}/publish`, POST `automations/{id}/execute` (202).
- PUT `automations/{id}/runtime-limits`.
- GET `automations/{id}/triggers`, PUT `automations/{id}/triggers/{kind}`, POST webhook `rotate`.
- POST `hooks/{opaque-id}` for signed ingress only.
- GET `executions`, GET `executions/{id}` and authorized `executions/{id}/export`, POST `cancel|retry|rerun|resume`.
- GET `runtime/health` for authorized operational administrators: actual worker/scheduler liveness, queue/leases, oldest due job and scoped dead letters. Internal worker rows remain inaccessible through ordinary ORM user reads; this endpoint returns only aggregate liveness.

Validation/publication take an expected draft version. No runtime endpoint exposes raw database operations or editable histories.

## Deployment and operation

1. Review the additive migration and back up the target database through normal deployment procedures. Test the migration on a production-like isolated database/branch. No production database was changed during this implementation.
2. Deploy API and worker code together against the existing PostgreSQL database. Apply `backend/venv/Scripts/python.exe -m alembic upgrade head` from `backend`, using the normal migration credentials/direct connection. Production startup should follow the repository's explicit migration policy.
3. Start one or more supervised worker processes from `backend`:

```powershell
venv/Scripts/python.exe -m app.apps.power_apps.worker --poll-seconds 1
```

Use the same database, stable encryption configuration and installed modules as the API. Configure process restart, termination grace of at least the poll interval plus the bounded handler/DB timeout, and liveness monitoring. Long-lived workers belong on an application/worker host; a serverless HTTP request is not the durable worker. Increase replicas within measured database capacity and quota limits; do not infer production capacity from the local benchmark.

4. Open the runtime page for a supported saved draft. Validate, review identity/input/capacity policy, publish, then explicitly activate. Configure each schedule/webhook/subscription intentionally. Existing drafts are never activated by deployment.
5. Check operational health and a small non-business-data manual run. Investigate failures through the run page/dead letters. Pause ingress before maintenance if needed; accepted queue records survive restarts. A disabled environment or revoked identity stops future actions.
6. Rotate webhook secrets through the authorized control. Preserve the application's encryption key as required by the existing encrypted-provider infrastructure; application-key rotation needs a corresponding secret migration/reconfiguration plan.

No new package dependency or queue service is required. Deployment configuration is the existing environment plus the three validated Power Apps quota settings above. A credential-free worker override example is provided in [backend/deployment/power-apps-worker.env.example](../backend/deployment/power-apps-worker.env.example).

## Verification and measured limits

Verified results:

- **189 passed** in the PostgreSQL Power Apps, authoring, runtime, migration and company-security regression suite.
- **1 additional compiler regression passed** for parallel-loop shared-variable rejection and sequential acceptance.
- **2 passed** in the independent PostgreSQL process-crash/replacement-worker and multi-session load suite.
- **25 passed** in the mocked-browser editor/recovery/responsive/performance suite, including the 250-node canvas.
- **19 authoring live cases verified**: 18 passed in the combined regression run; Scenario A then passed a clean rerun after a temporary editor hot-reload error was corrected.
- **5 runtime live cases passed**, including reviewed publication/activation, real history/export, wait cancellation, safe retry, confirmed re-run, signed ingress, schedules, reviewer/tenant isolation and independent loop-instance selection.
- TypeScript, Power Apps ESLint and the production frontend build passed. Existing large-bundle warnings remain.

Artifacts: [desktop debugger](qa/power-runtime/execution-debugger.png), [mobile dashboard](qa/power-runtime/executions-mobile.png), [sanitized execution report](qa/power-runtime/execution-report.json), [load measurements](qa/power-runtime/load-measurements.json) and [process recovery measurements](qa/power-runtime/recovery-measurements.json).

The final full backend log is `.tmp/power-runtime-complete.log`; workload/process results are `.tmp/power-runtime-benchmark-verified.log`. The latest runtime UI verification is `.tmp/power-runtime-final-live.log`. Tests use disposable `business_suite_*_test` PostgreSQL databases, generated isolated schemas, or temporary SQLite browser fixtures; destructive test setup is guarded against the configured application database.

Coverage includes requested scenarios A–J: persisted simple runs; exact conditional routing; schedule duplicate prevention; durable waits/resume; an actual killed worker process during a controlled handler and fenced recovery in a replacement process; transient failure/backoff; parallel joins including failed siblings; tenant/RBAC isolation; concurrent leases/queue integrity; and published-version integrity during draft edits. Additional checks cover webhook signatures/replay/rotation, malformed schemas, secret/prototype/expression guards, service-policy revocation, loop expansion/deadlines, immutable snapshots, safe retries, retention and tenant fairness.

The load harness runs on a shared development host with other isolated verification processes, rather than an exclusively reserved production host. It measures batches of 10, 50 and 100 submitted three-step runs, plus 500 and 1,000 queued one-step runs, with eight worker threads using independent PostgreSQL sessions. Admission remains capped by the configured environment/tenant limits; these are not claims of 100/1,000 simultaneously running workflows. It records enqueue/processing time, queue waits, throughput, query count/aggregate client query wall time, worker CPU, process RSS, retry count and error rate. Database-server CPU is not measured. The recovery test explicitly expires the crashed lease to avoid a 30-second test sleep; it does not claim a shorter production visibility timeout.


Recorded local results (eight worker threads, independent database sessions):

- 10 queued runs, 3 step(s) each: enqueue 1.93s; processing 5.64s; 1.77 runs/s; queue-wait p95 2.95s; error rate 0%.
- 50 queued runs, 3 step(s) each: enqueue 8.18s; processing 30.67s; 1.63 runs/s; queue-wait p95 27.22s; error rate 0%.
- 100 queued runs, 3 step(s) each: enqueue 16.60s; processing 60.26s; 1.66 runs/s; queue-wait p95 55.53s; error rate 0%.
- 500 queued runs, 1 step(s) each: enqueue 80.51s; processing 107.97s; 4.63 runs/s; queue-wait p95 107.17s; error rate 0%.
- 1,000 queued runs, 1 step(s) each: enqueue 157.85s; processing 231.37s; 4.32 runs/s; queue-wait p95 227.13s; error rate 0%.

The benchmark process RSS ended at 425.7 MiB. CPU/RSS refer to the Python benchmark process, including enqueue work and worker threads; aggregate query wall time can exceed elapsed time because requests overlap. All measured successful jobs had one attempt; transient retry behavior is covered separately. The killed-handler run recovered to completed in 4.90s after explicitly expiring the lease, with attempts start=2, set=1, log=1 and four total claims. No uncommitted output survived the crash.

The previously documented legacy AI operator fixture failures and unrelated repository-wide PMS/InternHub failures are outside this change. The passing scoped suites do not certify every Business Suite module or a production concurrency SLA.

## Phase 4 boundary

Phase 3 supplies durable orchestration, least-privilege dispatch, immutable publications, retry/idempotency/wait contracts and real operational history for the registered local executors. Phase 4 must implement connector authorization, hardened network/SSRF adapters, credential vault resolution/rotation, connector input/output schemas, real service-specific idempotency, uncertain-write reconciliation and explicit provider registrations. Unsupported connectors/native actions remain blocked until their actual server-side integrations are implemented and tested. Approvals remain a later phase.
