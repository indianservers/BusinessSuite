# Membership/subscription UX: improvements 11–25

This extends improvements 1–10 in the existing Products/Services catalog and customer workspace. Shared buttons, native searchable selects, details sections, form scrolling and smart-window footers are reused. No schema migration or production data changes are required.

11. **Name and tier first:** customer-plan rows and details lead with the offering name and purchased tier, with the plan number secondary. New purchases retain a name snapshot. Older purchases without a name snapshot fall back to the current offering name.
12. **Compact summary:** status, access dates, renewal preference, billing timezone and benefit balances are grouped with the selected plan and list rows.
13. **Benefit balances:** finite allowances show, for example, “8 of 20 sessions remaining” using a compact native progress indicator. Zero and unlimited remain distinct; an allowance of zero never divides by zero.
14. **Distinct states:** awaiting first use, pending approval, scheduled access, active, paused, suspended, expired and cancelled each have an explanation. Expiry is derived without rewriting stored lifecycle history.
15. **Predictable actions:** server-provided availability includes reasons for permissions, status, pause configuration, expiry and lifetime plans. Action buttons retain their accessible action names and associate the reason as a description.
16. **Pause versus suspension:** both use the existing confirmation dialog and explain stopped access and continuing validity. Suspension is described as an administrative block.
17. **Renew versus Extend:** renewal activates an eligible plan with later expiry; extension preserves status. Both previews explicitly say balances are unchanged and no automatic payment is collected.
18. **Usage history:** benefit name, signed usage/return quantity, actor, timestamp, recorded source reference, original reversal and compensating usage IDs. Transaction links are not invented from free-text references. History is server paginated.
19. **Lifecycle history:** readable descriptions, old/new expiry for extension and renewal, actor and timestamp, with newest-first pagination. Existing append-only history is preserved.
20. **Useful filters:** kind, effective status, inclusive expiry-date bounds and availability of recorded benefit balances filter on the server before pagination. Active/Renewals tab constraints are explained. Invalid date ranges are rejected on the server and prevented in the UI.
21. **Contextual empty states:** no active plans, no expiring plans, no matching filters, no purchase benefits, no usage and no lifecycle history have relevant explanations and available next steps.
22. **Reminder preferences:** selectable 30/7/1-day presets and removable custom intervals, deduplicated and limited to 20 intervals in the existing 0–3650-day range. The UI distinguishes saved preferences from delivered messages.
23. **Business timezone:** new plans start with the scoped business/module timezone default. The shared searchable native select uses the same timezone option pattern as Defaults Settings. Existing values are preserved. Summary dates follow the configured date format and activity timestamps identify their timezone; date-only validity semantics are unchanged.
24. **Mobile benefit editing:** individual compact benefit summaries expand using the existing catalog details component. New empty benefits open for entry; existing benefits start collapsed on mobile. The established scroll body and Save footer remain in place.
25. **Plan changes when supported:** a read-only comparison shows current purchased terms and an alternative’s catalog terms/benefits. Changing a purchased plan, effective change dates, proration, price differences, refunds and benefit migration are explicitly unavailable. There is no approval mutation or inferred quote.

## Local verification

Normal authenticated Chrome requests against the isolated FastAPI QA server at `127.0.0.1:8799` and Vite at `127.0.0.1:5198`; database `.local/offerings-browser-qa/audit.sqlite`. Test data is synthetic. No API route mocks or production/external financial operations.

- Backend regression suite: **94 passed**, covering the new workspace presentation/filter/history cases plus the prior previews, offering engine, shared catalog and service checkout tests.
- New browser scenarios: **7 passed**, zero failed, skipped or flaky. Final results: `output/plan-ux-next-local/results.json`; all seven browser/console/HTTP error lists are empty.
- Earlier UX scenarios: **4 passed** again, including assignment, renewal and cancellation on desktop, tablet and mobile. Results: `output/plan-ux-local/results.json`.
- Existing Products/Services create-and-view smoke tests: **2 passed**, with zero browser/HTTP errors. The combined final browser verification is **13 passing scenarios** across the three suites.
- TypeScript: `npx tsc --noEmit --pretty false` **passed**. `git diff --check` passed.
- Browser error assertions reject uncaught errors, console errors and HTTP failures. The new cases cover actual usage and compensating reversals, balance summaries, filters, all read-only state labels, pause/suspend/resume, extend/renew consequences, actor history, comparison without purchase changes, timezone/reminder save/reopen, 390px mobile and 768px tablet benefit editing, and 26 usage records across two activity pages.

The mobile shared catalog editor is exercised through the CRM route; it is the same component used by Sales. The existing Sales mobile page-section navigation is not redesigned. Desktop coverage also exercises the Sales catalog, and customer-plan workflows run in the existing CRM customer profile.

Visually reviewed the final desktop summary, comparison and paginated usage screenshots, plus the 390px and 768px benefit editors. The allowance input and existing Save footer remain visible while editing. Screenshots are in `output/plan-ux-next-local/`; the five-module reference comparison remains in `output/plan-ux-local/editor-comparison.png`.

During testing, the frontend server stopped and was restarted. Browser testing also caught an unavailable-button accessible-name issue and stale activity on revisiting a tab; both were corrected before the final runs. Test selectors were adjusted to the existing searchable-select popup and mobile navigation behavior.

Run from `backend`:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_plan_ux_workspace.py tests/test_plan_ux_previews.py tests/test_catalog_offerings.py tests/test_shared_catalog.py tests/test_service_checkout.py -q --disable-warnings --maxfail=1 --tb=short
```

Run from `frontend` with the isolated servers running:

```powershell
npx tsc --noEmit --pretty false
npx playwright test --config playwright.plan-ux-next-live.config.ts
npx playwright test --config playwright.plan-ux-live.config.ts
```

Automatic billing, reminder delivery, upgrades/downgrades, proration, automatic refunds and renewal benefit resets/rollovers remain separate unsupported backend capabilities. The read-only UX never claims those operations succeeded. Native Business Pack customer-plan enrollment restrictions remain unchanged. PostgreSQL-specific performance/concurrency and production deployment are not verified by these SQLite local checks.
