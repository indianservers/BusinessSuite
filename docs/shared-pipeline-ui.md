# Shared pipelines

The shared compact board follows the supplied screenshots: horizontal pale stage lanes, white cards, stage totals, a small toolbar and horizontal scrolling. Advanced configuration lives in drawers and menus. BusinessSuite navigation and branding remain.

## Module integration

- CRM: `/crm/pipeline` and Deals Pipeline view. Create pipelines; add, reorder and configure stages; quick-add deals into open stages. The detail drawer opens the existing record workspace.
- PMS: project Board, with shared rendering also used by existing task arrangement panels. Create named project pipelines from Delivery, Support or Simple templates. Named boards are projections of the same project tasks by status, not independent task memberships. Omitted statuses are counted explicitly.
- Sales: Sales Orders Board offers the native document workflow and new configurable operational pipelines. Operational movement never changes approval, payment, invoice or delivery state. Stage rules can require native document statuses. Unassigned orders can enter a custom pipeline. Published Sales stages are retained to preserve assignments; deletion of published stages is not supported yet.
- HRMS: Recruitment Candidates Board supports job-specific stages, templates, candidate quick-add and confirmed movement. Candidate drawers expose interviews and explicit employee conversion, followed by an onboarding link. Conversion enforces Hired prerequisites; it does not automatically finish onboarding.

## Everyday usability

The shared board supports pointer and keyboard dragging, a Move menu, cancellation, error recovery, compact/comfortable density, configurable card fields, search, owner and attention queues, sorting and personal/team saved views. Saved views include native module filters. Record details and recorded stage history open in a right drawer. Quick-add uses native domain forms and permissions. Manual ordering is disabled while another sort is active.

The horizontal stage editor offers draft Save/Cancel, stage creation, reordering, templates that append missing stages, and safe deletion/remapping where supported. Occupied PMS custom status names cannot be renamed until tasks move through normal transitions. CRM remaps retain the same outcome; configuration cannot silently close deals.

## Operational controls

- Capacity and aging thresholds are configurable. Native create/move paths enforce supported capacity limits.
- CRM stages support required fields, approval requirements and optional owner notifications.
- Hiring stages support required contact fields, completed interview and accepted-offer prerequisites.
- Sales operational stages support required order fields and actual document-status prerequisites.
- PMS task drawers support native follow-up capture. Existing record workspaces retain notes, attachments and related records.
- Next actions come from actual CRM follow-ups, PMS follow-ups/due dates, HR interviews and Sales follow-ups.
- Transactional stage events feed the existing automation engine. The drawer links to the existing workflow builder; workflows still need explicit configuration.

Stage history is recorded on native transition paths and new-record creation. Authoritative events carry an internal origin marker; public event payloads cannot forge operational assignments or recorded ages. Older records without recorded entry events show unknown stage age instead of treating creation time as stage entry. Deep conversion/funnel analytics remain deferred until this history is reliable.

## Persistence and permissions

The service reuses existing ServicePolicy and ServiceEvent tables; no new database migration is required. Native record visibility and business workflow checks remain authoritative. Team views and configuration require management permissions. CRM/PMS configuration saves detect stale snapshots; hiring/Sales configuration uses versions. Sales assignments detect stale moves.

Deploy backend and frontend together. Key routes include CRM pipeline configuration, PMS board configuration, HR per-job configuration and `/api/v1/pipeline-workspaces/...` for preferences, history and Sales operational pipelines.

## Validation and remaining scope

Automated browser coverage uses illustrative records and mocked APIs: pointer/keyboard ordering, cancellation, failed moves, read-only access, details, density persistence, templates, saved views, stage editor transactions, mobile overflow and CRM/PMS/HR adapters. Backend tests cover atomic configuration, stale saves, tenant isolation, WIP, hiring prerequisites, named PMS projections, history and Sales operational assignments without financial mutation.

Production build and focused regression results are reported in the implementation chat. Screenshots are under `docs/qa/pipeline-ui/`. No production deployment or live-user acceptance has been performed.

Further work includes per-stage pagination/virtualization, independent PMS pipeline memberships, published Sales stage removal with explicit remapping, additional lifecycle boards and deeper analytics. These are not implied to be complete by the shared UI rollout.

Final checks: frontend production build passed; browser suite passed; 12 focused backend pipeline/configuration/movement tests passed; existing CRM stage requirement/closure test passed. An additional CRM productivity test is blocked by its fixture lacking current company/branch setup (409 before transition validation); its expectations were left unchanged.

## Live acceptance follow-up

Local backend restarted on port 1534. QA records use the `QA Pipeline 1104` prefix. CRM pipeline stages and a deal were created through the UI; the deal moved from QA Intake to QA Review. Sales operational pipeline and QA Review stage were created through the UI; order SO-000002 moved into QA Review while its native document status remained Draft. PMS board 81 was created for project 46 and QA Verification was added. HR job QA Pipeline 1104 Hiring has its own named pipeline and added QA Review stage.

Issues found and fixed during live checks: PMS selected board ID was omitted by the frontend service; settings could open before the selected board loaded; overlapping refreshes could supersede pending loads; stage draft IDs could collide with template IDs; Sales Cancel did not close its editor; Sales search omitted the title when an order number existed; recovered Sales requests retained an old error notice. Sales metadata reads now batch through native scoped queries, and PMS metadata checks each project once rather than once per task. PMS stage quick-add now uses a small native-task drawer with a link to the full form.

HRMS live acceptance: created QA Pipeline 1104 Candidate in Applied, then confirmed movement into the added QA Review stage. PMS quick-add created QA Pipeline 1104 Task in QA Verification. Browser regression coverage now verifies named PMS board selection sends board_id and opens the matching editor. Final build and the focused backend/browser suites passed.

PMS live acceptance completed: the QA task moved from QA Verification to In Progress and remained there after a full browser reload. All four modules completed live pipeline creation, stage creation and card movement. QA records were retained for review; no existing business records were moved. The local backend and frontend remain running.

## Visual refresh

The pipeline UI now uses the latest supplied violet reference across CRM, PMS, Sales and HRMS: contextual headings, subtle wave background, loaded-record overview cards, closed-outcome progress ring, semantic stage icons and tints, card status/priority pills, avatar initials, descriptive empty states, clearable search, matching stage editors and a violet navigation treatment on pipeline pages. PMS cards expose existing descriptions, tags, attachment counts and subtask progress when provided by the API. CRM stages expose configured probabilities. Metrics explicitly describe loaded records, and no historical change percentages or synthetic team/checklist values are generated. Desktop/mobile browser interaction coverage and module adapter tests pass.

The visual pass also consolidates HRMS board controls into the shared toolbar, hides its duplicate summary row in board mode, keeps mobile overview tiles in a swipeable row and preserves compact/comfortable density, dark styling and keyboard movement. Sidebar contrast was checked at the desktop breakpoint.

Visual refresh validation: final `npm run build` passed, and `node scripts/test-pipeline-ui.cjs` passed after the HRMS toolbar consolidation. Desktop and mobile screenshots were inspected; existing production chunk-size warnings remain. No backend schema or workflow changes were needed for this visual pass.
