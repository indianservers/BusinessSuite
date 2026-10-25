# Business Suite integrations

This is a practical integration catalog, not a claim that these connectors are already implemented. Most services with an API, webhook, or supported import/export format can be connected, subject to their permissions and subscription plans.

## What can connect

- Calendars: Google Calendar, Microsoft Outlook / Microsoft 365, Apple Calendar / iCloud, Exchange, and other CalDAV calendars. Connect meetings, due dates, availability, reminders, and scheduling. ICS imports/subscriptions provide a simpler limited alternative.
- Files: Google Drive, OneDrive, SharePoint, Dropbox, Box, and S3-compatible storage. Attach documents to tasks, projects, customers, employees, and invoices while respecting source permissions.
- Spreadsheets: Google Sheets and Microsoft Excel. Import records, publish reports, and synchronize selected ranges with explicit ownership and conflict handling.
- Meetings: Google Meet, Microsoft Teams, Zoom, and Webex. Create conference links and associate scheduled meetings; recordings/transcripts depend on separate permissions and provider plans.
- Tasks and projects: Google Tasks, Microsoft To Do, Apple Reminders through native EventKit, Todoist, Trello, Asana, ClickUp, Monday.com, Notion, Jira, Linear, and Azure DevOps. Map tasks, owners, statuses, deadlines, comments, and project references.
- Email and contacts: Gmail, Microsoft Outlook, IMAP/SMTP, Google Contacts, and Microsoft contacts. Associate correspondence and contacts with CRM records. Request email permissions separately from calendars.
- Messaging: Slack, Microsoft Teams, Discord, Telegram, Twilio, and WhatsApp Business Platform. Send authorized alerts, approvals, and task notifications. WhatsApp business messaging has provider-specific opt-in/template requirements.
- Sales and support: Salesforce, HubSpot, Zoho CRM, Pipedrive, Zendesk, Freshdesk, and Intercom. Exchange leads, deals, contacts, tickets, and handoffs.
- Accounting and payments: QuickBooks, Xero, Zoho Books, supported Tally interfaces, Stripe, Razorpay, and PayPal. Map invoices, payment statuses, expenses, and reconciliation, with financial approval controls.
- Commerce and inventory: Shopify, WooCommerce, supported Amazon seller APIs, shipping providers, and barcode systems. Exchange products, orders, stock, and shipment statuses.
- Development: GitHub, GitLab, Bitbucket, CI systems, and error monitoring services. Associate commits, pull requests, build results, and incidents with project tasks.
- HR and identity: Google Workspace, Microsoft Entra ID, Okta, supported payroll/attendance providers, and DocuSign / Adobe Acrobat Sign. Connect identity, employee lifecycle, attendance, approvals, and signatures.
- Automation and data: n8n, Zapier, Make, Power Automate, signed webhooks, REST APIs, approved databases, and BI tools. Connect workflows where a dedicated connector is not justified.

Repository foundations already include CRM calendar models and meeting sync actions, project GitHub/GitLab webhook integration, and n8n event-feed documentation. Each needs its own production readiness assessment.

## Suggested order

1. Google Calendar: authenticate and export CRM meetings.
2. Calendar selection, inbound events, and task due-date export; unify CRM and project calendar views.
3. Google Drive: attach/link files with narrow file permissions.
4. Google Sheets: selected imports and report exports.
5. Google Meet, Outlook/Teams, and Apple Calendar support.
6. Messaging, task platforms, accounting, and automation based on actual workflows.

## Google Calendar: implemented first phase

Open `/crm/calendar-integrations` and choose **Connect Google Calendar**. The browser redirects to Google for consent, then returns to the same page. An authenticated backend exchanges the authorization code using PKCE and encrypted, user/organization-bound state valid for ten minutes. The browser checks the returned state against its own session before exchanging the code. Tokens are encrypted at rest and are not returned to the browser.

CRM's existing meeting sync action now creates or updates an event in the connected user's primary Google calendar. Meeting title, description, location, start/end, and cancellation status are exported. Expired tokens refresh during sync. A deterministic event ID makes retries update the same event. Disconnect removes the locally stored credentials; users can also revoke the app in Google Account permissions.

Not yet implemented: importing Google events, background sync, selecting other calendars, attendees/invitations, automatic Google Meet creation, recurrence, project tasks, automatic remote deletion after a local delete, or remote changes flowing back into Business Suite. Cancellation exports when a cancelled meeting is explicitly synced. This phase sends no guest invitations. Connecting Calendar does not grant Drive, Sheets, Gmail, or Google Tasks access.

### Google Cloud setup

1. Open [Google Cloud Console](https://console.cloud.google.com/) and select or create the application's project.
2. Enable **Google Calendar API** in APIs & Services → Library.
3. Configure **Google Auth Platform** branding, audience, and data access. Set the app name/support details, choose the appropriate audience, and add your Google account as a test user if using an external testing app.
4. Add the scope `https://www.googleapis.com/auth/calendar.events`. This allows event access across the user's calendars; this implementation uses only the primary calendar.
5. Create an OAuth client of type **Web application**. Register the exact frontend callback URL. For the standard local Vite port, use `http://localhost:5173/crm/calendar-integrations`. If your frontend runs on another port, change both the registered URL and server setting. For production use `https://YOUR-APP-DOMAIN/crm/calendar-integrations`.
6. Add these settings to the backend environment. Keep the secret on the backend, outside source control:

   ```dotenv
   CRM_GOOGLE_CALENDAR_CLIENT_ID=YOUR_CLIENT_ID
   CRM_GOOGLE_CALENDAR_CLIENT_SECRET=YOUR_CLIENT_SECRET
   CRM_GOOGLE_CALENDAR_REDIRECT_URI=http://localhost:5173/crm/calendar-integrations
   ```

7. Ensure backend `SECRET_KEY` is stable across restarts and instances; it encrypts stored credentials and OAuth state. Restart the backend, sign in to Business Suite with CRM manage permission, open Calendar Integrations, and connect Google Calendar in a normal browser tab.
8. Create a test CRM meeting with calendar sync enabled, or use an existing meeting's sync action. Confirm its title/time in Google Calendar; update and sync it again to confirm no duplicate event.

External apps in Google's Testing mode normally receive refresh tokens that expire after seven days for these scopes. Production use may require Google verification, published privacy information, and Workspace administrator approval depending on audience and policy.

### Next synchronization phase

Add provider-specific event mappings (organization, user, connection, calendar, local record, external event ID), durable sync cursors and jobs, cancellation/deletion policy, and explicit conflict handling. Use an initial event listing followed by incremental sync; an expired sync token requires a fresh full sync. Google push notifications signal that a calendar changed, so a worker must then fetch the changes and renew watch channels before expiration. Keep task records distinct from calendar events: tasks without a scheduled time should not automatically block availability.

### Apple Calendar options

- ICS export: user imports an event; later edits do not automatically update that imported copy.
- ICS subscription: a read-only published feed; refresh timing belongs to the client. Protect private feed URLs and provide revocation.
- iCloud CalDAV: server-side calendar access requires a separate connection flow and credential handling; it is not the same as Google OAuth.
- Native iOS/macOS app: EventKit accesses permitted calendars and reminders on the device. This is suitable for the Flutter application's native integration, rather than a browser backend.
- Users who display their Google account inside Apple Calendar can see exported Google events there without a separate iCloud connector.

## References

- [Google web-server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Calendar scopes](https://developers.google.com/workspace/calendar/api/auth)
- [Event creation](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert)
- [Incremental synchronization](https://developers.google.com/workspace/calendar/api/guides/sync)
- [Calendar push notifications](https://developers.google.com/workspace/calendar/api/guides/push)
- [Google OAuth token lifetime and testing](https://developers.google.com/identity/protocols/oauth2)
- [Apple EventKit](https://developer.apple.com/documentation/eventkit)
- [Apple Calendar accounts and CalDAV](https://support.apple.com/en-ca/guide/iphone/iphc37be2016/ios)
