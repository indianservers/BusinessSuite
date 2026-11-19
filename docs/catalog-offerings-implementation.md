# Native catalog offerings: implementation and rollout

Status: **partial implementation; not ready for the full requested rollout**.
Updated: 19 November 2026.

## Existing architecture and impact map

The canonical master is `srm_products` (`SRMProduct`), already shared by Products and Services. Legacy CRM product/service models are compatibility projections, not a suitable second master. `shared_catalog_details` stores workspace restrictions, versioned prices, images and custom fields; `shared_catalog_links` connects existing CRM and PMS records. Existing master, customer, employee, sales-order and invoice IDs are preserved.

- Shared catalog: `backend/app/shared/catalog.py` and `frontend/src/shared/catalog`. All five kinds use the existing listing, filtering, pagination, preview, archive, duplication, smart editor, category selection, save feedback and refresh transport. New fields are rendered inside existing `CatalogOptions` sections using existing form classes. No new stylesheet or frontend framework was added.
- CRM: deal catalog validation and lead line types accept all five kinds. Audience projections and follow-up type filters recognize the new master kinds. Existing customer/company 360 workspaces embed a lazy plan section with Active Plans, Benefits, Usage, Renewals and History views.
- PMS: the existing shared catalog/line selector and `CatalogLink` path support all five kinds. No projects are created automatically. Configurable project-template execution is still outstanding.
- Sales/POS: master lookup preserves offering kind; non-stock kinds cannot become physical inventory. Sales lines capture plan configuration, beneficiaries and selected start date. The existing receipt allocation transaction issues a customer plan on full invoice payment with a stable order/line idempotency key. Approval and first-use activation remain separate from payment. Checkout accepts optional plan dates and beneficiary IDs. Existing taxes, rounding, receipts, invoices and partial payments remain authoritative.
- Inventory: stock-only queries explicitly exclude memberships, subscriptions and bundles. The legacy `service_id` metadata alias remains exclusive to Services; other kinds use the existing `product_id` master reference. Bundle stock fulfillment is **not implemented**, so bundle checkout rejects rather than silently skipping stock.
- Selected Business Packs: catalog CRUD retains the native authority, enrollment and writer paths. Customer-plan operations and paid plan fulfillment in selected contexts explicitly reject until their new child tables have native context enrollment and isolation support. No guard exemptions were added.
- HRMS: no separate employee or customer entities were introduced. Plan configuration can store responsible employee references, but validated employee assignment workflows and HRMS benefit surfaces are outstanding. No HRMS billing endpoint was added.
- Appointments: the entitlement service understands booking/check-in/attendance/completion consumption stages, but scheduler confirmation, attendance and cancellation are **not yet wired** to it.
- Finance/reporting: existing invoice and payment accounting is reused. Plan price snapshots distinguish contract recurring configuration from fixed prepaid duration. Dedicated reports, automatic billing, renewal notifications, proration and plan-aware refund allocation are outstanding.

## Data and migrations

Plan/bundle definitions are validated JSON on the existing master. Existing `CatalogDetails.version` tracks definition changes, and purchased plans preserve configuration and price snapshots. No existing catalog rows are rewritten.

Additive tables:

- `catalog_customer_plans`: canonical offering/customer foreign keys, organization scope, source idempotency key, dates, status, beneficiaries, immutable purchase configuration and price snapshot, revision.
- `catalog_customer_entitlements`: plan benefit definitions and remaining balances; database check prevents negative balances.
- `catalog_usage_ledger`: usage and compensating reversals; unique request keys and unique reversal references prevent duplicate processing.
- `catalog_plan_events`: issue and lifecycle audit snapshots with unique request keys.

Migration heads added:

- PostgreSQL: `pg_20261119_127_customer_plans`, following the existing local `pg_20261118_126_report_crud` migration.
- Legacy migration tree: `20261119_088_customer_plans`, following `20261118_087_report_crud`.

Both migration files create append-only history triggers. Downgrades refuse populated tables. Mapper hooks additionally reject ordinary ORM audit mutations. Migration tests run each upgrade and empty downgrade in isolated SQLite, and compile the PostgreSQL upgrade and history triggers offline; **live PostgreSQL execution and concurrency tests remain required**.

No live database was changed. Use the existing Alembic deployment process against an isolated database branch first, with a direct migration connection. Inspect the actual deployed head and included uncommitted reporting migrations before applying the chain. Do not deploy the frontend customer-plan section without these tables.

## API contracts

Existing `/api/v1/catalog` routes retain their shapes and now accept `product`, `service`, `membership`, `subscription`, `bundle` as `kind`. Plan kinds require `plan`; bundles require `bundle.components`. Products/Services reject incompatible configuration. Only Products can enable inventory tracking. Nested bundle validation checks referenced records, visibility, circular references and maximum depth.

Customer-plan routes under `/api/v1/customer-plans`:

- `POST /`: manual authorized issuance; requires offering, customer, kind and request key.
- `GET /?customer_id=...`: visible customer plans with pagination.
- `GET /{id}`: balances, history and recent usage, with permission-derived `can_manage`.
- `POST /{id}/lifecycle`: activate, pause, resume, suspend, cancel, expire, extend, renew, transfer; requires current revision and request key.
- `POST /entitlements/{id}/consume`: positive quantity, reference and request key; validates active dates, eligibility, location, configured consumption event and remaining balance.
- `POST /usage/{id}/reverse`: one compensating reversal per usage entry; never deletes history.

These reuse catalog/module permissions, canonical customer access and tenant/branch/workspace item visibility. They do not grant access from payment alone. Read-only callers cannot use write endpoints. Automatic invoice scheduling is currently rejected in configuration rather than being presented as operational.

## Verification

- 76 tests passed across native offerings, existing shared catalog, POS master compatibility and existing service checkout, including a fully paid POS plan issuance/replay test.
- TypeScript `tsc --noEmit` passed after catalog, CRM, POS and customer-profile integration.
- Desktop and mobile Playwright checks passed for all five types using the existing application shell and editor workflows. Fixtures are restricted to browser tests; runtime code contains no seeded demo records.
- All 14 catalog browser scenarios passed across the broad run and focused rerun. Two older tests were updated to use the existing Product name label and follow the current mobile section navigation; the mobile category case passed on its focused rerun.
- The final focused offering/migration suite passed 17 tests. CRM, taxonomy and branch-reuse tests passed before a native-pack regression exposed historical Services with inventory tracking set. The API now preserves that legacy input compatibility while still coercing Services to non-stock; all 54 native-pack catalog tests passed after the fix.

Visual evidence is in `output/catalog-offerings/`: desktop/mobile catalog and editor screenshots for each type, plus four side-by-side comparison sheets. Computed card font, size, padding and radius are asserted equal across the five kinds. Products and Services retain their existing distinct editor implementations; the new kinds extend the Product compact editor.

## Remaining acceptance work

The requested end-to-end feature set is not complete. Do not describe the current branch as production-ready:

1. Bundle component selection at checkout, recursive fulfillment, inventory movement/restoration, tax and discount allocation, component scheduling and partial refunds.
2. Automatic POS entitlement discount resolution and stacking, customer benefits lookup in the cart and balance presentation.
3. Appointment confirmation/attendance consumption and cancellation/no-show reversals.
4. Native selected-context enrollment for customer plans and their audit/usage children.
5. Automatic billing jobs and idempotent payment webhooks, trials/grace enforcement, upgrade/downgrade/proration, renewal allowance reset/rollover and notifications.
6. Operational employee assignment, optional project/task template execution and employee benefit permissions.
7. Revenue/utilization/renewal/churn reports and exports based on actual transactions.
8. Real PostgreSQL migration, concurrent consumers, deployed-UI/API integration, tax/refund and full role-matrix acceptance tests.

The deliberate rejection paths prevent unsupported bundle sales, automatic billing or selected-context customer-plan writes from appearing successful while omitting required stock, finance or isolation behavior.
