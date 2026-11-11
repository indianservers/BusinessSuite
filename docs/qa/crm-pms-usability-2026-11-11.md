# PMS and CRM usability implementation — 11 November 2026

## Scope and goal status

The complete seven-phase improvement goal remains active. The batches below reduce page chrome and consolidate PMS filters. PMS first-screen acceptance has been measured; CRM has improved but still needs a representative collection with at least three records. Record consistency, seller queues, capture/onboarding, advanced-feature packaging and deeper collaboration work remain open.

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

## Batch 2 — PMS collection controls and first-screen acceptance

Committed source: `82b8ecaa`. This batch removes the extra task search from the workspace header and uses the collection search for List, Board, Calendar and Workload. Global search remains separate. The mounted collection owns quick filters, advanced grid conditions and attention queues, and passes the same matching tasks to planning views. Activity remains a different data source and does not imply task-filter coverage.

Status/priority/type filters are under More filters. Summary and alternate grid presentations are compact disclosures; their content, status distribution, catalog and preferences remain available. Save filters retains the existing per-user/company/workspace key. Table layouts names the existing grid configuration separately. This distinction improves labeling but does not yet satisfy the goal's single saved-configuration entry point.

Advanced conditions use the existing grid filter engine, remain visible as an active count when switching views, and are cleared by the collection's Clear filters action. Legacy persisted grid search is transferred into the visible task search. Custom-field read failures expose Retry fields; that retry button has not yet been exercised against an injected failure.

The shared filter dialog now describes its loaded-record scope. During live pointer testing, floating record-sync notices covered Apply filters. Modal-time CSS now hides both floating sync notices and the generic toast viewport while a modal owns interaction. Notices return after closing; existing drafts and sync entries are retained. Keyboard and pointer application of a Task contains condition were checked. The grouping prompt's invalid encoding was corrected.

### Evidence and limits

- Authenticated local workspace 7 contains four existing QA tasks. At 1280×720, scrollY 0, task rows occupy y491–555, y555–619 and y619–683: three complete rows, with title/scope/Create above them. At 1440×900 the four rows occupy y485–741. CRM first-screen acceptance is still outstanding.
- Current screenshots: `.local/crm-pms-usability/pms-1280.png`, `pms-1440.png`, `pms-calendar-390.png`, and `pms-filter-modal-390.png`. These are ignored local artifacts. A comparable saved before screenshot is still missing; earlier observed bounds are not a substitute for that deliverable.
- At 390×844 the document width is 390px. Searching High and switching List → Calendar retains exactly one matching task. An impossible query shows Tasks · 0; Clear filters restores Tasks · 4. No task dates/statuses or business records were intentionally changed. Viewport overrides were reset.
- Earlier in the batch: priority High retained one task across List/Board/Calendar; a Task contains Low advanced condition retained one task across Board/Calendar and reload. Clear filters restored four. Pointer Apply was repeated successfully after fixing the notice overlay, including on the phone modal.
- Focus queue checks passed. Grid unit checks passed for bounded server paging/access-preserving records, local search, numeric sorting, nested filters, grouping, selected exports and spreadsheet formula escaping. Pending-search tests passed all 12 assertions. These do not prove the later task-save, stale-edit, approval or role-isolation journeys.
- Follow-up source inspection found that the read-only custom-field batch POST was classified as a save by the API client. Both task/project lookup callers now set the existing `readOnlyPreview` flag. The backend endpoint only returns permission-checked field data; this prevents new lookup-triggered mutation events/sync entries. Existing browser-saved entries were not deleted or resubmitted. Their individual origins have not been established.
- Final frontend TypeScript no-emit check and production build passed after the read-only lookup fix. Existing Vite dependency annotation, mixed-import and large-chunk warnings remain.

The full goal remains active. PMS collection layout and filter continuity have stronger evidence now; CRM layout, unified saved configuration and the phase 3–7 business journeys remain open.

## Batch 3 — CRM collection surface and explicit Board scope

### Changes

- Deals has one page title with a short access-scope explanation. The redundant application breadcrumb is omitted only on the deal/pipeline collections; module navigation, Explore pages, sidebar, global actions and direct record breadcrumbs remain available.
- Sales overview is collapsed initially. It retains the three primary metrics and More sales metrics, including separate-currency totals. The grid uses the existing compact-controls option: presentation choices and record summary are disclosures. Filtered aggregate totals are inside Summary rather than in a separate row. Noncompact grids retain their existing statistics placement.
- The desktop browser-save stack is collapsed into a count/state disclosure. Expanding it exposes all original review/retry/discard controls; Escape closes the disclosure and focuses its summary. This prevents recovered copies from continuously covering collection controls. Phone sync status keeps its existing sheet. No saved copy is deleted, retried or resubmitted automatically.
- Switching to Board no longer silently picks the first/default pipeline. All pipelines is explicit, and stage names include pipeline names in that scope. Search and the selected pipeline survive Table → Board → Table. Existing transition dialogs and backend validation remain in charge of writes.

### Browser verification

Authenticated local QA branch, two existing deals, no deliberate deal writes or external communications:

- Before at 1280×720, first deal y1044.5–1108.5; final inline-heading layout places it at y523.5–587.5, second y587.5–651.5 with the existing Stage grouping retained. Both page and main scroller were at zero. At 1440×900 the same two grouped rows fit. These bounds measure layout, not performance. The dataset has only two deals: **the explicit three-record CRM acceptance remains unproven**, even though the measured remaining space can accommodate another 64px row. A representative three-record fixture is still required. A freshness/error notice can also consume additional height and must be included in failure-layout acceptance.
- Before/after screenshots: `.local/crm-pms-usability/crm-deals-before-1280.png`, `crm-deals-after-1280.png`, `crm-deals-after-1440.png`, `crm-deals-after-390.png`.
- Expanded Sales overview and checked the original primary counts. Expanded Summary with pointer and checked loaded/matching counts, INR sum ₹1.00, average ₹0.50 and Stage distribution. Mixed-currency totals still need a fresh multi-currency acceptance dataset.
- Impossible search returned zero records; clearing restored two. Search QA Smart Deal returned one; All pipelines Board displayed that same deal in Enterprise Solutions · Qualification; returning Table retained one. The earlier automatic pipeline selection had hidden that deal and is now removed.
- Expanded the five recovered browser copies, checked all review controls remained available, then Escape closed and returned focus to the status summary. No draft was discarded.
- At 390×844 document width was 390px. Existing phone record cards remain enabled. Keyboard Enter opens Presentation and exposes Table/Cards/List/category/frequent/favorite choices. The zero-result phone state and successful clear were checked. Advanced filter Apply was the actual pointer hit target and closed the modal successfully; existing saved copies did not obstruct it. Viewport was reset.
- Shared grid unit regression passed after statistics relocation. The production build and subsequent TypeScript no-emit check passed. Final inline-heading text/CSS changes were checked live, including a pointer hit-test proving Explore pages remains accessible beside Page actions. Existing Vite warnings remain; no performance benchmark or deployed acceptance was run.

This batch does not prove record opening/focus/scroll recovery, task/deal mutations, stale-edit recovery, workflow approvals, access-role isolation or later phases. Those journeys remain required.
