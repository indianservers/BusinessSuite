# Vercel and Neon readiness

Completed locally: 22 October 2026. Cloud deployment has not been performed because the Vercel, Neon and object-storage resources are not configured yet.

Implemented:

- Separate Vite and FastAPI Vercel project configurations, Python 3.12 pin, SPA routing, deployment environment templates and packaging exclusions.
- Private S3-compatible persistence for employee documents/photos, logos, resumes, document generation, tax proofs, PMS attachments, payroll/statutory exports, PDFs and analytics exports. Permission-checked downloads use signed redirects; JSON file references receive expiring links that normalize back to durable references on edits. Local files are staging only.
- Authenticated cron execution with PostgreSQL leases, bounded employee batches, durable progress, failed/expired-job retries, duplicate-credit protection and status monitoring. The included five-minute schedule requires Vercel Pro or an external scheduler.
- PostgreSQL-backed collaboration events, access checks on every feed request, commit-ordered cursors, cross-instance browser synchronization and fallback refresh. Vercel deployments do not depend on an in-memory WebSocket hub.
- Serverless startup skips schema/bootstrap writes; a separate provisioning command handles migration and seed-free bootstrap. Neon pooler connections use NullPool and avoid session startup options and prepared statements.
- Bounded, retry-safe baseline DDL avoids requiring elevated migration lock settings on managed PostgreSQL. Interrupted migration recovery preserves existing rows.
- Linux/Python 3.12/PostgreSQL CI, production frontend build checks and a credential-safe live deployment preflight command.

## Local verification

| Check | Result |
| --- | --- |
| Affected backend regression | 53 passed |
| Storage, configuration, scheduler and crash resilience | 11 passed (includes overlap with the regression run) |
| Private PMS file access and membership revocation | 2 passed |
| Positive and unsafe serverless configurations | 8 passed |
| Interrupted migration resume | 1 passed |
| Unique backend checks across these runs | **67 passed** |
| Unique real-API browser checks | **10 passed**, including 59 module pages, invitation/role/removal flow, drag-and-drop, two API instances and oversized-upload handling |
| Production frontend build | Passed |
| Main and standalone Inventory PostgreSQL schema verification | Passed; no expected tables or columns missing |

Browser failures in the initial run were corrected: the new test used PUT instead of the existing PATCH task endpoint, and the multi-session invitation test needed an absolute navigation URL and a timeout suitable for its complete flow. Targeted reruns passed. The machine-readable [results](docs/migrations/vercel-readiness-results.json) retain the latest result for each check.

S3 tests use boto3 against a local S3 emulator; they validate durable retrieval after local-file loss, signed responses, reference renewal and endpoint permissions. They do not verify actual cloud credentials, bucket CORS or provider permissions. The deployment preflight checks those when real resources exist.

## Deployment handoff

Follow [the deployment guide](docs/VERCEL_NEON_DEPLOYMENT.md). Create the two Vercel projects, a Neon database/preview branch and private S3-compatible storage; configure environment variables and CORS; run provisioning through Neon's direct URL; then validate a Vercel preview with the preflight command and real providers before promoting it.

The integrated SRM/FAM inventory routes are included. The separately retained legacy Flask compatibility service is not packaged into the FastAPI deployment.

Local raw evidence is in `.local/vercel-regression.xml`, `vercel-resilience.xml`, `vercel-cloudfiles.xml`, `vercel-configuration.xml`, `vercel-migration-resume.xml`, `vercel-browser-first-report.json`, `postgres-playwright-results.json` and `vercel-build-final.log`. The first Linux run passed 531 checks and exposed one hard-coded Windows path in the inventory source audit. That path now resolves relative to the repository, and its focused PostgreSQL regression passes. GitHub Actions runs the corrected full suite independently after push; CI uses fast bcrypt fixture hashing and separately verifies the unchanged production work factor.
