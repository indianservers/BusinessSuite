# Shared Telegram bot

Open `/power-apps/automations/telegram?environment=development`, or follow **Open Telegram configuration page** from Automations. One bot serves public customers and company employees, with separate conversations, identity mappings, enable controls and welcome messages. WhatsApp and Voice AI remain deferred.

## Setup and operation

Apply the Telegram operations migration using the deployment's existing migration command: `20261116_084_telegram_ops` for the main Alembic chain, or `pg_20261116_123_telegram_ops` for the PostgreSQL chain. Both add identity links, hashed one-time linking challenges, conversations and messages. Migration tests exercise upgrade/downgrade on SQLite; no production migration is performed by the test suite.

Connect using **Connect Telegram bot**. Leaving the token blank uses the temporary server-only bootstrap credential; a replacement token is optional. Setup verifies the bot identity, refuses an existing webhook or duplicate listener, and puts credentials in the encrypted backend vault. Tokens are never returned to the browser or stored in workflow definitions.

Run the backend and worker. From `backend`:

```powershell
.\venv\Scripts\python.exe -m app.apps.power_apps.worker --telegram-only --poll-seconds 3
```

The worker polls approximately every five seconds. Telegram permits one polling listener per bot and polling cannot run alongside a webhook. New private messages, known inline-button callbacks, shared locations and workflow document receipts from human senders are processed. Group chats and messages older than setup are ignored. Document receipts retain Telegram file metadata; this release does not download or scan file contents.

Use `--telegram-only` for a dedicated bot deployment: it leaves unrelated automation schedules, connector jobs and ActionBot queues untouched. Omit it only when intentionally running the general automation worker. The API does not start this worker. Supervise one instance using the API's existing database and encryption settings. Preserve the trained model directory (or set `LOCAL_NLP_MODEL_DIR`); an absent or incompatible artifact selects the reported rules fallback. Company AI commands use separate, revocable twenty-minute sessions and do not borrow browser credentials. Native PMS child plans still require their dedicated worker.

The versioned workflow still uses Telegram message received → check enquiry → Telegram send message. Sending follows the connector operation journal, retries and delivery outcome handling. Inbox replies show queued/execution state, not an unverified delivery claim.

## Employee identity and automatic authorization

Under **Identity linking & human handoff**, choose an employee and enter their numeric Telegram user ID. Employees can send `/id` privately to the bot to obtain that ID. Mapping requires both bot-owner/superuser authorization with Power Apps publish permission and employee update permission. The employee must belong to the company, be visible in the current branch, have an active BusinessSuite user account, and have Active, Probation or On Leave employment status with no effective exit date.

The identity mapping references the actual employee record and BusinessSuite user. A mapped employee's first chat opens company mode automatically. `/company` or `/start company` explicitly opens company mode, while `/public` opens public mode. Authentication uses the sender ID provided by Telegram polling, never a user-typed ID, display name or username.

Each company message rechecks the current employee status, branch/company membership, linked user status and revocation. CRM actions use the employee's own permissions and native CRM scope. Linking never grants the bot owner's CRM permissions to an employee. Old numeric allowlist entries alone no longer grant access. Revoke a link before moving an employee or Telegram account to a different mapping.

Authenticated users can optionally generate a one-time company linking code for their own account. This cannot select another user's account. It supports company members who use an application account rather than an employee mapping.

## Public identity

Visitors can submit enquiries without a login. Their private Telegram sender ID provides continuity, but does not by itself prove an existing CRM identity. No CRM account is auto-linked by name, phone, or Telegram username.

To link an existing customer, the bot manager chooses a CRM contact, lead or explicitly verified Sales customer account ID and generates a one-time command. Share it privately with the verified customer; they send `/link <code>` to the bot. CRM manage permission and record visibility are checked at issue and consumption. Codes are random, stored only as SHA-256 hashes, expire after ten minutes, and are single-use. A new code invalidates earlier unused codes for that target. Commands are redacted from incoming history and automation payloads.

A linked public customer remains a public user and cannot open the company interface. Revoking a public link removes its CRM association; subsequent enquiries continue as an unverified visitor. Existing messages and created CRM records remain in history.

## CRM lead and task creation

Enable **Create CRM leads and tasks from completed requests** in interface settings. This is off until explicitly enabled, to preserve existing intake-only bots. Enabling requires an established bot branch and CRM lead/task create authority.

Public Sales collects name and requirement, then creates a native CRM lead and a linked follow-up task. Repeat Sales enquiries reuse that public identity's existing lead and create a new task. A linked CRM contact is attached to follow-up tasks. Support and Order status create CRM tasks; they do not pretend to retrieve order information.

Company mode accepts **Create lead** (name then requirement), **Create task**, and **Internal request** (description). Company-created leads are separate records, and tasks are created under the employee's native CRM permissions and ownership rules. They are CRM tasks, not PMS project tasks.

Native CRM validation, required fields, custom-field requirements, duplicate rules, branch boundaries and audit/timeline behavior apply. Lead/task creation and message update acceptance share one transaction. Replaying a Telegram update cannot duplicate records. If native validation or authority rejects creation, the request is retained in the handoff inbox without claiming CRM success; partial lead/task writes roll back.

## Human handoff

Send `/human`, `human`, or `talk to a person` in either interface. The conversation enters Waiting, the bot owner receives an in-app notification, and subsequent messages are recorded without automatic replies. Waiting/assigned threads notify the responsible person when new messages arrive.

The inbox shows the 50 most recent conversations, filters by state and displays up to 50 recent messages per thread. Staff with authorized access and Power Apps execute permission can claim an unassigned conversation. Only the bot owner/superuser can assign someone else; the target must currently belong to the company and have Power Apps execute authority. Another staff member cannot take over an assigned conversation.

Only the assigned person can queue a reply. Retries with the same client key reuse the existing execution. Resolve closes the handoff; Return to bot clears the intake state and resumes automation. Both actions are audited. Interface switching keeps company/public histories separate.

Immediately before provider delivery, company identity, interface enablement, staff assignment and current permissions are checked again. An old queued automatic reply is blocked after human handoff. A queued staff reply is blocked if assignment or company authorization was revoked.

## Limits and validation

This release supports guided intake, bounded verified customer lookups, reviewed ActionBot changes, native appointments, document receipts and staff replies. One bot remains scoped to one organization/environment. Voice AI and WhatsApp are deferred. Staff need authorized Power Apps access to operate the web inbox. The employee picker lists up to 200 visible active employees with user accounts.

Automation payloads follow the workflow's retention policy. The dedicated identity/inbox tables persist independently; this release does not add an automatic transcript purge policy. Linking codes themselves are never kept in those transcripts.

Checks: `tests/test_telegram_operations.py`, `tests/test_telegram_migrations.py`, `tests/test_power_telegram.py`, `tests/test_power_telegram_automations.py`, and `playwright/power-telegram-automations.spec.ts`. Provider calls are mocked in automated tests. Run browser checks with `npx --prefix frontend playwright test --config=frontend/playwright.telegram.config.ts`.


## ActionBot model connection

Both Telegram interfaces now connect to the existing ActionBot model pipeline. **ActionBot AI model** on the Telegram configuration page controls enablement and provider selection. Publish sourced facts separately under **Knowledge, industry workflows & service operations**. The default is the server's existing local intent model, using the same company/branch release selection as ActionBot. The status response reports whether a compatible trained artifact is active or the existing retrieval/rules fallback is in use. A local classifier is not a generative chat LLM.

Provider choices are local, the existing ActionBot preference, or the configured OpenAI/Gemini/Claude adapter. Cloud models reuse the existing scoped provider configuration, keys, model name, usage logging and data-sharing controls; Telegram never stores a second provider credential. Enabling/saving AI configuration requires bot ownership/publish permission and current AI access. Explicit cloud selection requires an enabled provider with data sharing allowed. The same runtime checks apply again during requests.

Free-text messages are durably queued after Telegram ingress commits. The Power Apps worker processes the AI inbox separately from the polling transaction and queues the answer through the existing Telegram delivery pipeline. Known commands and in-progress name/requirement intake remain deterministic. Consecutive pending messages in the same conversation are combined within a bounded prompt. Superseded requests, disabled AI, interface switches, cancelled intake and active human handoffs cannot emit an old AI response. Provider error details are sanitized; failures move the request to staff review.

Company requests run through the canonical suite command service under the linked employee's AI and business-module permissions. The engine retains its conversation memory, authorized native reads, local model or existing provider selection, validation, usage controls and action previews. It never borrows the employee's browser session. A company action proposal can be reviewed through expiring Telegram buttons. All preview pages must be visited before approval. Exact plan hashes, employee identity, current permissions, source state and handoff status are rechecked before canonical execution. Each company AI command uses a separate short-lived initiating session; expiry and normal session revocation remain enforced. Explicit structured Telegram CRM intake retains its existing configured creation path.

Public requests never enter the privileged suite planner and receive no business-tool catalog, company memory, internal saved-agent knowledge, credentials or other chats. The local model can classify a supported request into enquiry intake; otherwise it asks the visitor to choose a topic. Cloud replies receive only approved public business information and a bounded recent transcript from that same public conversation. A model-selected Sales/Support/Order status topic starts the existing intake; Human requests use the existing handoff queue. Customer messages are untrusted model input and cannot grant employee access.

AI requests reuse the automation event table. Experience memory, explicit customer links and exact approvals require SQLite migration85 or PostgreSQL migration124 in addition to the earlier identity/inbox migration. Run `tests/test_telegram_ai.py` for model integration, public prompt isolation, canonical company planning, update deduplication, disablement, cancellation, handoff and sanitized-failure checks. Provider responses in tests are simulated; they do not establish live cloud connectivity.


## Verified experience and service operations

Managers publish knowledge with an HTTPS/HTTP source, document reference, audience, language and expiry. Approval provenance is stamped on the server. Only approved unexpired audience-appropriate facts are eligible. Factual replies quote the approved content and cite its source; publish approved Telugu/Hindi variants when translated factual content is needed. Guided menus/intake support English, Telugu, Hindi and mixed-script values. Names, amounts, dates and identifiers remain verbatim; the local intent classifier does not provide unrestricted multilingual generation.

Public `/account`, `/orders`, `/appointments` and `/myrequests` require a current verified link. Account-wide Sales reads require an explicit customer account link; linking a CRM contact does not grant its entire company's records. Private replies bind the exact verified identity and target IDs, then recheck current link, owner permissions and native record visibility at delivery. Revocation or relinking blocks already queued private content.

Workflow builders define typed questions, required document MIME types, urgency reasons, staff skills, reviewers and allowed service-stage transitions. Initial stage approval can defer native CRM creation. Stage changes use optimistic revisions and expiring exact reviews. Editing the published experience invalidates in-progress workflow versions; start a fresh request after such changes. Terminal service stages do not falsely close an outstanding native CRM task.

Handoffs match mapped employees by bot branch, language, skills, configured availability, working hours and per-bot capacity. The owner remains responsible if no candidate qualifies. Availability here is the configured routing roster; native employee leave checks apply to appointment availability. Deadlines escalate through configured recipients and then the owner. A queued reply does not stop the deadline; successful transport does. SLA scans paginate active deadlines so older answered threads cannot starve newer overdue requests.

Claimed staff can generate a sourced suggestion, edit it and manually queue the reply. Suggestions never auto-send; stale transcript/source revisions, expiry or reassignment require fresh review.

Native appointment services select a provider plus required room/equipment resources. Verified customers book only their own account; employees use their own current Sales permissions. Creation, rescheduling and cancellation each require an exact expiring review. Native availability and revision checks run again on execution, rejecting intervening bookings, changed prices or unavailable resources. No payment capture or invoice posting is implied.

Additional checks: `test_telegram_experience.py`, `test_telegram_customer_privacy.py`, `test_telegram_routing_regressions.py`, `test_telegram_booking_flow.py`, `test_telegram_action_approvals.py`, `test_telegram_sessions.py` and `test_telegram_staff_workflows.py`. Automated Telegram/cloud calls are mocked; native CRM/appointment writes are exercised against test databases. Browser checks use mocked APIs and do not verify live Telegram transport.
