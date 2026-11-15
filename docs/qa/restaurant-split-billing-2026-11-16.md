# Restaurant split billing â€” integration verification

Restaurant tabs now support immutable allocations of original charge quantities into separate canonical invoices. Each invoice supports partial and final native collections. Split billing reserves the original tab and lines, so whole-tab billing cannot charge them again. Original sales-order quantities, inventory and ledger operations remain canonical.

Cash projections count only actual receipt allocations in the exact collection register. New collection provenance retains the native cashier and currency and must remain valid through the outer transaction. Existing historical payments remain readable after their register closes. Missing or partial attribution schema with known split provenance fails closed; unrelated legacy-empty registers retain their previous zero projection.

## Integrated source and shared boundaries

The focused backend patch was integrated onto `ec4af18b5`; snapshot ancestry was not merged. Accounts billing and project hooks remain present. Exactly four schema-extension entries were added, preserving every prior key/value and migration 119 unchanged. Three current shared files required additive merges; three frontend-dependent DTO/capability/test additions remain in the separate UI overlay.

Migration `pg_20261116_120_rest_split` depends on `pg_20261116_119_cash_intent`. It retains four immutable provenance tables, native scoped relationships, source and quantity guards, and deferred PostgreSQL commit checks. Downgrade refuses retained history. Runtime support is still unpublished; these checks do not activate a business pack.

## Current-main verification

- 56 functional tests passed, zero skips or failures, 304.10 seconds: split bills, projection/schema quarantine, immutable allocations and settlement audit.
- 6 PostgreSQL tests passed, zero skips or failures, 113.06 seconds: actual migration 119â†’120 preserving native records, missing/partial-schema denial, and five independent transaction races.
- 8 adjacent PostgreSQL cash-intent/Retail tests passed, zero skips or failures, 27.14 seconds, after the shared register-cash hook was integrated.

Evidence: `.local/restaurant-split-main-sqlite.xml`, `.local/restaurant-split-main-postgres.xml`, `.local/restaurant-cash-main-compat-postgres.xml`, `.local/restaurant-main-source-proof.json`, and `.local/restaurant-main-transitive-preservation.json`. PostgreSQL jobs used guarded owned databases and completed cleanup.

## Independent review and remaining work

Earlier peer review reproduced seven genuine failures involving late register mutations and incomplete attribution tables/columns; those failures prompted the finite correction. Its targeted 13-case correction and coherent 58-case donor run passed before integration. These overlapping cohorts are not added to the current-main totals. Earlier source-qualified evidence and failed attempts remain in the donor evidence directory and `.local/restaurant-split-qa-before-main-integration.md`.

A separate raw-connection PostgreSQL test must prove deferred SQL guards independently of the ORM commit listener. Its first attempt failed before collection because a direct-service fixture omitted the authenticated company binding; only the fixture was corrected, and that attempt is retained. The corrected test also passed on the integrated main working tree: **1 test passed in 54.43 seconds**, covering close, reassignment, currency change and shared-cashier changes rejected by deferred SQLSTATE 23514, plus register deletion rejected by FK SQLSTATE 23503. It bypasses the ORM outer-commit listener and verifies that each rollback preserves the earlier cash payment of 10 and remaining balance of 49. Evidence: `.local/restaurant-split-main-raw-postgres.xml`. Restaurant controls, native browser verification, first activation and final full-suite verification are separate gates. No release-complete or production-activation claim is made.


## Existing-style split-bill controls

The separate six-file overlay adds item-quantity selection, exact-cent bill previews, invoice balances, partial collections and an authorized link to existing register closing. It reuses existing cards, inputs, selectors, buttons and grid components; no shared menu, layout or style file changed. The capability response adds an explicit native-plus-pack closing permission and invoice projections expose the canonical invoice number.

All six integrated files match the frozen native-browser candidate. Current-main capability/closing checks passed **4 tests in 38.95 seconds**; the full frontend TypeScript project completed with zero diagnostics, and the browser script passed syntax checking. The donor actual-app browser passed **1 test in 145.65 seconds** at 1440/390 widths: two invoices of 59 from one original order, cash20/card39/cash59 receipts, cash-only closing79, table release, and Chef/Cashier restrictions. Its five known shared follow-up/statistics HTTP503 responses are explicitly retained as unresolved integration errors; the browser test is not represented as a zero-HTTP-error full-app signoff. Mobile screenshot was visually inspected and retains existing components. Evidence: `.local/restaurant-ui-main-source-proof.json`, `.local/restaurant-ui-main-caps.xml` and donor `restaurant-split-browser-verification.json`. Pack activation and full-suite verification remain outstanding.
