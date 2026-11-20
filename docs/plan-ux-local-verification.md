# Membership and subscription UX: improvements 1–10

Implemented in the shared catalog and existing customer workspace. Products and Services pages were not redesigned. The implementation reuses `SmartRecordPicker`, `NativeSelect`, the catalog dialog classes, existing buttons, scoped APIs, validation and form scrolling.

1. **Named beneficiaries:** search the existing customer directory by name, email or phone; select readable records, remove selections, prevent duplicates and enforce the plan’s beneficiary limit.
2. **Eligible offering picker:** search offering names/codes; retain selected restrictions on reopen, resolve archived names, and preserve unavailable selections until explicitly removed. No numeric-ID entry is required.
3. **Validity versus billing:** summaries distinguish access duration from recurring billing preferences and prepaid/postpaid terms.
4. **Honest automation status:** the UI says automatic billing, renewal execution and reminder delivery are not connected. Saving preferences does not activate them.
5. **Calendar previews:** server-calculated start, exclusive expiry and last access date use the same calendar helper as assignment. First-use dates are examples; approval does not postpone the existing validity clock. Billing timezone is displayed separately from the service’s date-only calendar.
6. **Renewal preview:** show current/new status and expiry, zero amount collected and unchanged benefit balances. No automatic invoice, payment, reset or rollover is claimed.
7. **Conditional benefit fields:** discount amount/percentage/special-price and stacking controls appear only for applicable benefit types. Percentage validation is capped at 100.
8. **Explicit unlimited:** a checkbox stores unlimited as null. Finite zero stays zero and means no allowance. Empty finite inputs cannot autosave a misleading value.
9. **Action-specific confirmations:** buttons identify the operation and plan kind, including “Renew membership” and “Cancel subscription”. Invalid renewal dates cannot be submitted; stale revisions require a refreshed preview.
10. **Cancellation consequences:** explain immediate loss of access, unavailable remaining benefits, no automatic refund/credit, unchanged invoices/payments and retained history. “Keep membership/subscription” dismisses without cancellation.

The three POST preview endpoints use the application’s `readOnlyPreview` request option, avoiding save notifications, record synchronization and refresh loops. Assignment submits the reviewed offering version and date; changed terms are rejected rather than silently accepted. Existing idempotency protections remain in place.

## Local verification

Real Chrome against Vite `127.0.0.1:5198` and FastAPI `127.0.0.1:8799`, using the disposable `.local/offerings-browser-qa/audit.sqlite` database and normal authentication/authorization. No route mocks, production database, payment collection or external notification delivery.

- Backend: **84 passed**, including calendar boundaries, previews without side effects, assignment/version retries, stale and foreign-plan rejection, lifecycle, shared catalog and checkout regressions.
- Frontend: TypeScript `tsc --noEmit --pretty false` passed.
- Browser: **4 passed** with `frontend/playwright.plan-ux-live.config.ts`: catalog create/edit and saved restriction hydration, zero/null persistence, conditional fields, leap-year preview, named beneficiaries, invalid renewal prevention, renewal and cancellation at 1440px desktop, 768px tablet and 390×844 mobile. See `output/plan-ux-local/results.json` for the final run (zero failed, skipped or flaky cases).
- Existing Products/Services create-and-view smoke tests: **2 passed** on the final combined run. An earlier overlapping run timed out after the product dialog disappeared; the isolated product rerun and final combined run both passed without application changes. No broader production readiness claim follows from these smoke tests.
- Browser assertions reject uncaught errors, console errors and HTTP errors. Renewals preserve balances; cancellation dismiss preserves active status, and confirmation retains balances/history while changing status.
- Visually reviewed the five actual editor screenshots together in `output/plan-ux-local/editor-comparison.png`, plus desktop renewal and mobile assignment/cancellation screenshots. Shared typography, header/footer, inputs and buttons remain consistent. Existing service scheduling tabs are retained.

Commands from `backend`:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_plan_ux_previews.py tests/test_catalog_offerings.py tests/test_shared_catalog.py tests/test_service_checkout.py -q --disable-warnings --maxfail=1 --tb=short
```

Commands from `frontend` (isolated servers running):

```powershell
npx tsc --noEmit --pretty false
npx playwright test --config playwright.plan-ux-live.config.ts
```

Automatic billing, reminder execution, membership discounts at checkout, renewal benefit resets/rollovers and automatic refunds remain separate unfinished capabilities. These UX changes describe the existing supported effects; they do not implement those financial or scheduled operations. Native Business Pack customer-plan operations retain their existing availability restriction.
