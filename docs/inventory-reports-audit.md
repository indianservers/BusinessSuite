# Inventory reports: accuracy audit and implementation

Date: 19 November 2026. Scope: the existing Business Suite Sales and Finance inventory reports. This delivery improves reporting and posting accuracy; **full enterprise acceptance remains conditional on the gaps listed below**. Production data was not accessed or changed.

Final verification: **10 unique live-browser cases passed, 0 failed**; **97 inventory backend tests passed, 1 skipped**. The browser total consolidates the nine-case run and the later classic-route check; two repeated targeted cases are counted once. The skipped backend case requires real PostgreSQL concurrency/load testing. A separate Sales/POS/catalog compatibility run passed 67 tests; it overlaps the inventory suite and is not an additional 67 unique inventory cases. TypeScript validation and diff checks passed. All **26 Excel/PDF export pairs** were validated against response snapshots.

## Evidence

- [Browser results](../output/inventory-live-audit/results.json), [classic-route retests](../output/inventory-live-audit/classic-rerun-results.json), [case and export validation](../output/inventory-live-audit/audit-summary.json).
- [Screenshots and downloadable Excel/PDF snapshots](../output/inventory-live-audit/screenshots.html).
- [Database checks](../output/inventory-live-audit/database-validation.json). Each report also has a `*-response.json` snapshot and per-workflow observations in that directory.

The browser suite logs in through the real application, creates isolated records through authenticated HTTP requests, and operates actual report controls. It has no route interception or mocked report responses. Its ten cases cover 13 views in each stock realm, 15 classic report routes, responsive controls, filters, pagination, a populated batch report and downloads. Transactions are posted to the disposable SQLite database; they are not static frontend fixtures. Transaction-entry forms themselves are not exhaustively exercised by this report suite.

## 1. Architecture and source of truth

Sales and Finance are separate stock realms and must not be added together. A Sales invoice, POS checkout and stock movement can describe the same sale; the report reads the stock movement once rather than summing all three documents.

- **Sales master:** `SRMProduct` in `backend/app/apps/srm/models.py`. Shared Products/Services/Memberships/Subscriptions/Bundles catalog entries use this master. Physical reports exclude services, memberships, subscriptions and bundles. Actual component movements remain eligible physical product movements.
- **Sales quantities:** `SRMInventoryBalance`, keyed by company, product and warehouse. `SRMProduct.current_quantity` is a cache, not a warehouse quantity. `SRMInventoryMovement` is the posted movement history; it has no draft-status field. Order/invoice drafts are not stock movements.
- **Finance master and cache:** `FAMStockItem` has current quantity, average cost, costing configuration, units, thresholds and warehouse defaults. `FAMStockMovement` plus `FAMStockMovementLine` is the transaction ledger. Both header and line company, and header `status=posted`, are checked. `balance_quantity` on an old Finance line is product-wide; it is not used as a warehouse running balance.
- **Opening stock:** Finance retains `FAMStockOpeningBalance` and a corresponding posted movement. Reports count the movement only. Sales opening stock also creates its native movement and warehouse balance.
- **Purchases, sales and returns:** Finance stock documents use the existing `create_posted_stock_document`/`post_stock_movement_record` paths. Generic movements retain their actual movement type and source identifiers. Purchase/sales return directions are calculated from recorded incoming/outgoing quantities, not guessed from invoice totals.
- **Transfers and adjustments:** `FAMStockTransfer`/`FAMStockAdjustment` create posted ledger movements. Sales creates paired transfer-in/out movements. A transfer changes two positions, with net zero company quantity and cost. These existing workflows are immediate posting workflows; they do not have independent dispatch/receipt or in-transit accounting.
- **Reservations:** `FAMInventoryReservation` stores active reserved quantity, optional warehouse allocation and expiry. Expired reservations no longer reduce availability. The Sales ledger has no equivalent reservation balance; its available quantity is explicitly unknown.
- **Valuation and receipt layers:** `FAMInventoryValuationLayer` stores receipt quantities, original costs and remaining quantities/values. New postings maintain these layers. Original receipt amounts remain recorded. Reports retain historical movement costs and do not revalue old issues at a later selling price or average.
- **Batch/serial/expiry:** Sales has `SRMInventoryBatch` and `SRMSerialNumber`; batch available quantity, unit cost and dates support the current expiry report. Finance movement lines do not carry batch identity. Historical batch availability cannot be reconstructed from current batch rows.
- **Commercial and finance links:** purchase bills, GRNI, Sales orders/invoices, product integration links and vouchers remain in their native modules. The existing gross-margin report uses explicit invoice attribution, not description matching. An unlinked or unresolved revenue credit does not become fabricated profit.
- **Business Packs:** Retail/Pharma retain their native stock workflows and reporting selection. Shared-ledger analysis rejects a selected pack context rather than reading the wrong stock realm. Embedded Flask inventory sources are not independently merged into these totals.

Frontend path: `FAMWorkspacePage.tsx` continues to own the existing report routes and headers. Its report content uses `InventoryReports.tsx`, existing Card/Button/Input/NativeSelect/GridTable/Recharts components and existing responsive conventions. Sales retains the native Retail workspace wrapper. The shared reporting query is in `backend/app/shared/inventory_reporting.py`; it extends `/fam/inventory/reports?analysis=true` and `/srm/inventory/reports`.

## 2. Reports audited and enhanced

The existing report workspace now has Overview, Stock summary, Stock ledger, Valuation, Purchases, Sales movement, Low stock, Stock ageing, Expiry & batches, Adjustments, Transfers, Dead stock and Reconciliation views. The classic summary, warehouse, ageing, reorder, dead-stock, valuation and Finance item-ledger pages reuse this same corrected component and server queries, retaining their original route/header. Financial and other native report routes remain available.

- Summary separates opening stock, purchases, purchase returns, sales, sales returns, transfers, other adjustments, physical quantity, known reservations and available quantity.
- Ledger calculates opening/closing quantities with SQL windows partitioned by product and warehouse. Pagination and transaction/date filtering occur after the running-balance calculation. A filtered page therefore retains its correct opening balance. Exact movement-ID drill-down is available.
- Valuation sums signed, recorded movement costs through the selected date. It does not substitute selling prices, invoice totals or today's cached average for historical issue costs. Currency totals remain separate; malformed currencies have no invented monetary total.
- Purchases/sales/adjustments/transfers expose posted transaction rows and their cost, reference, creator, poster and status. Sales movement cost is not presented as revenue. The linked, existing gross-margin report is explicitly an all-dates financial report.
- Low stock uses known allocated available stock, otherwise physical stock, against existing item thresholds. No missing supplier, lead-time or demand policy is invented.
- Ageing uses actual receipt dates and reconstructed FIFO depletion of recorded quantities, not product creation or last movement date. This is an age-allocation basis, not proof of historical lot provenance. Transfers use the destination receipt date.
- Dead stock uses absence of recent commercial issues, not an arbitrary recent adjustment or transfer. Only positive stock positions qualify.
- Expiry uses current available batch quantities and costs. Unsupported Finance expiry is explicitly labelled. Historical expiry quantities are rejected because current rows are not historical snapshots.
- Reconciliation compares independently stored balances with ledger sums. Sales comparisons are per warehouse, so offsetting errors cannot cancel. Finance also compares remaining receipt layers with its stock cache. Negative stock and discrepancies remain visible, with differences and investigation guidance. No repair button or automatic historical correction was introduced.

## 3. Calculation and posting corrections

- Finance outward issues use inventory cost instead of an arbitrary submitted rate. The selected warehouse must have sufficient stock when negative stock is disabled; stock in another warehouse cannot satisfy the issue.
- The Finance posting path serializes company/item mutations and rejects an already-posted source. PostgreSQL lock behavior still needs its dedicated runtime test.
- Weighted-average cost uses recorded monetary ledger amounts, retaining currency cents instead of repeatedly multiplying a rounded unit-rate cache. Four-decimal rate-cache rounding does not replace recorded line values.
- Finance issue vouchers total recorded line values. A warehouse COGS posting uses the actual issue value, including FIFO issue cost, rather than the new remaining-stock average.
- New receipt layers are consumed on issues and retain exact total remaining value. Weighted-average currency-cent residuals are apportioned across remaining layers. Inconsistent legacy layers are preserved and reported; new receipts do not silently repair them.
- FIFO receipts and ordinary issues use ordered, reconciled receipt layers. Incomplete/mixed-method FIFO layers, specific identification without source identity, and FIFO transfers/returns without receipt provenance are rejected explicitly.
- Sales receipt/opening averages are weighted rather than simply replaced by the latest purchase rate. Transfer receipts use the actual outgoing cost.
- Finance transfer incoming cost follows the posted outgoing cost, preserving company inventory value despite a different submitted rate.
- Opening/transfer/adjustment internal movement numbers now use distinct document-type/company/record-ID namespaces. Identical source document numbers no longer collide; original references and all existing movement numbers remain intact.
- Original Finance item-ledger and purchase/sales-register reads now exclude draft, cancelled and foreign-company headers. Opening stock is not classified as a purchase.
- COGS includes recorded sales-return credits. A gross-margin row with unresolved return revenue credits is marked incomplete and has no calculated profit.
- The integrity check no longer treats zero valuation layers as a pass against positive stock, or hides a discrepancy within a whole currency unit.

## 4. Reconciliation scenarios

Controlled transaction tests verify:

1. Opening 100 + purchase 50 − sale 30 = **120**.
2. Opening 100 + purchase 50 − purchase return 10 − sale 30 + sales return 5 = **115**.
3. Opening 100, transfer 20: source **80**, destination **20**, company total **100**. Repeated posting is rejected. Browser fixtures exercise both stock realms and inspect database positions.
4. Physical **100**, reserved **20**, available **80**. Browser fixtures also verify 115 physical versus 95 available.
5. An issue of 120 against 100 is rejected with negative stock disabled. With the Finance control enabled, closing **−20** and value **−200** remain visible; they are not clamped.

Additional tests cover historical/date filtering, paginated opening balances, offsetting warehouse errors, deliberately inconsistent cache/layer values, no silent repair, FIFO versus weighted-average costs, export contents and index migrations. For receipts of 100 units at 10 and 50 at 20, issuing 30 leaves weighted-average inventory value **1,600** and FIFO value **1,700**. A large-quantity test verifies an actual **400,000** issue/voucher and **1,600,000** remaining layer/report value without multiplying a rounded displayed unit rate.

These are isolated test database findings, not a claim that a production database has reconciled. Existing production discrepancies were neither inspected nor corrected.

## 5. Browser, responsive and export verification

The live suite covers all 26 report/source combinations, real filters and date-preserving drill-down, server pagination, populated Sales batch expiry and these viewport sizes: 1920×1080, 1366×768, 768×1024 and 390×844. Mobile uses the existing native selector and collapsible filter controls; tests operate them and inspect actual ledger rows. Wide tables scroll within their container rather than widening the page.

Each case records uncaught errors, error console messages and failed API responses, and fails if unexpected errors occur. See the final JSON result for authoritative case counts/statuses. Initial development-server interruptions, a response-selector timing error and the reproduced transfer-number collision were corrected and rerun; they must not be counted as separate passing cases.

Both Excel and PDF are downloaded from the actual UI for every report/source. The artifact builder validates each Excel data row against its report response and parses every PDF. PDFs include all report columns in repeated-identity sections rather than silently dropping wide columns. Representative PDFs are rendered and inspected. Excel strings are stored as text; source names are not executed as formulas. Downloads contain the report source, date and filter basis.

## 6. Performance and deployment

Aggregation and ledger windows run in SQL. The browser receives bounded server pages of 25/50/100 rows. Filters and pagination are URL-backed and query-cache scoped. Export generation stays on the server and rejects more than 5,000 records explicitly; it does not silently truncate or load the full ledger into browser memory.

SQLite and PostgreSQL migrations add composite company/status/date, company/item/warehouse/movement and reservation indexes. The index migration is tested against the disposable database. **No production migration was applied.** PostgreSQL concurrency/load verification and production-sized query plans remain required before deployment. Background exports are not implemented.

## 7. Remaining gaps and acceptance limits

- Full supplier/category purchase analytics, purchase-price variance, frequency and outstanding-PO/GRNI drill-downs are not implemented in the new transaction report. Native purchase/GRNI screens remain the reference.
- The overview does not yet include every requested KPI/distribution or cumulative value trend. Stock movement trends are bounded to the latest 90 date/currency points; unit totals may combine different base units, which is disclosed.
- Lead-time/demand-driven replenishment, preferred suppliers and warehouse-specific threshold policies need additional authoritative configuration. Current suggestions must not be confused with such a model.
- FIFO transfers/returns preserving original layers and specific-identification documents need native provenance support. Those postings are rejected, not approximated. Transfer in-transit, partial dispatch/receipt and discrepancy workflows are not represented by the existing immediate-transfer schema.
- Historical reservation/batch balances, immutable historical unit/currency configuration and original transferred-lot age are unavailable. Historical reports do not fabricate these values. Mixed units must be compared at item level; unrecorded conversions cannot be certified.
- The existing financial margin report is not a new period-filtered revenue/refund analytics engine. Return-credit attribution remains incomplete; incomplete profit is withheld. Broad refund, landed-cost/freight allocation and financial reconciliation workflows need further browser coverage.
- Reconciliation currently detects balance/ledger, receipt-layer and negative-stock exceptions. It is not yet an exhaustive source-document orphan/duplicate/reference/batch-allocation detector. Arbitrary repeated inventory-create requests without a stable source identity are not universally idempotent; source-identified postings and existing checkout controls are separate guarantees.
- Business Pack reports, bundle component fulfillment, every entry form/action and real PostgreSQL concurrent updates were not exhaustively browser-tested by this suite. Existing unsupported bundle fulfillment is not implied to work by report availability.
- Very large exports require a background job workflow. Large-volume performance and production schema migration execution remain unverified.

These gaps prevent an unconditional enterprise-ready or production-reconciled claim.

## 8. Repeatable checks

Start the existing disposable server with `backend/venv/Scripts/python.exe backend/scripts/serve_offerings_browser_qa.py` (or `--reuse` for its existing synthetic database). It pins its database to `.local/offerings-browser-qa/audit.sqlite` and disables external integrations. Start Vite on port 5198 with `VITE_DEV_API_PROXY_TARGET=http://127.0.0.1:8799`.

From `frontend`, run `npx playwright test --config=playwright.inventory-live.config.ts`. Keep the suite serial because the first case creates the fixtures used by later cases. From the root, run `backend/venv/Scripts/python.exe backend/scripts/build_inventory_audit_artifacts.py` to validate downloads and rebuild the screenshot index. Test records are retained only in the isolated QA database for review; no real records are cleaned up.

Backend coverage is in `backend/tests/test_inventory_reporting_accuracy.py` plus the existing `test_fam_inventory*`, `test_fam_stock*` and `test_erp_audit_inventory*` regression suites. The real PostgreSQL concurrency case skips when its dedicated database is unavailable. The separate Sales/POS/catalog regression run also passed; overlapping suites must not be added together as unique cases.
