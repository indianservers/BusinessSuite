# Membership and subscription UI polish

The customer-plan workspace now has a compact plan list beside the selected plan on wider containers, and a stacked layout on smaller screens. Selected rows, status badges, tab navigation and a primary renewal action establish a clear hierarchy using the existing catalog theme and shared controls.

Plan rows no longer repeat complete summaries and every benefit. The detail panel groups status, dates, renewal and timezone, with consistently styled benefit balances and progress indicators. Long explanations and action-availability reasons are available in expandable help sections rather than beside every button. Accessible action descriptions and permission checks remain intact.

Assignment, lifecycle and comparison windows reuse the existing smart-window structure with improved padding, field spacing, validity previews and footers. Products and Services pages were not redesigned. Scoped CSS uses the existing theme tokens; dark-mode status contrast and reduced-motion preferences are supported. On mobile, selecting a plan brings its details into view below the fixed navigation.

Local validation uses real Chrome, normal authentication, Vite `127.0.0.1:5198`, FastAPI `127.0.0.1:8799`, and the disposable `.local/offerings-browser-qa/audit.sqlite` database. New synthetic customer and plan records provide realistic screenshot content without altering production data. No API route mocks or financial operations are used for the visual review.

- Seven existing workspace browser scenarios passed after the layout changes.
- Dedicated visual/interaction scenario passed at 1600px, 768px and 390px, including dark mode, unavailable-action explanations and renewal previews. No console, HTTP or uncaught browser errors.
- Four earlier catalog/assignment/renewal/cancellation scenarios passed again after the final polish. Total: **12 passing browser scenarios** across the three suites; final TypeScript validation and `git diff --check` passed.
- Final screenshot evidence: `output/plan-ui-polish/workspace-1600.png`, `workspace-768.png`, `workspace-390.png`, `workspace-dark.png`, `mobile-viewport.png` and `renewal-390.png`.
- Visual scenario and results: `frontend/playwright.plan-ui-polish-live.config.ts`, `playwright/plan-ui-polish-live.spec.ts`, `output/plan-ui-polish/results.json`.

The work changes presentation and selection scrolling. Existing assignment, renewal, cancellation, billing and benefit semantics are unchanged; unsupported scheduled billing, refunds and proration remain explicitly unavailable.
