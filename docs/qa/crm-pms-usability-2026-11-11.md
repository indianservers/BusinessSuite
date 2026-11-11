# PMS and CRM usability implementation — 11 November 2026

## Scope and goal status

The complete seven-phase improvement goal remains active. This first batch reduces page chrome and makes the PMS overview optional. It does not complete first-screen acceptance, collection-control consolidation, record consistency, seller queues, capture/onboarding improvements, advanced-feature packaging or deeper collaboration work.

## Batch 1 changes

- Page-owned AI writing actions are available through one keyboard-accessible **AI writing** menu beside Page actions. Editor-owned writing buttons retain their existing presentation and insertion paths.
- The menu uses the existing writing endpoint and draft dialog. Closing its dialog returns focus to the menu trigger. Choosing a recipe does not open the chatbot or send a business message.
- The PMS board has a compact workspace title and loaded task/project counts.
- Its full hero, membership tools, clickable metrics and delivery pipeline remain available in **Workspace overview**, collapsed initially. Expansion is remembered per user, company and workspace. Storage failure does not block access to work.
- The PMS board bypasses the duplicate module-page wrapper because it already owns its workspace shell. Other PMS destinations retain that navigation.
- The existing writing browser runner now opens page recipes through the menu. Its full disposable API matrix was not run in this batch.

## Verification

- Frontend TypeScript no-emit check passed after the initial component changes. The full production build (TypeScript and Vite) passed after the final changes. Existing dependency annotation, mixed-import and large-chunk warnings remain. The updated writing runner also passed Node syntax validation.
- In-app browser inspection used the authenticated local preview at localhost:5186 and its existing QA workspace. No business task, deal, document, membership or automation was changed.
- Confirmed menu recipe visibility, Escape returning focus to AI writing, opening Write task description, and closing the draft returning focus to the same trigger.
- Confirmed Workspace overview expands, exposes the delivery pipeline and survives a reload. The saved preference was returned to collapsed after verification.
- Inspected 1280×720, 1440×900 and 390×844. Phone document width was 390px at a 390px viewport. Temporary viewport overrides were reset.
- First-screen acceptance remains incomplete. At 1280×720, the first task was below the viewport (measured top approximately 877px after the initial shell changes). Nested views, collection summaries and duplicate filters/search remain the next implementation target. Do not treat absence of horizontal overflow as proof of a complete phone workflow.
- The legacy `frontend/scripts/test-workspace-management.cjs` failed its initial fixture assertion: expected three Workspace list articles, found zero. It hardcodes localhost:5174/universal-workspaces-qa.html; port 5174 currently serves a different application. It did not verify the modified board, and this is not counted as a passing regression test. A future run needs an isolated Business Suite fixture server.
- No production deployment, provider dispatch, broad accessibility audit or performance benchmark was performed.

## Remaining acceptance checklist

1. Phase 1: three visible records at 1280×720 and 1440×900; compact phone workflow; remaining navigation duplication.
2. Phase 2: one coherent collection search/filter state; clear-all across contributing filters; consistent results across views; understandable personal/shared saved configuration and preserved preferences.
3. Phase 3: predictable title opening and cell editing; aligned preview/full task and CRM behavior; focus/scroll/selection preservation; deep links and Back; labels, monetary/date formatting and consolidated row actions.
4. Phase 4: complete deal summary and next-action queues; log call and schedule follow-up journey; matching queue counts and access scope.
5. Phase 5: contextual capture defaults, progressive fields, drafts and custom-field validation; role-specific setup and templates.
6. Phase 6: guided scheduling, automation recipes/outcomes and report discovery/drill-down/sharing/filter coverage, preserving existing engines and protections.
7. Phase 7: assess and implement appropriate document page/discussion extensions and cross-project capacity reservations; verify revision/conflict protection and avoid unsupported collaboration claims.

For each phase, retain desktop/phone/keyboard evidence, focused regression results and negative-case coverage. The full goal also requires before/after artifacts, updated comparison/backlog and an evidence-backed final report.
