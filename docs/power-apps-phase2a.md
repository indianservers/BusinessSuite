# Power Apps — Phase 2.A

The existing Automation Studio has been enhanced in place. It remains a standalone Power Apps component, with existing routes, definitions, snapshots, tenant/environment scopes, and backend mutation permissions preserved. No PMS, CRM, HRMS, or InternHub integration was added. Phase 3 was not started.

## Editor enhancements

- React Flow canvas retains cursor-centered wheel zoom, native touch pinch, pan, minimap, fit, multi-selection and multi-node drag. Canvas options add reset to 100%, persisted optional grid snapping, and Bezier/orthogonal routing. The default connection style applies to newly created edges; individual existing edges retain their saved style. Alignment guides identify matching node origins while dragging; dropping aligns the single selected node. Multi-node dragging preserves relative placement.
- Groups have editable labels and collapse/expand controls. Members and their incident connections are hidden while collapsed, without changing graph topology or deleting positions. Search and validation navigation expand the containing group. Read-only viewers can expand groups locally without saving changes.
- Sticky notes and annotation blocks are movable, editable plain text. New notes avoid existing cards. Labels and notes use React text rendering; user HTML is never executed.
- Ctrl/Command F opens canvas search by name, ID, description or type and focuses a result. Breadcrumbs support navigating to an authorized referenced sub-workflow and back to its parent. Parent trails are session navigation state; they are not an execution stack and are not reconstructed after a full reload.
- Copy, cut, paste and duplicate support nodes, complete selected groups and notes. Pasted node IDs, internal edges and dynamic step references are remapped. Undo/redo, confirmed deletion and draft recovery remain available.
- Every output, including error outputs, has an add button. Automatic insertion accepts exactly one compatible input. Inserting on a connection requires exactly one compatible input/output pair and validates both resulting edges against arity, types and topology. Ambiguous branches leave the graph unchanged and require explicit connections.
- Connections have arrowheads and textual branch/error labels, node-adjacent and selected highlights, editable labels/styles, deletion, a keyboard-accessible reconnection form, and draggable endpoints. Reconnection validation excludes the connection being replaced. Bezier and orthogonal paths update as nodes move.
- The resizable inspector has Parameters, Input / Output, Settings and Documentation tabs, inline errors, schema-driven controls, optional conditional fields (`visible_when`), declared schemas, and node disable controls. Disabled nodes block their path in local preview; they do not fabricate pass-through output.
- The node library includes persistent local favorites and recent types, icons, descriptions, configuration counts, searchable categories and honest preview/runtime capability labels. Preferences store only public node type IDs.
- Workflow settings include descriptions, tags, and literal non-secret workflow variables. Version comparisons identify organization metadata changes as well as node/edge/settings changes.

## Variables and safety

`VariablePicker` lists searchable upstream output schemas and trigger references with types and paths. It also lists `{{workflow.variables.name}}` values and `{{env.name}}`, the environment already authorized by the server. Numeric/boolean fields reject incompatible suggestions. Unknown/dynamic types remain eligible for design-time mapping and must be checked during real runtime implementation.

Typing `{{` opens autocomplete. Choosing an entry replaces the unfinished prefix rather than nesting braces. Both server and browser parse property references only; arbitrary JavaScript is not supported. Secret names, prototype properties, inline credential objects and nonliteral workflow variable definitions are rejected. No credential values or general environment variables are fetched or suggested.

Only the authorized environment name is exposed in this phase. Additional environment variables need a server-owned, permission-filtered metadata/value adapter before they can be offered. Credential references remain references, and external record/directory/template providers remain injected capabilities. No dummy integration results are returned.

Backend validation checks static sub-workflow references in the same tenant, environment, ownership scope and archive state. Unavailable IDs produce a generic blocking issue without disclosing foreign resource details. Oversized numeric references fail safely. Drafts may retain incomplete business configuration, while malformed/unsafe structures cannot be persisted.

## Persistence and compatibility

Schema version 2 is extended additively with defaults:

- Node `disabled` defaults to false.
- Edge `style` defaults to `bezier`.
- Group `collapsed` defaults to false.
- `annotations`, `tags` and `variables` default to empty collections.
- `editor` defaults to grid snapping and Bezier connections.

Existing v1 imports and v2 drafts continue to load. All additions live inside the existing JSON definition; this enhancement requires no new database migration. Existing version snapshots remain immutable, and restoring still creates a separate draft.

Autosave retains its 1100 ms debounce and optimistic version check. Server autosave pauses during an active drag and resumes after release, preventing repeated requests during long drags. Local recovery and before-unload protection remain active. Selection-only changes do not save. Asynchronous validation/preview responses compare workflow content rather than viewport coordinates, so an auto-fit animation cannot silently discard a completed result. No editor control can bypass backend publishing or execution authorization.

Limits remain 500 nodes, 1500 edges and 100 groups, with at most 100 annotations (4000 characters each), 20 tags (60 characters each), and 50 literal scalar workflow variables. Preview retains its smaller design-time complexity bounds.

## Reusable component API

Public exports are available from:

`frontend/src/apps/power-apps/applications/automations/builder/index.ts`

The exports include `AutomationBuilder`, `AutomationCanvas`, `WorkflowNodeComponent`, `NodeLibrary`, `NodeConfigurationPanel`, `VariablePicker`, `ConnectionEditor`, `ValidationPanel`, `WorkflowToolbar`, `WorkflowMinimap`, `WorkflowHistoryPanel`, `WorkflowSearch`, `NodeGroup`, `WorkflowAnnotation` and `WorkflowBreadcrumbs`, plus typed graph, configuration, reference, variable and breadcrumb contracts.

The builder receives catalog, permissions, persistence, validation, preview, navigation and reference callbacks. These components do not import any business module data models. They target the repository's React/TypeScript stack; graph contracts and server validation are independent of the canvas library. A host must provide a React Flow provider for direct use of the lower-level canvas primitives; `AutomationBuilder` provides one itself.

## Validation evidence

- **55 Power Apps/PostgreSQL tests passed**, including schema compatibility, persistence, previews, permissions, unsafe imports, variables and workflow-reference validation.
- **25 UI browser tests passed**, including the new premium interactions and existing route/mobile/performance regressions.
- **12 live application browser tests passed**, including all ten requested workflow scenarios. No unexpected browser page or console errors were observed in those scenarios.
- TypeScript, targeted ESLint and production build passed. The build retains existing bundle-size/third-party annotation warnings.
- A broader PostgreSQL run recorded **94 passed, 3 failed** across Power Apps, Business OS, PMS, CRM and InternHub. Two PMS tests expect 404 where current custom-field code returns 422: `test_custom_fields_validate_types_and_project_scope` and `test_type_specific_fields_and_plural_names`. InternHub's `test_hrms_provisions_intern_login` inserts Company ID 1 even though that company already exists; it also fails in isolation on a fresh test database. These modules/tests were already modified elsewhere in the shared working tree; this enhancement did not change their runtime or fixtures. They remain unresolved and prevent claiming that the entire repository passes.

Screenshots and JSON timing evidence are saved under `docs/qa/power-studio-premium/`. These show isolated test workflows, never claimed production activity.

The browser suite exercises the existing dashboard/routes, permissions, recovery, conflicts, templates, versions, mobile/tablet layouts, mouse/touch navigation, 10/50/100/250-node measurements, and the new organization, palette, insertion and breadcrumb interactions.

The actual application suite uses real FastAPI authentication and persistence against an isolated temporary database. Its ten design-time scenarios are simple action, conditional branches, parallel branches, approval, error path, 50 nodes, 100 nodes, groups/annotations, variable mappings and rejected invalid connections. Each scenario creates a real draft, edits it through the browser, checks undo/redo, saves/reloads, compares topology, configuration, positions and metadata, checks unique IDs and edit permissions, and inspects browser page/console errors. These scenarios do not execute external integrations. PostgreSQL coverage separately verifies the real migration chain and backend contracts.

Reproduce from `frontend`:

```powershell
npx playwright test --config=playwright.power-apps.config.ts --workers=1
npx playwright test --config=playwright.power-studio-live.config.ts
npx eslint src/apps/power-apps --ext ts,tsx --max-warnings 0
npm run build
```

From `backend`:

```powershell
$env:FAST_TEST_PASSWORD_HASHES='1'
$env:POSTGRES_TEST_DATABASE='business_suite_power_studio_test'
venv/Scripts/python.exe scripts/run_postgres_tests.py tests/test_power_apps.py tests/test_power_studio.py tests/test_power_apps_migration.py tests/test_power_studio_migration.py -q --disable-warnings
```

The guarded PostgreSQL runner recreates only the named test database. No production migration, deployment, external action or application-data mutation was performed.

## Remaining limitations

Publishing, activation, live integrations, approval continuations and workers remain unavailable. The 48 node definitions retain their editor-only runtime status; only the existing pure transformations support local previews. Bounded loops are modeled and validated, but runtime loop execution belongs to Phase 3. Collapsed groups conceal their incident edges rather than inventing proxy executable ports. Automatic insertion refuses branching ambiguity. Alignment guides align node origins, not every possible shape/center geometry. General environment variables and live connector schemas require authorized adapters. Browser-local favorites/recent lists are per browser rather than organization settings.

Production builds retain the repository's existing large-chunk and third-party annotation warnings. Broader regression results are reported explicitly; this document does not claim exhaustive certification of every unrelated module in the shared working tree.
