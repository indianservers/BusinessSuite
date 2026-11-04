# WhatsApp Communication Hub

The hub reuses the existing WhatsApp sender, encrypted credentials, durable message reservations, webhook verification, canonical CRM records, and shared collaboration services. No credentials, message identifiers, database tables, migrations, or duplicate message stores were introduced.

## Completed experience

- The default team inbox combines chronological messages, delivery evidence, unread queues, person/deal linkage, employee ownership and handover, resolved status, personal snoozing, saved views, and responsive contact drawers.
- Inbox, Templates, Campaigns, Analytics and Settings share one workspace. Legacy received/sent/template/profile URLs remain registered. Existing email, reminders, forms and consent features remain available.
- The approved-template picker uses actual Meta structures and the existing variable review, consent, service-window and send-reconciliation flow.
- Rich media supports image/sticker previews, audio/video playback controls, PDF previews and document downloads. Attachments are loaded on demand through an authenticated endpoint. An interrupted download can be retried without sending a message.
- A file can be attached within an open customer-service window. Image uploads are capped at 5 MB; documents/audio/video at 16 MB; stickers at 0.5 MB. The existing durable send path handles text captions, attachment-only sends, request idempotency and uncertain provider outcomes. Audio and stickers cannot have captions. Meta validates supported codecs.
- Inline context shows authorized linked deals, quotations and invoice totals/outstanding balances. Relationships use explicit canonical person, stakeholder, deal and customer IDs, never fuzzy phone/name matching. Each collection uses its source domain's existing visibility and finance access checks. Lists show up to 50 records and identify truncation.
- CRM follow-ups use the existing shared editor and `/crm/growth` service. Users can schedule, reschedule, assign, set priority/reminders/products, record outcomes and complete follow-ups from the chat. These are canonical CRM activities with the existing timeline/reminder behavior; personal snoozes remain separate. Context refreshes periodically and after follow-up edits.
- Dedicated WhatsApp analytics aggregates the complete authorized contact set in bounded batches, rather than reusing the page-limited cross-channel summary. It includes active/new/unread conversations, received/outgoing/sent/delivered/read/failed/pending messages, pending CRM follow-ups, recorded first-response duration, daily activity, current employee workload, template performance and campaign attribution. Date, authorized owner, and authorized linked-record team filters are supported. Campaign reporting counts existing campaign automation delivery links to canonical messages and excludes transactional automations.

## Original requirement completion

- Quoted replies use the selected canonical message's confirmed provider identifier as the native Meta `context.message_id`. Targets must belong to the same organization, contact, sender connection and authorized branch. Incoming webhook context is retained beside existing media/template payloads; the transcript displays quote previews and can jump to loaded originals. Quote selection can be cancelled and retained in drafts. Quoted free-form replies continue to require the existing service window; approved-template sends do not carry an invalid free-form quote. The original durable request ID/digest/reconciliation flow remains authoritative.
- Product/service, exact tag and priority filters now operate on the inbox endpoint before pagination. Product selection reuses the CRM audience projection and its authorized catalogue/relationship queries, including direct product links, deal catalogue lines, stakeholder contacts and converted lead relationships. Multiple offerings match any selection. Tags match complete comma-separated CRM tags case-insensitively. Priority uses the next pending CRM activity, falling back to record priority; native Critical priority is supported. Business filters narrow to WhatsApp conversations instead of reintroducing unmatched email-only rows. Saved inbox views retain these filters.
- Chat now opens the existing deal capture, quotation quick-action form, manual invoice composer and full PMS Task Studio inside the workspace. Canonical person/customer/deal IDs are prefilled and domain permissions remain enforced by the original creation endpoints. Deal and task drafts are isolated by chat/user/organization/branch scope. Task Studio retains its project, assignment, custom-field, attachment and task-key retry logic; the existing idempotent task-to-contact/lead link service is called before completing the chat action. A failed link can be retried against the already created task. Quotation numbers and invoice request IDs preserve their existing uniqueness/idempotency rules. Busy-state guards prevent duplicate submissions and premature closing of invoice/task creation. Original page behavior remains the default outside chat.

## Backend changes and reuse

- `backend/app/services/whatsapp_media.py`: a small adapter using the existing connection and server credentials for Meta multipart uploads and bounded authenticated downloads. Encrypted upload receipts are bound to actor, organization, conversation, connection and expiry. Downloads accept only a media ID recorded on an authorized message, pin provider hosts, disable redirects, check media types/size, and return private no-store responses. Tokens are never exposed in a media URL.
- `backend/app/services/whatsapp_workspace.py`: retains the existing send reservation, consent/window enforcement, receipts and inbound deduplication. Adds media payload validation and stores inbound/outbound attachment metadata in the existing message JSON field as a media envelope. Approved-template JSON remains unchanged for template messages. Text/template request digests retain their existing format.
- `backend/app/services/whatsapp.py`: adds an optional media argument to the existing provider; existing text/template calls keep their behavior.
- `backend/app/services/whatsapp_hub.py`: read-only context and reporting adapters. Reuses CRM visibility queries, CRM pending activities, SRM invoice visibility/customer authorization, existing workflow/reading state and canonical campaign delivery links.
- `backend/app/api/v1/whatsapp_cloud.py`: adds authenticated media upload/download, aggregate context and WhatsApp-only analytics endpoints to the existing router. Extends existing send input with an optional encrypted media receipt.
- `backend/app/apps/communication/engagement_api.py`: includes recorded media metadata in the existing conversation response.

- `backend/app/services/whatsapp_replies.py`: canonical quote target validation, provider reference snapshots and inbound quote resolution. No new storage table.
- `backend/app/services/whatsapp_inbox_filters.py`: existing CRM priority/tag projections and shared product/service audience filtering.
- The existing send schema gains an optional numeric `replyTo`; the provider gains optional reply context. Existing unquoted text/template/media calls and digests retain their prior behavior.

## Frontend changes and reuse

- `frontend/src/apps/communication/WhatsAppCloudPanel.tsx`: hosts the dedicated analytics component.
- `frontend/src/apps/communication/whatsapp/MessageMedia.tsx`: authenticated blob previews/downloads, abort handling, URL cleanup, actionable errors and retry.
- `frontend/src/apps/communication/whatsapp/BusinessContext.tsx`: inline canonical business records and shared follow-up editor.
- `frontend/src/apps/communication/whatsapp/Analytics.tsx`: WhatsApp-only metrics, daily chart, methodology, date and owner/team filters.
- `frontend/src/apps/communication/whatsapp/Composer.tsx`: upload controls, attachment draft retention, caption checks, and a synchronous send guard around the existing durable request flow.
- `frontend/src/apps/communication/whatsapp/Inbox.tsx`, `types.ts`, `whatsapp.css`, and `center/EngagementInbox.tsx`: shared media/context integration for both the team inbox and older paginated WhatsApp history.
- `frontend/src/apps/crm/FollowUpWorkspace.tsx`: exports the existing editor and permits WhatsApp as its initial channel. The original CRM page retains its existing default.

- `frontend/src/apps/communication/whatsapp/ChatCreateActions.tsx`: lazy shared forms and canonical PMS link completion.
- `frontend/src/apps/communication/whatsapp/InboxFilters.tsx` and `QuotedMessage.tsx`: business filters, quote previews and transcript jumps.
- `frontend/src/apps/crm/CRMWorkspacePage.tsx`: optional prefill/draft scope for the shared deal dialog and a submission guard.
- `frontend/src/apps/crm/CRMRecordDetailPage.tsx`: optional initial canonical relationships for quotation creation, accessible dialog labeling and a submission guard.
- `frontend/src/apps/srm/pages/SRMWorkspacePage.tsx`: exports the existing invoice composer with optional prefilled customer/person and busy reporting. Chat shows all invoice inputs directly; standalone behavior remains unchanged.
- `frontend/src/apps/project-management/pages/TaskStudioPage.tsx`: optional embedded mode, scoped draft, callbacks and busy reporting. Chat creates a shared task, completes its canonical CRM link, and stays in the conversation; ordinary PMS routes still navigate as before.

## Verification

- TypeScript compilation passed.
- WhatsApp cloud/workspace, shared team-inbox, hub and remaining-requirement tests, PMS Task Studio and task-record-link regressions: 69 passed. Coverage includes canonical links, CRM follow-up schedule/complete, read-only finance restrictions, branch/tenant isolation, media upload authorization/content/size checks, provider payload compatibility, webhook deduplication, durable media send retries, private downloads, unsafe-host rejection, complete analytics beyond an inbox page, follow-up deduplication, owner/team filters and campaign message attribution.
- An additional targeted regression verifies that transactional automation deliveries are excluded from campaign performance.
- `qa/whatsapp_hub_browser.cjs`: existing default inbox, templates/variables, legacy numeric conversation links, tablet/mobile navigation and horizontal-overflow checks passed.
- `qa/whatsapp_hub_extended_browser.cjs`: mocked image/audio/video/PDF previews, authenticated downloads and interrupted-download retry, inline sales/finance records, shared follow-up scheduling/completion, media send payload, analytics owner/team filters, invalid date handling and mobile overflow checks passed.
- `backend/tests/test_whatsapp_hub_remaining.py`: native provider quote payloads, quote idempotency, cross-conversation/unsent-target rejection, closed-window enforcement, inbound media quotes/deduplication, whole-tag matching beyond the first page, product/service relationships, follow-up/native Critical priority, branch isolation, canonical deal/quote/invoice creation, creation permissions, and PMS creation/retry/link visibility.
- `qa/whatsapp_hub_final_browser.cjs`: quoted reply selection/payload/transcript, product/tag/priority controls, actual shared deal/quote/invoice/PMS forms, canonical task links, remaining in chat, mobile page and dialog-content overflow checks. All APIs mocked.
- Additional captures: `docs/qa/whatsapp-hub-final-desktop.png`, `whatsapp-hub-create-mobile.png`.
- Screenshots: `docs/qa/whatsapp-hub-rich-context.png`, `whatsapp-hub-analytics.png`, `whatsapp-hub-analytics-mobile.png` and the existing inbox desktop/mobile captures.
- Tests use synthetic records and mocked transports. No live WhatsApp message, campaign or external provider verification was performed.

## Data and deployment limits

- Earlier inbound media recorded only as placeholders cannot be reconstructed without their original provider media IDs. New media webhooks retain those IDs; older unavailable attachments remain placeholders.
- Resolution duration now uses explicit previous/new status transitions in the existing append-only branch audit. Historical rows without transition evidence remain excluded. Response timing measures recorded inbound-to-confirmed-reply time within the selected date range; it does not invent missing samples.
- Message metrics use creation timestamps within the chosen range and current confirmed delivery states. Ownership, unread state and pending CRM activities are current snapshots for conversations active in that range. Sent includes delivered/read; delivered includes read. Chart days use UTC; date controls use the device timezone.
- Existing paginated history remains available beyond the team transcript's recent-message limit. Media remains subject to Meta retention and the hosting platform's request/response-size limits. No independent file archive or transcoding service was introduced.
- Creation requires authorized canonical records: a person (or linked deal) for sales documents, a customer company for invoices, and a writable PMS project for tasks. Unconverted leads can link directly to PMS tasks; sales documents require linking a person or completing the existing CRM conversion flow. No automatic contact creation or silent lead conversion was added.

## Provider references

Quoted replies follow [Meta's native reply example](https://www.postman.com/meta/whatsapp-business-platform/request/73yi2uj/send-reply-to-text-message) and [media reply example](https://www.postman.com/meta/whatsapp-business-platform/request/dv878df/send-reply-to-image-message-by-id). The media adapter follows [Meta's official media upload example](https://www.postman.com/meta/whatsapp-business-platform/request/q3rsuse/upload-image), [media URL retrieval](https://www.postman.com/meta/whatsapp-business-platform/request/ptjyi84/retrieve-media-url), and [media download flow](https://www.postman.com/meta/whatsapp-business-platform/request/zsq66eh/download-media). The application's upload caps are intentionally conservative.


## Original brief audit — 2026-11-04

The audit found and fixed functional gaps beyond the earlier UI checks:

- Follow-ups now queries pending canonical CRM activities, separately from personal snooze. Pending is a real workflow status beside Open and Resolved. Workflow audit entries retain previous state and handover text; the inspector shows authorized ownership/status history.
- WhatsApp queues, owner/team, contact classification, latest-message status and activity dates are applied before pagination. Search includes recorded message bodies, canonical company/customer details and authorized offerings. Literal wildcard characters are escaped. A timestamp/ID cursor orders by latest activity, preserving recently active older contacts. The original generic cross-channel API defaults and legacy ID pagination remain compatible.
- Chat context now includes canonical internal notes, lifecycle/tags, products/services and recent CRM activity. Notes use the existing CRM notes API. Tags/native record priorities use the original record update API. Product associations open the existing shared catalog editor. Follow-up priority stays in the shared follow-up editor for records without native priority.
- Unknown customers can use the existing matching review directly inside chat. Creation splits the international WhatsApp number into the existing CRM national-number/calling-code fields, rechecks exact matches, guards duplicate submissions and retains the newly created canonical ID if linking fails, so retrying does not create another person.
- Composer now includes emoji insertion and additional authorized company/deal/quotation/invoice variable mappings. Conclusive client rejection plus a no-record reconciliation unlocks the preserved draft; network/server uncertainty stays locked with its durable request ID. New-message and attachment controls wait until the previous outcome refresh finishes. Media uploads explicitly use the documented application size allowance instead of the generic smaller upload default.
- Interactive list/button replies, locations and shared-contact names produce useful inbound text instead of generic placeholders. Existing message IDs and webhook deduplication remain authoritative.
- Template previews show actual header/body/footer/buttons, library sync time and Meta management access. WhatsApp campaigns use an approved-template selector, editable variable values, explicit audience selection with canonical lead/customer, exact-tag and product/service filters, rendered template audience previews, scoped caches and a version guard against launching content changed after preview. Existing scheduling, consent, bulk approval, delivery cancellation and version deduplication remain in their original services.
- Resolution metrics use proven resolve transitions, measured from the last recorded reopen or first inbound message. Legacy transitions without prior-state evidence are excluded. Other metrics retain existing receipt and authorization rules.
- Real-API browser testing exposed a shared follow-up optimistic-version timezone mismatch. The pending API now emits UTC timestamps and comparison normalizes legacy naive UTC values. Genuine stale versions are still rejected.
- The shared catalog price-list query argument now has a plain `None` Python default with annotated HTTP validation. This fixes the existing CRM product/service adapters used to load the shared deal form, while retaining positive price-list ID validation.
- Chat refresh invalidates the selected conversation, current inbox and business context, avoiding repeated template/account reloads after every send or workflow action.

### Acceptance evidence

1. One workspace: inbox, templates, campaigns, analytics, settings and message composer are available from the hub.
2. Read/reply: combined chronological history, native quoted replies, media, drafts, recovery and copy/emoji controls.
3. Approved templates: real connected-account definitions, variables, previews and existing API send path.
4. CRM beside chat: authorized profile, notes, activity, offerings, sales documents, balances and shared creation forms.
5. Unknown identities: exact-match review, existing-record link and guarded create/link with retained retry ID.
6. Delivery: recorded provider IDs, signed webhook receipts, monotonic states and delivery evidence in conversation.
7. Follow-ups: shared editor for schedule/reschedule, assignment, reminder, priority, outcome and completion; canonical pending queue.
8. Campaigns/templates: original automation/delivery services, purpose consent, audience preview, scheduling, deduplication, stale-preview rejection, cancellation and history.
9. Responsive layout: existing mobile navigation, inspector and dialog overflow browser checks; shared catalog management uses the full-size dialog.
10. Integration preservation: original credentials, verification, send reservation, provider identifiers, receipt processing and tenant/branch permissions are reused. No credentials regenerated, migrations introduced, deployment performed or live delivery attempted.

### Reproducible verification

The regular backend regressions cover integration, hub behavior, CRM follow-ups, campaign controls, sales/finance creation, PMS and authorization. `tests/test_whatsapp_hub_audit.py` adds original-brief regressions for global message search, activity pagination beyond 200 contacts, queue semantics, canonical notes, interactive inbound content, resolution evidence, campaign version guards and follow-up version round trips.

`tests/test_whatsapp_hub_browser_e2e.py` starts a loopback bridge to the actual isolated test application and runs `qa/whatsapp_hub_api_browser.cjs` against the actual Vite frontend. Domain APIs are not fabricated: authentication, branch checks, validation and persistence execute normally. Meta requests and media transport are simulated, email sending is forbidden, the browser blocks external hosts, and campaign queues exist only in the test database. Enable with `WHATSAPP_HUB_BROWSER=1`; Vite defaults to `http://127.0.0.1:5191`.

`qa/whatsapp_hub_audit_browser.cjs` additionally verifies rejected-versus-uncertain send recovery, request-ID retention after reload, emoji insertion and every added server-filter control using mocked API failures. The three previous browser suites remain regression coverage for the desktop/mobile workspace, media, inline context and four shared creation forms.


### Final audit verification — 2026-11-05

- Broader backend regressions: 117 passed across WhatsApp integration/workspace, hub, shared engagement, customer campaigns, CRM follow-ups, sales/finance creation, PMS Task Studio and record links.
- After correcting the shared catalog default argument, the final focused rerun passed all 11 checks: original-brief audit regressions, price-list regression and the complete real-frontend/real-API browser scenario. The browser scenario also waits for the real analytics response and verifies both active conversations.
- All four standalone browser suites passed: base workspace, extended media/context/follow-ups, shared record creation and final audit/recovery/filter/mobile checks.
- TypeScript `tsc --noEmit` passed; targeted `git diff --check` passed. Existing dependency deprecation warnings remain.
- The real API browser scenario verifies quoted reply and document sends, canonical internal note, Pending, deal/quotation/invoice/PMS task creation and canonical task linking, follow-up schedule/complete, approved template variable mapping, signed inbound/dedup/read receipts, unknown contact create/link, own read cursor, campaign audience preview, isolated scheduled launch/dedup/cancel and real analytics data. Only provider transport is simulated. Campaign rows are cancelled inside the isolated test database without dispatch.
- No live messages, campaigns, credential changes, webhook configuration changes, schema migrations or deployment were performed. Previously missing provider media IDs and unrecorded historical resolution transitions cannot be recovered; these remain explicit data limitations.
