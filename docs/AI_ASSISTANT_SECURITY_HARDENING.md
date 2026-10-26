# AI Assistant security hardening

Implemented 26 October 2026 in the existing Business Suite. This report describes tested application boundaries; it is not a claim of immunity from every future prompt injection or a production security certification.

## Architecture and privilege boundaries audited

- `app.ai_agents`: OpenAI chat orchestration, tool definitions/registry/builder/executor, CRM/PMS/HRMS/cross-module adapters, conversations, action approvals, audit and usage services.
- `app.ai_operator`: cloud providers (OpenAI, Claude, Gemini), PMS task/setup planning, database workers, checkpoints, browser TFJS proposals, local brain sessions, workbench memory/playbooks, cross-module suite execution, invoicing assistant.
- `app.apps.ai_copilot`: older record summaries, scores and draft recommendations. Its external connector remains unimplemented and fails explicitly; its deterministic mock remains an explicit test provider.
- `app.access`, authentication/session dependencies, shared workflow/outbox, approval and document services: reused for actual identity, company, managed/native grants, record scopes and downstream authorization.
- Browser-local models produce proposals only. Every execution remains subject to backend schemas, scope, approval and business rules.
- No end-user SQL, shell, arbitrary file, migration, backup, infrastructure or generic internal endpoint execution capability is approved. No vector database or production PDF/email/web retrieval pipeline was found in these AI entry points. Existing PMS document search and policy/resume readers remain scoped reads.

The code-owned catalogue contains 44 legacy tools, 33 suite capabilities, 21 assistant tools and 12 approval actions. These are different layers, not 110 independent permissions. Runtime registrations cannot automatically become approved capabilities. Each legacy tool maps to a native permission; suite entries pin module, method, route and native permission alternatives; assistant tools use fixed native service branches and permission checks.

## Implemented authorization and execution controls

`backend/app/ai_agents/security.py` is the mandatory backend boundary. `security_catalog.py` contains reviewed capabilities. The boundary derives the actor from validated authentication, the company from the selected authorized company, and the session from the authenticated server session. Model content supplies none of this authority.

1. AI HTTP paths require an actual session. Sessionless access tokens do not authorize AI execution.
2. Mandatory native/managed module grants and business permissions apply to every approved tool. Domain handlers still validate record access, assignees and financial state. Super Admin cannot use AI to bypass permanent prohibitions or confirm someone else's AI action.
3. Legacy adapter reads/writes install native record scopes even for legacy accounts and Super Admin, with an explicit company. Own-record/company tests exercise real CRM records.
4. Tool arguments reject unknown top-level fields, authority/internal keys at nested levels, incorrect primitive types, nonfinite JSON, excessive nesting, collections and text. Native schemas continue checking business-specific arguments.
5. Suite API delegation retains the initiating session and signs the company, HTTP method, exact path and arguments. The existing HTTP middleware verifies the actual body/query digest; canonical API authentication and record checks still execute. No generic model-selected URL is exposed.
6. Approval seals bind actor, company, initiating session, policy/permission fingerprint, exact operation, nonce and issue time. Confirmations expire after 15 minutes. Existing locked approval state and idempotent receipts prevent duplicate effects. Editing signed arguments or changing rights invalidates confirmation.
7. Queued workers recheck the initiating session, current rights and exact signed approval. Checkpoint payloads must match the approved plan. Interrupted writes with unknown outcomes require reconciliation rather than blind retry.
8. Tool-call limits, provider timeouts, bounded output tokens/responses, bounded disclosures, execution checkpoints, retry ceilings and existing lease/queue controls constrain chains. Time limits are checked between local operations; they do not forcibly kill a database statement already in progress.
9. AI-origin outbox events retain a signed origin. Shared workflows cannot borrow another execution identity, fan out additional mutations or send unconfirmed external communications. Human-started workflows retain their existing authorization behavior.

## Permanently unavailable through AI

Workspace/company reset and deletion; permanent/bulk deletion; role/permission/security changes; audit/backup/storage deletion; database/schema/migration execution; shell/repository/infrastructure changes; self-approval and standing administrative consent.

PMS dependency/checklist removal, undo, event-rule administration and generic leave approvals are excluded from the AI execution catalogue. Their human interfaces are preserved. A forged registration or local/browser plan cannot re-enable them.

The legacy copilot used to report certain actions as executed without a real business write. Those write placeholders now return an explicit unavailable response. Draft confirmations always say `executed: false` and are sealed to their real initiator and context.

## Prompt injection, data minimization, history and memory

Prompt scanners and untrusted-content markers are additional signals, never the permission boundary. Tests deliberately model hostile instructions in CRM/PDF/email/web/tool/memory text and then propose forbidden actions directly to the executor. These tests do not claim a live PDF parser, mail ingestion connector or model followed a particular prompt.

Prior tool/assistant text is not promoted into authoritative instructions. Fresh authorized reads supply source context. Passwords, API keys, credentials, tokens and sensitive payroll/personal identifiers are excluded or redacted. Large results become valid bounded JSON with a narrowing message, rather than leaking an unbounded result.

Conversation/message queries are actor/company/fingerprint restricted, including administrator queries. Run/proposal histories, brain sessions and model memory recheck current authorization before reuse. Handoff notes carry their own company/context seal; creators and explicit recipients must retain module/source access. Freeform notes without a recheckable source stay private, and legacy unsealed notes are quarantined. Feedback lists follow the current conversation visibility. Record ACL changes invalidate cached context conservatively via a company ACL epoch; relevant ORM bulk changes also invalidate it. Old unsealed conversations/approvals are retained but quarantined, not backfilled with invented authority. A rights change can require starting a fresh conversation even when only part of its data was affected.

No vector index was added. A future RAG adapter must enforce current source permissions and tenant metadata before model disclosure; the absence of a production vector pipeline is not evidence that a future one is secure. Direct database maintenance/imports outside authenticated ORM flows must explicitly invalidate affected cached access context.

## Audit and administration

Master Suite → AI Management → AI Security is available at `/admin/control/ai-security` to authorized administrators. It displays reviewed tools, permission mappings, permanently unavailable capabilities, policy version, configuration review time, bounded execution limits and paginated company-scoped audit decisions. It permits disabling reviewed tools and adjusting bounded limits. Password step-up, reason, optimistic version checking and the existing admin audit protect configuration changes. The mandatory baseline has no disable switch.

The existing assistant context panel shows actual user, selected company, enabled modules and permission-bound write mode. Existing action cards continue to display proposals and backend results.

AI audit records contain allowlisted metadata, actor/company/session/correlation and outcome. They exclude raw prompts, credentials, tool arguments and result bodies. Unknown tool labels are hashed. Historical log payloads are minimized at read time without rewriting original evidence. HTTP audit persists sanitized AI decisions even when business transactions roll back, and records rejected AI HTTP requests that failed before tool dispatch. PostgreSQL/SQLite migration triggers and ORM hooks reject updates/deletions of AI audit rows. A privileged database owner can alter/drop database protections; AI has no database administration capability.

## Defects found and repaired

Unknown arguments accepted by legacy tools; inferred identity fields; unscoped legacy/superuser adapter reads; tenantless history/settings; cross-user AI approval execution; stale or editable approvals; missing selected-company headers in delegated calls; overbroad provider credential fallback; unsafe cached histories/memory; dynamic tool trust; destructive PMS AI paths; workflow service-account borrowing/fan-out; raw audit payloads; missing audit after rollback; cross-user handoff/feedback visibility; a secret-redaction character-class defect; and false successful execution claims.

Credential resolution now keeps user-private credentials private when there is no authoritative company/workspace binding. Shared credentials do not replace the initiating user's execution authority. Live keys are never returned to the model.

## Verification and CI

Evidence is under `docs/qa/suite-access/ai-security-*.log`. Verified results (overlapping suites, not additive):

- PostgreSQL broad regression after handoff changes: **277 passed** (`ai-security-complete-postgres.log`).
- PostgreSQL final adversarial/privacy boundary run: **92 passed**, including database audit immutability (`ai-security-complete-boundary.log`). The separate workflow boundary suite also passes in the broad run.
- SQLite final boundary run: **83 passed, 1 PostgreSQL-only trigger check skipped** (`ai-security-boundary-final.log`).
- SQLite operator/assistant/workflow regression: **148 passed, 1 PostgreSQL-only check skipped** (`ai-security-final-focused.log`).
- Final denial/model-result audit checks: **5 passed** (`ai-security-denial-audit.log`); PostgreSQL denial/audit immutability checks: **6 passed** (`ai-security-final-audit-postgres.log`).
- Final handoff/model-output/secret-redaction privacy checks: **8 passed** (`ai-security-final-privacy.log`).
- Real browser: **1 passed**, including persisted policy changes and desktop/mobile screenshots (`ai-security-browser.log`). An asynchronous page-load race discovered during retesting was repaired; stale responses no longer overwrite a newer policy/draft.
- Frontend TypeScript and production Vite build: **passed** (`ai-security-build.log`). Existing dependency annotation/deprecation warnings remain; they are not silently treated as security certification.

Earlier failing runs are diagnostic history and were superseded by the passing runs above. Most logs are local ignored QA outputs; `ai-security-verification.json` records the portable evidence summary.

- `test_ai_zero_trust.py`: prohibited capabilities even for Super Admin; authority injection; mutated registrations; real own/company source reads; confirmation tamper/expiry/revocation; hostile source content; minimized and immutable audit; stale history/memory; missing sessions; limits; exact delegated arguments; queued approval tampering; read-only CRM, Intern and Finance boundaries; restricted HRMS reads.
- `test_ai_workflow_boundary.py`: no service-identity borrowing or unconfirmed create/update/assignment fan-out.
- Existing operator/worker/brain/assistant suites: actual create/update/checklist/comment/assignment flows, replay protection, stale previews, queued permission withdrawal, rollback, invoice draft/issue/send/payment confirmations and PDF generation. Provider responses are controlled test inputs; business effects use real application handlers and disposable database records.
- Existing copilot tests: authorized summaries, lead scores, drafts, reports and module RBAC. Mock-provider tests verify application behavior, not live provider security.
- PostgreSQL runs exercise the full migration chain and SQL audit immutability. SQLite explicitly skips the PostgreSQL-trigger-specific test; the PostgreSQL run must pass it.
- Playwright uses real login and FastAPI responses through a disposable database bridge. It verifies the central page, exact policy review/password verification, persisted limits/tool disabling, reload and desktop/mobile layout.
- `.github/workflows/security-regressions.yml` includes mandatory AI and workflow regressions on pushes/PRs. The existing PostgreSQL deployment-readiness workflow runs the full backend suite and frontend build. CI failures fail their jobs; repository branch protection/deployment settings must separately require these checks.

## Remaining risks and unverified controls

- Live provider/model behavior, external email/webhook delivery, production secrets/infra permissions and production deployment were not exercised. They are not used as authorization evidence.
- The independently deployed inventory Flask application requires its own verified boundary before exposing additional AI capabilities. This patch does not certify that separate application.
- A full enterprise penetration test, sustained concurrent permission-revocation stress test and infrastructure/DB-account least-privilege audit remain outside this local verification. Revocation between preview/queue/execute is covered by application regressions.
- Existing platform-wide issues noted in the Phase 3 report, including public intake/communication boundaries and external integrations, remain separate work. AI hardening does not certify the whole Business Suite as production-ready.
- Legacy copilot external connectors were already unimplemented; unsupported write placeholders remain deliberately unavailable. New tools require a reviewed catalogue entry and tests before exposure.
- Deployment must apply revision 027 on the intended environment. Only guarded disposable test databases were recreated/migrated here; application/production databases and existing business workspaces were not migrated or reset.
