# Consolidated Business Pack foundation verification

Verified source: `dacb87e622a1c6d153f4452a729997de7ff3f66e` on main.

## Current-source results

- Anonymous canonical account birth, checkout and exact branch enrollment: **62 passed**, 88.01 seconds. Targets: `test_anonymous_birth.py`, `test_anonymous_cash_checkout.py`, `test_anonymous_enrollment_owner.py`. JUnit: `.local/anonymous-main-verification.xml`.
- Record boundaries, legacy compatibility, registry and private master enrollment: **140 passed**, 28.58 seconds. Targets: `test_business_pack_boundary.py`, `test_business_pack_legacy_boundary.py`, `test_business_pack_registry.py`, `test_business_pack_master_enrollment_guards.py`. JUnit: `.local/current-pack-isolation-verification.xml`.

Both batches ran from the original backend using its existing virtual environment, `FAST_TEST_PASSWORD_HASHES=1`, and without the PostgreSQL test URL overrides. They are SQLite regression evidence, not PostgreSQL concurrency or full application acceptance evidence. The source stayed unchanged during these batches.

## Behavior verified

A newly created canonical counter account receives its availability row and exact native branch ownership in the same transaction. Repeated enrollment reuses the exact owned row. Missing, inactive or mismatched existing ownership is rejected rather than adopted. Caller rollback removes the new graph and its ownership records.

The isolation batch checks ORM queries and cached identities, relationships, aliases, counts, raw/core projections, bulk writes, immutable source ownership, revoked grants and explicit master availability. It also checks legacy operations on unrelated unowned records. Private operational records cannot become shared masters through enrollment.

## Remaining release gates

These results do not certify all seven packs. Pack-specific functional, native PostgreSQL, concurrency and desktop/mobile evidence must be reconciled with the final consolidated source. Runtime activation remains disabled pending those gates. No production migration, deployment, or UI change was performed by this verification.

## Pharma backend integration

The subsequent backend integration adds migration 118, exact three-decimal dispensing for authorized Pharma batch-and-expiry medicines, and paginated affected-sales recall tracing. Other sale quantities retain two decimals; the historical ten-digit update range remains supported. The migration expands PostgreSQL quantity capacity without narrowing existing wider storage or rounding issued history.

The integrated source passed **32 tests**, 191.68 seconds: `test_pharma_dispensing_precision.py`, `test_pharma_precision_accounting.py`, `test_pharma_trace.py`, and `test_service_checkout.py::test_pack_foreign_provider_cannot_be_adopted_as_specialist`. JUnit: `.local/pharma-precision-main-verification.xml`. These SQLite checks cover actual canonical sale/refund postings, unsupported precision, cross-pack denial, rollback/retry and recall visibility. Eight protected refund/accounting/authorization files were unchanged; donor Python AST parity was verified for all owned sources, preserving the additive Restaurant router extraction. Proof: `.local/pharma-precision-main-source-proof.json`.

The isolated donor PostgreSQL gate recorded 145 passes and one migration-fixture failure before the migration was invoked. After correcting the missing historical order number, the finite migration gate passed all four cases. That evidence is source-specific and is not represented as a consolidated full PostgreSQL rerun. Pharma POS preview/browser follow-up is separate; this backend integration changes no UI.

The subsequent Pharma POS calculation patch retains the existing layout, classes, styles, buttons and global currency functions. It applies integer-cent preview calculations only to selected Pharma baskets containing FEFO lines, permits the verified three-decimal FEFO quantity step, and displays fractional payable amounts with cents. Actual serialized price and discount values feed the preview. Unsupported values remain subject to the native checkout validation.

All **17 native monetary golden cases** pass on the integrated helper. The POS source matches the reviewed browser donor after line-ending normalization; **544 JSX tag/style/static-text entries** and legacy formatter bodies match the pre-change design. Proof: `.local/pharma-fefo-main-design-proof.json`. The isolated final PostgreSQL browser batch passed **six cases**, 289.426 seconds, including actual 0.125 × 1.09 checkout/replay at 0.17 and mobile footer amounts of 0.17 and 0.12. It is a finite browser gate, not a full application suite.

## Checkout rollback and schema probes

The next integration expires only tracked native product quantity caches after a checkout savepoint rolls back. Canonical stock balances and commands remain unchanged. Installation checks use the existing fresh name-only schema probe, retaining the same required model/FK columns without retaining stale metadata between calls.

Current-source SQLite verification: **31 passed**, 96.25 seconds, across `test_service_workflow_recovery.py`, `test_service_pack_role_composition.py` and `test_service_checkout_schedule.py`. JUnit: `.local/service-recovery-main-verification.xml`. Tests cover failed native receipt allocation, original-key retry, caller savepoint rollback after a cached stock read, unavailable employees and context-specific service/financial permissions.

The isolated Hospital/Salon donor also retains a 98-case PostgreSQL target gate and a subsequent 11-case PostgreSQL race/schema gate, including eight independent-request races and three schema invalidation checks. These are source-specific evidence, not a full current-source suite claim. The integrated race tests retain native bounded-busy responses, advised same-key retry, canonical row counts and the existing total workflow deadline. No UI or runtime activation changed.

## Durable cash movements and Restaurant installation checks

Migration 119 adds optional UUID intent provenance to the existing native cash movement. A company/key identifies one immutable movement and its original actor, register, branch, business context, currency and normalized body. An exact retry returns the original movement ID and a fresh summary; conflicting reuse is rejected. Existing keyless rows remain supported and unchanged. Native write permission, current context and currency are rechecked around writer acquisition, insertion, commit and replay.

The existing POS callback retains the original body/key until acknowledgment. It requires a fresh server capability marker before sending a keyed command, preventing an older backend from silently accepting it as an unprotected keyless movement. Layout, styles, buttons, cash-close logic and Pharma cent calculations remain unchanged. Apply the backend and migration before enabling the frontend callback.

Restaurant readiness now checks its deployed domain tables, native scoped FKs, uniqueness, cancellation provenance and branch-history guards in addition to the foundation tables. Missing or weakened installation blocks readiness. This does not publish runtime support or activate a pack.

Verification: **28 PostgreSQL tests passed**, zero skips/failures, 106.42 seconds: four real cash concurrency/migration cases, 21 cash API/Retail cases, and three Restaurant catalog/readiness cases. Current-source SQLite verification passed **50 tests**, 76.33 seconds. The main frontend TypeScript project passed. The callback's eight recovery/version scenarios and 544 unchanged design entries were verified on the reviewed current-page candidate. All 15 integrated backend/test sources and both frontend sources match that tested material after line-ending normalization. Evidence: `.local/cash-readiness-main-source-proof.json`, `.local/cash-readiness-main-verification.xml`, and `.local/parallel-cash-restaurant-native/20261116-caeb119/native-terminal-proof.json`.

## Construction material warehouse selector

`GET /srm/industry/material-warehouse-options` supplies only canonical warehouse IDs and names, with literal search and 50-row pagination. It retains native SRM view permission, exact Construction `materials.request`, active branch ownership and explicit current-context master availability. Any private operational warehouse is excluded, including one owned by the current context. Authority and the returned source page are rechecked before returning; no stock data, write lock or mutation is exposed. The general warehouse route remains unreleased for this context.

Current-source verification: **37 passed, one PostgreSQL-only row-lock test skipped**, 123.94 seconds, across `test_construction_warehouse_options.py` and `test_business_pack_construction.py`. Tests include ordinary native users, missing permissions, Doctor/Chef contexts, inactive or unenrolled warehouses, private sources and original Construction operations. The four source files match the reviewed candidate. Evidence: `.local/construction-warehouse-main-verification.xml` and `.local/construction-warehouse-main-source-proof.json`. This backend selector changes no UI; wiring the existing material form is a separate Construction integration step.

## Production dependency compatibility

GitHub's PostgreSQL readiness run at `49e0375bd` failed collection because the shared planned-services module imported `jose`, absent from production dependencies. It now uses the same installed PyJWT API and exception base as the core security module. Cursor algorithms, audience, signing secret, expiry handling and validation logic are unchanged.

All **60 tests passed**, 86.62 seconds, across the four affected employee-planning/scheduling modules. All 60 also collect successfully with imports of `jose` explicitly blocked. AST comparison confirms only imports changed. Evidence: `.local/planned-services-pyjwt-verification.xml` and `.local/planned-services-ci-import-proof.json`. The subsequent GitHub readiness run must be checked separately; local results are not represented as a successful CI run.


## Leave routing browser teardown

The existing browser harness now drains pending route callbacks before closing its context, then checks HTTP and page errors again. Nested cleanup always closes the context, browser and server. All eight original assertions, selectors, timeouts and route callbacks are preserved; application UI source is unchanged.

The frozen candidate passed one actual native-API browser test at desktop 1440 and mobile 390 pixels in 29.45 seconds. Five focused teardown scenarios also verify that late HTTP failures, route failures and page errors still fail and cleanup runs. Main matches the tested script after line-ending normalization; `node --check` and `git diff --check` passed. Evidence: `.local/leave-routing-native-final-c315/result.json` and `.local/leave-routing-main-proof.json`.


## Deterministic quoted CRM lead searches

Explicit closed commands such as `Show me lead records containing "Cedar"` now preserve the exact quoted text as the native CRM lead search payload without neural inference. Empty, unterminated, overlong or compound commands ask for clarification instead of returning an unfiltered list. Other explicitly selected modules remain separate. The conservative parser limit is 200 characters; this is not claimed as the native endpoint limit. Native tool authorization and validation remain unchanged.

Current main-source verification passed all **55 tests** in 1.01 seconds across quoted searches, the common action catalog and the existing safe read grammar. Evidence: `.local/quoted-crm-main-verification.xml`. No application UI files changed.


## Accounts delivery integration

Integrated the focused 38-file Accounts candidate without merging donor ancestry. All 38 sources match the reviewed candidate after line-ending normalization. The independently documented native evidence covers 179 distinct PostgreSQL cases, including 11 concurrency cases; see `accounts-delivery-final-2026-11-16.md` for source-specific results and provider limits.

On the integrated main working tree, all **14 focused tests passed**, zero skips, in 113.15 seconds across native project selectors, immutable project links and the default/transaction-owned PMS attachment operation. Full frontend TypeScript checking exited zero. Evidence: `.local/accounts-main-source-proof.json` and `.local/accounts-main-focused.xml`. Existing desktop/mobile styles, shared layouts and menus are unchanged; Accounts-specific controls reuse existing components. Runtime support remains unpublished pending foundation and activation gates.


## Committed test-race isolation and commercial fixture ownership

The concurrent master-capture test previously committed its actor, branch and winning company into the suite database through an independent session. It now reuses the existing fully migrated, disposable PostgreSQL race fixture. Both original and legacy collection paths retain their 15-second barrier and exact `[201, 409]` result, verify the winning native ownership, and assert six primary-table key sets remain unchanged. The connected-commercial fixture now explicitly owns its existing CRM team member alongside the other fixture records. No production behavior or original response assertions changed.

Current integrated-source PostgreSQL verification passed **4 tests**, zero skips, in 52.02 seconds across both race collection paths and two commercial workflows. Guarded provisioning cleaned up its owned database. SQLite compatibility passed **2 tests**, with the one PostgreSQL-only race skipped, in 15.93 seconds. A separate donor-source 13-case PostgreSQL canary also passed and independently observed zero primary residue after each race; its older source is not represented as a complete current-main suite. Evidence: `.local/master-race-main-postgres.xml` and `.local/master-race-fixture-main.xml`.


## Cash recovery across registers and concurrent tabs

Cash Save now recovers an existing immutable body/key within the same user/company/branch/business context before accepting a new movement, including when its original register has closed or another register is active. A successful recovery finishes that click without creating a second movement. Exact closed-register absence is signaled only through three specific headers after fresh native authority, currency, company-wide key absence and writer checks; the existing HTTP 400 response body is unchanged. Other errors retain the pending command. Access and context are checked again after asynchronous refresh before updating the form.

A non-waiting exclusive Web Lock covers the whole Save operation, including pending storage reads, submission and acknowledgment. Its scope spans registers in the same financial context. Unsupported, denied or occupied locks submit nothing. The existing form and design are preserved; 544 design entries and 1,297 JSX structure entries match the reviewed baseline. This coordinates participating same-origin tabs; it does not deduplicate unrelated commands with different UUIDs or coordinate older clients that do not use the lock.

Current integrated source passed **48 portable callback/store/form scenarios** and an actual two-worker Web Locks concurrency model with one UUID, one POST and one deferred worker. The model is explicitly not a real-browser or live-provider test. All **8 PostgreSQL absence/replay/Retail tests passed**, zero skips, in 26.78 seconds using guarded owned-database cleanup. All seven integrated sources match the final candidate SHA manifest. Evidence: `.local/cash-recovery-main-source-proof.json`, `.local/cash-recovery-main-postgres.xml`, and `.local/parallel-cash-locks/d069-final/final-manifest.json`.

The integrated full frontend TypeScript project also completed successfully with zero diagnostics.


## Restaurant immutable split bills

Integrated migration 120 and the focused Restaurant split-billing backend on current main. Immutable allocations reuse the original tab/charge snapshots and native invoices, receipts, allocations and register totals. Partial collection, exact replay and original-source reservation prevent overcollection and duplicate whole-tab billing. Chef and other business contexts retain their existing permission boundaries. Shared additions preserve Accounts billing hooks, cash intent protections and every existing schema-extension entry; migration 119 is unchanged. No frontend source changed in this backend integration.

Current integrated-source checks passed **56 functional tests** (304.10 seconds), **6 PostgreSQL migration/concurrency tests** (113.06 seconds), **8 adjacent cash/Retail PostgreSQL tests** (27.14 seconds), and **1 independent PostgreSQL raw-commit test covering five late mutations** (54.43 seconds). All cohorts had zero failures or skips. The raw proof confirms actual SQL guards rather than relying on the ORM listener. Guarded owned-database cleanup completed. Source qualification, evidence and remaining UI/activation/full-suite gates are recorded in `restaurant-split-billing-2026-11-16.md`. Runtime support remains unpublished.
