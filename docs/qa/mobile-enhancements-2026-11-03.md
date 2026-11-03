# Mobile enhancements — 3 November 2026

Scope: CRM, PMS, Sales–SRM and HRMS at widths below 768px. Shared mobile behavior is activated only inside these applications. Existing desktop views remain the fallback. No production data was used for verification.

## Implemented checklist

1. Bottom tabs navigate directly; a separate contextual action button opens shortcuts.
2. Dock text increased to 11px, retaining icons and visible labels.
3. Explicit route aliases and accessible current-page state cover detail and workspace pages.
4. Live attention badges use existing follow-up, task-summary and leave-request APIs.
5. Module roles prioritize employee self-service, manager actions or administrative creation.
6. Sales quotes and quote builders remain under `/srm/quotes` on mobile.
7. Quick-action and filter sheets support downward handle dismissal, tap close and Escape.
8. VisualViewport handling hides floating navigation while the keyboard occupies the screen and reveals focused fields.
9. Compact mobile header; branch selection and settings remain available in Workspace tools.
10. Consolidated AI/back-to-top tools; POS checkout has separate space above the dock.
11. Existing table controls become labeled record cards while retaining their event handlers.
12. Bottom-sheet filters and active chips cover CRM leads/follow-ups, PMS work/reports, Sales profitability and HR attendance/directory.
13. Long-form action groups remain sticky, with dock and keyboard spacing.
14. Mobile search/filter state and scroll positions persist within user and company scope.
15. Larger touch targets, form controls and checkbox areas are mobile-scoped.
16. Initial mobile lead capture offers name, phone and source; optional details expand.
17. Customer/lead contact strips offer permitted call, WhatsApp, email and note actions.
18. Due/overdue follow-up queue supports completion and rescheduling with a reason.
19. CRM pipeline shows one selected stage with stage counts on phones.
20. Existing call-outcome form uses a mobile sheet, retaining notes and next-follow-up scheduling.
21. My Work offers Today, Overdue, Upcoming and Awaiting Review focus filters.
22. Task quick editing connects status, priority, due date and assignments to existing workflows and permissions.
23. Project summary surfaces progress, blockers, next milestone and the project owner's name when available.
24. Task conversation combines recent work updates, comments, attachments and activity, ordered by timestamp.
25. Mobile reports add completion summaries, status distribution, date presets, workload and trend shortcuts.
26. Catalog selection uses mobile cards, stock hints and quantity increment/decrement controls.
27. Sales quote creation follows Customer → Items → Pricing → Review, validates item values and saves a draft through existing quote APIs.
28. Commercial order/invoice timelines display the statuses provided by the backend; missing statuses are identified explicitly.
29. Mobile payment entry includes amount, method, receipt date and reference, retaining the existing idempotency key.
30. Invoice PDF controls provide preview, download and native sharing where supported.
31. Attendance home provides current status, last punch, hours and profile-linked check-in/out.
32. Leave dates retain duration/balance estimates; the mobile balance panel stays within reach.
33. Manager approval cards submit the same review decisions and reasons as desktop controls.
34. Payslips lead with month/net pay and expandable earnings/deductions details.
35. Employee directory cards show manager context and retain contact privacy restrictions.

## Verification

- Playwright suite: `playwright/mobile-enhancements.spec.ts`.
- Configuration: `frontend/playwright.mobile-enhancements.config.ts`; isolated Vite cache in `frontend/vite.mobile-qa.config.ts`.
- Final verification partitions: 19 passed / 2 skipped; 33 passed / 6 skipped; 6 passed. Combined: **58 passed, 8 intentionally inapplicable cases skipped**, covering all 66 configured cases.
- Phone viewports: 320×740 and 390×844. Desktop: 1440×1000. Resize checks cross the 768px boundary and return to mobile with sheets closed.
- Browser checks include actual routed application views, request/response fixtures for attendance/payments/approvals/tasks, touch-sheet dismissal, read-only task controls, employee shortcuts, keyboard viewport behavior, record labels and POS overlap.
- A mobile wizard also created a quote against the real disposable SQLite backend: customer and catalog item selected, line saved, and ₹100 + 18% tax verified as ₹118.
- TypeScript check passed; scoped ESLint passed; production build passed. Existing bundle-size and dependency annotation warnings remain non-blocking.
- Screenshots were inspected for the rendered mobile dock and application layouts.

## Practical limits

Browser emulation does not certify physical iOS/Android keyboard behavior or the operating system's share panel. PDF sharing is offered only when the browser reports support; download and open-viewer links remain available. Timeline statuses, stock and report data remain subject to existing backend visibility and permissions.
