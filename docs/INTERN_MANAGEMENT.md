# HRMS Intern Management with PMS execution

Implemented October 25, 2026. Intern-facing pages remain in the separately deployable `frontend/interns-hub` application. Administrative pages live in the existing HRMS application and use its existing login.

## Navigation and record ownership

The expandable **Intern Management** navigation contains five pages:

- `/hrms/interns/dashboard`: scoped program totals, PMS execution totals, recent PMS activity, deadlines and batch overview.
- `/hrms/interns/batches`: batches, HRMS intern directory, membership history, onboarding and existing learning/support tools.
- `/hrms/interns/tasks`: create or reuse a PMS task, preview recipients, distribute assignments, retry delivery and manage recurrence.
- `/hrms/interns/reviews`: HRMS daily reports and the shared PMS submission/evidence/review panel.
- `/hrms/interns/performance`: server-derived performance, batch comparison, completion decisions and certificate issuance.

HRMS owns employees, department, designation, reporting manager, attendance, approved leave, program batches, memberships and completion decisions. PMS owns the task description, per-assignee execution, evidence assets, submission versions, review decisions, scores and activity history. Both HRMS and PMS review surfaces invoke the same PMS work service. The standalone Interns Hub uses adapters over that service; it does not write the historical Hub task/submission tables.

`PMSTaskAssignee` now holds independent execution state, deadline, reviewer and maximum score. A shared task remains one `PMSTask`; adding 10,000 interns does not create 10,000 task descriptions. Ordinary PMS assignee edits preserve existing intern execution records. PMS completion commands reject an unfinished intern approval workflow.

## Authorization rules

- Interns: active HRMS-linked intern account; their own assignments, evidence, submissions and certificates only. Portal tokens cannot call general HRMS/PMS APIs or intern administration. Interns cannot submit scores or approval states.
- Ordinary employees: no Intern Management administration. Existing PMS membership can independently permit their own PMS work.
- HRMS managers and leads: explicit HRMS/PMS permission plus their reporting/batch/department scope. Membership and historical records remain scoped to the existing company boundary.
- HR administrators: organization-scoped management. This does not create PMS review permission.
- PMS project managers/organization administrators: the narrow HRMS Intern Management surface can be used when the backend grants scoped program access; other HRMS pages remain protected.
- PMS reviewers: existing project `approve` permission and reviewer delegation are checked for every decision. A project viewer or a role named Manager cannot bypass these checks. Existing PMS superuser rules still apply within the tenant.
- Evidence: only its owner or a PMS approver can download it. Local static uploads reject the PMS work/legacy evidence namespaces, so a known file path cannot bypass the API. Evidence metadata/deletion and completed review decisions cannot be overwritten through ordinary PMS file/review endpoints.

The API applies company/tenant scope before pagination and counts. User-provided lists, export filters, batch references and target projects are revalidated server-side.

## Distribution and scheduling

Recipient selection supports individual interns, multiple batches, a department and the authorized program scope, with exclusions. Overlapping memberships are deduplicated. An idempotency key is unique within the organization; reusing it for different input returns 409.

Delivery processes 500 recipients per transaction. The durable job retains its cursor and failure details; retry does not reset an existing PMS assignment. Daily/weekly schedules create one new shared PMS task per occurrence. The existing authenticated `/api/v1/internal/cron` endpoint advances pending delivery jobs and due occurrences when both HRMS and PMS are enabled. Schedule errors remain visible and retryable. Configure the existing cron secret/scheduler in the deployment.

Delivery counts describe a distribution request. Execution counts describe its shared PMS task across all assignees; the UI labels this distinction. Notifications use the existing in-app notification catalog.

## Reporting, scoring and completion

Daily reports remain HRMS records and retain manager review decisions. Missing-report checks exclude weekends and approved leave, and respect weekly reporting. Reported minutes are explicitly self-reported.

Task evidence is versioned in PMS. Revisions create another submission rather than replacing the reviewed version. A reviewer must confirm evidence inspection. Only the latest eligible version can receive a new decision; earlier decisions remain immutable. Approved assignments cannot be resubmitted by the intern.

The default score weights are quality 40%, timeliness 20%, reporting 15%, task completion 15%, and communication 10%. Batch policy may change them, with server validation requiring a total of 100. Unassessed components stay unassessed and the available component weights are normalized. Counts and quality use PMS records; date/batch filters and approved leave are applied on the server. Risk labels describe explicit conditions rather than inferred browser activity.

Completion checks configured duration, approved tasks, reporting/attendance thresholds, and optional learning/final-project requirements. Selecting a different completion batch recomputes eligibility. A manager decision and server recomputation are required before issuance. The certificate is registered in the existing `EmployeeCertificate` catalog using the existing document upload service, with a unique verification ID. Issuance is idempotent.

## Migrations and historical data

Revision `pg_20261025_017_intern_pms` (and equivalent SQLite-tree revision) adds per-assignee execution columns, PMS work submission/review tables, HRMS program/history/job tables, certificate document links, and tenant-scoped learning courses. The migration preserves existing rows and can tolerate partially applied additions. An actual old SQLite schema was upgraded twice in the migration regression test. Downgrade intentionally preserves evidence/history tables.

Existing Hub task histories require explicit project/reviewer mapping through **Task Assignment → Preserve Existing Hub History**. Imports process up to 100 histories at a time, copy versions/reviews/evidence into PMS, retain original records, and record an idempotent mapping. Missing evidence blocks that task's import with a visible reconciliation error. Historical tables remain read-only archives; runtime task/performance reads use PMS. No production migration or historical import was run during this work.

## API surfaces

New HRMS APIs use `/api/v1/interns-hub/management`: access/options, paginated interns and individual performance, batch CRUD/transitions, membership operations/history, project task selection, recipient preview, distribution jobs/retry, schedules/pause/resume, daily report reviews, PMS review read models, announcements, dashboard/batch analytics, completion decisions, certificate issuance, export and historical import.

PMS APIs use `/api/v1/project-management/work`: per-assignee start, evidence upload/download, versioned submissions, immutable review and reviewer delegation. The existing PMS task page includes **Submissions & Reviews**, and `/pms/reviews` exposes the same review component used by HRMS.

Existing Interns Hub task/file/submission endpoints are compatibility adapters. Both surfaces now share the PMS submission/review request models and validation.

## Verification and evidence

The full selected regression suite passed **78 tests**, covering intern applications, intern portal behavior, program orchestration, migration retry, private static-file protection, PMS access/task composition, employees and authentication. Additional focused checks passed after the delivery metric and upload-path corrections. Main frontend TypeScript checking and the separate Interns Hub production build passed.

Browser checks used disposable SQLite data on loopback ports 1548, 5180 and 5181, through the actual HRMS and standalone intern interfaces. Verified scenarios included batch creation/lifecycle, enrollment, two-batch deduplication, task execution/submission, a revision request in HRMS, version-2 submission, approval in PMS, performance updates, selected-batch eligibility, manager completion, certificate issuance, and daily report review. Separate QA runs were used for revision and completion scenarios. Security file-upload/download cases were exercised through automated API tests.

Screenshots in `docs/qa/intern-management` cover all five pages plus revision, approval, certificate issuance, and phone layouts. The supplied references were studied from `C:/Indian Servers/Mockup images/Interns-Admin`:

- `01_admin_dashboard.png` → `dashboard-desktop.png`: six metrics, chart panels and operational/batch tables.
- `02_batches_interns.png` → `batches-desktop.png`: five metrics, tabbed directory and batch management with an action panel.
- `03_task_assignment.png` → `task-assignment-desktop.png`: focused assignment form, recipient preview and distribution table. Task editing/supporting files link to PMS.
- `04_reports_submissions.png` → `reports-reviews-desktop.png`: reports and submissions with evidence inspection through the shared PMS panel.
- `05_performance_completion.png` → `performance-desktop.png`: performance comparisons, individual evaluation and completion/certificate tabs.

Desktop evidence uses a 1680×987 viewport; phone checks use 390×844. Phone navigation scrolls without overlapping labels, filters stack, metrics use two columns, and wider tables scroll inside their panels. Document width was verified at 390px. The application page hides the student artwork on mobile and contains no résumé/document upload.

`backend/scripts/benchmark_intern_management.py` creates a disposable file database with 10,000 interns, 100 batches, 20 shared seed tasks and 10,000 seed assignments. The recorded run returned 50-row first/last directory pages in about 62/69 ms; dashboard and batch analytics took about 489/473 ms. Distribution of an additional 10,000 recipients took about 6.25 seconds in 20 chunks and created one shared task; replay was idempotent. Exact SQL counts and measurements are in `docs/qa/intern-management/benchmark.json`.

## Operational limits

- The benchmark is a single-process SQLite exercise, not PostgreSQL concurrency or production capacity certification. PostgreSQL migrations and locking behavior still need staging validation before deployment.
- Exports intentionally return an authorized page (up to 200 records). Batch comparison is capped at 200 batches and option pickers are bounded; the main directory and work queues are server-paginated.
- Cron must be configured for remaining distribution chunks and recurrence. External email/SMS delivery is not added; notifications/reminders use existing in-app records.
- Public applications retain the existing installation's onboarding setup. This change does not add a new cross-domain tenant-discovery service or move existing customer records between tenant partitions.
- HRMS daily reports remain editable records with review history; PMS task evidence/reviews have immutable version history. No browser activity is claimed as verified work time.
- The existing HRMS shell/navigation and real data replace static mockup labels/numbers. The result follows the reference layout but is not a pixel-identical screenshot reproduction.
