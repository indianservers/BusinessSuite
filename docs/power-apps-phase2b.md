# Power Apps — Phase 2.B: Intelligent Automation Studio

This enhancement extends the existing standalone Automation Studio. It keeps the existing React Flow canvas, 48-node registry, graph schema version 2, routes, tenant/environment checks, optimistic saves, immutable version snapshots, and recovery behavior. No native PMS, CRM, HRMS or InternHub event producers, actions or subscriptions were installed. Publishing and live execution remain disabled.

## Delivered authoring tools

All tools are available inside the editor through **Create with AI** and **Authoring tools**. The resizable white/purple drawer preserves the underlying canvas viewport when changing tabs.

- **AI Workflow Designer** uses the existing Business Suite structured provider gateway. It supports design, explanation, improvements, conditions, mappings and validation/error explanations. A graph preview, deterministic before/after comparison, structured configuration review and explicit approval separate proposals from drafts. Incomplete proposals can be corrected and server-validated before approval. Applying a proposal is an undoable draft change and follows ordinary autosave/version checks.
- **NodeRecommendationPanel** ranks registered nodes deterministically using output schemas, compatible ports, available catalog types, context and credential requirements. Users explicitly choose an output port. The insertion helper checks compatibility, arity and topology before adding a node/connection; it does not invent configured connectors.
- **DataMappingStudio** has Available Data, Mapping Connections and Destination Fields columns. It supports drag/drop and keyboard selection, safe reference bindings, constants, required/optional fields, type indicators, sample JSON and validated application. Mapping presets are reusable within the portable workflow definition.
- **ConditionBuilder** supports typed comparisons, date/boolean comparisons, list membership and nested AND/OR groups. **SwitchRouterEditor** supports up to 12 named branches and a default route. Dynamic ports use the same catalog derivation in graph validation and canvas rendering; connected branches cannot be removed accidentally.
- **LoopConfigurationEditor** exposes sequential/bounded-parallel mode, a maximum count, concurrency limit, exit conditions and timeout. **MergeConfigurationEditor** exposes all/first/first-successful/first-completed/keyed semantics. These are design contracts; concurrent completion timing and loop iteration require Phase 3.
- **ReusableBlockLibrary** saves non-trigger selections with explicit input/output contracts and defaults, creates immutable version snapshots, inserts pinned versions, edits drafts with conflict checks, duplicates blocks, displays authorized usage, and archives unused blocks. Dependency checks reject cycles, unavailable versions, archived dependencies and excessive expansion depth.
- **TemplateMarketplace** contains 39 versioned definitions across the 12 requested categories, including 31 additional marketplace examples. Templates use registered schemas and preview before use. New scheduling/record/webhook designs identify their ingress prerequisites. No template binds a live module or credential automatically.
- **WorkflowSimulator** evaluates the existing pure preview allowlist and restricted mapping interpreter, using only supplied JSON. Explicit external-action fixtures are labeled synthetic. Step/play/pause controls inspect a prepared deterministic timeline; they are not a background worker or durable execution scheduler.
- **WorkflowDebugger** shows input/output, branch decisions, active ports, variable state, errors and canvas highlights, with JSON report export. External actions remain unexecuted. It does not fabricate integration timings.
- **WorkflowDocumentation** generates purpose, trigger/step descriptions, conditions/routes, declared inputs/outputs, mappings, connector/credential prerequisites, error strategy, draft version and available saved-version history. Export is Markdown; viewing uses escaped plain text.
- **WorkflowImportExport** previews and validates portable JSON, strips credential references and tenant-bound workflow/block links, remaps IDs/internal references, checks schema compatibility and preserves drafts. The existing export menu also uses the portable preparation service. Legacy v1 imports pass through the existing v1-to-v2 adapter.
- **WorkflowQualityPanel** combines structural validation with actionable completeness, reachability, documentation, error coverage, reference, complexity and executor findings. Its label explicitly states that it is not security certification or a reliability guarantee.

## Mapping and condition contracts

Node `mappings` bind registered configuration fields to a safe source reference or a literal constant, a bounded operation list, an explicit target type and nullable behavior. The interpreter supports strings, numbers, booleans, ISO dates/times, arrays, objects and nested JSON.

Declared mapping types must match the destination registry schema, and mapping preview validates the actual sample value against that destination. The UI initially selects the destination type. Loop count/concurrency and router topology remain literal configuration so bindings cannot bypass structural bounds.

Operations are `default`, `convert`, `concat`, `format_date`, `format_number`, `filter`, `map`, `rename`, `conditional`, `lookup` and `path`. Together these cover null/default handling, explicit conversion, concatenation, formatting, array filtering/mapping, key renaming, conditional values, lookup tables and safe dotted JSON-path selection (including array indices). Arguments may contain authorized upstream references. Missing optional source data can use an explicit default or nullable contract. Incompatible target values fail rather than being silently coerced.

Safe paths include trigger/step outputs, literal workflow variables and `env.name`. General environment variables and credentials are never exposed. Paths do not evaluate JavaScript, Python, SQL, shell, arbitrary functions or wildcard JSONPath programs. Array/mapping depth, operation count, input size and output size are bounded.

Existing flat condition configuration remains supported. New condition groups hold typed rule objects. Legacy flat numeric comparisons retain their compatibility behavior; new visual condition groups require numeric operands or explicit mapping conversion. Switch ports are derived from named routes without creating a second node registry. Merge branch keys must be unique and match incoming connections.

## AI authorization and availability

`POST /power-apps/automations/ai/propose` requires Power Apps view/create access, current AI module access, AI permission, enabled governance, usage/rate limits and an enabled company-scoped provider with explicit data sharing. It calls `app.ai_operator.providers.generate_json` with the existing encrypted provider settings and typed output model. It never supplies operational business tools.

Credential references are removed from outbound graph metadata, and the existing redaction service handles sensitive text. Provider-generated graph types, configuration fields, expressions, ports, topology and references are checked with the authoritative graph model and validation service. Invalid output fails closed. There is no hardcoded AI fallback, mock provider selection or automatic publish/activation.

The editor exposes clear authorization/unavailable/error states. A real provider must be configured in existing company AI administration to use generation in a deployed environment. Automated gateway contract tests replace provider transport with explicit test fixtures; they do not certify a live model/provider connection or imply that production credentials were used.

Testing found that the shared tenant boundary did not recognize the existing gateway's scope-key-only provider rows. A narrow boundary rule now recognizes the current company, current user's private scope, and same-tenant workspace scopes while keeping native workspace authorization in its existing endpoints. Foreign company/user/workspace keys remain hidden, and changing a provider/log scope to a foreign tenant is rejected. Power Apps itself selects company providers only; it does not inherit private/workspace credentials.

## Storage, versioning and API changes

No new database table or migration is required. Additive JSON fields extend the same v2 graph:

- Node `mappings`.
- Graph `mapping_presets`, `block_contract` and `block_references`.
- Additional registered configuration fields for condition groups, named router branches, loop settings and merge keys.

Reusable blocks use existing `PowerResource` rows with `application_id=reusable-blocks` and existing immutable `PowerVersion` snapshots. Inserted nodes are materialized copies with pinned source/version metadata; editing a block never edits an existing workflow copy. Phase 3 must define compiled immutable runtime block resolution before publishing is enabled. The current API does not expose deletion of block versions. Archival is denied when any tenant resource references the block, while usage results expose only resources visible to the caller.

New endpoints under `/power-apps/automations`:

- `POST /ai/propose`: authorized structured proposal; never mutates a workflow.
- `POST /intelligence/analyze`: documentation, quality and authoritative reference validation.
- `POST /intelligence/review`: normalize/validate a reviewed proposal using the canonical graph model.
- `POST /mapping/preview`: pure transformation of supplied sample context.
- `POST /portable/prepare`: validated portable graph with stripped references and remapped IDs.
- `GET/POST /blocks`, `PUT /blocks/{id}`, `GET /blocks/{id}/versions`, `GET /blocks/{id}/usage`, `POST /blocks/{id}/archive`.

The existing `/preview` endpoint adds explicit `synthetic_outputs` and `injected_errors` fields. External fixture keys/types are checked against declared outputs. Local deterministic nodes cannot be impersonated by synthetic outputs, and error ports activate only on failure. Concurrent join ordering reports Requires Production Executor. No execution records or business-side mutations are produced.

Read-only analysis/review/portable routes are classified as view operations in the shared access catalog; writes retain their original create/edit permissions. Ordinary workflow saves additionally check pinned block dependencies. Deletion/copy/paste preserve or prune block metadata so provenance cannot make an otherwise valid draft unsavable.

## Component entry point

Typed public exports remain in:

`frontend/src/apps/power-apps/applications/automations/builder/index.ts`

The requested AIWorkflowDesigner, NodeRecommendationPanel, DataMappingStudio, ConditionBuilder, SwitchRouterEditor, LoopConfigurationEditor, MergeConfigurationEditor, ReusableBlockLibrary, TemplateMarketplace, WorkflowSimulator, WorkflowDebugger, WorkflowDocumentation, WorkflowImportExport and WorkflowQualityPanel are exported. They receive catalog, graph/document, permission and service callbacks; none import native business-module data models. The server-side registry and v2 serialization format remain canonical.

## Security findings and fixes

- Provider tenant scope is explicit and tested, including foreign scope write rejection and same-tenant workspace compatibility.
- Unregistered node/configuration types, prototype identifiers/properties, expression injection, arbitrary operations, cycles and excessive complexity fail validation.
- AI proposals remain separate from draft state until validated and approved. Draft changes while a proposal is pending prevent accidental replacement.
- Imports are normalized server-side before application. Exported credential references and tenant links are stripped, and recognizable secret-looking literal text is redacted.
- Debug reports redact recognizable secret text; no decrypted credentials or unauthorized business records are fetched.
- Synthetic fixtures are explicit, schema-checked and labeled. They cannot impersonate successful local logic or a live external action.
- Normal results use normal ports; injected failures use explicit error routes. Unsupported executors are never reported as successful integrations.
- Optimistic workflow/block version checks, tenant/environment/ownership scoping and immutable snapshots remain authoritative.

## Verification

- Backend Power Apps, authoring, migrations and company security boundary: **142 passed** against the isolated PostgreSQL test database.
- Mocked-browser editor, recovery, responsive and performance regression suite: **25 passed**.
- Combined real-API browser suite: **19 passed**, including all five Phase 2.B scenarios, reviewed AI proposals, visual logic controls and the existing Phase 2.A regressions.
- TypeScript (`tsc --noEmit`), Power Apps ESLint and production build: passed. The final gateway prompt addition also passes Python compilation.

The broader legacy AI provider/operator suite is **not green**: 20 tests fail at existing verified-company-membership requirements because their shared fixture creates unassigned users. A temporary fixture investigation was reverted because assigning company membership changes those tests' private-scope assumptions. Production authorization was not relaxed. Dedicated gateway company/user/workspace boundary tests are included in the passing scoped suite. Earlier unrelated PMS/InternHub regression failures also remain outside this change; this report does not certify the whole repository.

Visual QA: [simulation and debugger screenshot](qa/power-studio-intelligence/simulation.png).
Portable scenario artifacts: [workflow](qa/power-studio-intelligence/scenario-e-workflow.json) and [debug report](qa/power-studio-intelligence/scenario-e-debug.json), containing synthetic test data only.

The five scenario fixtures are in `backend/tests/fixtures/power_studio_scenarios.json`: Manager Approval, Intern Bug Escalation, Employee Onboarding, CRM Lead Qualification and Complex Data Processing. Backend tests evaluate their original mappings and branches. Real-application browser tests create drafts through authenticated APIs, edit configuration/mappings, save and insert reusable blocks, preview/apply/undo templates, export/import/undo portable graphs, inspect simulation/debug reports, generate documentation/quality findings, save/reload and check permissions/tenant isolation. Browser-generated approval proposals are explicitly labeled transport fixtures in tests.

Reproduce from `frontend`:

```powershell
npx playwright test --config=playwright.power-apps.config.ts --workers=1
npx playwright test --config=playwright.power-studio-live.config.ts --workers=1
npx eslint src/apps/power-apps --ext ts,tsx --max-warnings 0
npm run build
```

From `backend`:

```powershell
$env:FAST_TEST_PASSWORD_HASHES='1'
$env:POSTGRES_TEST_DATABASE='business_suite_power_studio_test'
venv/Scripts/python.exe scripts/run_postgres_tests.py tests/test_power_apps.py tests/test_power_studio.py tests/test_power_intelligence.py tests/test_power_apps_migration.py tests/test_power_studio_migration.py tests/test_company_security_boundary.py -q --disable-warnings
```

All test databases are isolated/disposable. No production database migration, deployment, external action or production AI-provider call was performed.

## Remaining dependencies and Phase 3 readiness

The authoring surface and pure simulation contracts are ready for a separately authorized durable runtime phase. Publishing and execution are still blocked. Phase 3 must implement immutable published definitions and compiled block resolution, authorized connector/native-record schemas, credential resolution, trigger ingress, leases, durable jobs/checkpoints, idempotency, retries/backoff, cancellation, approvals/delay continuations, bounded loops, concurrent merge ordering, native permission checks at execution time, audit/retention policy and crash recovery.

Current block insertion is materialized, not a live shared executable call. Mapping presets are workflow-local/portable. JSONPath is a safe dotted/index subset. Simulation playback reveals an already prepared pure timeline rather than executing durable work. General environment variables and live connector schemas require authorized adapters. Provider availability requires explicit company configuration. Production builds retain the repository's existing large-chunk and third-party annotation warnings.
