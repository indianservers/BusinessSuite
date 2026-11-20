# Memberships, subscriptions and bundles: browser audit

Date: 19 November 2026. Status: **production acceptance blocked**.

Final consolidated live-browser result: **35 unique cases passed, 0 failed, 0 skipped** after fixes and recovery reruns. Their latest observations contain **0 uncaught browser errors, 0 unexpected console errors and 0 unexpected API failures**. One additional legacy fixture regression remains failed, as detailed below. These figures cover executed cases only; unimplemented requirements remain blocked.

## Environment and evidence

Chrome through the repository's Playwright installation, with the actual Vite frontend and FastAPI application. The live suite does not intercept or mock API responses and logs in through the application's login and company-selection screens. Database assertions read the disposable SQLite database directly after important writes. Production databases, payment providers and customer records were not used.

- [Executed case statuses and totals](../output/offerings-live-audit/case-summary.json)
- [Latest Playwright rerun](../output/offerings-live-audit/results.json)
- [Server-interrupted run](../output/offerings-live-audit/interrupted-server-run-results.json) and [recovery rerun](../output/offerings-live-audit/rerun-results-1.json)
- [Five-column screenshot comparison](../output/offerings-live-audit/comparison.html)
- [Mobile editor comparison](../output/offerings-live-audit/mobile-editors-side-by-side.png)

The live case index is authoritative for executed browser cases. Unimplemented acceptance requirements below are **blocked**, not passed or skipped browser tests. The separate older browser suite uses mocked API fixtures; its 14 passing cases are frontend regression evidence only. Backend regression: **83 passed** across catalog offerings, shared catalog, service checkout and CRM deal catalog. Frontend TypeScript compilation passed.

Execution history: the final full run passed its first 21 cases, then the development server stopped and 14 cases failed with connection errors. Those cases were rerun after restart. Two bundle tests also needed to search the component selector instead of assuming their record appeared in its first 20 results; repeated synthetic runs had grown the dataset. The consolidated index reports each unique case's latest result and retains previous attempts. Raw run totals must not be added together as distinct cases.

Additional checks: route guards passed 843 anonymous-access and 651 disabled-module cases with no private-record render. One additional legacy fixture script, `frontend/scripts/test-appointments-complete.cjs`, **failed**: its defaults mock initially omitted the current payload contract; after that fixture was corrected it timed out finding the `Available resources` navigation button. This is an unresolved fixture/regression check, not a passing appointment workflow. The live appointment case separately covers All branches and an actual branch switch.

## Reproduced and fixed

- **PASS:** Open create/edit drafts survived debounced catalog refresh. Previously, list readiness temporarily changed permission-derived rendering and unmounted the editor, losing changes. The editor now uses stable permission checks while retaining ownership and server-side authorization.
- **PASS:** Membership, subscription and bundle deep links retain their selected type instead of resetting to Products.
- **PASS:** Desktop and mobile POS expose consistent offering filters and correctly label new kinds. Plan lines retain quantity one rather than merging into an unsupported quantity.
- **PASS (guard only):** Unimplemented bundle checkout is visibly unavailable before payment. An attempted direct sale returns 503 without creating a partial sales order. Bundle purchasing itself remains blocked.
- **PASS:** Customer profiles can assign existing membership/subscription definitions and use existing lifecycle APIs through shared dialogs. Requests retain an idempotency key across retries.
- **PASS:** Active Plans excludes cancelled, paused and expired/out-of-validity plans before pagination; History preserves cancelled records. Renewals uses expiry ordering.
- **PASS:** Customer profiles avoid unauthorized background finance-connection requests when branch/access prerequisites are absent. Backend finance authorization remains intact.
- **PASS:** SRM Viewer can open catalog routes authorized by existing backend read permissions. Create controls remain absent; direct writes are rejected.
- **PASS:** Bundle selectors have explicit accessible labels, reusing existing controls and styling.
- **PASS:** Appointments waits for a selected branch before loading capabilities and records; the Service editor waits before requesting scheduling options. Previously these requests produced 409 errors in All branches mode. Selecting a branch continues through the existing branch-switch confirmation.
- **PASS:** Plan and bundle editor helper text describes their own fields while preserving the existing editor layout.

## Database and workflow validation

- **PASS:** All five create/view workflows write the canonical master rather than separate module catalogs. Membership duration presets of 1, 3, 6 and 12 months persist; non-stock plans do not enable inventory tracking.
- **PASS:** Customer membership assignment, pause, resume and manual renewal persist plan state and ordered lifecycle events. Subscription assignment and cancellation preserve history.
- **PASS:** A paid membership purchased through the native POS creates an invoice for 118, payment of 118, zero remaining balance and exactly one active customer plan linked to its order line. Replaying that same checkout leaves invoice, receipt and plan counts unchanged. See the paid and replay database JSON artifacts.
- **PASS:** Editing a subscription preserves independent term and recurring-billing settings. This verifies stored configuration, not automated collection or reminder delivery.
- **PASS:** Membership edit/archive preserves the master record and archive filtering works. Invalid renewal and circular-bundle requests return 422 and leave their persisted state unchanged.
- **PASS:** Mixed bundle definitions retain products, services, plans, nested bundles, quantities and optional components. This verifies definition persistence, not fulfillment or tax allocation.
- **PASS:** Search, type filtering and pagination execute real HTTP queries. CRM and PMS catalog references use the same master records without duplicating them.
- **PASS:** Read-only mutation, private-workspace access and cross-company access fail without data changes. Deliberate 403/404 responses are expected negative-test evidence.

## Responsive and visual verification

All five listings and editors are exercised at 1920×1080, 1366×768, 768×1024 and 390×844. Assertions check page overflow, editor bounds, shell font family/font size/border radius and usable navigation. Forty screenshots cover five offerings, two views and four viewports. The comparison page arranges the existing Products and Services alongside the new types.

The new types reuse the existing Product compact editor and catalog views. Services already has a different internal two-step editor; that existing workflow is preserved. Shared shell consistency does not prove pixel-identical business-specific field layouts or exhaustive keyboard/accessibility coverage.

## Console, HTTP and regression observations

Each executed case writes an `*-observations.json` recording uncaught browser errors, console errors, API failures and intentional negative statuses. The suite fails passing workflows if unexpected errors occur. Expected rejection statuses are 403/404 for authorization, 422 for invalid data and 503 for deliberately unavailable bundle checkout.

Appointments, service scheduling, HRMS benefits, PMS projects, invoices and sales reporting were opened in real Chrome as route regressions. The invoice listing also displays the invoice generated by checkout. These checks establish existing-page availability only; they do not establish plan entitlements or fulfillment integration.

## Remaining acceptance blockers

- **BLOCKED:** Recursive bundle fulfillment, stock deductions, component taxes/discounts, allocation, partial refunds and bundle sales reporting. Disabling checkout prevents partial commercial writes but does not satisfy bundle purchasing.
- **BLOCKED:** Automatic membership discounts in POS, eligibility/stacking, full subscription-purchase coverage and broad existing-product/service sale regressions in this live suite.
- **BLOCKED:** Appointment eligibility, service restrictions, remaining-session enforcement at booking/check-in, credit consumption and cancellation reversal through scheduling UI.
- **BLOCKED:** Automated recurring billing, provider/webhook duplicate delivery, billing dates, reminder delivery, grace/trial enforcement, proration, mid-cycle upgrade/downgrade, renewal allowance reset and rollover.
- **BLOCKED:** Native Business Pack context enrollment for customer-plan operations; the current server deliberately rejects unsupported pack context rather than bypassing scope isolation.
- **BLOCKED:** HRMS employee/provider benefit assignments and PMS onboarding/task/fulfillment automation. Shared catalog references and page availability do not satisfy these workflows.
- **BLOCKED:** Refund/payment reconciliation scenarios and dedicated renewal, churn, utilization and plan revenue reports.
- **NOT VERIFIED IN LIVE BROWSER:** Simultaneous consumption, insufficient balance through a booking workflow, expiry-time transitions, inactive nested components at sale, selected-date activation, suspension/extension UI, and production PostgreSQL migrations/concurrency. Backend coverage must not be substituted for those missing end-to-end cases.

## Repeat the audit

From the repository root, start the disposable backend with `backend/venv/Scripts/python.exe backend/scripts/serve_offerings_browser_qa.py`. It refuses an existing database unless `--reuse` is supplied. Test records remain solely in `.local/offerings-browser-qa`; retaining them supports verification. No cleanup of real records occurs.

In another PowerShell terminal, enter `frontend`, set `VITE_DEV_API_PROXY_TARGET=http://127.0.0.1:8799` and run `npm run dev -- --host 127.0.0.1 --port 5198`. Then run `npx playwright test --config=playwright.offerings-live.config.ts`. Keep this suite serial: later cases intentionally exercise records created by earlier cases. Synthetic credentials and company fixtures are defined in the isolated server script.

Finally run `backend/venv/Scripts/python.exe backend/scripts/build_offerings_audit_artifacts.py` from the root to refresh the case index and comparison. The suite writes screenshots, per-case observations, database evidence and failure traces under `output/offerings-live-audit`.

The passing cases support the specific behaviors described above. The remaining blockers prevent a production-ready acceptance decision.
