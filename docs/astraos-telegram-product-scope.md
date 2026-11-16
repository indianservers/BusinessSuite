# AstraOS reference and Telegram implementation scope

Research date: 16 November 2026. This is an implementation reference for BusinessSuite, based on AstraOS public pages. Marketing claims describe the vendor's positioning, not independently verified capabilities or guarantees. No authenticated product account was available. The seven industry preview URLs returned compilation shells to HTTP retrieval; their finished interactive behavior was not verified.

## Product model

[Homepage](https://getastraos.com/) positions AstraOS as a service-business customer acquisition operating system. The five stages are Attract (website and local search), Engage (conversational assistance), Book (scheduling and dispatch), Recover (missed-call and after-hours follow-up), and Grow (reviews and repeat business).

BusinessSuite now has Telegram identity linking, approved sourced knowledge, CRM intake, staff handoff, reviewed native AI actions and native appointment commands. Public CRM intake is live-verified. A company identity was linked live, but the first approved action timed out under the old duplicate-worker memory pressure; its fresh post-fix execution remains unverified. Dedicated public/company bot separation is the current implementation change. This is not a claim of full AstraOS lifecycle parity.

## Feature inventory and BusinessSuite implications

### Website factory and verified knowledge

The homepage advertises business website ingestion, extraction of business knowledge with provenance, industry rules, grounded content and page blueprints, and a mobile website renderer with booking and voice launchers. The demo builder accepts website URL, business name, and industry. Advertised knowledge includes services, certifications, FAQs, pricing constraints and emergency rules.

BusinessSuite implements approved facts with source references, audience restrictions, approval provenance and expiry. Grounded replies select eligible facts, and unknown information can go to staff. Automated website crawling, reviewed knowledge extraction, conversion-page generation and a public website chat/booking widget remain gaps.

### Voice and telephony � next version

[AI Voice](https://getastraos.com/products/ai-voice) advertises inbound reception, appointment request capture, emergency classification, transcripts and summaries. [IVR](https://getastraos.com/products/ivr) lists department routing, after-hours announcements/voicemail and emergency diversion. The product catalog additionally lists voicemail transcription and browser voice.

Per the requested scope, defer microphone UI, WebRTC, phone numbers, SIP/telephony providers, IVR, speech recognition, speech synthesis, call recording, voicemail and voice analytics. Text-based public/company routing is useful now and can later share a conversation service with voice.

### Booking and operational CRM

The homepage advertises autonomous calendar scheduling, service intake/dispatch, confirmations and calendar synchronization. The [product catalog](https://getastraos.com/products) describes patients, appointments, treatments, payments and workflows in an operational CRM. These require real availability checks, ownership, time zones, customer identity, conflict prevention, cancellation/rescheduling rules and audit trails.

Telegram can create native CRM leads/tasks and prepare exact reviewed appointment creation, rescheduling and cancellation. Native conflict and resource checks are covered by integration tests. Public live intake created CRM lead5/task2. Telegram-to-current shared POS scheduling parity, connected calendar synchronization, booking reminders and the fresh company live action approval gate still need end-to-end verification. No payment capture is implied by a bot booking.

### Recovery and notifications

[Missed Call Capture](https://getastraos.com/products/missed-call-capture) advertises SMS outreach in under a minute, service requirement capture and CRM callback tasks. The catalog adds SMS reminders/alerts, WhatsApp follow-ups, email notifications, appointment reminders and WhatsApp promotional/reactivation campaigns.

Handoff response deadlines and escalation are implemented. Proactive opted-in lead recovery, abandoned-booking nudges and reminder schedules with quiet hours, unsubscribe controls and channel delivery reporting remain gaps. Telegram requires the customer to initiate a bot chat; it cannot replace arbitrary phone-number outreach. Telephony-triggered recovery and WhatsApp delivery are outside this release.

### Reputation and growth

The homepage describes post-service review requests over SMS/WhatsApp and Google review growth. The catalog lists private feedback collection and Instagram reels/captions/content workflows. [Review Growth](https://getastraos.com/products/review-growth) has generic automation/CRM/notification copy rather than a detailed public workflow contract.

A later Telegram flow could collect service feedback and offer the same review opportunity consistently to customers; avoid filtering public-review access by rating. It needs a verified completed-service event and approved business review URL. No review request or marketing campaign is sent by this change.

### Conversation intelligence and owner operations

The catalog lists unified conversation history, searchable call transcripts, summaries, a daily owner brief, analytics for calls/messages/reviews, and meeting notes/action items. These are broader capabilities than a chatbot widget.

BusinessSuite retains conversation history, unresolved requests, qualification, routing/SLA information and actual delivery/execution references. Company messages use the existing permission-scoped ActionBot planner and require exact approval for proposed actions. Channel-wide conversion/revenue reporting and scheduled owner briefs remain unfinished.

### Deployment and commercial model

The public [setup wizard](https://getastraos.com/setup-wizard) describes account activation followed by clinic details, phone, messaging, calendar and purchased-product setup. This indicates an assisted onboarding path; it does not establish public self-service provisioning behavior.

The [pricing page](https://getastraos.com/pricing) advertised Starter at $120/month plus $199 setup; AI Voice at $299/month plus $299 setup; Complete OS at $399/month plus $399 setup; and Growth at $499+/month with custom setup on the research date. Currency is shown as '$' without further validation. Module pages can show different standalone prices. Starter bundles IVR/capture/routing/email/history; AI Voice adds receptionist/intake/transcripts/CRM; Complete OS adds website factory, calendar booking, messaging and reviews; Growth adds multi-location routing, concurrency, custom integrations, owner briefs, personas and SLA support. These are vendor prices, not BusinessSuite pricing or cost estimates.

## Seven industry operating packs

- Dental: patient and insurance enquiries, cleaning/consultation booking, urgent dental intake. Requires patient privacy and safe escalation; avoid diagnosis.
- Plumbing: emergency versus routine classification, burst-pipe/drain requirements, location and dispatch intake.
- HVAC: equipment/system type, heating/cooling failures, diagnostic visits, seasonal maintenance and replacement enquiries.
- Electrical: panel upgrades, EV charging and commercial qualification with safety escalation.
- Roofing: storm damage, roof age, leak details, inspection and quote requests.
- Salon/med spa: treatment information, approved price ranges, clinician availability and consultation booking; avoid unverified clinical advice.
- Legal: practice area, timelines, contact details and urgent routing; requires confidentiality and no unapproved legal advice or representation promises.

The common implementation pattern is configurable service/intake fields, urgency rules, eligibility, location, appointment type and escalation. The configurable industry builder supports questions, documents, urgency rules and reviewed stages. Curated, tested customer journeys for all seven industries still need to be packaged; a generic builder is not equivalent to turnkey industry coverage.

## Separate public and company bots

The requested architecture now uses distinct Telegram bot credentials. Public bots serve enquiries, approved public facts and verified customer operations. They do not elevate a linked employee into company mode. Company bots accept only verified staff/account identities and preserve each user's native permissions; they never fall back to public intake. Telegram usernames and typed numeric IDs do not grant access.

The current separation work adds server-owned bot purpose, purpose-specific configuration and runtime checks at intake, linking, queued AI, action approval and delivery. A purpose change invalidates incompatible authorizations instead of transferring them to another bot. Public handoff staff use verified ERP employee mappings and web permissions, so they do not need to authenticate to the public bot as company users.

The existing @GGU_AI_bot is intended to become exclusively public. A separate company bot token must be supplied and connected before that bot can be activated; the implementation must not silently reuse the public token or claim a second live bot exists without it.

## Verification limits

Public pages establish an advertised feature inventory, not uptime, response latency, hallucination guarantees, regulatory compliance, integration quality or actual conversion results. The homepage's zero-loss, grounding and sub-minute recovery claims were not independently measured. Industry demos need browser interaction and authenticated operational testing to validate end-to-end behavior. BusinessSuite capabilities above are explicitly marked as shipped or future; no AstraOS feature is assumed implemented merely because it appears in this document.


## Remaining priorities after the Telegram foundation

The public homepage was rechecked in the browser on 16 November 2026. Its claims still center on website acquisition, conversational engagement, scheduling, recovery and reputation. These are advertised capabilities, not independently established operational guarantees.

1. Complete live approval verification after the memory-sharing worker fix and verify a single availability/booking source across Telegram, POS, HRMS and calendars.
2. Add a public website chat/booking widget and reviewed website-to-knowledge import; website generation is a separate deliverable.
3. Add opted-in text follow-ups for unanswered leads, incomplete enquiries and abandoned bookings, with quiet hours and unsubscribe.
4. Add post-service feedback and consistent Google-review invitations without rating-based review gating.
5. Connect WhatsApp, SMS and email through channel adapters while preserving identity and conversation boundaries.
6. Ship tested customer journeys for each advertised target industry, rather than requiring every customer to assemble a workflow from generic questions.
7. Measure enquiry-to-qualified-lead-to-booking-to-paid conversion, recovery outcomes, channel costs and repeat business.
8. Add self-service onboarding and an operator health view showing delivery failures, stale knowledge, overdue handoffs and execution receipts.

Voice reception, telephony and missed-call detection remain intentionally deferred to the next version. The way to compete is to connect these customer-facing journeys reliably to BusinessSuite's existing operational records and report verified outcomes, not to copy unverified performance claims.
