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

1. Phase 1: normal-state three-record layout measured for live PMS and the real CRM shell with eight disposable records (see Batch 4). Continue failure-notice layouts and complete phone workflows; screenshots alone do not close this phase.
2. Phase 2: PMS has one task search, shared filter state and Saved views entry point. Continue CRM saved-configuration consolidation, preference isolation/legacy acceptance and coherent quick/advanced filter entry points across modules.
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

## Batch 4 — PMS saved configurations and representative CRM layout

### Implemented

- One **Saved views** control is available in List, Board, Calendar and Workload. It uses the existing shared grid manager and preference key, moved into the workspace filter bar through an optional host. The grid stays mounted while switching task presentations so the same manager, layout and selection state are retained; it is hidden outside List, not duplicated.
- Named views include search, project, assignee, priority, status, task type, attention queue, advanced conditions, table layout and task presentation. Loading a Board view from Calendar restores its Board presentation and filters together. Scope IDs are checked against currently available project/member choices.
- **Last filter snapshot** remains inside this menu, using the original `pms-board-view-{user}-{company}-{workspace}` key. Saving failures are caught with a message that current filters are unchanged. Older named layouts without collection context preserve the current workspace filters. This compatibility branch has source review but still needs an older-format fixture exercise.
- Labels identify saved configurations as personal/browser-local. No sharing or backend preference engine was added. Existing shared-grid keys retain user/company/workspace isolation, and the task collection remount key includes user/company as well as workspace. Fresh multi-user isolation acceptance remains open.
- A real-shell CRM fixture (`frontend/crm-usability-qa.html`, `frontend/scripts/fixtures/crm-usability.tsx`) contains eight clearly labeled disposable opportunities. It uses AppLayout, module navigation and the actual Deals components with the same global collection styles. All suite API calls are served by a local Axios adapter; writes are rejected. It is gated to development on loopback and does not contact business APIs/providers.
- The larger fixture exposed a grid virtualizer render loop: derived layout objects changed identity without changing column geometry, causing repeated measurement/state updates. Column measurement now depends on the serialized geometry values. Cold-load fixture inspection after the fix produced no fresh render-loop errors. An unrelated concurrent main-entry HMR change also caused a duplicate-root error in the live preview; a cold reload recovered it, and saved-view restoration was repeated afterward.

### Verification and artifacts

- Frontend no-emit check and production build passed for the saved-view integration. A second production build passed after the virtualizer correction. Additional TypeScript checking of source plus the new fixture passed. The first temporary external config lacked the frontend ambient type roots and failed on unrelated existing `Array.at`/DOM types; correcting its type roots to match the frontend resolved those configuration errors. The equivalent reproducible config is `frontend/scripts/fixtures/tsconfig.crm-usability.json`.
- Focus queue test passed. Shared-grid unit checks passed after the final grid change (paging, access-preserving records, sorting, nested conditions, grouping and export escaping); pending-search checks passed all 12 assertions.
- Live workspace: saved **QA usability High board 20261111** while searching High and focusing Unscheduled. Clear → Calendar showed four tasks; loading the named view restored Board, the High search and Unscheduled · 1. Reload retained the named entry; loading it again restored the same context. A filter snapshot saved from that context restored one matching Calendar task while keeping Calendar selected.
- Empty names leave Save current view disabled. Escape returns focus to Saved views. At an actual 390×844 viewport the menu occupied x0–310 and y374–773, document width 390; loading the named view restored Board and Escape returned focus. An earlier screenshot attempt targeted the other active tab; its viewport measurement caught that mistake, and `pms-saved-views-390.png` was overwritten only after confirming the correct tab was 390px wide.
- PMS at 1280×720 still shows three full task rows at y491–555, y555–619 and y619–683. Artifact: `.local/crm-pms-usability/pms-saved-views-1280.png`.
- CRM fixture at 1280×720 and 1440×900, main scroll zero: group header y489.5–523.5; records y523.5–587.5, y587.5–651.5, y651.5–715.5. Title, permitted-opportunity scope and Create deal are visible above the records. This proves normal-state layout for the fixture, not API correctness, financial aggregation or production acceptance.
- CRM fixture at 390×844: document width 390 and the existing mobile record-card presentation remains available. Artifacts: `.local/crm-pms-usability/crm-fixture-1280.png`, `crm-fixture-1440.png`, `crm-fixture-390.png`; Saved views artifact: `pms-saved-views-390.png`. Temporary viewport overrides were reset and the disposable fixture tab was closed.

The local QA named view/filter snapshot remains available for review. No task/deal business record or provider configuration was changed. Full access isolation, failed-write/stale-edit recovery and the phase 3–7 journeys remain open; CRM's separate legacy Board saved configuration also needs consolidation.

To repeat the CRM layout fixture, run `npx vite --host 127.0.0.1 --port 5199 --strictPort` from `frontend`, then open `http://127.0.0.1:5199/crm-usability-qa.html` in the in-app browser. Use a separate loopback port from the authenticated application. Type-check it with `npx tsc --noEmit -p scripts/fixtures/tsconfig.crm-usability.json`.
