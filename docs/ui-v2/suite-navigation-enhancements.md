# Dashboard and authentication navigation enhancements

Implemented on 27 October 2026. The dashboard retains its purple, blue, green,
orange, and cyan module colors and the existing Lucide application icons.

## Before login

1. **Consistent branding:** shared Business Suite mark, typography, and purple
   sign-in actions across the public entry, login, recovery, and dashboard.
2. **Clear public entry:** `/` opens an application explorer for signed-out
   visitors and `/dashboard` for authenticated visitors. Application links explain
   that sign-in and organization permissions are required.
3. **Remember-session control:** available on the unified login with an explicit
   shared-device explanation; applies to password and supported social sign-in.
4. **Persistent errors:** credential failures remain beside the form, receive
   focus, and retain the email. Validation messages are associated with fields.
5. **Relevant sign-in methods:** only configured providers appear. Company-domain
   providers sort first, with a contextual recommendation and retry on discovery
   failure. Google/Microsoft remain hidden when social login is unconfigured.
6. **Recovery confirmation:** a persistent, account-enumeration-safe inbox message
   provides “Try another email” and “Back to login.”
7. **Reset navigation:** success and “Back to login” explicitly reset the form and
   remove the reset token. Password mismatch and expired-link errors are visible.
8. **Accessible authentication:** field labels, described errors, password-manager
   autocomplete, one-time-code support, visible focus, a 44px password visibility
   control, and keyboard-operable recovery flows.

## Dashboard

9. **Account menu:** profile, account settings, help, and shared sign-out behind
   the formerly decorative chevron. Account settings can change a password using
   the existing authenticated endpoint.
10. **Named organizations:** `/access/me` returns names only for the user's
    memberships; the selector identifies the active company. Switching cancels
    queries, clears cached access, and reloads the authorized dashboard.
11. **Meaningful recommendation:** the hardcoded “Featured” badge is removed;
    recommendations reflect the user's role. HRMS retains its blue card styling.
12. **Continue working:** recent authorized page paths appear with a resume action,
    expandable history, and an option to clear history. Query strings and fragments
    are not stored in recent history.
13. **Favorites:** star controls pin applications, order favorites first, and
    optionally filter the grid to favorites. Preferences are scoped by user and
    company in this browser.
14. **Real counts:** application badges use unread notification counts grouped by
    their real destinations, filtered against current application/route access.
    Badges open the application's unread notification queue.
15. **Direct feature links:** People, Payroll, Leads, Projects, and the other chips
    navigate to registered feature pages. Unauthorized chips remain informational.
    In Finance, the Reports chip opens the existing Day Book report.
16. **Access loading/error states:** card skeletons and retry replace the grid
    while access loads or fails; no premature module count or contradictory
    “No applications assigned” state appears.
17. **Compact layout:** a persistent compact view reduces the hero and card copy,
    providing quicker application access on mobile while retaining the illustrated
    desktop view by default.

## After login

18. **One application catalog:** the module switcher and command search use the
    dashboard catalog, including Power Apps.
19. **Always-available suite home:** “All applications” is available in expanded
    and collapsed sidebars, breadcrumbs, account pages, and the special PMS and
    Power Apps layouts.
20. **Predictable sidebar groups:** expandable groups replace competing secondary
    “More” menus in the standard sidebar. Expansion choices persist by user,
    company, and application. Page filtering temporarily reveals matching groups.
21. **Clear search scopes:** the dashboard filters applications; the sidebar finds
    pages in the current application; Ctrl/Command+K opens the suite command
    palette. The palette labels its scope and supports keyboard selection and
    records in the existing HRMS/PMS search integrations.
22. **Breadcrumbs:** standard application pages show All applications → application
    → page/record, with accessible current-page semantics and authorized parents.
23. **Safe return destinations:** protected pages retain their requested internal
    path, query, and fragment through login. The continuation page refreshes access
    before navigating. Unsupported/external destinations fall back to the dashboard;
    unauthorized destinations show an explanatory dashboard notice. Legacy module
    login paths use the same flow.
24. **Suite notifications:** a shared bell and `/notifications` inbox work across
    applications, independently of HRMS navigation. They provide application and
    unread filters, pagination, mark-read actions, retry, and authorized links.
    Counts and feeds are scoped to the current recipient and active company.
25. **Shared sign-out:** logout attempts server revocation, then cancels queries,
    clears authentication and cached query data, and returns to `/login`, including
    when the logout request fails offline.

## Verification

- Passed: 26 desktop/mobile navigation journeys, 3 updated unified-login
  compatibility tests (including unsafe-destination rejection), and 6 API tests.
- Targeted ESLint and UTF-8/patch-whitespace checks passed.
- Browser journeys: `cd frontend; node node_modules/playwright/cli.js test --config=playwright.suite-navigation.config.ts`
- Login compatibility: `cd frontend; node node_modules/playwright/cli.js test --config=playwright.unified-login.config.ts`
- Viewports: desktop 1672×1000; mobile 390×844 with touch enabled.
- API checks: `cd backend; .\venv\Scripts\python.exe -m pytest tests/test_suite_navigation.py tests/test_notifications.py -q`
- TypeScript: `cd frontend; node node_modules/typescript/bin/tsc --noEmit`
- Browser fixtures use a disposable SQLite database served only on loopback. They
  do not modify the normal application database or send recovery emails.
- Company SSO availability and ordering are checked with explicit test-provider
  responses. Actual external identity-provider authentication requires configured
  organization credentials and is not exercised by these tests.
- Screenshots are saved under `docs/qa/suite-navigation-*.png`. Browser traces for
  failures are retained under `.tmp/suite-navigation-browser`.
