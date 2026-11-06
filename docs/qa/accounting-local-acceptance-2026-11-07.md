# Local accounting acceptance - 7 November 2026

Local PostgreSQL migrations were applied and the real BusinessSuite app was exercised with isolated mock accounting data. No live accounts were connected.

## Migrations

- Existing local app database: `business_suite` on loopback port 5432.
- Upgraded from `pg_20261106_084_payroll_delivery` to `pg_20261107_087_crm_templates`, including accounting mirror tables and background schedules/customer links.
- Used the configured maintenance role. The application's restricted runtime role was not elevated; access to the new accounting tables was verified.
- Schema validation passed: 831 tables and 9,710 columns. A repeat migration was a successful no-op.
- The app database still has zero accounting connections. Mock records were placed only in `business_suite_accounting_local_69918736_test`, which was migrated from an empty database through the same migration chain.

## Real app verification

The test app runs at `http://127.0.0.1:5196`, using its actual backend on loopback port 1542. The browser signs in normally and uses real API requests and PostgreSQL persistence. Browser responses are not intercepted. Only external provider reads are replaced with deterministic mock responses at the accounting adapter boundary; OAuth/provider requests that could contact a live account are blocked in the QA process.

Verified workflows:

- The one-minute worker automatically picked up due Zoho Books and QuickBooks connections; the test did not click Sync now.
- A complete Tally mock snapshot passed the normal authenticated bridge endpoint.
- Finance displayed schedule intervals, next-run times and successful sync state.
- Explicit customer links were created in CRM customer 360 for all three provider accounts. An unlinked CRM customer returned no accounting history.
- Customer 360 displayed provider invoices, payments and balances. INR and USD remained separate.
- The Sales invoice page showed a read-only external register and filtered real stored invoice data.
- Daily Sales Reports showed source document dates, invoiced value, receipts, current outstanding, freshness and the correct company timezone.
- Desktop and mobile app pages rendered without page-width overflow.
- A scheduled mock settlement changed the Zoho INR balance from 600.10 to 0 and daily receipts from 400 to 1000.10.
- A simulated Zoho outage retained the last successful snapshot. QuickBooks was skipped while paused during the same worker tick.
- Resuming QuickBooks and restoring the Zoho mock source allowed the next scheduled tick to recover.
- Settled status/balances and updated receipts were checked in the app after the background updates.

Tally device extraction and live OAuth authorization remain outside this mock acceptance run. Actual installations/accounts are still required for pilot validation.

## Read-only and isolation checks

SQL verification confirms three mock connections, three explicit CRM links and ten current mirror records. Native SRM invoices, SRM receipts and FAM vouchers remain at zero in the QA database. No mock transactions were posted to native accounting.

The local test login is stored in git-ignored `.local/accounting-qa-login.json`. Database credentials and session/control tokens are not included in this report or the public evidence files.

## Evidence

- [Migration verification](../../outputs/accounting-local-app/migrations.json)
- [Completed acceptance checks](../../outputs/accounting-local-app/results.json)
- [SQL verification](../../outputs/accounting-local-app/sql-verification.json)
- [Automatic sync in Finance](../../outputs/accounting-local-app/automatic-sync-desktop.png)
- [CRM customer 360](../../outputs/accounting-local-app/crm-customer-360-desktop.png)
- [External invoice management](../../outputs/accounting-local-app/external-invoices-desktop.png)
- [Daily sales report](../../outputs/accounting-local-app/daily-sales-desktop.png)
- [Settled customer balance](../../outputs/accounting-local-app/crm-settled-desktop.png)
- [Settled invoice](../../outputs/accounting-local-app/invoice-settled-desktop.png)
- [Updated daily receipts](../../outputs/accounting-local-app/daily-sales-settled-desktop.png)
- [Mobile customer 360](../../outputs/accounting-local-app/crm-customer-360-mobile.png)
- [Mobile invoices](../../outputs/accounting-local-app/external-invoices-mobile.png)
- [Mobile daily report](../../outputs/accounting-local-app/daily-sales-mobile.png)

Repeatable tooling: `qa/setup_accounting_local.py`, `qa/serve_accounting_acceptance.py`, and `qa/check_accounting_local_app.cjs`. The setup helper is restricted to loopback PostgreSQL and reuses the isolated QA database. The mock backend must be started separately from the normal local app.
