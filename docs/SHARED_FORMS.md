# Shared Forms plugin

Forms is one shared BusinessSuite feature, available at `/pms/forms`, `/crm/forms`, `/srm/forms`, `/hrms/forms`, and `/fam/forms`. It is not a separately duplicated app per module.

## Find and publish forms

Open **Forms → Published** to see published forms, including closed and internal forms. Open a form's **Publish** tab, enable **Allow anyone with the public link to respond**, and publish. Copy the URL or iframe embed code from the same tab. Public URLs use `/f/<unguessable-slug>` and work without signing in. Deployment is required to make a local development URL accessible on the internet.

Publishing without public access creates an internal response page. New forms belong to their creator. Imported PMS workspace forms preserve member submission access and Owner/Admin management access. Guests cannot submit internal workspace forms. Form responses and uploaded files are restricted to authorized form managers; a public URL does not expose responses or drafts.

## Delivered

- Dedicated All forms, Published, View responses, Custom fields, and Create/edit pages.
- Mockup-style header and Build, Design, Logic, Responses, Publish tabs; searchable field palette, three-column builder, field inspector and live preview.
- Click to add, pointer drag and keyboard drag, move up/down controls, duplicate/delete questions, duplicate a form as a private draft, templates, JSON definition import/export.
- Short/long text, email, telephone, URL, number, date, dropdown, single/multiple choice, consent, rating, section, page break and file upload.
- Required fields, choice validation, numeric bounds, conditional visibility based on earlier questions; hidden answers discarded by server validation.
- Stacked or multipage layout with progress and Back/Continue navigation; accent, font, button corners, submit label and thank-you message.
- Global customization catalog and management reference. Compatible visible/editable fields and options can be reused, with a persisted source-field reference. Published forms use a snapshot so later global edits do not silently change live questions. Collecting answers does not silently write them into CRM/HRMS records.
- Separate draft/live definitions, revision conflicts, explicit save state, unsaved-navigation protection, publish versions, public URL and iframe embed, closing/reopening, deadline and response cap.
- Server-generated image security code by default; optional Cloudflare Turnstile with server verification. All submissions also use a honeypot, durable rate buckets, validation, and UUID-based duplicate prevention. Built-in codes expire after five minutes and can be used once.
- Response pagination, search across all answers, per-response review/archive status, detail view, CSV and authenticated JSON exports. CSV cells are escaped against spreadsheet formula injection.
- Private PDF/PNG/JPEG response attachments: 2 MB each, 3 MB combined, at most three files. Files are checked by content signature and downloaded as attachments through authorization checks. Combined size accounts for base64 transport and hosting request limits.
- PMS task-intake adapter: select an authorized project and required title question. Tasks, attachments and responses commit together; current owner permissions are checked again on submission. Other modules use the same engine and can add their own adapters.
- Existing workspace forms and responses are imported idempotently on discovery. Internal forms remain internal. Original workspace APIs remain compatible; later legacy responses are imported without duplicates. Legacy draft definitions are imported once, then edited through the shared builder.

## Comparison with established form builders

This is the core shared release, not complete parity with every commercial plan.

Google Forms documents question reuse, sections, duplication, media, quizzes, collaboration and response charts. We cover the basic question/section/reuse workflow; media questions, quiz grading, shared live editing, response charts and Sheets synchronization remain. [Google editing guide](https://support.google.com/docs/answer/2839737?hl=en), [Google Forms overview](https://support.google.com/docs/answer/6281888?hl=en).

Jotform documents field/page branching, calculations, conditional emails, approvals, integrations and payments. We cover field visibility, multipage forms, uploads, reusable fields and the native PMS task action. Compound AND/OR rules, calculated fields, page-jump branching, conditional notifications, approval workflows, payment gateways and external connectors remain. [Jotform conditions](https://www.jotform.com/help/57-smart-forms-conditional-logic-for-online-forms/), [Jotform workflows](https://www.jotform.com/products/workflows/features/).

Typeform supports embedding and partial-response collection, including delivery into connected integrations. We cover public links, iframe embedding and full-response collection. Respondent save-and-resume, partial submissions, conversational one-question presentation, conversion analytics, webhooks and integration delivery remain. [Typeform embedding](https://help.typeform.com/hc/en-us/articles/360029249212-Embed-your-form), [Typeform partial responses](https://help.typeform.com/hc/en-us/articles/50681134074132-Capture-partial-responses-after-every-question).

Further backlog: legally meaningful e-signatures, custom domains, multilingual/localized form content, richer widgets/address inputs, a large template marketplace, builder autosave and undo/redo, form folders/trash/restore, shared ownership and collaborator invitations, PDF document generation, offline collection, accessibility alternative to the built-in image challenge, and tenant-configurable retention/storage quotas. These are not represented by placeholder controls.

## Deployment and extension

Apply migration `20261024_013` on the SQLite chain or `pg_20261024_013` on PostgreSQL, using the existing deployment migration runner. No deployed database was modified during local QA. Rate limits use the ASGI-resolved client IP; configure trusted proxy forwarding for the deployment. Pillow is a declared backend dependency. Existing SPA rewrites support `/f/:slug`.

For Turnstile, configure `FORMS_TURNSTILE_SITE_KEY` and `FORMS_TURNSTILE_SECRET_KEY`, allow the deployed hostname in Cloudflare, then choose Turnstile in Publish settings and republish. Secrets remain server-side. Missing configuration prevents publication, and verification outages reject submissions. Provider tokens are verified using Cloudflare's server API; tokens are single-use and expire. [Cloudflare server verification](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/). Live provider interaction was not tested because real site keys were not configured.

Shared frontend: `frontend/src/features/forms`. Common backend registration: `app.forms.router` and `app.forms.models` in the module registry. Canonical validation: `app.forms.schema` (also used by the legacy PMS routes). Product-specific intake options/actions: `app.forms.integrations`. Add a module adapter there rather than copying the renderer, builder, persistence or spam-protection code.

See [QA evidence](qa/shared-forms-2026-10-24/README.md).
