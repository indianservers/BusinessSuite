# PMS AI Assistant — implementation and verification

Baseline: main 2bd4778, with the preceding cross-module audit repairs retained. This feature is implemented locally and remains uncommitted. No deployment, push, production migration, live model request, customer communication or actual money transfer was performed.

## Integration and design

The floating launcher is mounted in AppLayout across PMS and the connected CRM/SRM screens. Its offset follows the navigation layout, with a full-screen mobile panel and safe-area spacing. The panel includes a welcome screen, suggestions, expandable layout, private conversation history/search/rename/removal, keyboard navigation, Enter/Shift+Enter, Escape/focus return, reduced-motion styles, editable action details and invoice line controls. Authorized Files and existing provider settings are linked directly.

The existing AI Operator remains the provider/configuration/security foundation. Provider keys stay encrypted on the backend, existing AI module policy and usage/rate limits apply, and provider API logs retain sanitized request/token telemetry. OpenAI assistant planning uses a single bounded Responses function call; Claude/Gemini use the existing structured adapters. The model proposes typed tool arguments, never arbitrary SQL, code, URLs or completed business actions. Provider output is validated before dispatch; invented tools are rejected. The existing sensitive-text redaction service is applied before model requests, stored prompts, and structured arguments. Provider I/O runs outside the tenant-wide business lock, with ownership/permissions and idempotency checked again before saving a proposal. No business context is sent to a model unless the provider is enabled and its existing data-sharing policy permits it.

Official source checked for the OpenAI boundary: https://developers.openai.com/api/docs/guides/function-calling . Provider behavior is verified with an external HTTP boundary mock; no live key/provider acceptance was available.

## Working workflows

The registry exposes 21 bounded capabilities: customer search; project search/summary; task search, overdue and own assignments; invoice search/prepare/issue/send; payment recording; project creation; task creation/assignment; document-title lookup; time summaries; custom-field definitions; invoice aging; customer invoiced-value/applied-cash summaries; collaborator lookup and assignment counts. Read tools always query current authorized records, with explicit bounded result limits. Financial summaries keep currencies separate and distinguish invoiced value from applied cash and recognized accounting revenue. CSV export quotes cells and protects against spreadsheet formula injection.

Every mutation is a proposal. The authenticated owner must approve its server-generated hash within 15 minutes. Tenant, workspace/project access, current action permission, input validation and financial state are checked again. Cancellation of a proposal creates no business record. Existing issued documents and receipts continue to use normal finance reversal flows.

Invoice workflow:

1. Type a natural-language request on a project, or use Create an Invoice and action details. Without a configured model, the panel explicitly identifies guided mode. Guided parsing supports bounded invoice amounts/percentages/due days and discovery, rather than pretending to be a general language model.
2. Choose from matching shared customers/projects. Similar names and spelling candidates are never silently selected. Page customer/project IDs and stored conversation references are reauthorized on the server.
3. Review the calculated proposal. Percentage billing requires a linked sales order. Previous invoices and reserved drafts reduce remaining value. Existing issued/cancelled reservations are preserved for finance review. Tax comes from explicit linked order tax amounts or an explicit user-entered verified amount; GST/VAT rates are never guessed. A model cannot supply independent tax/line guesses. Mixed-currency existing billing is refused.
4. Edit quantities, prices, discounts, tax amounts and dates, then prepare a fresh proposal. Confirm & create invokes the authoritative SRM project-invoice service. Invoice creation, dates, approval result and assistant audit commit together. Project/task operations also use the existing transaction-aware operation functions. Business request keys are namespaced to the assistant action, preventing collisions with unrelated caller UUIDs.
5. The returned persisted invoice can be opened in SRM and downloaded as PDF. Issuing and sending each require a separate confirmation. Sending uses the existing durable delivery-attempt service and reports its actual state. Recording cash likewise requires its own approved proposal and uses the existing atomic SRM receipt/allocation service, with idempotent retry.
6. Normal PMS billing, SRM invoice and customer-history queries are invalidated after actions. Prior saved-invoice cards refresh to the returned authoritative state rather than showing fabricated success.

Project proposals support a title, budget, dates and optional canonical customer/seller/currency linkage. Task actions create one task or assign one verified task to an active project collaborator. Broader task-plan operations remain available in the existing AI Operator.

## Persistence and migrations

New tables: pms_assistant_conversations and pms_assistant_messages. They store private ownership/tenant/workspace, bounded commands, typed arguments, action proposals, expiry/hash, result references and timestamps. They do not create a second customer/project/invoice ledger. Historical read cards are rebuilt or reauthorized when resumed. Removing financial permission or changing tenant prevents a stored conversation from becoming an access bypass.

Both maintained Alembic trees add revision 007 after commercial revision 006: 20261024_007 and pg_20261024_007. Upgrades are additive and check-first. The PostgreSQL schema manifest includes both tables. Downgrade preserves action evidence rather than deleting financial references. Both upgrade functions were replayed twice on a representative SQLite schema. Production and live PostgreSQL migrations were not run. Back up the database, apply the correct configured migration tree, then roll out the application. Do not run both trees against one database.

Conversations are removed from normal history through soft deletion; business actions and audit evidence remain. A retention/purge administration job is not implemented in this change.

## Configuration

Grant the existing ai_assistant permission (or the existing AI/settings administrator access), enable AI/PMS through the existing module/security controls, and retain the underlying action permissions: project/task management, invoice creation, finance approval and collection creation are separate. AI access grants no extra business permission.

Configure provider/model, encrypted key, data-sharing consent and maximum output tokens in /pms/settings/ai/openai (or Gemini/Claude). Existing provider timeout behavior and sanitized API usage analytics are reused. Without configuration, guided mode is usable and provider selection returns an actionable unavailable state. No key is put in a frontend bundle or fixture artifact. The panel streams real validation/result/error events over authenticated SSE; it does not simulate token-by-token typing. Streaming owns its database session because this FastAPI version can close dependencies before response iteration.

## Verification evidence

- **428 backend tests passed** in the selected PMS/CRM/SRM/FAM/Communication/Business OS/AI Operator/commercial/audit/file/notification/migration configuration regression suite (114.09 seconds). Warnings are existing SQLAlchemy/Pydantic/deprecation and isolated audit-runtime notices; no failing assertions were suppressed.
- Assistant tests include exact/partial/typo and ambiguous customer discovery, natural invoice requests, correct project/customer pairing, configured percentage/tax calculations and prior billing, explicit creation approval, normal SRM visibility, PDF validity, request-key edit conflicts/replay, stale/expired proposals, issue/send approval, payment recording, current permission/tenant revocation, project/task persistence, project commercial links/budgets/dates, migration replay, provider function calling, rejected hallucinated tools and transaction participation/rollback.
- A final focused assistant suite passed all 22 tests after streaming transaction ownership, secret-redaction, and currency-multiplier checks; a 37-test assistant/AI Operator follow-up also passed.
- Frontend TypeScript/Vite production build passed.
- Two Playwright tests passed against the actual loopback API and application components, without mocked commercial routes: the full CRM→SRM→PMS→invoice→sandbox-send→full-payment flow, and assistant preview→explicit approval→real SRM invoice→PDF→responsive/keyboard checks. They verify that no invoice exists before approval and that exactly one new normal invoice exists afterwards. Console page errors remain empty in those flows.
- Screenshots: qa/connected-commercial-2026-10-24/assistant-invoice-desktop.png and assistant-mobile.png. The loopback QA harness uses its own synthetic database and forced test delivery. Generated HTML is removed after testing; session-bearing traces are disabled.

## Honest limits and pending work

This delivers the mandatory assistant-to-authoritative-invoice workflow and the bounded tools above; it is not full enterprise feature parity with every item in the requested roadmap. Capability status remains Partial.

Still pending: customer create/update tools, quotation/estimate creation/conversion tools, expense writes, general custom-field writes, reminder/workflow mutation tools, arbitrary multi-step orchestration/compensation, rich document/file-content summarization, in-assistant uploads, general Markdown/table prose generation, microphone input, provider token-level streaming, configurable temperature/custom OpenAI-compatible endpoints, per-workspace assistant-specific quotas, and retention administration. Invoice notes and billing-address editing remain in the normal business-record workflow rather than assistant-specific fields. Existing normal screens/services remain available; no unsupported action is presented as completed. Collaborator search uses authorized business email; general name-to-person fuzzy matching is not claimed. Assignment counts are not availability predictions.

No live PostgreSQL, production provider acceptance or multi-process load/failure testing was performed. Guided parsing is intentionally narrower than configured model planning. Provider retries do not execute business mutations automatically. External sending and payment recording retain the underlying services' durable/idempotent behavior. Existing source limitations (expense billing, three-decimal currencies, accounting-company selection and finance-reviewed reversal/source release) are unchanged. The assistant cannot establish tax treatment when configuration is absent and cannot undo issued accounting records by deleting history.
