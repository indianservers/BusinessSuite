# Recurring billing and UAE accounting

Local development implementation, November 2026. India GST/TDS remains available.

## Recurring invoices

Use an existing SRM engagement linked to a shared customer and an existing recurring billing plan. Open the plan detail or Billing Plans and expand **Recurring billing schedule**. Choose the cadence on the plan, then the interval, first date, optional end date or never-expiring schedule, amount, payment terms, PDF layout, payment mode, salesperson, order reference, subject, notes and terms. Automatic drafts require an active plan and invoice-create permission. Pause/resume uses the existing plan lifecycle.

Scheduling reuses native billing milestones and invoices. Existing occurrence dates are skipped. Month-end and leap-year schedules retain their original anchor. Company/branch timezone determines when an occurrence is due. The scheduler checks current permissions and persists company/branch ownership. Automatic generation creates drafts; normal approval and accounting posting remain separate. Optional in-app notifications link to each newly created draft.

The existing SRM Reports directory includes **Recurring Invoice Details**, with occurrence dates, status, customer, currency, plan and linked invoice. Customer ID, status and inclusive date filters also apply to its CSV export. Amounts in different currencies are not combined.

Invoice PDFs use the shared company billing address, frozen when issued. Future edits to customer master data do not rewrite an issued snapshot.

## Local runtime

The current development frontend is `http://127.0.0.1:5207`, proxying the current backend on port 8001. The separate acceptance frontend is port 5206, proxying a disposable database on port 1568. Original development services are left running.

From `backend`, start the current-source local server with `venv\Scripts\python.exe scripts\serve_local_recurring_app.py`. It binds loopback, rejects remote databases and production configuration, and skips startup seeding/migrations.

The local worker runs `venv\Scripts\python.exe scripts\run_local_recurring_worker.py` every minute. It rejects remote databases and production configuration. The running hidden process ID is recorded in `.local/recurring-worker.pid`; stdout and stderr are `.local/recurring-worker.log` and `.local/recurring-worker.err.log`. This development process does not install a boot-time Windows service. The existing application worker and authenticated internal cron endpoint also invoke the same dispatcher.

No Vercel or DigitalOcean deployment was performed.

## UAE accounting

Open FAM → GST & tax compliance → UAE tax. Configure the TRN, emirate, and existing output-VAT liability and input-VAT asset tax accounts. Set the company's financial country/currency separately in existing Financial Settings; saving UAE tax preferences never changes an India company into a UAE company.

UAE sales invoice posting uses the output VAT account. UAE purchase bills and expenses use the input VAT account for the entered recoverable tax. Include nonrecoverable VAT in the expense value. Existing purchase/expense data fields retain their legacy internal `gst_amount` names; UAE form labels describe recoverable VAT. India TDS cannot be posted on a UAE purchase. Foreign-currency sales invoices require a supported conversion workflow before posting to a different base currency.

VAT201 is a manual, reconciled draft working paper. It supports emirate-level outputs, tourist refunds, reverse charge, imports, zero-rated/exempt supplies, recoverable inputs and adjustments. Saving the same period updates its version and audit history; stale versions are rejected. It is not a live transaction-derived tax return or portal submission.

The corporate-tax preview covers the ordinary adjusted taxable-income calculation. Free-zone treatment, small-business relief, exemptions and domestic minimum top-up tax require separate assessments and are explicitly rejected by that preview.

Official references: [FTA VAT Returns User Guide](https://tax.gov.ae/-/media/Files/EN/PDF/Guides/VAT-Returns-User-Guide.pdf), [FTA Corporate Tax General Guide](https://tax.gov.ae/DataFolder/Files/Guides/CT/CT%20General%20Guide%20-%20EN%20-%2010%2009%202023.pdf).

## Accounting transaction locks

FAM → Transactions & books → Transaction locking applies inclusive through-date locks to all accounting modules or sales, purchases, banking and accountant vouchers. It complements the existing financial-year and period locks. Creation/posting, original-date edits, cancellation, reversal and clone target dates are checked. A reason is required to lock or unlock, and stale configuration versions are rejected.

These are accounting voucher locks. They do not lock every operational sales/project document.

## Statements, purchase recurrence and bank rules

FAM Financial statements calculates trial balance, general ledger movements, profit and loss, and balance sheet from posted dated opening balances and effective voucher entries. Dates must fall in one financial year. Cancelled vouchers are excluded; an original with a draft reversal remains effective until the reversal is posted. The same calculations feed the existing CSV export jobs. Historical inactive ledgers remain included when they have balances. Base currency and tax country cannot be changed after posting, including postings in another branch.

Recurring bills and expenses copy an existing native source into a versioned schedule. The shared cadence helper anchors month-end dates. The existing minute worker generates native drafts with company/branch access and current permissions, and commits each draft and schedule cursor atomically. Duplicate source schedules are rejected. Pause/resume uses version checks, failures are visible on the profile, and tax-country/currency changes require review. Generated documents keep the usual posting process. No supplier payments or messages are sent automatically.

Bank transaction rules match description/reference text, direction and optional amount bounds, ordered by priority. Preview includes unmatched lines only. Applying a reviewed suggestion uses native posting and reconciliation; it requires banking management, voucher posting and reconciliation permissions. Repeated application returns the existing voucher. Changed rules, existing matches, unavailable accounts and accounting date locks block posting. This supports simple expense withdrawals and income deposits; tax splits and party settlements use their existing workflows.

The UAE VAT account register reads effective postings from the configured output/input VAT accounts for an AED-base UAE company. It compares those totals with the saved VAT201 working version. This is a tax-account reconciliation, not automatic determination of every VAT201 classification or filing.

## Verification

The full FAM/SRM regression passed 209 tests (four warnings). The subsequent least-privilege bank-rule account-options test also passed. TypeScript checking and the final production build passed. Both HTTP acceptance scripts passed against a fresh disposable local database, including actual minute-worker ticks. Browser checks confirmed generated purchase drafts, rule account choices, and the dated India P&L (synthetic income 1,250, expense 25, net profit 1,225).

Run the disposable acceptance backend with `venv\Scripts\python.exe scripts\serve_recurring_acceptance.py`. Run `scripts\verify_recurring_acceptance.py` and `scripts\verify_fam_gap_acceptance.py` using the same Python. Both use synthetic local credentials and wait for actual worker ticks. They verify invoice and purchase drafts, duplicate protection, status versions, PDF address/terms, approval, locking, idempotent posting, bank categorization/reconciliation, dated statements and CSV, separate India/UAE companies, UAE sales/purchase/expense VAT posting and register-to-working reconciliation. Results are under `outputs/recurring-acceptance`.

## Comparison coverage and remaining work

All 55 primary Zoho settings pages and all 71 individual report pages were loaded and inspected. The report coverage record is `docs/qa/zoho-books-report-coverage-2026-11-07.json`. This does not certify every nested tab, record action or report calculation as equivalent.

Remaining product gaps include recurring automatic sending/charging with provider integration, foreign-exchange conversion/settlement/revaluation, receipt OCR, full transaction-to-VAT201 classification and statutory submission/e-invoicing delivery. Special CT regimes require their own assessments. Cash-flow classification, ratios/equity movement and several specialized report variants still require implementation or deeper equivalence checks against existing analytics, PMS and shared services. Shared portals, automation, customization, documents and inventory should be reused instead of creating parallel systems.

The selected accounting integration targets are Zoho Books, Tally and QuickBooks (user preference, November 7). Reuse the existing shared accounting-sync connectors and their read-only mirrors; do not create duplicate connectors or treat a successful mirror sync as statutory submission or payment authorization. Zoho/QuickBooks use authorized provider accounts; Tally uses the existing local agent. Connected-account credentials and sandbox availability still need verification.

Zoho Books is the preferred UAE e-invoicing candidate: its UAE product documents accredited e-invoicing, and TallyPrime also documents UAE e-invoicing. Those product capabilities do not establish a verified external submission API contract for FAM. References: [Zoho UAE e-invoicing](https://www.zoho.com/ae/books/e-invoicing/), [TallyPrime UAE e-invoicing](https://help.tallysolutions.com/uae-e-invoicing-in-tallyprime/).

The existing FAM payment gateway provides INR Razorpay payment links. The user has not finalized the gateway and currently prefers Razorpay; this is not an instruction to enable recurring charges. Zoho's autocharge requires the customer's payment information held by its connected payment gateway; selecting an accounting platform alone does not select that gateway or establish mandates. Final gateway choice, supported merchant country/currency, recurring mandate API and test availability are pending. Reference: [Zoho recurring payment help](https://www.zoho.com/ae/books/help/recurring-invoice/receive-payments.html). No live charges, filings or outbound deliveries were performed.
