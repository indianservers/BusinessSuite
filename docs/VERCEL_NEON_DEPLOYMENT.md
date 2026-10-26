# Vercel + Neon deployment

The repository deploys as one Vercel project with two services, `frontend` (Vite) and `backend` (FastAPI), configured in the root `vercel.json`. Import with repository root `./`. Private S3-compatible storage and production environment variables must be configured before live deployment can be verified.

Public routing preserves request paths: `/api/*`, `/health` and `/uploads/*` reach the backend; all remaining paths reach the frontend, whose own rewrite supports SPA deep links. Browser API requests use `/api/v1`. Neither service makes server-side calls to the other, so no service bindings are declared. A static browser bundle cannot consume runtime-only internal service URLs. The legacy standalone Flask inventory application is excluded; integrated inventory remains part of FastAPI.

Run `npx vercel dev -L` from the repository root to test service routing locally. The existing `start-both.cmd` remains available for the independent local development servers.

Neon credentials supplied for this setup are saved only in ignored `.local/neon.env`. These are not automatically uploaded to Vercel. Set `DATABASE_URL` from that file in the project environment; use `DATABASE_URL_UNPOOLED` only for provisioning. Do not import all database aliases into the backend `.env` (Pydantic rejects unknown settings). Never expose database variables as `VITE_*`.

Both `BACKEND_PUBLIC_URL` and `FRONTEND_PUBLIC_URL` must be the same deployment origin; set `BACKEND_CORS_ORIGINS` to that exact origin. The root configuration intentionally declares no cron schedule pending confirmation of the required frequency and hosting plan.

## Resources

| Resource | Configuration |
| --- | --- |
| Frontend service | `frontend`, Vite preset, public SPA at `/` |
| Backend service | `backend`, FastAPI preset, Python 3.12, public `/api/*` |
| Neon PostgreSQL | Separate production and preview branches; choose a region near the API |
| Private object storage | S3, Cloudflare R2, or compatible provider; use separate bucket/prefix for previews |
| Scheduler | Choose a schedule explicitly; an external scheduler can call the authenticated endpoint |

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

For private Vercel Blob, set `STORAGE_BACKEND=vercel_blob` and the server-only `BLOB_READ_WRITE_TOKEN`. The backend writes private blobs through the Python SDK. Existing permission-checked APIs issue expiring, file-scoped links to `/api/v1/files/blob`; that endpoint validates the signature, purpose, audience, expiry and storage path before retrieving the private content. The Blob token never reaches browser code. The response uses private/no-store caching and attachment disposition. Existing record file references remain `/uploads/...` and are normalized when edited. S3-compatible storage remains supported as an alternative.

Set `STORAGE_BACKEND=s3`, bucket, region, credentials and optional custom endpoint. For AWS S3, omit the custom endpoint and use the actual region; for R2, use the account endpoint and region `auto`. Keep public access blocked. Scope runtime credentials to the chosen prefix with object Get/Put permissions and required multipart permissions; the deployment-check script also needs Delete permission for its temporary probe.

The upload and document/export paths persist files before returning their records. Download endpoints retain their existing permissions and redirect to short-lived signed object URLs. Existing `/uploads/...` record references are signed in API JSON responses; edited records normalize signed links back to durable references so expiry is not saved into the database. Public static upload serving is disabled in S3 mode. Local disk under `/tmp` is staging only. Form 16 merging and resume parsing can retrieve private inputs on a different instance.

Downloads use expiring links to the backend's `/api/v1/files/blob` endpoint, which retrieves private objects server-side. Configure backend CORS with the exact frontend origin. Bucket CORS is needed only for clients that access storage directly. Keep the bucket private. Example AWS/R2 CORS rule for direct storage clients:

```json
[{"AllowedOrigins":["https://YOUR-APP.vercel.app"],"AllowedMethods":["GET","HEAD"],"AllowedHeaders":["*"],"ExposeHeaders":["Content-Disposition"],"MaxAgeSeconds":3600}]
```

The current multipart UI accepts a total of **3 MB** per request, leaving room for multipart overhead under Vercel's payload limit. Match `VITE_MAX_UPLOAD_MB=3` and backend `MAX_UPLOAD_SIZE_MB=3`; large generated exports download directly from storage. Larger client uploads require a separate direct-upload flow and are outside this multipart contract. Local development can continue using local storage.

## Scheduled work

No schedule is enabled by default. To schedule `GET /api/v1/internal/cron`, add a top-level `crons` entry to the root `vercel.json` after choosing the cadence. Set a random `CRON_SECRET` of at least 32 characters; Vercel sends it as `Authorization: Bearer ...`. Missing or incorrect authorization is rejected. For Hobby, use a supported cadence or an external scheduler with the same authenticated request. A daily schedule is insufficient to reliably drain bounded batches for a larger organization.

The endpoint processes at most 25 employees per invocation. Six-minute PostgreSQL leases (longer than the configured five-minute function limit) prevent overlapping batches, committed cursors resume work, failed/expired leases retry, and the leave ledger prevents duplicate credit after a crash between business commit and progress recording. Pending days are resumed before current work; dates use Asia/Kolkata. Realtime event retention is seven days. Use `GET /api/v1/internal/jobs` with an authorized settings administrator to inspect status, attempts and errors. Do not run the old Celery Beat leave scheduler alongside this dispatcher.

## Realtime collaboration

Set `REALTIME_TRANSPORT=database` (automatic on Vercel). Authorized browser sessions poll the durable, cursor-based event feed about every three seconds, backing off in hidden tabs. Task/project/comment changes propagate across separate API instances. Each feed request recalculates project/workspace access; removing membership stops access to subsequent events. Appends serialize commit order to avoid skipping a delayed event. A periodic data refresh recovers from missed publishing or expired event retention. This transport does not depend on long-lived sockets or a process-local message hub. Local deployments may retain `websocket` mode.

## Build and validation

PMS Google login uses Firebase Authentication. Configure `FIREBASE_PROJECT_ID` and `FIREBASE_WEB_CONFIG` (the public Firebase web configuration JSON containing `apiKey`, `authDomain`, `projectId` and `appId`) on the backend and authorize the app hostname in Firebase. The PMS login page reads the public configuration from `/api/v1/auth/firebase/config`. Only existing active accounts with PMS access can sign in; Google login does not provision accounts or bypass module permissions, IP policies, account lockout, configured organizational SSO, or application MFA. Intern application sessions remain separate from staff login.

The runtime dependency list excludes unused scientific/native PDF packages; optional packages remain in `requirements-optional.txt`. Private storage uses boto3. CI explicitly uses a lower bcrypt work factor only for disposable test fixtures, while separately asserting the production hashing default remains at least 12 rounds. Production code does not read the test-only switch. GitHub Actions validates the dependency installation on Linux/Python 3.12, PostgreSQL migrations/tests and the frontend production build. Cloud preview validation remains necessary for Vercel bundle size, cold starts, the actual Neon pooler, S3 permissions and CORS, configured third-party providers, and plan limits.

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

This supports both S3-compatible storage and Vercel Blob. It checks the actual migration head, persists a temporary private object, removes local staging, verifies the signed API download and backend CORS, rejects unsigned API and direct object access, and runs authenticated API smoke requests. `--api-url` selects the API origin for the signed download as well as smoke requests. The API must share the shell's signing secret, storage configuration and upload path. The checker never prints credentials or signed URLs; it removes its temporary object. Keep bootstrap credentials available in the secure shell for smoke login, then remove the bootstrap password from the deployed API environment because cold starts no longer need it.

To verify suite tables and columns separately from cloud storage, run `venv/Scripts/python.exe scripts/verify_postgresql_schema.py --suite-only`. The separately deployed legacy Inventory/POS database is explicitly excluded by this option.

Live HTTP checks allow 60 seconds per request for serverless cold starts. Override this with `--timeout SECONDS` when needed. Failures report the check or exception type without printing provider URLs or credentials.

Before promoting a preview, run authenticated smoke checks and file upload/download after a fresh instance, two-session task collaboration, member removal, cron duplicate/retry tests, cross-module handoffs, payroll and PDF exports. Use a dedicated Neon preview branch and storage prefix.

## References

- https://vercel.com/docs/frameworks/backend/fastapi
- https://vercel.com/docs/functions/runtimes/python
- https://vercel.com/docs/functions/limitations
- https://vercel.com/docs/cron-jobs/manage-cron-jobs
- https://neon.com/docs/connect/connection-pooling
