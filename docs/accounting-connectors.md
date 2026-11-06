# Read-only accounting connectors

BusinessSuite mirrors external customers, invoices and customer payments without creating native CRM customers, sales invoices, receipts, vouchers or ledger postings. The external application remains the accounting authority. No live provider credentials were used during development.

## Using the framework

In Finance / Import Data, authorize Zoho Books or QuickBooks Online using the existing OAuth controls. Under Connected accounting / read-only sync, select that account and enable sync. QuickBooks defaults to sandbox; uncheck it explicitly for production. Existing Zoho accounts must be authorized again for the new contacts and customer-payments READ scopes. Select the same account and use Enable / reconnect sync to retain the mirror and history.

Sync now pulls all three entity types. View records offers paginated customers, invoices and payments, plus customer/currency invoice-outstanding balances. Pause blocks new runs and publication of in-flight snapshots. Resume permits subsequent runs. Disconnecting OAuth prevents future pulls without deleting the last successful snapshot. Tokens are never returned in connection lists.

Connection administration belongs to the authorizing user, company and selected writable branch, using existing Finance import permissions. Multiple branches can connect the same provider account: do not sum those mirrors as separate business activity. CRM customer 360, Sales invoice management and daily Sales Reports consume these mirrors through explicit customer links. Financial readers can see linked records only when the CRM customer is visible to them; the account owner can also inspect unlinked records. Credentials and connection administration remain owner-private.

## Data and operational guarantees

- Full paginated snapshots with changed-only upserts, keyed by connection, entity and stable external ID. This is not provider-side incremental/CDC sync.
- All entity pulls must succeed before a snapshot publishes. Failures preserve the previous records and freshness timestamp.
- Missing records are marked absent, not deleted. Reappearing records reuse their mapping. Absence cannot distinguish provider deletion from lost visibility.
- Money uses decimal strings and explicit currencies. No conversion or inferred currency. Invoice outstanding already includes allocated receipts; payments are not subtracted twice.
- Outstanding totals exclude drafts/voids/cancellations and unapplied customer credits/advances. They are invoice receivables, not a full customer ledger statement.
- Run history includes created/updated/unchanged/missing counts and sanitized errors. It does not archive every historical record payload.
- Atomic one-hour leases and fencing prevent concurrent snapshot publication; abandoned runs become interrupted on the next lease claim.
- Provider GET retries: three attempts for network failures, 429 and 5xx with capped backoff. Authorization failures require reconnecting. Failed runs schedule exponential retry delays capped at six hours; successful runs clear the failure count. Owners can retry manually.
- Limit of 50,000 records per entity; malformed, oversized or incomplete pagination fails instead of publishing truncated data.
- New cloud connections enable automatic sync every 15 minutes. Existing connections keep automatic sync off until enabled in Finance. Intervals can be set from 5 to 1440 minutes. Manual sync remains available. Webhooks and provider-side CDC are not enabled.
- Provider data requests are GET-only. OAuth token exchanges are POST. Intuit's accounting scope is coarse-grained; local adapter behavior enforces read-only use.

## CRM, invoices and daily reporting

Open any CRM/Sales customer 360 and expand **Manage accounting customer links**. Finance-authorized owners choose an account and the exact synced customer (search is available). The link uses stable provider IDs, never company-name matching. Unlinking removes the relationship without deleting external data. No native customers or accounting entries are auto-created.

The customer panel shows up to 20 invoices and payments, counts and invoice-outstanding balances by account/currency. **Open all linked external invoices** opens the paginated external register. Native invoice controls do not act on mirrored invoices.

Sales / Reports includes daily invoicing and customer receipts with a chart for one selected account/currency, date filters, counts, current outstanding and source freshness. Transaction timestamps use the company's timezone; undated records are excluded from daily totals and counted separately. Draft/void/cancelled invoices are excluded from invoiced value and receivables. Daily activity uses current source document dates; outstanding is the current snapshot, not a historical end-of-day balance. Native sales and external accounting totals remain separate to avoid counting the same invoice twice. No cross-account or cross-currency totals are inferred.

## Background execution

Long-running API servers start a one-minute accounting scheduler loop by default after normal startup/migrations. Set `ACCOUNTING_SYNC_WORKER_ENABLED=false` when running only dedicated workers. Test and serverless lifespans never start this loop.

The existing Celery worker also has an `app.worker.sync_connected_accounting` task scheduled every minute. Run the repository's worker and beat processes with Redis configured. Durable database leases prevent duplicate publication if multiple API instances, cron or Celery processes overlap.

Serverless deployment configuration adds a five-minute `GET /api/v1/internal/accounting-sync` cron. It requires the existing `Authorization: Bearer <CRON_SECRET>` capability; ordinary sessions cannot call it. Each call handles a bounded batch. The scheduler iterates verified company databases, uses a fresh session per account, and rechecks the owner's current grants, company membership, module status, branch access and record ownership before any provider request. Revoked access blocks sync and delays the next check without changing mirrored records.

Apply migrations before running the worker. This change does not launch a live deployment or apply migrations to customer databases. Large company volumes/full pulls may require smaller scoped datasets or a dedicated worker with a larger execution budget; serverless invocations can expire and their leases recover automatically.

## API

All routes use `/api/v1/accounting-sync`, an authorized session and `X-Suite-Branch`.

- `GET /connections`: account health and freshness.
- `POST /connections`: `{provider, source_connection_id, sandbox}` for cloud providers, or `{provider: "tally", account_id: "company GUID"}`.
- `POST /connections/{id}/reconnect`: `{source_connection_id}`; must match the same provider account.
- `PATCH /connections/{id}`: `{enabled: false|true}`.
- `PUT /connections/{id}/schedule`: `{auto_sync, interval_minutes}` for cloud accounts.
- `POST /connections/{id}/sync`: cloud pull; check returned run status, not only HTTP status.
- `GET /connections/{id}/runs`: recent attempts; optional limit up to 100.
- `GET /connections/{id}/records?entity=customers|invoices|payments&page=1&page_size=50`.
- `GET /connections/{id}/balances`: invoice-outstanding totals, currency and freshness.
- `PUT /connections/{id}/customer-links`: `{external_id, crm_company_id, source}`; explicit identity mapping.
- `DELETE /connections/{id}/customer-links/{link_id}`: unlink without removing the mirror.
- `GET /customer-360/{kind}/{id}?source=crm|srm`: linked accounting history.
- `GET /invoices?source=srm&crm_company_id=...&q=...&status=...&page=1`: external invoice register.
- `GET /report-sources?source=srm`: accessible account freshness and status.
- `GET /daily-sales?source=srm&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`: daily activity, up to 366 days.
- `POST /connections/{id}/rotate-bridge-token`: rotate the local-agent token.
- `POST /connections/{id}/snapshot`: complete Tally snapshot with exact account_id; also requires `X-Accounting-Bridge-Token`.

## Deployment and credentials

Apply the repository's normal migration workflow before starting the updated application. Both migration tracks include the new mirror/history tables. The local application database was migrated and verified on 7 November 2026. Live deployments and customer databases have not been changed.

Configure `IMPORT_ZOHO_CLIENT_ID`, `IMPORT_ZOHO_CLIENT_SECRET`, `IMPORT_ZOHO_REDIRECT_URI` and/or `IMPORT_QUICKBOOKS_CLIENT_ID`, `IMPORT_QUICKBOOKS_CLIENT_SECRET`, `IMPORT_QUICKBOOKS_REDIRECT_URI` through deployment secrets. Register the exact HTTPS callback URL. Zoho needs its organization ID and data centre; QuickBooks needs a matching realm and environment. Retain the installation encryption key across deployments: tokens use the existing encrypted secret storage.

## Local Tally agent

Run `backend/scripts/accounting_sync_agent.py` on the TallyPrime machine with backend dependencies installed. It contacts only loopback HTTP (port 9000 by default), sends XML Export requests, and uploads the normalized snapshot over HTTPS. No public inbound Tally port is required.

Register the exact company GUID in the Finance panel and save the displayed bridge token. Set `BUSINESSSUITE_URL` to your HTTPS origin, `BUSINESSSUITE_ACCESS_TOKEN` to an authorized unexpired user session, and `BUSINESSSUITE_BRIDGE_TOKEN` to that token in the agent environment. Secrets must not appear in command arguments or version control.

```powershell
python backend/scripts/accounting_sync_agent.py --company "Company Name" --company-guid "exact-guid" --currency INR --connection "sync-connection-uuid" --branch 1
```

The agent verifies company name/GUID and reads Sundry Debtors ledgers, standard Sales/Receipt vouchers and bill balances. Tally must be open with XML HTTP export enabled. Bill-wise ledgers and an explicit single base currency are required. Unsupported custom voucher types, ambiguous bill references, unallocated opening bills/customer credits, currency expressions or missing GUIDs fail closed. An accountant must map unsupported scenarios before publication. Company subgroup behavior and actual exported methods require verification with the customer's TallyPrime edition. The adapter is fixture-tested, not certified against a real Tally instance.

The bridge token is additional to company/branch/session authorization and is shown only on creation/rotation. A single agent should own each connection. Add `--watch --interval-seconds 900` for automatic local exports with capped retry backoff. Set `BUSINESSSUITE_REFRESH_TOKEN` to an authorized dedicated agent-session refresh token to renew expired access tokens while running. Rotated refresh tokens are retained in memory, not written to disk. Revoked/expired sessions must be reauthorized. No customer login password is stored. For a tenant database also set `BUSINESSSUITE_TENANT`; for a multi-company legacy account use `--organization` to select the correct company.

## Live acceptance later

Test full pagination, partial/full settlement, cancellations/deletions, customer identity, mixed currencies, repeat runs, expired access, reconnect and rate limiting in each test company. Compare balances with accountant-approved reports. Tally additionally requires opening-bill, bill-wise configuration, subgroup, currency and custom-voucher checks. Live provider reconciliation remains pending until test accounts are provided.

References: [Zoho contacts](https://www.zoho.com/books/api/v3/contacts/), [Zoho invoices](https://www.zoho.com/books/api/v3/invoices/), [Zoho payments](https://www.zoho.com/books/api/v3/customer-payments/), [Intuit invoice API](https://developer.intuit.com/docs/api/accounting/invoice), [Tally XML](https://help.tallysolutions.com/xml-integration/), [Tally collections](https://help.tallysolutions.com/collection-definition-attributes/).


## Mock verification

Backend fixtures in `tests/test_accounting_background.py` exercise scheduled provider reads, permissions/revocation, leases, retry/backoff, explicit CRM links, shared reader visibility, invoice filtering, timezone date boundaries and settlement updates without posting native transactions. Existing adapter/import tests remain part of regression coverage. No sample customer data is injected into live databases.

For UI verification, run Vite from the `frontend` directory, then run `node scripts/test-accounting-connected.cjs` with `ACCOUNTING_QA_URL` pointing to that server (default port 5198). The isolated `accounting-sync-qa.html` fixture intercepts every API request. It checks linking, invoice filtering, chart rendering, scheduling controls and desktop/mobile layout without a real account.


## Full local app acceptance (7 November 2026)

The normal local `business_suite` database has been upgraded through `pg_20261107_087_crm_templates`, including both accounting migrations, using the configured maintenance account. The runtime account remains restricted and has access to the new tables. Its accounting connection count remains zero.

Full app verification uses a separate local PostgreSQL database, mock provider responses at the adapter boundary, normal authentication, real API routes and real persistence. No browser API interception is used. The backend rejects live accounting/OAuth requests. Mock records are clearly named and do not create native invoices, receipts or vouchers.

Repeat the local setup from the repository root:

```powershell
backend/venv/Scripts/python.exe qa/setup_accounting_local.py
backend/venv/Scripts/python.exe qa/serve_accounting_acceptance.py --port 1542 --frontend-port 5196
```

In a separate terminal, start Vite from `frontend` with `VITE_DEV_API_PROXY_TARGET=http://127.0.0.1:1542` and `VITE_API_BASE_URL=/api/v1`, using port 5196. Then run `node qa/check_accounting_local_app.cjs` from the repository root. The test waits for real one-minute scheduler ticks to verify settlement, outage retention, pause/resume and recovery. Tally uses an authenticated mock bridge snapshot; extracting data from an actual Tally installation still requires pilot validation.

QA login information is stored only in git-ignored `.local/accounting-qa-login.json`. Database and session secrets remain under `.local` and must not be published. Evidence is saved in `outputs/accounting-local-app/`, and the acceptance summary is in `docs/qa/accounting-local-acceptance-2026-11-07.md`.
