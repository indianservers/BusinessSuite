# Interns Hub

A domain-independent, separately deployable, mobile-first intern product for repeated customer installations. It uses the **same HRMS backend, database, employee accounts, organization structure, and attendance records** as BusinessSuite. Do not deploy another backend or copy the database.

## Local development

From this directory run `npm ci` and `npm run dev`. The app opens on port 5178. `/api` proxies to the existing backend at port 1534; override `HRMS_API_PROXY` to point to another development backend.

For isolated visual QA, run `backend/venv/Scripts/python.exe backend/scripts/serve_interns_hub_qa.py` from the repository root and set `HRMS_API_PROXY=http://127.0.0.1:1548` before starting Vite. This creates a disposable SQLite database in a temporary directory and never connects to the HRMS database. The QA-only login is `intern@example.com` / `InternHub@123`. These credentials are not installed in the real application.

## Separate subdomain deployment

1. Deploy the existing backend changes, with HRMS enabled in `INSTALLED_APPS`. Run its normal migration command, `alembic upgrade head`, against the existing shared database. Both migration directories include the Interns Hub tables.
2. Create a separate frontend deployment whose root directory is `frontend/interns-hub`. Install with `npm ci`, build with `npm run build`, and serve `dist`. Node 22 is supported.
3. Configure this installation by editing `dist/config.js` after building: set `apiBaseUrl` to its existing HRMS API root and `hrmsLoginUrl` to its HRMS admin sign-in URL. The same compiled build can be deployed to any number of customer domains with different config files. Serve `config.js` with `Cache-Control: no-store`. As a build-time alternative, set `VITE_API_BASE_URL=https://YOUR_EXISTING_BACKEND/api/v1` and `VITE_HRMS_URL=https://YOUR_HRMS_DOMAIN/hrms/login` before building. These are public URLs, not secrets. Do not put database credentials or backend secrets in this deployment.
4. Add the exact intern origin (for example `https://interns.example.com`) to the existing backend's `BACKEND_CORS_ORIGINS`. Keep all existing origins. Configure the subdomain on this frontend deployment with HTTPS.
5. Configure SPA rewrites to `index.html` for client routes. A Vercel configuration is included. If a same-origin reverse proxy is preferred, proxy `/api` to the existing backend and use `/api/v1` as the API base.
6. The backend needs persistent shared storage for protected submission uploads. Hub uploads live in `intern-hub-private` beside `UPLOAD_DIR`, outside the publicly mounted upload directory, and are served through authorized download endpoints. All backend replicas must use the same persistent filesystem volume. Serverless ephemeral storage is insufficient for durable uploads; use an appropriate shared storage implementation before deploying there. The existing backend upload limit is respected (maximum 50 MB).

The frontend root has its own package manifest, lockfile, environment example and build. It does not include or import the HRMS frontend bundle. No customer domain is hardcoded or registered. Each installation uses its existing HRMS deployment and database; the runtime config does not create new database tenants or a second backend. No production deployment is created automatically by this change.

## HRMS setup and administration

Use the existing HRMS admin login, then open `/hrms/interns-hub` to assign tasks, review submissions, read daily reports, publish learning modules, issue certificates, and answer support requests.

Create an employee with employment type `Intern`, assign department/designation/reporting manager, and create or link a user account. Newly provisioned intern accounts receive the `intern` role. Existing `employee` accounts linked to an active intern also work. The employee status must be Active or Probation. Admin and manager accounts cannot use the intern portal. Reporting managers manage only their own interns; HR administrators retain their normal management scope.

The Hub profile reads organization details directly from HRMS. Personal contact/profile changes write back to the same employee record. Attendance writes to the shared HRMS attendance table. Internship-specific workflow tables reference the existing employee IDs.

## Access and content rules

Intern login uses the existing password, lockout, IP policy and MFA implementation. Tokens carry an `interns_hub` restriction, including refresh and MFA-issued tokens, and cannot access HRMS APIs. The server checks active intern eligibility on every portal request, so changing employee status/type removes Hub access immediately. Each intern sees only their own tasks, submissions, reports, files and certificates. The leaderboard exposes names and aggregate metrics only within the intern's department.

Assessment answers are scored on the server and answer keys are not sent to interns. Final internship certificates require every assigned task to be reviewed as complete, and are issued by HRMS staff. Downloads are generated PDFs. Empty production accounts show empty states; mockup names and scores exist only in the explicit QA script.

## Verification

`npm run build` builds the independent app. From the repository root, run `backend/venv/Scripts/python.exe -m pytest backend/tests/test_interns_hub.py backend/tests/test_auth.py backend/tests/test_employees.py -q`. Desktop and mobile reference screenshots are in `docs/qa/interns-hub`.

## Public applications

`/apply` is the public, mobile-first application page; `/login` is the intern login, and `/application-status` verifies the applicant's email/password before displaying their decision. Applicants submit details only: there is no resume or document-upload field. Save Draft stores non-credential form fields in browser session storage; passwords and identity numbers are excluded.

Applications remain Pending without a user or employee account. HR staff review them at `/hrms/interns-hub/applications`, assign branch, department, designation, manager and joining date, and approve or reject them. Approval creates an HRMS employee, a restricted intern account using the applicant's already-hashed password, and a unique `IH-…` intern ID. The applicant can then sign in with their chosen credentials and view that ID. No email delivery service is assumed. Application status is checked in the portal.

ID numbers are encrypted using a purpose-specific key derived from the existing backend secret. Staff listings show only the last four characters. Review notes are visible to the applicant. The application database migration follows the initial Interns Hub migration.
