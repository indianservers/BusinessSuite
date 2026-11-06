# Universal product implementation

Updated: 7 November 2026. This is a phased implementation plan, not a claim that every industry workflow is production-ready.

## Phase 1 — Custom-record runtime foundation

Implemented in this change:

- Formulas evaluate through bounded numeric AST interpretation, with decimal constants, dependency ordering, cycle detection and server-owned results.
- Rollups evaluate on scoped reads for count, sum, average, minimum and maximum. Parent totals reflect child edits, reassignment and soft deletion without a background cache. A lookup field identifies the parent; ambiguous relationships are rejected. Optional conditions exclude nonmatching children.
- Lookup values must reference live records in the configured enabled custom module. User/owner choices use scoped active-user queries. Referenced records cannot be deleted until unlinked.
- Auto-numbers use the existing primary key. Defaults are persisted and computed/automatic values cannot be supplied by clients.
- Custom-record writes validate and calculate in a savepoint. Formula/rule failures do not leave partial record/value/audit writes.
- Search and bounded pagination are available for records and related lists. Search matches persisted input values, not virtual computed values.
- Buttons create real CRM tasks, Approval OS requests/history, or custom-record timeline events; HTTPS links return a navigation result and no-op returns skipped.
- Native task/approval permissions remain required. Button retries use an actor/button request key and lock the custom module/record. Unresolved connector outcomes block another execution even with a different key.
- Webhooks use the existing governed connector preflight and adapter. Permission/configuration checks happen before external IO. Delivery intent is committed before IO; uncertain outcomes require reconciliation and are not automatically retried.
- Legacy formula/rollup configuration endpoints also publish a field definition so their outputs appear in the field library. Field-library edits are authoritative.
- The UI now supports named custom modules, field/lookup/formula/rollup configuration, configurable record actions, validation conditions, relationships, linked-record selection, related lists and paged record browsing. Actions run against the selected record instead of a hardcoded record ID.
- Three PMS `replaceAll` calls were replaced with equivalent global replacements to preserve compatibility with the existing ES2020 build target.

### Verification

Final results: 50 backend regression tests passed; 17 runtime tests passed on isolated PostgreSQL; desktop/mobile browser checks passed; TypeScript and the production Vite build passed. The two backend counts overlap and should not be added as distinct test cases. JUnit reports have zero failures, errors or skipped cases.

Commands, from the respective backend/frontend directories:

```powershell
$env:FAST_TEST_PASSWORD_HASHES='1'
./venv/Scripts/python.exe -m pytest tests/test_customization_runtime.py -q
./venv/Scripts/python.exe scripts/verify_customization_postgresql.py
node scripts/test-customization-runtime.cjs
npm.cmd run build
```

The PostgreSQL runner initializes a separate loopback-only cluster using the repository's existing PostgreSQL binaries, runs the actual migration/test setup and stops that cluster. It does not modify the application database or require changing its account privileges. Test logs remain under ignored `.local/customization-pg-*` directories.

Acceptance coverage includes formula chains/defaults/tampering/rollback, all five rollup operations, child reassignment/deletion, scoped lookup/owner access, read-only roles, literal search and pagination, related lists, action replay/input mismatch, native task and approval creation, unsafe URLs, governed connector denial and ambiguous delivery. Connector network calls are mocked; no real message or provider operation is sent.

Browser verification mounts production customization components in an isolated QA shell with mocked API responses. It checks field setup, picker use, computed-field read-only behaviour, saving without computed fields, action retry keys, related records, paging and desktop/mobile layout. Backend behaviour is verified separately through HTTP tests on SQLite and PostgreSQL.

Artifacts: `outputs/customization-phase-1/regression.xml`, `postgresql.xml`, `records-desktop.png`, `records-mobile.png`.

### Boundaries

- This phase applies computed/related-record semantics to custom modules. It does not automatically add those semantics to native CRM, HR, PMS, SRM or FAM fields or SQL exports. Native integrations require explicit adapters and acceptance tests.
- Computed values are virtual API results; raw stored JSON/EAV rows contain inputs. Decimal API results are strings to preserve precision. Evaluation is bounded to 16 relationship levels and 5,000 evaluated records; large workloads require incremental aggregation in a later performance phase.
- CRM task creation reuses native validation/scope/timeline helpers. Approval requests reuse Approval OS storage/history and appear in the existing approval system; this phase does not introduce a second approval engine.
- Existing customization permissions remain the operational access model. Per-custom-module business-role grants and portable pack identifiers need design before broad staff self-service rollout. Existing database uniqueness rules for custom identifiers are retained.
- Connector delivery ambiguity is durably blocked for reconciliation. A reconciliation UI/provider-status workflow is not added here; provider credentials and live delivery certification remain separate.
- Metadata configuration for saved views, Kanban, layouts and global picklists is retained. This phase does not implement every advertised view/board execution behaviour.
- Existing CRM industry templates still do not install their advertised automations and reports. They are addressed in Phase 2, not relabelled as complete here.

## Phase 2 — Reusable industry packs and onboarding

Versioned, repeatable installation of module choices, names, fields, relationships, statuses, operational role grants, forms, automations and reports. Separate business setup from optional demo data. Validate native-module field adapters, import/export/report access, upgrades and uninstall/disable behaviour. Reuse CRM templates, Power Apps, existing automation and report services.

## Phase 3 — Booking and salon operations

Resource availability, duration and conflict prevention; staff/chair allocation; walk-ins and no-shows; deposits/refunds; packages/redemption; memberships; commissions and consumable stock handoffs. Reuse HR, CRM, service catalogue, POS and finance.

## Phase 4 — Service jobs and repair shops

Customer asset/vehicle records, inspections, estimates/revisions/customer approval, job cards, technician/bay allocation, parts issue/return, labour billing, delivery and warranty/rework. Reuse projects/tasks, inventory, quotes, approvals and invoices.

## Phase 5 — Serialized vehicle sales

Vehicle unit details and documents, exact-unit reservation/sale/cancellation/return, test rides, pre-delivery inspections, exchange and lender/registration handoffs. Extend existing serial inventory and sales flows.

## Phase 6 — CA and accounting practice operations

Client/service/period obligations independent of previous-period completion; collection checklists; review/sign-off; filing acknowledgements; delegated client-book access; close/delivery work queues and validated accounting-provider mappings.

## Phase 7 — Logistics execution

Consignments, packages/weights/rates, trips/dispatch, vehicle/driver assignments, delivery events/POD, exceptions/returns, COD and carrier settlement, and shipment/trip profitability. Reuse commercial and finance services.

## Phase 8 — Industry acceptance and rollout

Real complete business journeys, concurrency and access tests, provider failures, cancellation/return/refund reversal, stock/accounting reconciliation, mobile usability, migration/restore rehearsal and workload tests. Certify each pack separately before selling it as a complete industry solution.
