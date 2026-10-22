# Vercel + Neon deployment

The repository supports two Vercel projects, private S3-compatible uploads, resumable cron batches and collaboration synchronized through PostgreSQL. Cloud projects and credentials must be configured before live deployment can be verified.

## Resources

| Resource | Configuration |
| --- | --- |
| Frontend Vercel project | Repository root directory `frontend`, Vite preset |
| API Vercel project | Root directory `backend`, FastAPI preset, Python 3.12 |
| Neon PostgreSQL | Separate production and preview branches; choose a region near the API |
| Private object storage | S3, Cloudflare R2, or compatible provider; use separate bucket/prefix for previews |
| Scheduler | Included five-minute Vercel Cron configuration requires Pro; an external scheduler can call the same endpoint |

Use runtime environment templates `backend/.env.vercel.example` and `frontend/.env.vercel.example`. Set actual values in Vercel environment settings, never in Git. All `VITE_*` values are public.

## Database provisioning

Use Neon's pooled connection URL, with `sslmode=require`, for the deployed API. The app uses SQLAlchemy NullPool in serverless mode, disables prepared statements, and omits session startup options for the pooler.

Provision once from a secure shell before enabling traffic. From `backend`, set `DATABASE_URL` to the **direct** Neon URL, set `BOOTSTRAP_ADMIN_EMAIL` and a strong `BOOTSTRAP_ADMIN_PASSWORD`, and keep `SEED_DEMO_DATA=false`:

```powershell
venv/Scripts/python.exe scripts/provision_deployment.py
```

Use the shell's Python interpreter on Linux. This runs the migration chain and idempotent identity/module bootstrap, including the shared event and scheduled-job tables. It does not create/drop a database and does not import demo records. The baseline uses bounded, retry-safe DDL batches, avoiding elevated lock settings on managed PostgreSQL. Run one provisioner at a time. Do not use `create_db.py` to create databases inside Neon.

For deployment, keep `SERVERLESS=true`, `DATABASE_AUTO_MIGRATE=false` and `SEED_DEMO_DATA=false`. Serverless lifespan startup performs no migrations, schema inspection, demo seeding or bootstrap writes. Stable, explicit signing secrets and scheduler credentials are required; invalid configuration fails startup.

## Private uploads and generated exports

Set `STORAGE_BACKEND=s3`, bucket, region, credentials and optional custom endpoint. For AWS S3, omit the custom endpoint and use the actual region; for R2, use the account endpoint and region `auto`. Keep public access blocked. Scope runtime credentials to the chosen prefix with object Get/Put permissions and required multipart permissions; the deployment-check script also needs Delete permission for its temporary probe.

The upload and document/export paths persist files before returning their records. Download endpoints retain their existing permissions and redirect to short-lived signed object URLs. Existing `/uploads/...` record references are signed in API JSON responses; edited records normalize signed links back to durable references so expiry is not saved into the database. Public static upload serving is disabled in S3 mode. Local disk under `/tmp` is staging only. Form 16 merging and resume parsing can retrieve private inputs on a different instance.

Configure bucket CORS with the exact frontend origins, methods `GET` and `HEAD`, allowed headers `*`, and expose `Content-Disposition`. This is required for browser downloads that follow API redirects. Do not make the bucket public. Example AWS/R2 CORS rule:

```json
[{"AllowedOrigins":["https://YOUR-APP.vercel.app"],"AllowedMethods":["GET","HEAD"],"AllowedHeaders":["*"],"ExposeHeaders":["Content-Disposition"],"MaxAgeSeconds":3600}]
```

The current multipart UI accepts a total of **3 MB** per request, leaving room for multipart overhead under Vercel's payload limit. Match `VITE_MAX_UPLOAD_MB=3` and backend `MAX_UPLOAD_SIZE_MB=3`; large generated exports download directly from storage. Larger client uploads require a separate direct-upload flow and are outside this multipart contract. Local development can continue using local storage.

## Scheduled work

`backend/vercel.json` invokes `GET /api/v1/internal/cron` every five minutes. Set a random `CRON_SECRET` of at least 32 characters; Vercel sends it as `Authorization: Bearer ...`. Missing or incorrect authorization is rejected. For Hobby, remove the five-minute Vercel cron entry and use an external scheduler with the same authenticated request. A daily schedule is insufficient to reliably drain bounded batches for a larger organization.

The endpoint processes at most 25 employees per invocation. Six-minute PostgreSQL leases (longer than the configured five-minute function limit) prevent overlapping batches, committed cursors resume work, failed/expired leases retry, and the leave ledger prevents duplicate credit after a crash between business commit and progress recording. Pending days are resumed before current work; dates use Asia/Kolkata. Realtime event retention is seven days. Use `GET /api/v1/internal/jobs` with an authorized settings administrator to inspect status, attempts and errors. Do not run the old Celery Beat leave scheduler alongside this dispatcher.

## Realtime collaboration

Set `REALTIME_TRANSPORT=database` (automatic on Vercel). Authorized browser sessions poll the durable, cursor-based event feed about every three seconds, backing off in hidden tabs. Task/project/comment changes propagate across separate API instances. Each feed request recalculates project/workspace access; removing membership stops access to subsequent events. Appends serialize commit order to avoid skipping a delayed event. A periodic data refresh recovers from missed publishing or expired event retention. This transport does not depend on long-lived sockets or a process-local message hub. Local deployments may retain `websocket` mode.

## Build and validation

The runtime dependency list excludes unused scientific/native PDF packages; optional packages remain in `requirements-optional.txt`. Private storage uses boto3. GitHub Actions validates the dependency installation on Linux/Python 3.12, PostgreSQL migrations/tests and the frontend production build. Cloud preview validation remains necessary for Vercel bundle size, cold starts, the actual Neon pooler, S3 permissions and CORS, configured third-party providers, and plan limits.

Local checks:

```powershell
Push-Location backend
venv/Scripts/python.exe -m pip install -r requirements-test.txt
venv/Scripts/python.exe scripts/run_postgres_tests.py -q --tb=short
Pop-Location
Push-Location frontend
npm ci
npm run build
Pop-Location
```

`test_serverless_deployment.py` exercises durable object storage through the AWS SDK and a local S3 emulator, feed access/cross-session delivery, scheduler retries and Neon settings. The S3 emulator does not certify real cloud credentials. The opt-in `serverless-collaboration.spec.ts` exercises separate API instances; run the browser QA server with `REALTIME_TRANSPORT=database`, then `qa/serverless_second_instance.py`, and set `SERVERLESS_COLLABORATION_QA=1` for Playwright.

The separately retained legacy Flask Inventory service is not packaged into the FastAPI function. The integrated SRM/FAM inventory routes run within this API. Legacy Flask compatibility routes require their own service if enabled.

After configuring the real services, run from `backend`:

```powershell
venv/Scripts/python.exe scripts/check_deployment.py --api-url https://YOUR-API.vercel.app
```

This checks the actual migration head, a temporary private object round trip, signed/unsigned access, bucket CORS and authenticated API smoke requests. It never prints credentials or signed URLs; its temporary object is removed. Keep bootstrap credentials available in the secure shell for smoke login, then remove the bootstrap password from the deployed API environment because cold starts no longer need it.

Before promoting a preview, run authenticated smoke checks and file upload/download after a fresh instance, two-session task collaboration, member removal, cron duplicate/retry tests, cross-module handoffs, payroll and PDF exports. Use a dedicated Neon preview branch and storage prefix.

## References

- https://vercel.com/docs/frameworks/backend/fastapi
- https://vercel.com/docs/functions/runtimes/python
- https://vercel.com/docs/functions/limitations
- https://vercel.com/docs/cron-jobs/manage-cron-jobs
- https://neon.com/docs/connect/connection-pooling
