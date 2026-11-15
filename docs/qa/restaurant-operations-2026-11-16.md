# Restaurant operational integration

Source: isolated `codex/restaurant-operations` checkout seeded from the in-progress source snapshot `a1ea850b1a94884b7a4d0595ed96f376796f16ec`, whose parent is main commit `5f41e2c3`. The original working checkout was left intact. Review the owned changes against the snapshot, not against main alone.

Implementation commits, pushed only to `origin/codex/restaurant-operations`:

- `3502cc2d`: Restaurant backend, migration 117, and backend tests.
- `da31a600`: separately reviewable native delete extraction and exact request-operation registrations.
- `b1a6d5a1`: separately reviewable existing Restaurant screen wiring and real browser test.

## Resulting behavior

Existing tables/tabs, canonical catalog menu products and modifiers, table transfers, kitchen prepare/ready/serve, native invoices, partial/final receipts and anonymous settlement remain in place.

Unissued, unbilled whole lines can be removed only with both native create/delete rights and the Restaurant order capability. An issued line, incomplete modifier group, billed/paid source, stale revision, or removal of every remaining line is rejected. The actual native draft line is deleted; quantities are never zeroed. Original charge/quantity/tax snapshots remain immutable, with a frozen original line identity and a nullable live FK. A database check prevents repointing an active snapshot to a different native line. Missing lines require exact immutable cancellation commands. Migration downgrade refuses to discard cancellation provenance.

Table reservations use the canonical IndustryRecord with the explicit `restaurant_reservation` kind. They reference actual Restaurant tables, capacity, times and optional canonical CRM customers. Company writer serialization protects overlapping bookings, including bookings hidden by native Own visibility. Rescheduling, cancellation, elapsed no-show and seating at an existing matching open tab use revisions and UUID retries. Reservations have no service/provider/price/PMS fields, and cannot enter appointment visit/invoice paths.

Daily summaries report current states of orders/tickets created on the selected local day and reservations starting on that day. They are operational counts, not a cash/revenue report. Native visibility and company/branch/pack ownership remain in force. Chef/Server roles cannot read the manager report; an additional Hospital assignment does not expand Restaurant rights.

The UI patch reuses Card, Button, Input, NativeSelect and GridTable. It adds modifier selection, removal, transfer, reservation and summary controls without CSS/menu/layout-system changes. Reservation actions wait for the refreshed revision after rescheduling. No deployment or RuntimeSupport activation occurred.

## Verification

All commands use the existing backend virtual environment and the isolated backend as cwd. `FAST_TEST_PASSWORD_HASHES=1` is the existing explicit test-only bcrypt setting; assertions and timeouts were not weakened.

- Full Restaurant backend matrix: **171 passed, 144 warnings, 991.11 seconds**. Targets: test_restaurant_kitchen.py, test_restaurant_tabs.py, test_restaurant_modifiers.py, test_restaurant_modifiers_http.py, test_restaurant_transfers.py, test_restaurant_settlement.py, test_restaurant_anonymous.py, test_restaurant_customer_assignment.py, test_restaurant_payment_callback.py, test_restaurant_header_references.py, test_restaurant_removals.py, test_restaurant_reservations.py, test_restaurant_reports.py, test_restaurant_cancel_migration.py. Arguments: `-q --tb=short --junitxml=../restaurant-regression.xml`.
- New-workflow matrix: **22 passed, 16 warnings, 119.47 seconds**; included removal rollback/retry, complete modifiers, bill after removal, native-delete denial, reservation conflict/capacity/lifecycle, role/cross-pack reporting and migration provenance.
- Final schema/source smoke: **10 passed, 4 warnings, 42.69 seconds**.
- Valid native invoice attempt against an unpriced reservation: **1 passed, 2 warnings, 13.84 seconds**, actual HTTP 409, with no invoice binding.
- Supplemental anonymous settlement after removal: **1 passed, 4 warnings, 40.14 seconds**, with fresh HTTP-request sessions on the fixture outer transaction. Insufficient full tender is rejected; failure of the second native allocation leaves no invoices/receipts/customer binding/stock changes; identical retry and replay settle exactly once. The initial reused-SQLite-session retry collision was reproduced and then tested with production-shaped session lifetimes; no shared ownership checks were changed.
- Frontend main TypeScript project: `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`, exit 0.
- Final frozen browser batch: **4 passed, 8 warnings, 302.14 seconds**. Targets: the unpaid tab/kitchen scenario in test_restaurant_tabs_browser.py, both scenarios in test_restaurant_settlement_browser.py, and test_restaurant_extensions_browser.py; RUN_CONTROL_BROWSER=1. Actual API responses, canonical named customer, modifier removal, transfer, reservations, split settlement and Chef denial were verified at 1440/390 widths. Strict request-error and page-overflow assertions passed.
- PostgreSQL migration/concurrency: pending the integrator-assigned recovered loopback test slot. The native test module is present but no unexecuted native test is counted as passing.

Successful JUnit/log evidence and separate backend/shared/frontend/migration patches are retained in the isolated checkout, with review patches under `.local/restaurant-review/`. Failed development runs are not counted as passes. The initial browser output-directory issue, a repeated-activation test fixture error, and a real stale-revision UI race were corrected; strict browser error/overflow checks remain.

## Shared integration and remaining gates

Integrator coordination approved migration 117 and the finite integration changes. Shared files changed are `backend/app/apps/srm/api/router.py` (native commit=False deletion extraction), `backend/app/business_packs/request_operations.py` (six exact route rules) and `backend/alembic_postgresql/schema/extensions.json` (one column). No shared authorization engine, Payroll/Home, Company-master adapter, accounting helper, master or ledger was replaced.

PostgreSQL must still verify the deployed migration chain and competing reservation/removal/kitchen commands, as well as the existing transfer/settlement/anonymous concurrency matrix. Apply the schema and shared integration patch together with the owned backend before enabling the new surface. Persisted cancellation deliberately retains at least one tab item and rejects issued/billed items; whole-tab voiding/refunds are outside this change.

This document does not claim native release completion while that evidence gate remains open.
