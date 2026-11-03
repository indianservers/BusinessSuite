# Customer communications

Open **CRM → Communication Hub → Customer communications** (`/crm/communication-hub?section=customers`). This extends the existing hub, WhatsApp connection and suite email worker.

## Set up a business

1. Apply the PostgreSQL migration chain with `backend/venv/Scripts/python.exe -m alembic upgrade head` from `backend`. Revision `pg_20261103_067_customer_comms` follows the WhatsApp branch-routing migration.
2. Select a writable branch. Add customer recipients, their billing/service/delivery role, timezone and language. Record evidence for each channel/purpose permission. None of the checkboxes implies permission for another purpose; signup does not grant marketing consent.
3. Link each recipient explicitly to the appropriate business record. An order link also authorizes notifications for its invoices, service engagements and shipments. Customer IDs in different modules are never treated as interchangeable.
4. Configure business SMTP under Settings, or use the existing suite transport. SMTP supports mandatory TLS on 465/587, encrypted credentials, public destination addresses and a provider-verified sender. An explicitly disabled business connection does not fall back to another sender. Configure WhatsApp and approved Meta templates using the existing WhatsApp workspace.
5. Create an automation from a preset, preview the audience, and activate it. Delays are minutes from the event. `days_before=3` means three days before the deadline; `-3` means three days overdue. Equal quiet-hour values disable quiet hours. Business weekdays use Monday=0 through Sunday=6 in the customer's timezone.
6. For promotions/welcome campaigns, use Preview then Launch. A rule version launches at most once per recipient and step. Editing creates a new version and invalidates unsent intents from the previous version. Above the configured bulk threshold, a CRM administrator must explicitly approve the launch.

Business SMTP and WhatsApp credentials belong to a company. Customer recipients, rules, shipments, notes and delivery intents are branch-private. Existing module permissions and record visibility still apply. Workers re-evaluate current company membership, branch grants and send permissions.

## Source events and reminders

| Source | Change fields | Deadline |
| --- | --- | --- |
| SRM order | status, expected end | expected end date |
| SRM invoice | status, due date, paid/balance amounts | due date |
| SRM engagement | status, planned start/end | planned end date |
| Shared service follow-up | status, due time | due time |
| SRM contract | status, expiry | expiry date |
| CRM lead | status, next follow-up | next follow-up time |
| CRM meeting | status, start | start time |
| CRM quotation | status, validity/expiry | expiry date |
| Shipment | status, expected date, tracking link | expected date |

Draft changes are not sent to customers. Rules may select source statuses and recipient roles. New rules do not replay old pending source events. Due rules skip settled/terminal/draft records. Birthday and anniversary rules require greeting consent. Welcome rules also run when an authorized staff member adds a recipient.

Source changes and durable events commit atomically. Intent fan-out and the processed event marker commit together. Before dispatch, the worker checks the source snapshot again. Payment, completion, cancellation, rescheduling, changed contact details, unlinked records, paused/revised rules, withdrawn permissions and incoming customer replies can stop an obsolete message.

Collection reminders now require an outstanding issued invoice and an explicitly linked, opted-in billing/primary recipient. The action queues a real delivery intent; it never claims a message was sent merely because a reminder record exists.

Shipments have their own explicit status and optional HTTPS carrier tracking link. The system does not infer shipment progress from an order or simulate carrier updates. Update shipments through the workspace or its API.

## Sending and recovery

The existing email thread/authenticated cron invokes `process_email`, which also processes customer events, due journeys, notes and provider receipts. Keep `EMAIL_WORKER_ENABLED` configured for the hosting mode. No additional background service is needed.

Email uses the existing transactional outbox and its durable reservation before provider I/O. An SMTP acceptance is **accepted**, not confirmed customer delivery. WhatsApp continues to use its durable request IDs, signed webhook receipts, template approval checks and service-window rules.

States include queued, waiting_provider, accepted, sent/delivered/read where supported, retry_wait, blocked, cancelled, failed and reconciliation_required. Definitive temporary email rejection backs off for a maximum of three provider attempts. A timeout or unknown response is held for reconciliation, never automatically retried. WhatsApp local rate limiting defers the intent. Manual retry permits blocked intents that have not crossed a provider boundary and definitive provider rejections, with at most five attempts. WhatsApp failures that already have a provider message ID require reconciliation first.

Use the company pause switch, quotas and delivery error filters to investigate failures. A missing connection is blocked with a setup message. Campaign emails include a withdrawal link. Manually issued preference links expire after 30 days and revoke earlier manually issued links; links embedded in campaign emails expire after 90 days. GET does not unsubscribe, protecting against email link scanners. POST withdraws promotions and greetings without exposing customer identity or permitting anonymous opt-in.

## Customer replies and follow-ups

Customer history combines outgoing delivery intents, incoming WhatsApp messages, verified email reply events and clearly labelled internal notes. Conversation assignments and dated internal follow-ups are available through the API; the workspace can assign a conversation and schedule a note. Due notes create an internal notification once, after checking the assignee's current branch access.

For email receiving, connect a receiving-service/mailbox bridge:

1. Save an active business SMTP connection.
2. Generate receiver credentials in Settings. Store the returned secret in your receiving adapter; it is returned once and encrypted on the suite server. Rotation invalidates the previous secret.
3. POST to the returned `/api/v1/integrations/customer-email/{organization_id}` URL. Set `X-BusinessSuite-Timestamp` to Unix seconds and `X-BusinessSuite-Signature` to `sha256=` plus the hexadecimal HMAC-SHA256 of `timestamp + "." + raw_request_bytes`, using that secret.
4. JSON fields: `event_id`, `in_reply_to`, `from_email`, `to_email`, `subject`, `body`, `authenticated_sender`. The receiving adapter must verify sender authentication (for example provider-verified SPF/DKIM results) before setting `authenticated_sender=true`.
5. `in_reply_to` must match the provider/thread ID stored on the suite email outbox. Business SMTP returns its RFC Message-ID for this purpose; an SES bridge must map incoming thread headers to its corresponding SES provider ID. The sender must match the mapped customer, and the destination must match the configured business mailbox/reply-to address.

The receiver validates signature freshness, limits request size/rate, rejects unmatched threads and deduplicates provider events. It inherits the exact original conversation's company and branch. Email replies can stop follow-up steps and have a shared inbox read state. The application does not poll an arbitrary SMTP server for mail; SMTP alone provides no receiving API. Incoming HTML and attachments are not rendered or imported by this adapter.

## Provider requirements and operational limits

Automated WhatsApp messages require an approved template and recorded permission; the existing provider service validates template name/language before sending. Free-text replies retain the existing service-window validation. See [WhatsApp Business Messaging Policy](https://business.whatsapp.com/policy) and [SES sending lifecycle](https://docs.aws.amazon.com/ses/latest/dg/send-email-concepts-process.html).

Customer timezone/language is retained, but message translations are authored explicitly per rule/template. The workspace reports message usage estimates, not invented provider costs or attributed revenue. No carrier API is configured automatically. Email delivery/read tracking needs provider delivery-event support; SMTP acceptance alone remains the highest email delivery state in this implementation. The email receiver requires the external receiving adapter described above. Public customer acquisition forms continue to use the existing webform/lead capture features; staff enroll customer recipients after recording their channel/purpose permissions.

## Verification

- `tests/test_customer_communications.py`: API validation, event rollback, source changes, consent withdrawal, duplicate campaigns, due-date rescheduling, quiet hours, tenant/branch isolation, encrypted credentials, token rotation/expiry, bounded rejection retries and signed inbound reply deduplication.
- Existing email, WhatsApp and collection suites cover compatible delivery behavior, webhook receipts and ambiguous outcomes.
- `playwright/customer-communications.spec.ts`: workspace navigation, customer creation without implicit marketing opt-in, automation preview, password field handling and mobile overflow. Browser API responses are mocked; backend integration tests exercise the real APIs and disposable PostgreSQL migration chain.
- Tests use synthetic contacts and mocked providers. No real customer messages are sent.
