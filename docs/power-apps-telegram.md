# Shared Telegram bot

Open `/power-apps/automations/telegram?environment=development`, or follow **Open Telegram configuration page** from Automations. One bot serves public customers and company employees, with separate conversations, identity mappings, enable controls and welcome messages. WhatsApp and Voice AI remain deferred.

## Setup and operation

Apply the Telegram operations migration using the deployment's existing migration command: `20261116_084_telegram_ops` for the main Alembic chain, or `pg_20261116_123_telegram_ops` for the PostgreSQL chain. Both add identity links, hashed one-time linking challenges, conversations and messages. Migration tests exercise upgrade/downgrade on SQLite; no production migration is performed by the test suite.

Connect using **Connect Telegram bot**. Leaving the token blank uses the temporary server-only bootstrap credential; a replacement token is optional. Setup verifies the bot identity, refuses an existing webhook or duplicate listener, and puts credentials in the encrypted backend vault. Tokens are never returned to the browser or stored in workflow definitions.

Run the backend and worker. From `backend`:

```powershell
.\venv\Scripts\python.exe -m app.apps.power_apps.worker --poll-seconds 1
```

The worker polls approximately every five seconds. Telegram permits one polling listener per bot and polling cannot run alongside a webhook. Only new private text messages from human senders are processed; group chats, attachments and messages older than setup are ignored.

The versioned workflow still uses Telegram message received → check enquiry → Telegram send message. Sending follows the connector operation journal, retries and delivery outcome handling. Inbox replies show queued/execution state, not an unverified delivery claim.

## Employee identity and automatic authorization

Under **Identity linking & human handoff**, choose an employee and enter their numeric Telegram user ID. Employees can send `/id` privately to the bot to obtain that ID. Mapping requires both bot-owner/superuser authorization with Power Apps publish permission and employee update permission. The employee must belong to the company, be visible in the current branch, have an active BusinessSuite user account, and have Active, Probation or On Leave employment status with no effective exit date.

The identity mapping references the actual employee record and BusinessSuite user. A mapped employee's first chat opens company mode automatically. `/company` or `/start company` explicitly opens company mode, while `/public` opens public mode. Authentication uses the sender ID provided by Telegram polling, never a user-typed ID, display name or username.

Each company message rechecks the current employee status, branch/company membership, linked user status and revocation. CRM actions use the employee's own permissions and native CRM scope. Linking never grants the bot owner's CRM permissions to an employee. Old numeric allowlist entries alone no longer grant access. Revoke a link before moving an employee or Telegram account to a different mapping.

Authenticated users can optionally generate a one-time company linking code for their own account. This cannot select another user's account. It supports company members who use an application account rather than an employee mapping.

## Public identity

Visitors can submit enquiries without a login. Their private Telegram sender ID provides continuity, but does not by itself prove an existing CRM identity. No CRM account is auto-linked by name, phone, or Telegram username.

To link an existing customer, the bot manager chooses a CRM contact or lead ID and generates a one-time command. Share it privately with the verified customer; they send `/link <code>` to the bot. CRM manage permission and record visibility are checked at issue and consumption. Codes are random, stored only as SHA-256 hashes, expire after ten minutes, and are single-use. A new code invalidates earlier unused codes for that target. Commands are redacted from incoming history and automation payloads.

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

This release supports text messages, CRM intake and staff replies. It does not expose customer record lookups, approve transactions, book appointments, process attachments, or route one bot across multiple organizations. Staff need authorized Power Apps access to operate the web inbox. The employee picker lists up to 200 visible active employees with user accounts.

Automation payloads follow the workflow's retention policy. The dedicated identity/inbox tables persist independently; this release does not add an automatic transcript purge policy. Linking codes themselves are never kept in those transcripts.

Checks: `tests/test_telegram_operations.py`, `tests/test_telegram_migrations.py`, `tests/test_power_telegram.py`, `tests/test_power_telegram_automations.py`, and `playwright/power-telegram-automations.spec.ts`. Provider calls are mocked in automated tests. Run browser checks with `npx --prefix frontend playwright test --config=frontend/playwright.telegram.config.ts`.
