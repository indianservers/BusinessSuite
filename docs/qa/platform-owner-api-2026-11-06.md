# Local Platform Owner backend API verification — 6 November 2026

Scope: Platform Owner portal and its linked public signup/legacy owner authentication endpoints. This is not a claim that every ERP module API was tested. No browser was used in this run.

## Results

- 46 route/method pairs inventoried from the running local OpenAPI document; each has a successful request.
- 390 live HTTP checks passed across workflows and authentication boundaries.
- 25 post-fix live HTTP checks passed, including 14 malformed nested payloads.
- 79 regression tests passed across portal, public signup and company security boundaries. JUnit: `outputs/platform-owner-api-regression.xml`.
- Local backend: `http://127.0.0.1:1534/api/v1`. Actual local PostgreSQL stores were used by HTTP tests; regression tests use isolated fixture stores.

## Authentication and sessions

Real logins issued bearer sessions for the Platform Owner, reviewer, sales, support, billing, analyst, business global superuser and an actual company-scoped admin. The company identity confirmed is_superuser=False. Every protected route/method pair was exercised with anonymous, malformed bearer, business-superuser and company-admin identities: all returned401. Platform identity was rejected by the business identity endpoint. Staff role denials, assignment-scoped lists/detail404, session invalidation on access changes, password reset and revocation were checked. Reports-only API key allowed reports, denied interactive/session/signup/customer routes, and returned401 after revocation.

## Workflows checked

Versioned signup CRUD and stale edits; preview/atomic bulk commit; archive/restore and legal hold/retention guard; one-use applicant correction and withdrawal; all five staff invitation/activation flows; staff access review/restriction; private reset/replay rejection; task/view/template/note/report-schedule CRUD; 20 record kinds; local outbox preview/requeue; customer provisioning and progress; catalogue plan creation/edit/duplicate guard; trial extension, snapshots/restore, entitlements, future plan scheduling and paid conversion; payment-reference deduplication; suspend/resume, invitation revoke/resend; two-party company-admin transfer; support consent; customer assignment/export; cancellation/offboarding; reports/CSV exports; settings, global search, audit, login history and due checks.

Time-dependent execution, aged retention purge, expired support/session/key, provisioning failure reconciliation and subscription enforcement are additionally covered by the regression suite; the live run does not age production-like dates or claim every race/load scenario was tested.

## Bugs found and fixed

Fourteen regression cases reproduced server exceptions or incorrect acceptance of malformed values. Validation now rejects malformed favorites/page size/business weekdays, staff role/permission/boolean values, assignment IDs/legal-hold booleans, null checklists, non-object record edits, application collections and payment currencies with422. Rejected staff mutations preserve existing sessions. All14cases pass in regression and against the reloaded local server.

The initial rapid run hit the existing request throttle; the runner now observes Retry-After. Security settings were not weakened. A development autoreload interrupted one validation attempt; the final post-reload run passed25checks.

## Endpoint inventory

Every item below has positive live coverage; protected entries also have the four denied-identity checks described above.

- [x] `GET /api/v1/auth/signup/options` — 1 checks; successful request verified.
- [x] `POST /api/v1/auth/signup` — 1 checks; successful request verified.
- [x] `GET /api/v1/auth/signup-requests` — 5 checks; successful request verified.
- [x] `POST /api/v1/auth/platform/login` — 8 checks; successful request verified.
- [x] `GET /api/v1/auth/platform/me` — 5 checks; successful request verified.
- [x] `POST /api/v1/auth/signup-requests/{ident}/review` — 5 checks; successful request verified.
- [x] `GET /api/v1/platform/me` — 15 checks; successful request verified.
- [x] `PATCH /api/v1/platform/profile` — 6 checks; successful request verified.
- [x] `GET /api/v1/platform/sessions` — 6 checks; successful request verified.
- [x] `POST /api/v1/platform/sessions/revoke` — 6 checks; successful request verified.
- [x] `GET /api/v1/platform/signups` — 13 checks; successful request verified.
- [x] `POST /api/v1/platform/signups` — 6 checks; successful request verified.
- [x] `GET /api/v1/platform/signups/{ident}` — 7 checks; successful request verified.
- [x] `PATCH /api/v1/platform/signups/{ident}` — 6 checks; successful request verified.
- [x] `POST /api/v1/platform/signups/{ident}/action` — 10 checks; successful request verified.
- [x] `POST /api/v1/platform/signup-bulk` — 7 checks; successful request verified.
- [x] `POST /api/v1/platform/signups/{ident}/review` — 5 checks; successful request verified.
- [x] `POST /api/v1/platform/signups/{ident}/request-info` — 5 checks; successful request verified.
- [x] `POST /api/v1/platform/signups/{ident}/tracking-link` — 5 checks; successful request verified.
- [x] `GET /api/v1/platform/signup-export` — 6 checks; successful request verified.
- [x] `GET /api/v1/platform/staff-directory` — 5 checks; successful request verified.
- [x] `GET /api/v1/platform/staff` — 11 checks; successful request verified.
- [x] `POST /api/v1/platform/staff/invite` — 9 checks; successful request verified.
- [x] `PATCH /api/v1/platform/staff/{ident}` — 11 checks; successful request verified.
- [x] `GET /api/v1/platform/records/{kind}` — 34 checks; successful request verified.
- [x] `POST /api/v1/platform/records/{kind}` — 9 checks; successful request verified.
- [x] `POST /api/v1/platform/record/{ident}/action` — 28 checks; successful request verified.
- [x] `POST /api/v1/platform/api-keys` — 5 checks; successful request verified.
- [x] `GET /api/v1/platform/events` — 5 checks; successful request verified.
- [x] `GET /api/v1/platform/login-history` — 5 checks; successful request verified.
- [x] `GET /api/v1/platform/search` — 5 checks; successful request verified.
- [x] `GET /api/v1/platform/settings` — 5 checks; successful request verified.
- [x] `PUT /api/v1/platform/settings` — 11 checks; successful request verified.
- [x] `GET /api/v1/platform/plans` — 5 checks; successful request verified.
- [x] `POST /api/v1/platform/plans` — 6 checks; successful request verified.
- [x] `PUT /api/v1/platform/plans/{ident}` — 5 checks; successful request verified.
- [x] `GET /api/v1/platform/customers` — 6 checks; successful request verified.
- [x] `GET /api/v1/platform/customers/{ident}` — 7 checks; successful request verified.
- [x] `POST /api/v1/platform/customers/{ident}/action` — 22 checks; successful request verified.
- [x] `GET /api/v1/platform/customers/{ident}/export` — 5 checks; successful request verified.
- [x] `GET /api/v1/platform/reports` — 13 checks; successful request verified.
- [x] `GET /api/v1/platform/report-export` — 5 checks; successful request verified.
- [x] `POST /api/v1/platform/operations/run-checks` — 10 checks; successful request verified.
- [x] `GET /api/v1/platform/public/{token}` — 11 checks; successful request verified.
- [x] `POST /api/v1/platform/public/{token}` — 13 checks; successful request verified.
- [x] `POST /api/v1/platform/password-reset` — 1 checks; successful request verified.

## Evidence and repeatability

- `outputs/platform-owner-api-local.json`: endpoint coverage and390checks; secrets excluded.
- `outputs/platform-owner-api-invalid-inputs.json`:25post-fix live checks; secrets excluded.
- `backend/scripts/qa_platform_api_local.py`: repeatable localhost-only HTTP runner; optional PLATFORM_QA_OWNER/PASSWORD environment overrides. It respects rate limits; creates labelled QA records, disables created staff and revokes keys. Backend must already be running.
- Run regression from backend: `venv/Scripts/python -m pytest tests/test_platform_portal.py tests/test_public_signup.py tests/test_company_security_boundary.py -q`.

## QA residue and cleanup

Synthetic records are labelled APIQA1106170330 (successful workflow run), APIQA1106170225 (initial throttled run), and a later APIQA validation prefix. The successful QA customer is offboarded with ERP records preserved; offline receipt is synthetic, no money was charged. New QA staff are disabled, integration key revoked, interrupted pending staff invitation revoked. Active sessions with exact device BusinessSuite-local-API-QA were revoked after testing; browser sessions were not targeted. QA leads/plan/history remain labelled for inspection. Messages stayed in the local outbox; no deployment, push or external send occurred.
