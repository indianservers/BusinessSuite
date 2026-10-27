# People, intern programs and work operations

The HRMS and PMS workspaces use the same employee, batch, PMS assignment and review records. The intern portal shows each intern their own work and messages.

## Entry points

- HRMS: **Intern Management → Profiles & Work** (`/hrms/interns/operations`). Starts with interns; the People filter can include other employees.
- PMS: **More → People & work management** (`/pms/people-work`). Starts with all authorized employees and interns.
- Interns Hub: **Notices & Warnings** (`/notifications`). The bell shows unacknowledged messages.
- PMS employee inbox: **More → My notices & warnings** (`/pms/my-notices`).
- Intake: **Signups & Approvals** (`/hrms/interns/applications`).

## Daily operation

1. Create a batch/group in the existing Groups & Programs workspace. Set department, program, project, primary supervisor, primary mentor, additional mentors, capacity, dates and completion policy. Existing batch task templates and recurring task distribution remain available.
2. Review applications with server-side search, status filters and pagination. Select the current page or all matching reviewable applications. Preview the common onboarding settings, then start the bulk decision operation. Individual validation failures are recorded without undoing successful approvals. Errors are paginated separately from the progress response.
3. Find people by name, employee ID, email, department, group, supervisor, account availability and employment status. Saved views are local to the current account and browser device.
4. Open **Study profile** to see HRMS details, authorized PMS assignments, progress, deadlines and warning history. Open the full HRMS profile for detailed profile editing. **Assign work to selected** carries selected employee IDs into the existing distribution workspace.
5. Use **Overdue work**, **Awaiting review**, **No supervisor**, and **Open warnings** as follow-up queues. Overview cards are organization/supervisor-scope totals; directory filters narrow the actual list.
6. Select people and change their reporting supervisor, send an in-app notice or send a warning. Use **Active accounts only** when messaging a whole filtered group. A preview shows the recipient count and sample names. Accountless/inactive recipients must be excluded before messages can be sent.
7. Recipients acknowledge receipt in their inbox. Acknowledgement does not resolve a warning. Managers record a separate resolution note; the original message and acknowledgement remain in history.

Primary mentors, additional mentors and coordinators can see assigned batches and their participants if their account already has an authorized management role and permission. PMS project permissions still control assignment/review actions. Giving someone a batch role does not grant global HRMS or PMS administration.

## Durable operations

`workforce_jobs` holds a fixed recipient snapshot, actor, organization, request key, operation, cursor and results. Notice/warning delivery and cursor advancement commit together in chunks of 250. Onboarding commits each application and cursor together, up to 25 applications per tick. Request-key retries return the original job; a different payload with the same key is rejected.

Large intake failures are kept in `workforce_job_failures` and paginated by the API. The job response includes only a bounded sample and total failure count. `workforce_messages` records each recipient's message, acknowledgement, resolution and actors. Reporting supervisor changes also write employee audit records.

Recipient scope, actor access and account eligibility are checked again while processing. Supervisor changes reject self-reporting and reporting cycles. Failed delivery/reassignment jobs stop at the failing chunk; fix the underlying issue and retry. Pending jobs resume automatically; failed jobs require an explicit retry. A completed intake operation can have individual failures, which are shown separately and can be selected again after correction.

## Deployment and workers

1. Apply migration `pg_20261026_029_workforce_ops` through the established PostgreSQL Alembic deployment workflow. The legacy migration chain also contains the equivalent revision. Both follow the existing Notes workspace migration. The existing production build migration script advances to the new head; no database changes are performed in request handlers.
2. Deploy the backend, BusinessSuite frontend and the separate Interns Hub frontend. Both frontends need the new backend routes and schema.
3. Run a persistent worker with the application's normal server-side environment:

   ```powershell
   python scripts/run_workforce_worker.py --interval 2
   ```

   Run this from `backend` on a supervised worker host. A bounded invocation is available with `--once`. The worker also continues existing task-distribution jobs and recurring assignments.

   Alternatively, invoke the existing protected `/api/v1/internal/cron` endpoint frequently with its configured `CRON_SECRET`. Each request processes bounded chunks. A low-frequency scheduler will make a 20,000-person operation slow; the persistent worker is intended for large intakes. Do not put the secret in browser code.

4. Without a worker/scheduler, the first chunk still runs and the UI offers **Process next chunk**. Closing the browser preserves progress but does not itself run remaining chunks.

Only in-app delivery is implemented here. No email, SMS or WhatsApp delivery is claimed. Production migrations, worker provisioning and deployment are separate operational steps; they are not performed by local development tests.

## Verification

Run the workforce operation/migration tests together with existing intern application, management and portal tests. Coverage includes notification ownership, acknowledgement versus resolution, employee support, reporting cycles, backup mentor scope, read-only manager restrictions, request-key deduplication, chunk retry, partial onboarding failures and a 20,000-profile paginated directory with bounded query count.

Both production frontend builds are checked. Disposable loopback browser QA exercises warning creation, profile history and intern acknowledgement at desktop/mobile sizes. The database fixture is local SQLite; migration round trips test both migration variants on SQLite. These checks are not evidence of PostgreSQL concurrency performance or 20,000 simultaneous sessions. Benchmark those workloads on a staging database and worker before the large intake.
