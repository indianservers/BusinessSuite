# Connected commercial workflow — 24 October 2026

## Implemented workflow

Project Billing now selects the same CRM customer, contact and shared team used by Sales. A project may be independent or linked explicitly to an opportunity, sales order and engagement. The existing CRM won-deal → SRM order → confirmed engagement/project workflow carries these references forward without duplicating the buyer. CRM and SRM show accessible related projects.

PMS creates a draft in the existing SRMInvoice/SRMInvoiceLine ledger. The same ID, number, totals and payment balance appear in PMS, SRM invoice detail/list and CRM customer commercial history. Draft manual lines can be edited. Finance issues an immutable document, previews/downloads a valid PDF, and explicitly sends through shared Communication delivery. Document, delivery and payment states are separate. Collections now uses real outstanding invoices and one atomic receipt-and-allocation action rather than hard-coded example values. Payment retries are idempotent; the backend supports audited reversal of new single-invoice payments. Posted accounting payments require accounting reconciliation before reversal. The invoice screen annotates reversed payments; reversal is currently an API/finance operation.

## Canonical identities and authorization

- Own legal entities remain Company; tenant/organization IDs remain isolation boundaries. SellerGrant explicitly permits additional sellers; no grants are inferred or created automatically.
- Customer identity is CRMCompany (including the existing CRM accounts alias). CRMContact remains the shared business contact. CRMAccount account-registry and PMSClient remain compatibility extensions linked by CustomerLink, never fuzzy-matched by names/domains.
- User/CommonPerson/employee relationships supply identity and tenant resolution. CRMTeam and its existing CRMOwner membership extension supply shared company teams. Workspace/project membership remains independent.
- CRMCompany owns shared business fields. Linked compatibility columns update in the same database transaction through a one-way listener. Issued invoice snapshots never follow profile changes.
- Existing permission names, tenant filters, project membership and seller authorization are enforced server-side. Task management alone grants no invoice authority. Linked documents, customer history, Communication records, exports/PDFs and FAM postings use financial access checks. CRM linked commercial details additionally respect SRM record access.
- Legacy NULL organization IDs are confined to tenant 1 for compatibility, rather than treated as globally visible.

## Financial and delivery behavior

New invoices use the existing global INV series with a locked sequence, seeded from historical numbers. Decimal calculations are server-authoritative: two-decimal money, HALF_UP rounding, quantity precision of ten decimals, explicit tax/discount amounts and bounded validated lines. No client-supplied total is authoritative. Supported currency validation excludes three-decimal currencies; automated jurisdiction-specific tax determination/e-invoice certification is outside this change.

Billing sources include manual lines, partial approved billable time, explicitly mapped approved milestones and existing order-line invoice flows. Time reservations and milestone/order overlap checks prevent repeat billing under concurrent submissions. A milestone is billed as a whole installment; proportional tax/discount comes from its explicit source order. Expense billing is unsupported. Cancelled/credited source reservations remain held for finance review; there is no automatic release that could cause accidental rebilling. Cancellation retains documents/history and requires reversal of applied cash and posted accounting entries. Invoiced amounts are never treated as cash receipts.

Delivery attempts are persisted before provider invocation and correlated with the shared Communication message. Accepted messages alone become sent. Configuration failures/rejected recipients expose actionable blocked/failed results and safe retry; an ambiguous provider outcome is unknown and requires reconciliation rather than automatic resend. Invoice creation survives a later delivery failure.

Production SMTP uses COMMUNICATION_EMAIL_PROVIDER=smtp and existing MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD, MAIL_FROM, MAIL_STARTTLS and MAIL_SSL_TLS settings. Secrets belong in deployment configuration. The stub provider is restricted to local/dev/test. No production provider was configured and no customer messages were sent during verification.

## Migration and reconciliation

Both maintained Alembic paths add revision 006 after the existing messaging revision 005: 20261024_006 and pg_20261024_006. They add commercial metadata/mapping/delivery/receipt/source reservation tables, a default-zero line discount and expanded quantity precision. Historical invoice IDs, numbers, statuses and totals are retained. Downgrade deliberately preserves financial metadata.

Back up the database and stop old application writers during the migration/rollout. Use the repository's normal migration runner for its configured database path. Do not run both migration trees against one database. No production migration was run in this task.

From backend, first review a dry-run inventory:

```powershell
venv/Scripts/python.exe scripts/reconcile_commercial_identity.py --organization 1
```

Only after reviewing the actual source and target IDs, apply explicit mappings using an active administrator in that tenant:

```powershell
venv/Scripts/python.exe scripts/reconcile_commercial_identity.py --organization 1 --actor 1 --map pms_client:12=34 --map crm_account:56=34 --apply
```

The IDs above are illustrative, not defaults to execute. Dry-run also proposes project links backed by existing explicit engagement/project/order/customer IDs. Reviewed proposals can be applied with --backfill-projects --actor <admin-id> --apply. Ambiguous duplicates, missing entities/currencies, secondary seller mismatches and unknown legacy invoice customer IDs remain review items. The command does not automatically rewrite historical financial customer references or fabricate missing issued snapshots. Existing issued documents lacking trustworthy metadata require explicit finance review before new delivery.

## Verification

- Backend regression selection: **336 passed**, covering CRM, PMS, SRM, FAM, Business OS, Communication, PostgreSQL configuration and new connected-commercial tests.
- New connected-commercial tests: same-record reads, canonical customer updates, shared teams, commercial project handoff, immutable snapshots, Decimal totals/discounts, partial time and milestone overlap prevention, concurrent/idempotent invoice requests, payment application/reversal, tenant/seller/permission denial, mocked SMTP PDF attachment, truthful failed delivery and migration preservation/replay.
- Both migration upgrade functions were replayed twice against a historical SQLite fixture; live PostgreSQL DDL/concurrency remains unverified.
- Frontend TypeScript/Vite production build passed. git diff --check passed. Existing dependency/deprecation warnings remain.
- Human-style browser exercise used the actual local API and synthetic data: PMS invoice creation → same SRM detail → issue → sandbox delivery → CRM history; direct PMS issue/send; PDF download and rendered inspection; 320px responsive billing; receipt application changed INV-000002 from 290 outstanding to 250 in SRM and PMS.
- Screenshot evidence is in qa/connected-commercial-2026-10-24. The loopback-only QA harness uses a separate temporary database, random session secret and forced test delivery. It is not a deployment route.

## Operational limits

This implementation is locally verified, not production acceptance. Production migration, real PostgreSQL acceptance and configured-provider delivery acceptance remain rollout work. Secondary-seller FAM postings are blocked until the correct authorized accounting-company context is available; they cannot silently post into the tenant's default books. Legacy/multi-invoice receipt reversal and posted allocation reversal require Accounting reconciliation. No general expense billing, automated source-reservation release, fuzzy merge or historical snapshot reconstruction is claimed. No deploy, merge, push or live customer communication was performed.
