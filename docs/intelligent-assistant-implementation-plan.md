# BusinessSuite intelligent assistant implementation plan

Updated: 10 November 2026. Scope: one assistant across CRM, HRMS and PMS first; reuse existing AI, authorization, provider settings, approvals and workers. OpenAI means the server-side OpenAI API, not a ChatGPT subscription. Cloud credentials stay in the existing encrypted provider configuration.

## Phase 1 — Unified briefing, evidence and reviewed native actions

### Deliverables

- Extend `/ai-operator/suite` and the existing AI workspace; no parallel assistant backend or credential store.
- Select OpenAI or Gemini through existing scoped provider adapters. Retain Claude compatibility. Offer an explicit local rules mode for deterministic briefs and bounded task creation; do not represent it as a general-purpose local LLM. Preserve the existing browser-local PMS model separately.
- Read current CRM tasks, selected-workspace PMS projects/tasks and personal HR leave/tickets through canonical APIs and existing tool authorization.
- Daily briefing: overdue, due-today, blocked and high-priority work; personal/all-visible scope, module and deadline filters. Mark bounded source coverage and source failures.
- Delivery signals: project-linked blocked/overdue tasks and missed project deadlines. Attribute only to actual project/client links; no inferred CRM customer matching or unsupported financial impact.
- Source identifiers, retrieval timestamps and authorized deep links. Cloud answers select from server-issued evidence IDs; reject fabricated citation IDs. Distinguish a source list from independently verified claim-level entailment.
- Reuse exact-plan previews, hashes, expiry, approval, cancellation, queued execution and receipts. Local bounded commands can prepare CRM/PMS tasks; HR leave/helpdesk actions continue through the existing cloud tool catalog and business rules.
- Show citations and source coverage in the current operator UI. Clear scoped data when workspace, organization or branch changes.

### Engineering work

1. Add shared evidence and local-plan helpers, plus a deterministic briefing service with canonical reads.
2. Add evidence to existing command prompts/results without changing the approval contract.
3. Add provider selection and a briefing component to the existing suite workspace.
4. Exercise ranking, timezone boundaries, missing dates, completed work, source limits, authorization failures, local no-cloud behavior, citations and approval-before-write.

### Acceptance

- Native briefs work without a model key; local mode makes no model request.
- Unauthorized module data is never included. Failed reads are explicitly marked; an unavailable source is never reported as empty.
- Only real authorized source IDs become citations. Task drafts have no business effects before approval.
- Existing suite operator/approval regressions and frontend type checks pass.
- Live OpenAI/Gemini verification is conditional on configured test credentials; mocked transport tests are labeled accordingly.

## Phase 2 — Broader native tools, invoice drafts and usable reports

### Deliverables

- Expand CRM: owner/date/status/customer filters, task reminders, follow-up plans, lead/deal summaries and internal notes.
- Expand PMS: task creation with assignees, milestones, due dates, dependencies, checklists and status updates through existing validators/executors.
- Expand HRMS: personal leave requests, helpdesk tickets, policy answers and authorized manager availability/approval queues. Keep sensitive payroll fields out of general context.
- Add typed report requests: module, entity, dimensions, measures, date range, status, owner, customer and output format. Use approved report services and deterministic aggregates, with filter/source metadata and export authorization.
- Reuse SRM invoice draft tooling and canonical customer, seller, currency, tax and line validation. CRM/PMS context does not substitute for SRM/FAM permissions or installed modules. Issuing/sending invoices, posting ledgers and taking payment remain separate business actions.
- Replace short local command coverage with more typed local intents and, if justified, a browser-local model adapter feeding the same validator. Unsupported local requests ask for structured fields instead of silently switching to cloud.

### Acceptance

Real CRUD integration tests for each added tool; denied-role and tenant tests; exact report totals on known fixtures; invalid filters rejected; invoice drafts cannot issue, post or charge money; ambiguous customer names require selection. Test pagination and filters against canonical endpoint contracts.

## Phase 3 — Reminders, commitments and connected communication

### Deliverables

- Scheduled reminders with explicit timezone, recipients, channel, quiet hours, deduplication, owner, expiry and cancellation.
- Reuse the existing notification/email dispatch and durable jobs. Store schedule configuration, not a long-lived user bearer token; reauthorize at execution.
- Pilot Google Workspace OR Microsoft 365 using existing OAuth/vault/connector code. Add the collaboration channel used by the pilot customer; expand afterward.
- Inbox/meeting-to-task drafts, customer commitment links and delivery follow-through. Keep author/source/time and ambiguity attached to extracted commitments.
- Connection health, scope checks, token/subscription renewal, incremental sync, revocation and deletion propagation. Never infer user access solely from service-account or bot membership.
- Outbound reminders show recipients/content before approval or use narrowly configured standing consent. Handle send timeouts as unknown until reconciled; do not blindly repeat messages.

### Acceptance

Duplicate jobs/events produce one effect; cancelled/expired rules do not send; permission withdrawal blocks execution; timezone/quiet-hours cases pass; send receipts reconcile; live pilot OAuth and webhook recovery are verified. Public Google app verification and tenant admin consent are tracked where applicable.

## Phase 4 — Proactive business operations and measured expansion

### Deliverables

- Source-backed customer → deal → project → delivery → invoice views using explicit existing entity links.
- Capacity scenarios using authorized skills, allocations, leave, working calendars and dependencies. Label projections and missing evidence.
- Reusable playbooks with limits, owner, expiry, stop rules and inspectable memory. Allow bounded reversible autonomy only under explicit policy.
- Model routing by measured quality/cost, optional voice and regional languages, and allowlisted MCP tools sharing the same policy gateway.
- Production observability: source freshness, policy denials, approvals, partial/unknown outcomes, token/cost ceilings, circuit breakers and incident handling.

### Acceptance

Versioned benchmark of factual answers, business workflows, ambiguity, prompt injection, tenant boundaries, revocation and connector failures. Require authoritative receipts for claimed writes and no unauthorized disclosure/effects in the release suite. Compare overlapping workflows with ClickUp under equivalent data/access conditions; report domain coverage separately from reasoning quality.

## Delivery order and dependencies

Each phase ships only after its own acceptance checks. Phase 2 depends on shared tool/evidence contracts from Phase 1; Phase 3 depends on reliable native writes, jobs and receipts; Phase 4 depends on proven source freshness, identity mappings and recovery. Calendar estimates follow baseline testing and pilot scope selection; no unverified deadline is implied.

## Phase 1 implementation record

Implemented in the current checkout:

- `GET /ai-operator/suite/briefing`: deterministic priorities and overdue/blocked project signals over canonical CRM/PMS/personal HR sources, with filters, timestamps, bounded coverage and explicit unavailable-source status.
- Shared evidence helpers and validated source references in suite command results. Unsupported source references fail validation; responses with no references are labeled unsourced. This validates source identity, not independent factual entailment.
- OpenAI/Gemini/local selection in the existing suite workspace. Local summaries and explicit CRM/PMS task drafts require no configured model; existing browser-local PMS inference remains available in PMS Assistant Studio.
- Reviewed task drafts use the existing approvals, canonical writes, worker and receipts. Organization/branch changes clear scoped UI state and discard obsolete command responses.
- No database migration or new model SDK dependency was needed.

Verified on 10 November 2026:

- Backend: 37 tests passed across `test_ai_daily_briefing.py`, `test_suite_operator.py` and `test_suite_module_agents.py`.
- Browser: the isolated development fixture passed briefing/filter/source/provider/approval and branch-reset checks. All fixture data and provider responses are simulated.
- Frontend: TypeScript check and production build passed. The build reports dependency annotation, mixed-import and large-chunk warnings.
- Python compilation and changed-file whitespace checks passed.

Live cloud calls were not verified: OpenAI and Gemini routing used mocked provider transports. Delivery risk is currently project-linked evidence, with PMS client IDs where explicitly linked; automatic CRM customer matching, full capacity analysis and monetary impact remain later-phase work. Invoice creation, full report exports and scheduled outbound reminders are not new Phase 1 features. Remaining phase work must not be labeled shipped merely because supporting legacy code exists. No production deployment or external message was performed.

## Phase 2 implementation record

Implemented in the development checkout on 10 November 2026:

- Extended the same suite operator, tool allowlist, independent security catalog, approval hashes and canonical module APIs. No parallel credential store, execution engine or database migration.
- CRM task reads support status, priority, owner, customer, lead/contact/deal and deadline-queue filters. Company people lookup resolves actual user identities for ownership. Reviewed task creation/update supports owner and timezone-aware reminder timestamps; changing a reminder also checks the current deadline.
- PMS task creation supports assignees, parent tasks and milestone links. Reviewed milestone creation can supply a new milestone ID to a later task step. Existing task plans continue to handle dependencies, checklists, dates and status changes.
- HR sources include published policies only, authorized team leave availability, and the permission-protected leave approval queue. Existing self-service leave/helpdesk actions now also have typed local preview forms.
- Manual invoice drafts require a real customer, nonempty validated lines, nonnegative prices/tax/discounts, valid currency syntax and consistent dates. Clients cannot set invoice status, override line totals or reserve billing sources. Canonical SRM validation and calculation remain authoritative. Approval creates drafts; issuance, sending, payment and ledger posting remain separate.
- Added `GET /ai-operator/suite/reports/{module}` for CRM tasks/deals, PMS project tasks, personal HR leave and SRM invoices. Reports support validated filters, dimensions and count/amount measures. Source reads paginate under the existing call/data budgets, mark partial scans, and never combine amounts across currencies. Dates use an explicit timezone. Unsupported dimensions/filters fail rather than being silently ignored.
- CSV exports use the same report query, require module export access plus analytics export permission, escape spreadsheet formulas and include coverage/filter metadata on group rows. JSON previews include source references, retrieval times and filter metadata.
- The existing `/ai-agents/operator` workspace now includes report filters, aggregation preview, CSV download and typed local action forms for CRM/PMS tasks, milestones, leave, helpdesk and invoice drafts. Forms prepare the same exact-plan review; no cloud request is needed to prepare them.

Validation:

- 52 backend tests passed across native operations, daily briefing, suite execution and module-agent suites, including real canonical invoice/task/milestone execution, report pagination/totals, denied exports and unpublished-policy exclusion.
- Two development-fixture browser scenarios cover provider/source/briefing behavior plus report filters, CSV download, invoice preview, exact approval and branch resets. Fixture responses are simulated.
- Frontend TypeScript and production build passed; dependency annotation, mixed-import and large-chunk warnings remain. Python compilation and changed-file whitespace checks passed.

Server-only Gemini configuration:

- The supplied credential was saved using the existing encrypted provider storage on the BestERP backend for the primary company. It was not written into repository files, local environment files, frontend bundles or application logs.
- Google accepted the credential for model discovery. Generation through the deployed adapter did not pass: the last generation attempt returned HTTP 503; a separate model attempt returned HTTP 404. The stored configuration is disabled until a successful generation test. Do not report the provider as operational based on model discovery alone.
- Phase 2 application code has not been deployed to production. The authorized production change was the server-only provider credential/configuration and synthetic connectivity tests. No customer records were sent in those tests.

Remaining: scheduled outbound reminder delivery, connected mail/calendar synchronization and commitment monitoring belong to Phase 3. General browser-local model coverage remains limited to the existing PMS model; Phase 2's broader local actions use typed deterministic forms.

## Phase 3 implementation record

Implemented in the development checkout on 10 November 2026, with both Google and Microsoft pilot support:

- Added reviewed one-time/daily/weekly reminders for authorized CRM, PMS, HRMS and invoice records. Previews freeze source, recipients, channels, timezone, quiet hours and expiry; approval uses the existing signed security context. The existing email worker rechecks current access before preparing and sending each occurrence. Cancellation suppresses pending deliveries; unique occurrence keys prevent duplicate effects. Unknown email outcomes require an evidence-backed reconciliation and never trigger an automatic resend.
- Added source-backed commitments from selected Gmail/Outlook messages, Google/Microsoft calendar events, or attributed pasted transcripts. Reused existing connector credentials and read operations. Mail bodies are encrypted in the commitment artifact and excluded from connector output logs. Pasted transcripts are explicitly unverified. Local extraction is conservative; configured cloud providers remain optional.
- Exact source quotations are required for candidates. Users resolve ambiguity, confirm an actual owner and due date, and prepare the existing CRM/PMS task plan for a separate exact-action approval. Source changes, deletion or revoked connections invalidate retained quotations and block stale task plans. Connected sources are rechecked before preparing task drafts and periodically by the existing worker, with bounded work per pass.
- Extended the existing operator workspace with reminder review/receipts, commitment review, connection readiness and selected-source browsing. No second execution engine or credential store was introduced.
- Added an additive unique request-key index on the existing automation job table in both migration chains: generic revision `20261110_077_ai_job_requests`, active PostgreSQL revision `pg_20261110_094_ai_job_requests`.

Release limits and live acceptance:

- Validation passed: 432 backend tests across reminders, commitments, migrations, native actions, suite execution and existing connector/runtime suites; three isolated browser scenarios; frontend TypeScript compilation and production build. Build warnings remain for dependency annotations, mixed imports and chunk size. Browser/provider fixtures are simulated.

- No Phase 3 application deployment or production migration has been performed. Development fixture browser tests simulate accounts and delivery; they are not live mail/calendar acceptance.
- A read-only production readiness check found Google OAuth configured, Microsoft OAuth unconfigured, and no connected accounts for either provider. Live consent, provider delivery, calendar access and webhook recovery remain unverified. Phase 3 is implemented locally but has not met the full live-pilot acceptance gate above.
- Server administrators must configure `POWER_MICROSOFT_CLIENT_ID` and `POWER_MICROSOFT_CLIENT_SECRET`, retain the existing server-only Google credentials, and register `POWER_OAUTH_REDIRECT_URI` to match the backend `/api/v1/power-apps/integrations/oauth/callback` URL exactly. Account owners then connect the required mail/calendar accounts through existing connector management. Secrets stay on the server.
- This release reads selected sources and monitors their commitments; it does not build an unrestricted mailbox index. Existing connector synchronization remains responsible for provider watch/subscription recovery.

## Phase 4 implementation record

Implemented in the development checkout on 10 November 2026:

- Added a Business operations panel to the existing operator workspace. All private panel state is discarded when company, branch, workspace or project changes.
- `GET /ai-operator/suite/operations/delivery` composes current project/task access with the canonical SRM project-billing service and authorized CRM customer/deal reads. Customer and opportunity edges use `ProjectCommercial` references; invoices use the canonical project billing relations. A shared customer name does not establish a project/invoice link. Unavailable modules, missing links, sample bounds and retrieval times are visible. Invoice face-value totals use decimal arithmetic and stay separated by currency; they are not receivable balances or predicted revenue loss.
- `POST /ai-operator/suite/operations/capacity-scenario` previews visible allocations plus explicitly entered additional hours. Availability comes from the native capacity service, including working schedules, weekly overrides, applicable holidays and approved leave. Maintained project skill/away policy is labeled as owner-supplied evidence. Date/lag conflicts use existing authorized project dependencies. Missing estimates, unavailable capacity, missing skills, omitted people and bounded dependency coverage remain explicit. Scenarios make no business writes. Allocation remains a weekday estimate spread across assignees, not an optimized schedule or full company capacity forecast.
- Reused existing project playbooks, memory, rule worker, exact-plan previews and reversible status/priority automation. New rules have a future timezone-aware expiry (default 30 days), 1–100 proposal budget (default 20), proposal counter and stop-on-unresolved-outcome behavior. One outstanding proposal prevents overlapping proposals. New standing-consent policies default to a 30-day expiry; the executor checks policy/rule expiry again before effects. Existing policy revision/revocation and undo evidence remain authoritative. The new UI enables reviewed proposals; it cannot enable standing autonomy.
- `GET /ai-operator/suite/operations/health` reports bounded owner telemetry for the current security context: request states, policy denials, unresolved outcomes, receipt counts, provider availability, latency, token totals and known pricing. Only logs tied to currently verifiable suite runs appear. Unknown pricing/usage remains unknown; private response bodies are excluded.
- Added a five-minute same-owner/scope/model circuit breaker after three consecutive transient provider failures for suite calls. It performs no network retries or provider fallback. Existing security settings, token/output/time/cost limits and provider data-sharing configuration remain in force.
- Added opt-in `provider: auto` routing. The selected project must have at least three distinct successful cloud outcomes rated by its owner; eligible models require at least 80% owner quality pass and technical success in a bounded 30-day sample. Routing orders eligible models by owner quality, fully known configured mean cost, then latency. Missing cost sorts last. The current enabled scope/model, data-sharing permission and circuit state are rechecked; disabled or changed models cannot inherit earlier eligibility. The decision is frozen on the request, displayed with the response and reused on an idempotent retry. Reviews are mutable, one per outcome, and do not approve actions. Owner ratings are not independent factual verification or statistical proof of superiority.
- Idempotent suite-command retries now reverify the stored security context before returning private prior results, including the concurrent request-key recovery path.
- Added a versioned deterministic acceptance manifest at `backend/tests/fixtures/assistant-release-v1.json` and runner `backend/scripts/run_assistant_benchmark.py`. Run with the backend interpreter; it writes JUnit evidence to `.local/assistant-release-v1.xml`. It covers native workflow receipts, citations, ambiguity, untrusted text, tenant/owner boundaries, revocation, uncertain sends, rule limits, routing and missing-cost behavior. Provider transports and browser fixtures remain simulated.
- Reused existing tables and providers. No Phase 4 schema migration, new credential store, external messages or production deployment was performed.

Release gate: production rollout still depends on the Phase 3 account consent/recovery and delivery checks. Live model quality/cost benchmarks and an equivalent-data ClickUp comparison have not been performed. Existing voice dictation remains available; regional-language quality and remote MCP expansion are optional, unvalidated extensions rather than release claims.

Validation: the versioned 120-case backend benchmark passed, followed by 37 overlapping targeted operations/suite regression tests covering the final security-context retry fix and one added case. Four isolated browser scenarios passed, along with the production TypeScript/Vite build, Python compilation and whitespace checks. Browser and provider transports are simulated. Existing dependency-annotation, mixed-import and large-chunk build warnings remain.

## Local NLP command training and workflow validation

Added on 10 November 2026:

- Authored 120 synthetic command examples each for CRM, PMS, Sales (SRM) and HRMS: 480 unique utterances across 20 intent families per module. The maintained corpus is `backend/app/ai_operator/local_corpus.py`; authorized users can inspect each module's 120 examples using `GET /ai-operator/suite/local-model?module=CRM` (or PMS, Sales, HRMS) and the new Local command library in the operator workspace.
- The server now fits an offline TF-IDF nearest-example intent model from this corpus, combined with conservative entity/filter grammar and typed slots. This is actual local retrieval-model fitting, not neural LLM fine-tuning or 120 distinct capabilities per module. No production conversation/customer data is added to training. The browser assistant and editable voice transcripts use this same server interpreter; the existing browser-local PMS neural model and its weights have not been retrained.
- `backend/scripts/train_local_nlp.py` exports `model.json`, all 480 `commands.json` examples and `evaluation.json` under `.local/local-nlp-v1/`. It records the corpus SHA-256 and evaluates 40 separately authored development paraphrases. The implementation was improved using those results, so this is not an untouched generalization benchmark or a claim of general English accuracy.
- Local requests automatically choose the relevant existing allowlisted source tools. Reads apply current native permissions, selected project, timezone, ownership/status/date filters and evidence citations. Missing or disclosure-limited data is not reported as an empty company-wide result. The classifier abstains on unknown, destructive, injected or compound requests. A read containing a quoted title cannot silently become a creation.
- “What are todays jobs?” uses the live deterministic briefing for authorized CRM/PMS due-today and overdue work. HRMS explicitly labels its pending personal requests rather than pretending they are all dated today. Sales today-work queries inspect invoice due dates. “Check todays reminder” checks active, nonexpired schedules for the current owner/company/concrete branch/module and rechecks the underlying record before showing it.
- CRM/PMS task creation and updates, PMS milestones/schedules, HR helpdesk tickets and CRM internal notes prepare the existing exact-action approvals; no record is written by intent recognition. Quoted titles, selected task IDs, explicit statuses/priorities and timezone-aware relative dates are supported. Clarification follow-ups retain prior intent/slots and refetch current sources.
- “Send a message to all leads” asks for channel and exact content. For example: `CRM: email all leads subject "Check-in" body "Hello {{name}}, may we arrange a call?"`. Complete audiences of at most 50 leads use the canonical CRM greeting preview with current contactability, opt-out and duplicate-destination checks. Partial source pages cannot be called all leads. The assistant shows recipients, eligibility and content, then hands the draft to CRM Greetings for fresh native review and final confirmation. It does not expose the send token or add an automatic-send tool.
- Invoice issuance/delivery, payments, incomplete invoice/order/leave/reminder requests, confidential payroll and unconnected attendance queries remain explicit clarifications or canonical-workspace handoffs. Recognizing these intents does not authorize or implement those operations. Voice transcription capability still depends on the existing browser setup.

Examples to try with Assistant set to Local intelligence:

- `CRM: what are todays jobs`
- `CRM: check todays reminder`
- `CRM: email all leads subject "Check-in" body "Hello {{name}}, may we arrange a call?"`
- `CRM: create task "Call the client" due tomorrow`
- `PMS: show blocked project tasks`
- `PMS: create project task "Review release" due tomorrow` (select a project)
- `Sales: show unpaid invoices`
- `Sales: show invoice totals by currency`
- `HRMS: show my leave balance`
- `HRMS: create HR ticket "Laptop access"` (requires an employee profile)

Validation includes all 480 training utterances, canonical source/payload contracts, 40 development paraphrases, guarded actions, missing details, permissions, timezone boundaries and compound/injected commands. Native integration tests use real module APIs for today's jobs, current reminders, CRM/PMS tasks, HR helpdesk and Sales reads. Lead outreach is previewed without sends, then final confirmation is separately tested using the isolated stub provider: opted-out leads are skipped, edited content invalidates approval, and replay produces no duplicate delivery. No real lead message or model API call was made. The release benchmark manifest now includes the NLP suites. Production code has not been deployed in this work.

Final verification: 600 focused local-model/workflow checks passed; a broader 654-case assistant regression run also passed before the final local guard refinements. All five isolated browser scenarios and the final production TypeScript/Vite build passed. The existing dependency-annotation, mixed-import and bundle-size warnings remain. The exported development evaluation records 480/480 exemplar matches and 40/40 authored paraphrase matches, with its non-independent evaluation status explicitly recorded.

## TensorFlow local intent training

Implemented and trained on 10 November 2026 following the explicit TensorFlow request:

- Four genuine TensorFlow 2.20.0/Keras neural classifiers: CRM, PMS, Sales and HRMS, each with 20 intent classes and 120 authored commands. Each classifier uses normalized TF-IDF word/bigram inputs, Dense(64, ReLU), training-time Dropout(0.1), and Dense(20, Softmax). Adam performs actual gradient-based training for 220 epochs with recorded seeds. Slot text (quoted titles/messages), colon-delimited payloads and numeric record IDs are removed from intent features; actual slot values remain separately validated action inputs.
- Internal model validation uses 100 training and 20 validation commands per module (one validation example per intent) with a fixed corpus vocabulary. The final exported models are then refitted on all 120 commands per module. Every final network fits its 120 examples. Internal validation accuracy is CRM 65%, PMS 60%, Sales 55%, HRMS 55%; raw neural development-paraphrase accuracy is 29/40 (72.5%). These small-sample results do not establish general English understanding or production readiness.
- The assistant combines the neural scores with the existing exact-example, entity/filter and ambiguity checks. Neural choices need score ≥0.80, margin ≥0.20 and lexical support; explicit semantic constraints and native permission/action review remain authoritative. A softmax score is not a calibrated correctness probability. Missing, stale or malformed artifacts explicitly fall back to the existing local retrieval/rules interpreter, without invoking a cloud provider.
- The backend loads safe numeric portable weights exported from TensorFlow rather than importing TensorFlow into the ERP runtime. Every exported probability was compared with TensorFlow over all 480 examples: maximum absolute difference below 0.000001. All four `.keras` files were also reloaded and produced identical outputs. Artifacts validate corpus/feature versions, vocabulary, module labels, dimensions and finite numeric weights; inference never executes serialized model code. The model-inspection API and local command library show whether TensorFlow-trained models are active or fallback is in use.
- Training uses a separate environment pinned by `backend/requirements-local-nlp.txt`, preserving the existing API environment. The trainer is `backend/scripts/train_tensorflow_local_nlp.py`; it records Python, TensorFlow, Keras and NumPy versions, seeds, split metrics, raw prediction failures and export parity. Keras artifact handling follows the [official TensorFlow save/load documentation](https://www.tensorflow.org/tutorials/keras/save_and_load).

From the repository root, reproduce training with:

```powershell
backend/venv/Scripts/python.exe -m venv .local/tensorflow-venv
.local/tensorflow-venv/Scripts/python.exe -m pip install -r backend/requirements-local-nlp.txt
.local/tensorflow-venv/Scripts/python.exe backend/scripts/train_tensorflow_local_nlp.py
```

Outputs are in `.local/local-tensorflow-v1/`: `CRM.keras`, `PMS.keras`, `Sales.keras`, `HRMS.keras`, `bundle.json`, `evaluation.json`, combined `commands.json` and one 120-command JSON file per module. Local inference discovers this directory automatically. For deployment, copy the validated artifacts to a server-owned directory and set `LOCAL_NLP_MODEL_DIR` to that directory; the backend needs only `bundle.json`. No production deployment, neural training on customer data, external messaging, or cloud model call was performed. The existing separate browser-local PMS model was not retrained; the suite UI uses these newly trained server-local models through its existing API.

Final TensorFlow verification: 636 backend checks passed with `LOCAL_NLP_REQUIRE_MODEL=1`, including real trained-artifact inference on all 480 examples, native local workflows, stale/malformed-model fallback, slot validation and policy guards. The combined interpreter passes the 40 authored development paraphrases; raw-neural scoring remains separately reported as 29/40. Five browser scenarios and the production build passed. TensorFlow-to-portable maximum probability error is 0.0000002346473581, and all Keras reload comparisons match exactly. No live lead messages were sent.

## Server-local datasets, query review and training UI

The local training workbook is `backend/app/ai_operator/assets/nlp-training-template.xlsx`. Its Commands sheet contains 480 sample queries: 120 each for CRM, PMS, Sales and HRMS, covering all 80 currently supported module–intent pairs. Intents lists the accepted labels; Instructions explains the upload format. Columns are module, query, intent and split (train/validation/test). Add genuinely unseen validation/test examples; copies or normalized equivalents of training commands are rejected as held-out data.

Two pages are available at `/ai-agents/nlp-datasets` and `/ai-agents/nlp-training`. Upload validates Excel, previews sanitized rows and requires explicit privacy review and approval. The second page queues TensorFlow training, shows metrics and requires a separate activation action. Uploaded rows augment the existing base corpus. Model files, training snapshots, logs and numeric weights remain on the server/local filesystem; browser APIs return metadata and results only. Private model activation is scoped to company, branch and workspace. Configure LOCAL_NLP_TRAINING_PYTHON for the separate TensorFlow environment and LOCAL_NLP_TRAINING_DIR for private server storage; the default uses .local/tensorflow-venv and .local/nlp-training.

The ai_nlp_queries table captures sanitized text/voice queries and predictions, including provider failures, with replay-safe identity. Predictions are pending examples until an authorized reviewer supplies a valid label and explicitly approves privacy. Only approved curated examples are exported or used for training. Structured forms are excluded. Deletion leaves a replay tombstone and erases the training text. Query memory does not replace existing assistant run-history retention.

New migration pairs are generic 078/079 and PostgreSQL 095/096. They add query memory/datasets and extend queued-job idempotency for training. No production migrations or deployment were performed. Training jobs recheck source approval, revisions and authorization before training and activation. Cancellation and source deletion prevent publication. Uploaded validation/test examples are kept out of training; training accuracy is separately labeled and is not evidence of general-language accuracy.

Validation includes 32 focused backend tests, including a real server-side TensorFlow training/activation cycle, migration roundtrips, workbook parsing and scoped query review. The two-page Excel upload/review/training/activation browser flow passed, and the production frontend build passed.

Local storage override (10 November 2026): backend/.env points base models to C:/Indian Servers/ERPTrainedModel/base and future training runs/activation pointers to C:/Indian Servers/ERPTrainedModel/training. Existing authored artifacts were copied with SHA-256 verification; the original copies are retained. The standalone trainer now honors the configured base model path, while reviewed models require a separate output directory. Restart backend/worker processes after changing storage configuration.

## Platform-only training access

Training is now restricted to the independent platform identity realm. Customer training/query-review routes return 403 and the customer assistant no longer links to training pages. Platform owners can use nlp.train; the model_trainer role has only nlp.train. A central server-side account restriction denies this role other platform workflows even if a URL is entered manually. The trainer UI contains only upload/review/train/results and sign-out.

Local entry: http://localhost:5186/platform/nlp-training. The local saisatish trainer account is stored as a hashed-password platform administrator record, independent of customer users; no password is stored in source. Platform username login maps an unqualified identifier to its platform.local account. Existing email sign-in continues to work.

The platform-only local API can run without customer schema initialization: from backend, run venv/Scripts/python.exe -m uvicorn app.platform_owner.training_app:app --host 127.0.0.1 --port 1535. Point the frontend VITE_DEV_API_PROXY_TARGET to http://127.0.0.1:1535 and launch Vite on 5186. The full platform API also mounts these training endpoints. No customer database session is opened for platform workbook training.

Platform datasets/jobs reuse platform_records. The shared Excel validator, TensorFlow trainer, safe numeric inference/export validation and model storage are reused. Approved synthetic/anonymized workbooks train a platform-scoped model; successful runs need explicit activation, with restoration of the authored base model available. Models live under C:/Indian Servers/ERPTrainedModel/training/platform/runs. Source approval and trainer authorization are checked before training and activation. Existing customer query capture remains pending and is not automatically imported into platform training.

Verification: 60 focused backend tests passed, including actual TensorFlow training/activation, customer-superadmin exclusion, trainer-only permissions, username login, approval gating and existing platform regression tests. Live browser sign-in reached the training-only page and the authenticated metadata API; the page was visually inspected.

Owner account correction (local database only): the account is now saisatish@indianservers.com with role owner, all platform permissions and overview as its landing page. The previous trainer-only local identifier is no longer active for sign-in; old sessions were revoked. Platform sign-in requires a valid email again and remains case-insensitive. The local platform API on 1535 now mounts the complete platform router, so owner navigation and authorization work across the portal. Passwords remain hashed in the local database and are not recorded here. Live browser verification confirmed owner overview, full navigation and settings access using the updated account.

## Expanded local training and conversational actions

Generated platform-synthetic-3000-v1: exactly 1,000 distinct command strings for each of PMS, CRM and HRMS (3,000 total), with 50 paraphrases for each of the 20 existing intent classes in each module. The 120 original commands per module are retained. The source-controlled generator rejects cross-label normalized-feature conflicts and adds only feature-distinct new examples; some original examples remain feature-equivalent. These synthetic variations do not add business capabilities or establish broad conversational understanding. No customer queries or credentials were used.

A real TensorFlow 2.20.0 training run (300 epochs) completed as local platform run 212. The existing Sales model remains supported with its 120 examples. All three requested final classifiers fit their 1,000 commands; the internal 20-example validation per requested module scored 100%, but uses heavily templated synthetic data and is not an independent language benchmark. Raw neural performance on the existing authored development set is 28/40; the complete rules/neural interpreter remains 40/40. Maximum TensorFlow-to-portable error is 0.00000023870539866965856 and all Keras reload errors are zero. Run 212 was activated locally after verification.

The generated 3,000-row corpus is C:/Indian Servers/ERPTrainedModel/datasets/platform-synthetic-3000-v1/commands.json. Trained artifacts and evaluation.json are in C:/Indian Servers/ERPTrainedModel/training/platform/runs/212/model. Both the server inference runtime and local command library recognize the 1,000-command models. Platform workbook uploads/reviewed exports now support up to 4,000 rows. The existing 480-row downloadable starter workbook remains available.

Local action dialogue now retains validated slots between turns and asks one focused question at a time. Plain-text titles, numeric IDs, project selection, channels, subjects, bodies, leave types/dates/duration/reason, and reminder dates/times can be supplied through follow-ups. Revisions invalidate the previous pending approval; cancellation prevents the original draft from executing. Previously supplied fields survive later replies, and unsupported/unsafe instructions do not authorize actions. The UI shows the conversation chain and allows an explicit yes/approve/confirm response to approve the current exact plan through the existing native approval endpoint.

Connected actions reuse the canonical executor: CRM/PMS task creation and changes, milestones, CRM internal notes, HR helpdesk tickets, leave submission, self-reminder scheduling and lead email batches. Lead email previews now produce an executable reviewed action rather than a CRM page-opening handoff. Native recipient permissions, current consent, signed-preview binding and batch idempotency are rechecked at send time. Partial lead-source pages are never called all leads. Email requires a connected provider; WhatsApp/SMS delivery is not added by this change. Unsupported financial finalization, payroll/attendance and manager leave approval remain outside the local action catalog.

Reminder execution reuses native preview/grant creation after suite approval; it schedules a one-time reminder to the current user and explicitly displays its 24-hour expiry. Leave submission retains native validation and manager approval. Delivery receipts report per-status counts. Provider failures enter reconciliation and are not automatically resent. Internal preview tokens and request IDs are hidden from the action-review UI.

Validation: the broad 640-case assistant/local-model/reminder regression passed; a production frontend build passed. Focused native multi-turn tests exercised task creation/date revision, project selection, four-turn email preparation and simulated sending with opt-outs, cancellation, leave submission and active reminder creation. Browser checks cover lead preview/action review and typed confirmation without a second model command. No real lead messages were sent: delivery tests use an isolated stub provider. Only local training/account storage was changed; no production deployment was performed.

## Action model v2: expanded commands and trained dialogue acts

The active local release is platform run 214. It has 1,200 synthetic authored commands each for PMS, CRM and HRMS (3,600 total; 60 surface variants for each of 20 supported intent labels per module). Sales retains its existing 120 commands. The parameterized expanded_corpus.examples(60) generator preserves the original module examples and rejects cross-label feature conflicts. The corpus is stored in C:/Indian Servers/ERPTrainedModel/datasets/platform-action-v2/commands.json.

A separate genuine TensorFlow/Keras Dense dialogue-act classifier was trained for 350 epochs on 3,120 state-labelled replies (over 1,000 per requested module). Inputs include the module, pending action and requested field, so the same response can be interpreted in context. Classes are provide_value, clarify, confirm_action, cancel_action, new_request and unsafe_request. Its safe numeric export is dialogue.json; the original model is dialogue.keras. Runtime inference does not import TensorFlow and never runs in the browser. Classifier output cannot authorize execution. It supplements slot filling (including conjunctions inside a requested title/body); typed validation, module permissions, canonical APIs and explicit current-plan approval remain authoritative.

The dialogue development set contains 852 wording variants excluded from gradient training and vocabulary fitting, with no identical normalized input features across splits. Contexts are shared, and the authored development wording was inspected while improving the dataset: this is not an untouched general-language benchmark. Raw dialogue-act accuracy is 672/852 (78.87%), while training fit is 100%. Maximum portable probability difference is 0.00000032589437071184335, and Keras reload error is zero. These results do not establish a best-in-class model or general language competence.

There are 540 portable conversation examples: 180 one-shot requests, 180 multi-turn requests and 180 independent-chat scenarios across the three modules. The planning-only conversation benchmark passes all 540; it executes no business writes or deliveries. The combined interpreter also recognizes all 3,600 authored training commands and retains 40/40 on the pre-existing authored development set. Training recognition is seen-data fit, not a held-out accuracy claim. Testing exposed and corrected scheduling-vs-status, existing-task-vs-creation, follow-up-note-vs-task, and negative-assignee filter routing errors.

The UI now has New conversation to start a fresh request without inheriting slots, selected task IDs or a previous approval. Pending conversations remain independently accessible; fresh requests do not approve or cancel another chat's draft. Explicit confirmation wording still uses the reviewed native approval endpoint. Native integration tests interleave pending conversations and validate receipts, cancellation, opt-outs and at-most-once execution. Safety refusals cannot be overridden by the dialogue model.

Future platform training jobs automatically train both the intent and dialogue heads, run the synthetic conversation benchmark and verify artifacts before allowing activation. The local training page exposes separate dialogue and conversation metrics. Run 214 models and evaluation files are in C:/Indian Servers/ERPTrainedModel/training/platform/runs/214/model. No production deployment or real customer delivery was performed.

Validation: 631 broad checks passed before the final semantic refinements; the final 624-case intent/action regression passed after those fixes. Four platform training/activation checks passed, including real TensorFlow training of both heads. Three browser cases passed for lead action review, typed confirmation and independent New conversation behavior. The production frontend build passed with existing bundle/dependency warnings.

## Action model v3: conversation repair training

Run 216 retains 1,200 commands each for PMS, CRM and HRMS (3,600 total) and adds 144 distinct contextual repair scenarios. These cover clarification questions, ambiguous yes/no replies, title corrections, negated priorities, cancellation and dates supplied before a title. The supervised dialogue training set now contains 3,264 turns. The main classifiers and dialogue head were genuinely retrained on the server; no browser training or external model API was used.

The local policy now prevents yes/okay/help replies from becoming literal task titles, retains the pending field after clarification, replaces the corrected title/subject/body/reason, and resolves the replacement portion of a negated-value correction. A negated priority without a replacement asks for the new value instead of retaining the denied priority. Polite cancellation and curly-apostrophe clarification replies are recognized. HR ticket priority corrections are carried through to the canonical payload. Revisions invalidate previous approvals, and none of these controls lets model output authorize execution.

Three fixed-seed TensorFlow dialogue candidates were compared against the existing authored development set. Seed 7322 was selected: training fit 100%, development accuracy 667/852 (78.29%). This set is used for model selection and has been inspected during tuning, so it is not an unbiased test score. End-to-end planning correctness is separately checked: all 684 authored scenarios pass (180 single requests, 180 multi-turn, 180 independent conversations and 144 repairs), together with all 3,600 authored module commands and the pre-existing 40 development paraphrases. The planning benchmark performs no business writes. Native integration tests separately verify actual module effects after approval.

Artifacts are in C:/Indian Servers/ERPTrainedModel/training/platform/runs/216/model. The source corpus and repair scenarios are in C:/Indian Servers/ERPTrainedModel/datasets/platform-action-v3. Previous releases remain available for rollback. Future platform training runs include the repair examples, three-seed dialogue selection and the expanded benchmark.

Validation includes a 633-case assistant regression run, 35 candidate action/conversation checks, four real platform training/activation checks, and three browser cases covering typed approval, independent chats and ambiguous yes during clarification. Corrected titles and priorities were executed through the real CRM, PMS and HRMS APIs in isolated tests. No real customer messages were sent and no production deployment was performed.

## Action model v4: stronger reply encoding and unseen-wording evaluation

Local run 218 is the next active candidate/release. It retains 1,200 authored commands each for PMS, CRM and HRMS (3,600 total), plus the existing 120 Sales commands, and retrains the dialogue head on 3,264 state-labelled turns. The new local-action-dialogue-v2 feature contract combines explicit module/action/pending-field context with reply words, bigrams and character 3–5-grams. Vocabulary is fitted from training rows only and capped at 4,096 terms. Numeric inference applies the exact training weights, validates dimensions/finite values and supports existing v1 exports for rollback. Nothing trains or loads model weights in the browser.

Raw authored-development dialogue accuracy improves from 667/852 (78.29%) in run 216 to 758/852 (88.97%) in run 218. Model selection still uses this inspected development set, so it is not an unbiased test result. A separate frozen set of 120 wording probes was written outside the training corpus and model-selection code. First comparison on this set improves from 85/120 (70.83%) to 91/120 (75.83%). These are small synthetic sets, not production accuracy or evidence of a best-in-class model. The model cannot authorize execution; typed validation, native permissions and exact-plan approval remain mandatory.

New follow-up handling accepts explicit references such as choose the project with ID 12, the record is number 12 and leave type #12. A reply naming the wrong entity type is rejected, and ambiguous/multiple/negative IDs are not guessed. Word-based relative dates such as in two days, in one week and the day after tomorrow resolve against the selected timezone. Noon/midnight and first/second-half leave replies are supported; approximate reminder times still ask for an exact value. Negating a date asks for its replacement rather than retaining the denied date.

Both the UI and local command API recognize explicit start-a-new-conversation controls. A new conversation clears pending values and selected action sources without approving or cancelling another pending draft. The API ignores any supplied action plan on a conversation reset. Natural clarification cues can use the trained reply classifier to ask for details, never to execute an action.

Future platform retraining automatically retains the released 1,200-command authored baseline in each requested module, preventing a small new workbook from shrinking the model back to 120 examples. Company-scoped private training is not merged into this global baseline. The pipeline also records separate unseen-wording metrics after model selection. Reproduce a local authored release with backend/venv/Scripts/python.exe backend/scripts/train_authored_action_release.py --release <lowercase-release-name> --owner <local-platform-owner-email>; the helper refuses non-local databases.

Artifacts and reports: C:/Indian Servers/ERPTrainedModel/training/platform/runs/218/model. Source training data: C:/Indian Servers/ERPTrainedModel/datasets/platform-action-v4. Earlier releases remain available for rollback. All 684 authored planning scenarios, all 3,600 authored commands and the existing 40 development paraphrases pass. Native verification includes 676 regression checks, 35 focused language/control checks, four real training-retention checks and four browser scenarios. The production frontend build passed. No real customer messages or production deployment were performed.
