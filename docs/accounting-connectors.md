# Read-only accounting connectors

BusinessSuite mirrors external customers, invoices and customer payments without creating native CRM customers, sales invoices, receipts, vouchers or ledger postings. The external application remains the accounting authority. No live provider credentials were used during development.

## Using the framework

In Finance / Import Data, authorize Zoho Books or QuickBooks Online using the existing OAuth controls. Under Connected accounting / read-only sync, select that account and enable sync. QuickBooks defaults to sandbox; uncheck it explicitly for production. Existing Zoho accounts must be authorized again for the new contacts and customer-payments READ scopes. Select the same account and use Enable / reconnect sync to retain the mirror and history.

Sync now pulls all three entity types. View records offers paginated customers, invoices and payments, plus customer/currency invoice-outstanding balances. Pause blocks new runs and publication of in-flight snapshots. Resume permits subsequent runs. Disconnecting OAuth prevents future pulls without deleting the last successful snapshot. Tokens are never returned in connection lists.

Connections belong to the authorizing user, company and selected writable branch, using existing Finance import permissions. Multiple branches can connect the same provider account: do not sum those mirrors as separate business activity. Native CRM matching and existing sales dashboard integration are separate follow-up work.

## Data and operational guarantees

- Full paginated snapshots with changed-only upserts, keyed by connection, entity and stable external ID. This is not provider-side incremental/CDC sync.
- All entity pulls must succeed before a snapshot publishes. Failures preserve the previous records and freshness timestamp.
- Missing records are marked absent, not deleted. Reappearing records reuse their mapping. Absence cannot distinguish provider deletion from lost visibility.
- Money uses decimal strings and explicit currencies. No conversion or inferred currency. Invoice outstanding already includes allocated receipts; payments are not subtracted twice.
- Outstanding totals exclude drafts/voids/cancellations and unapplied customer credits/advances. They are invoice receivables, not a full customer ledger statement.
- Run history includes created/updated/unchanged/missing counts and sanitized errors. It does not archive every historical record payload.
- Atomic one-hour leases and fencing prevent concurrent snapshot publication; abandoned runs become interrupted on the next lease claim.
- Provider GET retries: three attempts for network failures, 429 and 5xx with capped backoff. Authorization failures require reconnecting. Users can retry failed runs.
- Limit of 50,000 records per entity; malformed, oversized or incomplete pagination fails instead of publishing truncated data.
- Sync is synchronous and on demand. No recurring jobs or webhooks are enabled. Pilot volumes should guide moving execution to a durable worker.
- Provider data requests are GET-only. OAuth token exchanges are POST. Intuit's accounting scope is coarse-grained; local adapter behavior enforces read-only use.

## API

All routes use `/api/v1/accounting-sync`, an authorized session and `X-Suite-Branch`.

- `GET /connections`: account health and freshness.
- `POST /connections`: `{provider, source_connection_id, sandbox}` for cloud providers, or `{provider: "tally", account_id: "company GUID"}`.
- `POST /connections/{id}/reconnect`: `{source_connection_id}`; must match the same provider account.
- `PATCH /connections/{id}`: `{enabled: false|true}`.
- `POST /connections/{id}/sync`: cloud pull; check returned run status, not only HTTP status.
- `GET /connections/{id}/runs`: recent attempts; optional limit up to 100.
- `GET /connections/{id}/records?entity=customers|invoices|payments&page=1&page_size=50`.
- `GET /connections/{id}/balances`: invoice-outstanding totals, currency and freshness.
- `POST /connections/{id}/rotate-bridge-token`: rotate the local-agent token.
- `POST /connections/{id}/snapshot`: complete Tally snapshot with exact account_id; also requires `X-Accounting-Bridge-Token`.

## Deployment and credentials

Apply the repository's normal migration workflow before starting the updated application. Both migration tracks include the new mirror/history tables. No existing development or customer database was migrated during implementation.

Configure `IMPORT_ZOHO_CLIENT_ID`, `IMPORT_ZOHO_CLIENT_SECRET`, `IMPORT_ZOHO_REDIRECT_URI` and/or `IMPORT_QUICKBOOKS_CLIENT_ID`, `IMPORT_QUICKBOOKS_CLIENT_SECRET`, `IMPORT_QUICKBOOKS_REDIRECT_URI` through deployment secrets. Register the exact HTTPS callback URL. Zoho needs its organization ID and data centre; QuickBooks needs a matching realm and environment. Retain the installation encryption key across deployments: tokens use the existing encrypted secret storage.

## Local Tally agent

Run `backend/scripts/accounting_sync_agent.py` on the TallyPrime machine with backend dependencies installed. It contacts only loopback HTTP (port 9000 by default), sends XML Export requests, and uploads the normalized snapshot over HTTPS. No public inbound Tally port is required.

Register the exact company GUID in the Finance panel and save the displayed bridge token. Set `BUSINESSSUITE_URL` to your HTTPS origin, `BUSINESSSUITE_ACCESS_TOKEN` to an authorized unexpired user session, and `BUSINESSSUITE_BRIDGE_TOKEN` to that token in the agent environment. Secrets must not appear in command arguments or version control.

```powershell
python backend/scripts/accounting_sync_agent.py --company "Company Name" --company-guid "exact-guid" --currency INR --connection "sync-connection-uuid" --branch 1
```

The agent verifies company name/GUID and reads Sundry Debtors ledgers, standard Sales/Receipt vouchers and bill balances. Tally must be open with XML HTTP export enabled. Bill-wise ledgers and an explicit single base currency are required. Unsupported custom voucher types, ambiguous bill references, unallocated opening bills/customer credits, currency expressions or missing GUIDs fail closed. An accountant must map unsupported scenarios before publication. Company subgroup behavior and actual exported methods require verification with the customer's TallyPrime edition. The adapter is fixture-tested, not certified against a real Tally instance.

The bridge token is additional to company/branch/session authorization and is shown only on creation/rotation. A single agent should own each connection. This prototype requires a renewable authorized session for unattended operation; it does not store customer login passwords or automatically refresh user sessions.

## Live acceptance later

Test full pagination, partial/full settlement, cancellations/deletions, customer identity, mixed currencies, repeat runs, expired access, reconnect and rate limiting in each test company. Compare balances with accountant-approved reports. Tally additionally requires opening-bill, bill-wise configuration, subgroup, currency and custom-voucher checks. Live provider reconciliation remains pending until test accounts are provided.

References: [Zoho contacts](https://www.zoho.com/books/api/v3/contacts/), [Zoho invoices](https://www.zoho.com/books/api/v3/invoices/), [Zoho payments](https://www.zoho.com/books/api/v3/customer-payments/), [Intuit invoice API](https://developer.intuit.com/docs/api/accounting/invoice), [Tally XML](https://help.tallysolutions.com/xml-integration/), [Tally collections](https://help.tallysolutions.com/collection-definition-attributes/).
