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
