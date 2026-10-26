# Interns Hub

Interns Hub is a product of Indian Servers Pvt Limited. Keep customer domains, API endpoints and hosting configuration outside the application code so the product can be installed on thousands of servers. Each customer installation uses its own configured BusinessSuite backend and data; a portal deployment does not create a new tenant or database.

A domain-independent, separately deployable, mobile-first intern product for repeated customer installations. It uses the **same HRMS backend, database, employee accounts, organization structure, and attendance records** as BusinessSuite. Do not deploy another backend or copy the database.

## Local development

From this directory run `npm ci` and `npm run dev`. The app opens on port 5178. `/api` proxies to the existing backend at port 1534; override `HRMS_API_PROXY` to point to another development backend.

For isolated visual QA, run `backend/venv/Scripts/python.exe backend/scripts/serve_interns_hub_qa.py` from the repository root and set `HRMS_API_PROXY=http://127.0.0.1:1548` before starting Vite. This creates a disposable SQLite database in a temporary directory and never connects to the HRMS database. The QA-only login is `intern@example.com` / `InternHub@123`. These credentials are not installed in the real application.

## Separate subdomain deployment

1. Deploy the existing backend changes, with HRMS enabled in `INSTALLED_APPS`. Run its normal migration command, `alembic upgrade head`, against the existing shared database. Both migration directories include the Interns Hub tables.
2. Build from a complete repository checkout: from `frontend/interns-hub`, install with `npm ci` and build with `npm run build`. The portal uses the suite's shared profile component at build time; do not upload only this source folder to a cloud builder. The compiled `dist` contains its dependencies and can be served independently. Node 22 is supported.
3. Configure this installation by editing `dist/config.js` after building: set `apiBaseUrl` to its existing HRMS API root and `hrmsLoginUrl` to its HRMS admin sign-in URL. The same compiled build can be deployed to any number of customer domains with different config files. Serve `config.js` with `Cache-Control: no-store`. As a build-time alternative, set `VITE_API_BASE_URL=https://YOUR_EXISTING_BACKEND/api/v1` and `VITE_HRMS_URL=https://YOUR_HRMS_DOMAIN/hrms/login` before building. These are public URLs, not secrets. Do not put database credentials or backend secrets in this deployment.
4. Add the exact intern origin (for example `https://interns.example.com`) to the existing backend's `BACKEND_CORS_ORIGINS`. Keep all existing origins. Configure the subdomain on this frontend deployment with HTTPS.
5. Configure SPA rewrites to `index.html` for client routes. A Vercel configuration is included. If a same-origin reverse proxy is preferred, proxy `/api` to the existing backend and use `/api/v1` as the API base.
6. Submission uploads use the shared PMS work-evidence storage and permission checks. Configure the existing backend's private Vercel Blob or S3-compatible storage for serverless deployments, or a persistent upload volume for self-hosted deployments. Local serverless staging is temporary. The existing backend upload limit is respected.

The frontend root has its own package manifest, lockfile, environment example and build. It does not include or import the HRMS frontend bundle. No customer domain is hardcoded or registered. Each installation uses its existing HRMS deployment and database; the runtime config does not create new database tenants or a second backend. No production deployment is created automatically by this change.

### Repeatable compiled releases

After building, package a customer release into a new directory outside the Git checkout:

```powershell
npm run package:release -- --output C:/releases/interns-customer-001 --api-base-url https://app.customer.example/api/v1 --hrms-login-url https://app.customer.example/hrms/login
```

This creates a self-contained static site in `.vercel/output/static` and a Vercel Build Output API configuration. Link the release directory to its dedicated frontend Vercel project, then run `vercel --prebuilt --prod` from that directory. Keeping the release outside the monorepo avoids accidentally selecting the main BusinessSuite project. For other hosts, serve the static directory with SPA fallback and `Cache-Control: no-store` for `config.js`. Customer URLs live only in that runtime file; the compiled application can be reused across installations.

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

The portal opens at `/login` for signed-out users. `/apply` shows a Google sign-in gate and only renders the mobile-first application after successful Google authentication; `/application-status` verifies the applicant's email/password before displaying their decision. Applicants submit details only: there is no resume or document-upload field. Save Draft stores non-credential form fields in browser session storage; passwords and identity numbers are excluded.

Applications remain Pending without a user or employee account. HR staff review them at `/hrms/interns-hub/applications`, assign branch, department, designation, manager and joining date, and approve or reject them. Approval creates an HRMS employee, a restricted intern account using the applicant's already-hashed password, and a unique `IH-…` intern ID. The applicant can then sign in with their chosen credentials and view that ID. No email delivery service is assumed. Application status is checked in the portal.

HR staff manage the public role list in the **Internship roles for applications** card on that same Applications page. Save changes to publish them; removing a role does not alter existing applications. Role settings are scoped to the staff member's organization. `INTERN_HUB_ORGANIZATION_ID` selects the organization accepting public applications for this installation (default 1). Addresses are limited to 200 characters on both the application form and API.

### Google application signup through Firebase

Set `INTERN_SIGNUP_FIREBASE_PROJECT_ID` on the backend. In Firebase Authentication, enable Google sign-in and add the portal hostname under Authorized domains. Microsoft signup is disabled. Provider secrets never go in this repository or the browser.

Pass the public Firebase web configuration as `--firebase-config-file path/to/firebase-web.json` when packaging a release. It is stored in the runtime `config.js`, keeping the compiled application customer-independent. Analytics is not enabled by the signup flow. The frontend loads Firebase Authentication when an applicant chooses a provider; the backend checks token signatures, audience, issuer, expiry and allowed provider against the configured project. Successful Google verification issues a purpose-bound, two-hour application session stored in this browser tab. The server requires it for application options, submissions, corrections and uploads, and binds the application email to the verified Google email. Drafts are isolated by Google email. Application sessions never authenticate to employee or intern APIs, link existing accounts, or grant employee access. Applicants still complete their application and choose an intern password, and HRMS approval remains required.

ID numbers are encrypted using a purpose-specific key derived from the existing backend secret. Staff listings show only the last four characters. Review notes are visible to the applicant. The application database migration follows the initial Interns Hub migration.
