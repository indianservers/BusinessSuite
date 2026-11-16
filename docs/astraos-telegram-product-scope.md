# AstraOS reference and Telegram implementation scope

Research date: 16 November 2026. This is an implementation reference for BusinessSuite, based on AstraOS public pages. Marketing claims describe the vendor's positioning, not independently verified capabilities or guarantees. No authenticated product account was available. The seven industry preview URLs returned compilation shells to HTTP retrieval; their finished interactive behavior was not verified.

## Product model

[Homepage](https://getastraos.com/) positions AstraOS as a service-business customer acquisition operating system. The five stages are Attract (website and local search), Engage (conversational assistance), Book (scheduling and dispatch), Recover (missed-call and after-hours follow-up), and Grow (reviews and repeat business).

For BusinessSuite, Telegram provides text engagement and structured intake first. The configuration shipped in this change establishes the shared channel and access boundary; it does not implement the entire AstraOS lifecycle.

## Feature inventory and BusinessSuite implications

### Website factory and verified knowledge

The homepage advertises business website ingestion, extraction of business knowledge with provenance, industry rules, grounded content and page blueprints, and a mobile website renderer with booking and voice launchers. The demo builder accepts website URL, business name, and industry. Advertised knowledge includes services, certifications, FAQs, pricing constraints and emergency rules.

BusinessSuite should later maintain a company-approved knowledge base with source links, verification dates, service availability, prices, opening hours, locations and escalation contacts. Telegram answers should use that approved data. Unknown facts need an explicit fallback and staff handoff. The current bot uses deterministic intake, so it makes no generative factual claims. Website crawling, generation and retrieval-based answers are not implemented here.

### Voice and telephony — next version

[AI Voice](https://getastraos.com/products/ai-voice) advertises inbound reception, appointment request capture, emergency classification, transcripts and summaries. [IVR](https://getastraos.com/products/ivr) lists department routing, after-hours announcements/voicemail and emergency diversion. The product catalog additionally lists voicemail transcription and browser voice.

Per the requested scope, defer microphone UI, WebRTC, phone numbers, SIP/telephony providers, IVR, speech recognition, speech synthesis, call recording, voicemail and voice analytics. Text-based public/company routing is useful now and can later share a conversation service with voice.

### Booking and operational CRM

The homepage advertises autonomous calendar scheduling, service intake/dispatch, confirmations and calendar synchronization. The [product catalog](https://getastraos.com/products) describes patients, appointments, treatments, payments and workflows in an operational CRM. These require real availability checks, ownership, time zones, customer identity, conflict prevention, cancellation/rescheduling rules and audit trails.

BusinessSuite already has business modules to integrate in later work. Do not claim a booking or transaction has succeeded until the actual module confirms it. Current Telegram collection records an enquiry only; it does not create a lead, appointment, task or payment in those modules.

### Recovery and notifications

[Missed Call Capture](https://getastraos.com/products/missed-call-capture) advertises SMS outreach in under a minute, service requirement capture and CRM callback tasks. The catalog adds SMS reminders/alerts, WhatsApp follow-ups, email notifications, appointment reminders and WhatsApp promotional/reactivation campaigns.

For Telegram, subsequent work can add opted-in follow-up and reminder schedules with quiet hours, unsubscribe controls, delivery outcomes, retries and duplicate prevention. Telegram requires the customer to initiate a bot chat; it cannot replace arbitrary phone-number outreach. Telephony-triggered recovery and WhatsApp delivery are outside this release.

### Reputation and growth

The homepage describes post-service review requests over SMS/WhatsApp and Google review growth. The catalog lists private feedback collection and Instagram reels/captions/content workflows. [Review Growth](https://getastraos.com/products/review-growth) has generic automation/CRM/notification copy rather than a detailed public workflow contract.

A later Telegram flow could collect service feedback and offer the same review opportunity consistently to customers; avoid filtering public-review access by rating. It needs a verified completed-service event and approved business review URL. No review request or marketing campaign is sent by this change.

### Conversation intelligence and owner operations

The catalog lists unified conversation history, searchable call transcripts, summaries, a daily owner brief, analytics for calls/messages/reviews, and meeting notes/action items. These are broader capabilities than a chatbot widget.

Current BusinessSuite Telegram history retains incoming messages, interface state, planned replies and links to actual execution delivery status. Later reporting should distinguish enquiries, qualified leads, confirmed bookings, response time, delivery failures, handoffs and repeat contacts. The company interface should eventually expose permission-scoped work queues and summaries. It currently records internal requests only.

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

The common implementation pattern is configurable service/intake fields, urgency rules, eligibility, location, appointment type and escalation. These should be company configuration, rather than seven disconnected bots. This release retains the existing generic Sales/Support/Order status intake.

## Two interfaces on one Telegram bot

The company web configuration page controls the bot, while public and company users interact through separate command routes inside the same Telegram account. `/public` and `/start public` select customer intake. `/company` and `/start company` select the staff workspace only for approved numeric Telegram sender IDs. A deep link is an entry selector, never proof of staff identity.

The company interface currently offers Help and Internal request. The public interface collects topic, name and requirement. Interface switching clears the in-progress conversation so public requirements cannot become staff actions. Revocation is enforced at the next message. Disabling one interface leaves the other available. Separate welcome messages and approved staff IDs persist on the existing organization/environment-scoped trigger configuration.

The setup remains authenticated and permission-controlled. Only the owner or authorized superuser can edit bot settings. The same bot cannot be attached to a second organization listener. Future multi-company support needs explicit tenant binding and company selection; numeric Telegram IDs alone cannot decide which company owns a public enquiry.

## Suggested next implementation sequence

1. Link approved staff IDs to verified application memberships and delegated permissions before adding data access or business actions.
2. Add company-approved FAQs/services and a customer escalation inbox with a clear human handoff state.
3. Connect enquiry completion to CRM lead creation with idempotency and source attribution.
4. Connect public booking requests to service scheduling with real availability, confirmations and cancellation/rescheduling rules.
5. Add opted-in Telegram reminders, feedback and daily company summaries with delivery reporting.
6. Add WhatsApp through a channel adapter while preserving tenant, identity, permissions, conversation state and execution controls.
7. Introduce Voice AI and telephony in the next version, reusing the approved knowledge and business operations.

## Verification limits

Public pages establish an advertised feature inventory, not uptime, response latency, hallucination guarantees, regulatory compliance, integration quality or actual conversion results. The homepage's zero-loss, grounding and sub-minute recovery claims were not independently measured. Industry demos need browser interaction and authenticated operational testing to validate end-to-end behavior. BusinessSuite capabilities above are explicitly marked as shipped or future; no AstraOS feature is assumed implemented merely because it appears in this document.
