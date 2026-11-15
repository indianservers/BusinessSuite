# Restaurant operational integration

Source: isolated `codex/restaurant-operations` checkout seeded from the in-progress source snapshot `a1ea850b1a94884b7a4d0595ed96f376796f16ec`, whose parent is main commit `5f41e2c3`. The original working checkout was left intact. Review the owned changes against the snapshot, not against main alone.

Implementation commits, pushed only to `origin/codex/restaurant-operations`:

- `3502cc2d`: Restaurant backend, migration 117, and backend tests.
- `da31a600`: separately reviewable native delete extraction and exact request-operation registrations.
- `b1a6d5a1`: separately reviewable existing Restaurant screen wiring and real browser test.
- `1dbce4727`: production-shaped anonymous retry proof.
- `7c74be14e`: authenticated cancellation history retention and adversarial tests.
- `0f0cd69ff`: separately reviewable finite shared branch-history retention hook.
- `c41fff912` and the final evidence commit: verification documentation.

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
- First frozen PostgreSQL matrix: **34 passed, 6 failed, zero skipped, 123 warnings, 413.03 seconds**. Actual pre-117 data migration, reservation races, reports, transfers and settlement/anonymous concurrency passed. Cancellation success paths hit SQLSTATE 23514 from the unchanged migration-107 branch-history guard: generic branch cleanup attempted to delete a historical ownership anchor.
- Integrator-approved correction retains both historical ownership anchors only for the authentic typed Restaurant cancellation lease. A private issued-certificate set, exact session/object/native-row identity, current native DELETE/parent/source checks and original snapshot proof are required. Trigger 107, native FKs and all unrelated deletion paths remain unchanged.
- Corrected cancellation SQLite matrix: **13 passed, 18 warnings, 85.43 seconds**; includes forged flag/dict/unissued lease and wrong-line denial, remove-add, and rejected native-ID tombstone adoption. Default public native deletion parity: **1 passed, 3 warnings, 7.47 seconds**, with ordinary unowned legacy branch metadata still cleaned. These targeted SQLite checks precede the final native gate below; they do not substitute for PostgreSQL evidence.

- Final frozen PostgreSQL correction gate: **20 passed, 43 warnings, 196.52 seconds**, exit 0, zero failures/errors/skips. Exact targets: `tests/test_restaurant_removals.py tests/test_restaurant_operations_concurrency.py tests/test_restaurant_cancel_migration.py -q --tb=short --junitxml=../.local/restaurant-review/evidence/restaurant-native-retention.xml`, through the guarded original `run_snapshot_owned_postgres.py --backend <isolated backend> --label restaurant117`. This reruns all six previously failing cancellation scenarios plus adjacent native deletion, anti-forgery, fresh native identity, reservation/kitchen races and actual legacy-data migration. All **2,259 frozen source/test files** matched HEAD `c41fff9120646dd89697aea53b4971c06129dd2e` before and after; the original 171/backend and 4/browser runs preceded this internal retention correction and are not represented as full post-correction reruns. The owned launcher terminated, disposable database cleanup completed, and the integrator received the slot release.

Successful JUnit/log evidence and separate backend/shared/frontend/migration patches are retained in the isolated checkout, with review patches under `.local/restaurant-review/`. Failed development runs are not counted as passes. The initial browser output-directory issue, a repeated-activation test fixture error, and a real stale-revision UI race were corrected; strict browser error/overflow checks remain.

## Shared integration and remaining gates

Integrator coordination approved migration 117 and the finite integration changes. Shared files changed are `backend/app/branches/boundary.py` (finite typed cancellation history retention), `backend/app/apps/srm/api/router.py` (native commit=False deletion extraction), `backend/app/business_packs/request_operations.py` (six exact route rules) and `backend/alembic_postgresql/schema/extensions.json` (one column). No shared authorization engine, Payroll/Home, Company-master adapter, accounting helper, master or ledger was replaced.

PostgreSQL has verified the deployed migration chain and actual pre-117 data conversion, reservations, transfers, settlement and anonymous concurrency. The final 20-case gate additionally verifies corrected cancellation success/duplicate-command races and highest-line deletion/re-add with non-recycled native identities, without relaxing tombstone ownership checks. Apply the schema and shared integration patch together with the owned backend before enabling the new surface. Persisted cancellation deliberately retains at least one tab item and rejects issued/billed items; whole-tab voiding/refunds are outside this change.

The assigned Restaurant workflow gates are complete on the isolated snapshot. Integration into the consolidated source and application of migration 117 remain integrator work; production activation/deployment was not performed. The frontend main TypeScript project was checked, not the separate full multi-project npm typecheck.

Final review hygiene removed only an extra EOF blank line in the browser harness after the frozen gate; `node --check` and the full owned diff whitespace check pass. No application source or assertions changed after native verification.

## Main integration verification

At the user's explicit request, all nine owned Restaurant commits (excluding the in-progress snapshot commit) were cherry-picked cleanly onto `origin/main` at `fe4e437db5bbe79faf4ba7a93113e2863f414a78`. Existing POS currency, Pharma, Retail and consolidated desktop/mobile changes were preserved. Twenty owned file blobs, including Restaurant UI and browser harness, matched reviewed branch `3fc9480e1` exactly; only three shared files required additive automatic merges. The branch boundary retention hook also matched the reviewed source exactly.

The actual integrated candidate passed **25 tests, 1 explicitly deselected, 21 warnings in 152.11 seconds**: `tests/test_restaurant_removals.py tests/test_restaurant_reservations.py tests/test_restaurant_reports.py -k "not test_postgres_removing_highest" -q --tb=short`. The deselected native-sequence case passed in the prior 20-case PostgreSQL gate. Frontend main `tsc --noEmit -p tsconfig.json` exited 0. Full owned diff whitespace check passed. No additional PostgreSQL/browser run or production migration/activation/deployment was performed for this main integration. Other agents' uncommitted files in the original checkout were left intact.
