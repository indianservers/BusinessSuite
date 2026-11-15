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
