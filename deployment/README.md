# DigitalOcean Ubuntu Droplet

Production uses Ubuntu 24.04, PostgreSQL, Redis, Nginx, Python 3.12 and Node 22+.
The suite and Interns Hub are built from the same Git revision. One API worker
preserves the current in-process WebSocket behavior. Allow enough RAM and disk
for both frontend builds and retained releases.

## Amazon SES disabled — 18 November 2026

Amazon SES delivery is disabled in the active BestERP runtime configuration.
`EMAIL_PROVIDER=smtp`, `COMMUNICATION_EMAIL_PROVIDER=smtp`, and
`INTERN_HUB_SES_ENABLED=false`; dedicated site, shared SES, and Interns Hub
SES SMTP endpoints and credentials are cleared from the active environment.
No alternate `MAIL_SERVER` is configured, so outgoing email is paused and the
shared outbox worker leaves queued messages pending. Do not restore SES settings
from historical deployment instructions or backups without owner authorization.
A private pre-change environment backup is retained on the production server.

## Current BestERP host

As of 9 November 2026, `https://besterp.app` serves the suite from
`139.59.91.37` using Nginx, local PostgreSQL 18 on port 55435, and
`business-suite.service` on `127.0.0.1:8000`. The active release is
`/srv/business-suite/releases/20261109-besterp`, copied from the live
`20261109-grid9395` release rather than the uncommitted development checkout.
The final restore verified all 837 table counts and the complete user records.

The shared Notes frontend is selected by `frontend/dist` pointing to
`/srv/business-suite/suite-builds/shared-notes-20261109` on both suite hosts.
All module Notes links use `/pms/notes`; Create → Note uses `?new=1`.
The previous static releases and their hashed assets are retained for rollback
and already-open tabs, including the direct Google Drive/OneDrive controls.

The live API uses `REALTIME_TRANSPORT=database` so realtime updates poll without
holding WebSocket database sessions. Module-access database checks run in the
thread pool. Security counters and response audits use a separate bounded
database pool (two persistent connections plus three overflow), preventing them
from waiting for connections held by the handlers they must finish. These
changes require no schema migration. Browser acceptance is repeatable with
`qa/shared_notes_navigation_browser.cjs`, `NOTES_QA_ORIGIN`, and a private
`NOTES_QA_SESSION_FILE` containing a revocable test session.

The existing Apache sites on `164.92.119.35` still serve their frontends and
proxy API, uploads and health requests over verified HTTPS to `besterp.app`.
That host resolves `besterp.app` directly to the new origin in `/etc/hosts`.
Its former API and backup timer are disabled to keep one active database.
The source database, files, release and pre-cutover configuration are retained.

The active backend uses `business-suite.socket` to own `127.0.0.1:8000` and
passes its listener to the single Uvicorn worker with `--fd 3`. Ordinary API
process restarts retain the listening socket: requests queue during startup
instead of receiving connection-refused 502 responses through the public proxy.
This is startup buffering, not a second API worker or a guarantee against
timeouts during a prolonged outage. On the existing host, the service override
is `/etc/systemd/system/business-suite.service.d/socket-activation.conf`.

Before a matching backup or schema migration, stop **both**
`business-suite.socket` and `business-suite.service`, along with the relevant
writer jobs/timers. Otherwise incoming requests can socket-activate the API
during maintenance. The deployment script stops the socket before migrating;
starting the API service starts its required socket. Keep migration maintenance
bounded and verify `/health` before restoring traffic/jobs. To remove socket
activation, stop both units, restore the host/port ExecStart, disable/remove the
socket unit and override, then daemon-reload and start the service.

Private runtime configuration is `/srv/business-suite/shared/backend.env`;
uploads are `/srv/business-suite/shared/besterp-uploads`. The existing local
backup timer runs on the new host and includes the active database, uploads,
runtime settings, portal configuration and Google storage client configuration.

Suite login uses Firebase project `best-erp-a19f3`, with Google and Microsoft
providers enabled and both suite domains authorized. Interns Hub retains its
separate Firebase identity configuration. Microsoft storage uses the existing
Azure storage app, delegated `Files.ReadWrite`, `offline_access`, and `User.Read`,
and callback `https://besterp.app/api/v1/files-storage/oauth/callback`.
Each company administrator connects their own account in Settings → Files &
Storage and chooses a destination folder before enabling cloud uploads.
Credentials remain outside the repository. The Firebase Microsoft client secret
created during this deployment expires on 8 May 2027 and needs renewal before then.

The Interns Hub Google entry update is deployed on both hosts as a separate static
portal build under `/srv/business-suite/portal-builds/google-unified-*`.
Each release's `frontend/interns-hub/dist` symlink selects that build; the former
directory is retained alongside it as `dist.before-google-*`. Runtime `config.js`
is preserved, and older hashed assets remain available for already-open tabs.
`release.json` identifies the change as `intern-google-unified` and records the
source fingerprint. This update changes no database schema or API service.

The Notes cloud-copy feature is deployed on both suite frontends under
`/srv/business-suite/suite-builds/notes-cloud-*`, selected by each release's
`frontend/dist` symlink. Previous assets and `dist.before-notes-cloud-*` are
retained. The new origin API includes `app/api/v1/note_cloud.py` through the
Files & Storage router; the previous router source is retained in
`/root/notes-cloud-deploy`. No schema migration was required. The feature uses
existing OAuth storage accounts, and requires a user to choose Save to cloud;
it does not copy notes during deployment.

Direct personal-account connection from Notes is deployed as
`suite-builds/notes-connect-*` on both hosts. The shared OAuth callback handles
purpose-bound Notes consent in a popup and returns no provider tokens to the
browser. Personal Notes connections are excluded from company storage APIs.
The source module's export grant, company membership and owner checks protect
these operations; company storage administration still requires its existing
privileges. Backend rollback files are in `/root/notes-connect-deploy/before`.

The 10 November row-action and employee-workspace update is deployed on both
suite hosts as `suite-builds/row-workspace-20261110-v2`. It uses production revision
`03e457e3` plus the employee workspace assignment controls, searchable member
pickers, and workspace save-refresh ordering. HRMS employee Account tabs assign
CRM/HRMS memberships through the module workspace APIs and PMS memberships through
its native member API. The shared eligible-people endpoint no longer truncates
at 100 users; company and branch checks remain enforced. No schema migration was
required. Backend rollback source is retained under
`shared/row-workspace-20261110`; previous frontend targets are recorded in each
release's `shared/row-workspace-20261110-v2/frontend-deployed.json`.

## Organization ID and subscription access update — 14 November 2026

BestERP at `https://besterp.app` now uses frontend build
`suite-builds/organization-id-20261114-091004`, based on production revision
`8a970457f46f71adac35138fe51b06c0c9a74441` plus the Organization ID changes.
The primary API has the matching platform metadata changes and subscription
access fix. Administrative reads can inspect locally disabled modules while
subscription exclusions, expiry and suspension remain authoritative.

This scoped deployment requires no schema migration. Source backups, activation
state and verification reports are in `shared/organization-id-20261114-091004`.
The former frontend is retained as
`frontend/dist.before-organization-id-20261114-091004` in the active release, and
previous hashed assets remain available. Public health and assets, authenticated
Organization ID searches and customer details, and verification session revocation
passed. A rolled-back live database probe also confirmed that unlicensed Finance,
expired CRM and suspended CRM reads are denied, with no test records persisted.
Validation included 116 backend tests and an isolated production frontend
type check and build. This deployment changed the primary BestERP site; the legacy
Apache frontend and Interns Hub retain their previous builds.

The profile and organization-switcher follow-up is deployed as
`suite-builds/organization-profile-20261114-092702`. The account profile, suite/module account menus
and company switcher now show the selected organization reference. The access API
returns a reference for each authorized organization; approved signup IDs are
recovered from existing receipts, and non-signup companies use `ORG-C-<company ID>`.
New signup subscriptions retain the reference in metadata. Source rollback files
and authenticated verification reports are under `shared/organization-profile-20261114-092702`.
The prior Organization ID build is retained. Validation passed 58 backend tests,
frontend type checking/build, desktop/mobile browser checks and live access/API
checks. The temporary verification session was revoked; no migration was required.

## Previous shared Apache deployment

The migration to `164.92.119.35` uses the existing Apache server on Ubuntu 22.04,
PostgreSQL 18, Python 3.14, Redis, and one API worker bound to `127.0.0.1:8100`.
Port 8000 belongs to the existing School ERP application. Use the configurations
in `digitalocean/apache/` for this shared host; the Nginx setup below targets a
separate, fresh Droplet.

- Suite: `https://app.indianservers.com`.
- Interns Hub: `https://interns-hub.indianservers.com`.
- Current release: `/srv/business-suite/current`; private settings and uploads:
  `/srv/business-suite/shared`.
- API service: `business-suite.service`; Apache site: `business-suite.conf`.
- Daily local database/document backups: `business-suite-local-backup.timer`,
  02:30 India time, 14-day retention, private `shared/backups` directory.
- The `business-suite` Let's Encrypt certificate covers both hostnames. HTTP
  verification uses `/srv/business-suite/acme`; renewal reloads Apache.
- BestERP uses the shared email transport with dedicated SES SMTP credentials,
  region `us-east-1`, and sender `BestERP <info@besterp.app>`. Interns Hub keeps
  its existing `noreply@indianservers.com` sender and Mail Manager credentials.
  Credentials remain only in private server settings. See [SES deployment
  settings](../docs/ses-email.md). BestERP passed SES SMTP authentication on
  10 November 2026; no new integration emails were sent. The earlier legacy
  sender inbox test does not verify delivery from the new site sender.

The public Cloudflare cutover was verified on 9 November 2026. Both former
Vercel projects are paused. Both login pages and local-database health checks
passed through the public domains, and the HTTP certificate-renewal dry run
succeeded. The existing intern data, account hashes, and private documents were
verified against the final source snapshot.

The migration keeps a verified off-server database/document export. During the
final cutover the source database has a temporary write-blocking trigger so
pooled connections cannot create divergent data. Source-snapshot restores must
remove only `public.businesssuite_migration_write_blocker()` with `CASCADE` in
the restored target before starting it; normal post-cutover local backups do not
contain this gate. Restore into a new database and verify counts, account hashes,
and private files before activation.

## One-time setup

1. Point your suite and Interns Hub DNS names at the Droplet. Allow SSH, HTTP and
   HTTPS in the cloud firewall. Keep PostgreSQL, Redis and port 8000 private.
2. Clone the repository to `/opt/business-suite`, then run:

   ```bash
   sudo bash /opt/business-suite/deployment/digitalocean/setup.sh
   sudo chown -R businesssuite:businesssuite /opt/business-suite
   ```

   Install Node 22+ and npm system-wide using your approved distribution. Verify
   `sudo -u businesssuite node --version`. Configure GitHub read access for the
   `businesssuite` user (a repository deploy key for private repositories) and
   verify `sudo -u businesssuite git -C /opt/business-suite fetch origin`.
   The deploy checkout must be clean and on `main`; local edits are never reset.

3. Create PostgreSQL credentials using `sudo -u postgres psql`:

   ```sql
   CREATE ROLE business_suite LOGIN;
   \password business_suite
   CREATE DATABASE business_suite OWNER business_suite;
   \q
   ```

   Set `max_locks_per_transaction = 256` in
   `/etc/postgresql/<installed-version>/main/postgresql.conf` for the large schema,
   then restart PostgreSQL. Keep PostgreSQL listening on localhost. The database
   owner runs migrations; do not give the app PostgreSQL superuser credentials.

4. Edit the private files in `/srv/business-suite/shared/` as `businesssuite`:

   - `backend.env`: real PostgreSQL credentials (URL-encode the password), HTTPS
     domains/CORS, initial administrator credentials and distinct random
     session/cron secrets. Generate each secret with `openssl rand -hex 32`.
     Keep `SERVERLESS=false`, `DATABASE_AUTO_MIGRATE=false`, `SEED_DEMO_DATA=false`,
     `STORAGE_BACKEND=local`, and the supplied absolute upload directory. Configure
     email before enabling notifications. Carry over required Firebase/provider settings.
   - `frontend.env`: public frontend build settings; API defaults to `/api/v1`.
   - `interns.env`: public portal build settings.
   - `interns-config.js`: public API/suite URLs and existing Firebase web settings.
     This file is copied into the portal on every release. Authorize new domains
     in Firebase. The Firebase configuration is runtime configuration, not a VITE secret.
   - `backup.env`: private DigitalOcean Space endpoint, region, bucket and upload
     credentials. Prefer a different region from the Droplet. Keep this Space
     private: archives contain personal records and configuration secrets.

   Keep these files mode `0600`, owned by `businesssuite`, outside Git. Set bucket
   lifecycle retention deliberately (for example 30 days); the app never deletes
   backups. Store Spaces recovery credentials separately in your password manager.

5. Copy `deployment/digitalocean/nginx.conf` to
   `/etc/nginx/sites-available/business-suite`, replace both domains, and enable
   its symlink in `sites-enabled`. Remove the default site symlink if unused.
   Run `sudo nginx -t`, then `sudo systemctl restart nginx` (also applies its new
   group membership). Enable HTTPS:

   ```bash
   sudo certbot --nginx -d suite.example.com -d interns.example.com
   ```

6. Run the deployment command below. Confirm HTTPS login, portal signup, private
   uploads/downloads and scheduled email. Editing this repository does not configure
   a live server; the setup steps must be performed on your Droplet.

## Every deployment: one command

```bash
sudo -u businesssuite bash /opt/business-suite/deployment/digitalocean/deploy.sh
```

The script locks concurrent deployments, pulls `origin/main` with fast-forward
only, builds an isolated release, validates production settings, stops the API
and timers, backs up PostgreSQL/uploads/configuration to Spaces, migrates the
schema, switches the `current` symlink, restarts and checks `/health`. Only a
healthy release restarts timers. Build work happens before downtime; backup,
migration and startup require downtime. Backups must succeed before migration.
Old releases remain available; monitor disk usage and remove obsolete releases
manually after verifying recovery copies.

Fresh databases receive Alembic's PostgreSQL baseline. API startup creates the
foundation company, roles and first administrator. Existing administrator
passwords are preserved. Demo seeding stays disabled. The separate legacy
Inventory/POS Flask app requires its own database/runtime; this script deploys
the suite API and Interns Hub.

The jobs timer runs scheduled work/reminders every five minutes; the backup timer
creates an off-Droplet recovery copy hourly. Online PostgreSQL dumps are consistent,
but live uploads are not one transaction with the database. Deployment backups
stop the app first for a matching database/files copy. Stop any external writers
too if integrations write directly to the database.

```bash
sudo systemctl status business-suite business-suite-backup.timer business-suite-jobs.timer
sudo journalctl -u business-suite -u business-suite-backup -u business-suite-jobs --since today
sudo systemctl list-timers 'business-suite-*'
```

Monitor failures externally: a timer does not send alerts. Enable DigitalOcean
Droplet backups as an additional layer. Recovery to a specific moment requires
separate PostgreSQL WAL archiving/PITR configuration; this setup is not automatic
failover. Separately used Celery queues need dedicated worker/beat services.

## Existing data and crash recovery

Git stores code and schema migration instructions. It does **not** store live
employees, payroll, applications, passwords or uploads. A process crash can restart
against the existing PostgreSQL disk. Disk loss needs an external backup. Hourly
copies can lose changes since the last successful backup. Monitor them and perform
a restore drill before production cutover.

For an existing installation, stop writes on the old host, export PostgreSQL with
`backend/scripts/postgres_backup.py`, and copy uploads plus production configuration.
Restore into the new empty database before first deployment. Do not replace a live
installation with an empty database. Existing Vercel Blob/S3 files must be exported
to equivalent upload keys in `shared/uploads` and verified through authenticated
downloads before switching to local storage. Legacy storage readers remain for
data migration compatibility; the Vercel deployment workflow has been removed.

To recover from disk loss or failed schema changes:

1. Keep the API and both timers stopped. Recreate the host and an empty target
   database. Never restore directly over an existing production database.
2. Download one recovery prefix from the private Space onto a secure recovery
   host: `database.dump`, `files.tar.gz`, `manifest.json`. A prefix without a
   manifest is incomplete. Compare file SHA-256 hashes to the manifest.
3. Install Python dependencies in a venv. Extract the trusted archive into a private
   staging directory. Restore `config/*` into `shared/` with mode `0600` and
   `uploads/` into `shared/uploads`, owned by businesssuite. Keep existing files
   separately until recovery is verified. Restore backup credentials from your
   password manager; they are intentionally not archived.
4. Link `backend/.env` to the restored settings. From `backend`, with the configured
   target an **empty** PostgreSQL database:

   ```bash
   ../.venv/bin/python scripts/postgres_restore.py /secure/recovery/database.dump
   ```

5. Run the deployment command to build the intended revision and migrate. Verify
   record counts, login, payroll, private documents and both domains before enabling
   traffic. Record the deployed Git SHA alongside the backup's release name.

If deployment failed before changing the schema, the previous `current` release
is retained; inspect the error and restart it and timers once fixed. After schema
changes prefer a forward fix: code-only rollback may be incompatible. Restoring
the pre-deployment database loses newer writes, so keep traffic stopped and choose
a matching database/files/code recovery point.


## Mobile POS and scheduling preview — 17 November 2026

BestERP now serves `suite-builds/mobile-pos-20261117-173930-v4`. This is a scoped
frontend release based on production revision `513a38555e12`, with mobile POS
pagination, a dedicated compact terminal, POS-first Sales/Create navigation,
removal of the home Continue working section, and the appointments POS label.
The current production checkout and scheduling API behavior is retained.
No backend restart or schema migration was performed.

Rollback target and uploaded source/build archives are retained in
`shared/mobile-pos-20261117-173930`; the original frontend target is recorded in
`previous-frontend.txt`. Runtime app-config.js, the model mount, and previous
hashed assets remain available. Verification covered seven mobile viewports,
appointment cart pagination, Products search/filters, full AppLayout, TypeScript,
production builds, live geometry and public health.

At the user's request, 20 explicitly labeled DEMO Calendar bookings were created
through the application API for Indian Servers / Main, on 18–23 November 2026.
The demo setup contains one customer, two staff and two linked provider resources;
there are no demo payments, invoices or PMS tasks. Record IDs and dates are kept
in `shared/mobile-pos-20261117-173930/demo-calendar-records.json`.


## Mobile Appointments and Calendar — 17 November 2026

The active suite frontend is `suite-builds/mobile-bookings-20261117-v2`, retaining
the preceding POS/home/Create changes. Mobile appointments keep native record
actions and date controls while paging complete records. Calendar uses a compact
day agenda and All bookings view, with adaptive record pagination and a filter
dialog. Setup navigation and duplicate page headers no longer occupy the first
mobile record page. Desktop booking views and all backend operations are retained.

The five-viewport regression traverses all 20 records in each view, checks complete
card bounds and absence of scroll containers, and verifies that single-record
pagination is absent. Source/build archives and the prior frontend target are in
`shared/mobile-bookings-20261117`. Deployment required no backend restart or schema
changes. The 20 demo bookings created previously were reused without alteration.


## Mobile booking workflows — 18 November 2026

The active frontend is `suite-builds/mobile-booking-workflows-20261117`.
New appointment and ordinary/grouped rescheduling use dedicated mobile surfaces;
visit/payment details and calendar details use adaptive steps when content exceeds
the available screen. Native field state, validation, request identity, scheduling
revision checks and submit handlers remain in place. Short forms have no step bar.

Five-size workflow verification covers draft preservation, invalid-field focus,
reschedule request payloads, 18-receipt traversal and absence of scrolling/clipped
controls. The 20-record appointment/calendar regression also passes all five sizes.
Rollback target, build/source archives and live verification are retained in
`shared/mobile-booking-workflows-20261117`. No API restart, schema change or demo
booking change was required for this frontend deployment.

## Mobile appointment mockups — 18 November 2026

BestERP serves `suite-builds/appointments-mobile-20261118-v4`. This release builds
on the deployed POS and mobile booking workflow baseline, adding the mobile
Schedule calendar/week strip, physical Resources view, and New appointment sheet.
The appointments route bypasses the generic SRM mobile wrapper to avoid duplicate
headers. Working hours containing seconds are normalized before calendar placement.

Required scheduling API compatibility updates include resource editing, prebooking
availability/choices, customer context, and draft/workflow support. They use existing
records and permissions; no database migration was performed. The API restart retained
the existing socket. Source/build archives, the original backend files (`before/`),
and activation records are retained in `shared/appointments-mobile-20261117`.
The prior frontend `suite-builds/mobile-booking-workflows-20261117` remains available.

Validation: TypeScript and production build passed; 28 targeted backend tests passed
and one was skipped. Fixture checks covered 360/390/430px mobile and 1024/1586px
larger screens, availability failure/retry, booking conflict and successful booking.
Live browser verification used a temporary session and existing demo records; no
customer, appointment, payment, or physical resource was created during verification.
Live screenshots and the verification report are under `output/appointments-mobile-live`.
Live acceptance passed all three states at 360, 390 and 430px, with four existing
18 November bookings, correct time placement, resource filtering and editor access,
customer/service selection, draft-sheet close, no browser/API errors, and no page
overflow. This branch currently has no physical assets and the selected service has
no eligible employees; confirmation correctly remains unavailable. The temporary
verification session was revoked after testing.


## Appointment identity — 18 November 2026

The active frontend is `suite-builds/appointment-service-customer-20261118`.
Appointment entry no longer asks for a Title. Cards and visit headings identify
appointments by service and customer; an internal compatibility label is generated
from the selected names when creating a booking. Other record types retain their
own name/title inputs. Existing appointment data is unchanged.

The five-size workflow and 20-record mobile regressions pass. TypeScript and the
production build passed. Build/source archives and the prior frontend target are
retained in `shared/appointment-service-customer-20261118`. No backend or database
changes were made.

### Mobile Create Customer — 2026-11-18
Deployed customer-mobile-20261118. Fixed viewport customer editor with pinned Cancel/Save & new/Save buttons and adaptive steps within sections. Verified five mobile sizes (320x568 through 767x1024), reduced keyboard viewport, optional address/bank rows, retained drafts and mocked save. Shared appointment workflow regression, TypeScript and Vite build passed. Live 390x844 verified all four tabs and seven section pages: no scroll containers or clipped controls; short Legal & tax has no steps. No live customer was saved. Rollback: restore frontend/dist symlink to /srv/business-suite/suite-builds/appointment-service-customer-20261118.


## Reference mobile appointments with demo data — 18 November 2026

The verified appointment release is `appointments-mobile-demo-20261118-v11`.
Schedule, Resources, and New appointment use the supplied white/lavender/violet
mobile composition. The latest customer editor and service/customer naming changes
are retained. Mobile filters use compact sheets, resource cards report actual booked
time, and the appointment sheet retains a fixed confirmation action and compact summary.

Configured two existing demo HRMS staff (169 and 170) as eligible for System Repair
(service 9), without changing policy 1 or its 30-minute duration. Added three physical
assets in Indian Servers / Main: DEMO Mobile Chair 01 (32), DEMO Mobile Room 01 (33),
and DEMO Mobile Equipment Kit (34). Employees remain separate from physical asset CRUD.

A mobile UI POST created appointment 35 for DEMO Calendar Customer on 19 November
2026, 09:00–09:30 Asia/Kolkata, using employee 169 / provider 10 and equipment 34.
The actual service estimate is INR 333. No invoice, PMS task, or confirmation channels
were attached. All 20 earlier appointments retain their original status, revision,
timing and data; the branch has 21 appointments after this test.

Live testing exposed and resolved missing capacity/draft conflict-check compatibility,
optional waitlist inputs blocking the parent appointment form across timezone rollover,
and null customer phone values crashing the confirmation view. Original request replay
returns booking 35 without duplication; a different request for its occupied interval
is rejected with HTTP 409. Independent workflow form ownership prevents hidden optional
inputs from blocking appointment confirmation. The null-contact case has a helper regression.

TypeScript, production build, phone/message/calendar utility checks, two targeted backend
suites (33 passed with one skipped; 33 passed), and mobile fixture checks passed. Live
verification covers 360/390/430px, confirmation/recovery, persistence after reload, all
three schedule views, real resource categories, and absence of viewport overflow and
browser/API errors. Evidence is in `output/appointments-mobile-full-flow`; final
three-screen captures are in `output/appointments-mobile-live`.

Source/build archives and backend rollback files are retained in
`shared/appointments-mobile-20261117`. No schema migration was required. Retained
identical hashed assets were hard-linked to recover 2,342,145,874 bytes while preserving
all releases; subsequent appointment activations reuse identical assets by hard link.

### Mobile Add Product / Add Service — 2026-11-18
Deployed catalog-mobile-20261118. Catalog creation uses a fixed mobile viewport, pinned Cancel/Save actions (including Save and configure scheduling), and measured steps while keeping original controls mounted. Product/service titles now match the selected type. Verified both types at 320x568, 360x640, 390x844, 430x932, 767x1024 plus keyboard viewport; expanded follow-ups, pricing rows, image and custom fields, invalid-field reveal, retained values, and mocked save/configure payloads passed. TypeScript and production Vite build passed. Live product and service each traversed five pages at 390x844: no page/dialog scrolling, scroll containers, clipped controls or action buttons. No live catalog records saved. API health healthy. Rollback: restore frontend/dist symlink to /srv/business-suite/suite-builds/customer-mobile-20261118.


### Two-page mobile Product / Service — 2026-11-18
Deployed catalog-two-pages-20261118. Replaced automatic catalog pagination with exactly Essentials and Optional settings. Both use two fields per row. Essentials has all required inputs and Save; services include booking mode/duration, employee categories/subcategories, recurrence, tags and product subcategory. Optional settings share page two through a settings picker and single-row editors for repeatable values. Mobile Save also writes the native service booking policy after saving the catalog item; an interrupted policy save retains the item ID so retry updates it without creating a duplicate. Subcategory metadata is preserved in catalog custom fields. No backend or database changes deployed. Five mobile sizes plus reduced keyboard viewport, expanded optional follow-ups, pricing/images/custom fields, first-page save and policy retry passed with mocked APIs. Separate optional-settings checks passed at 320x568. TypeScript and production build passed. Live 390x844 checks confirmed two steps, no scroll containers or clipped controls in both Essentials forms and six optional setting groups. No live catalog record was saved. Health healthy. Rollback: restore frontend/dist symlink to /srv/business-suite/suite-builds/catalog-mobile-20261118.



### Standard SRM navigation and local data — 18 November 2026

The appointments, service scheduling and POS routes use AppLayout's standard navigation.
Appointment/resource switches remain local page controls. Customer picker options show
labeled mobile, email and record ID values from the authorized response and retain
listbox/keyboard behavior. Product creation exposes essentials directly, with native
expandable optional sections and a pinned save action; existing service scheduling setup
is preserved. Invalid optional inputs expand their section before focus.

Browser record caching now mirrors server-approved persistent snapshots to SQLite WASM
in an OPFS worker. SQLite startup runs in the background; an existing IndexedDB snapshot
can render immediately. IndexedDB also remains the cross-tab invalidation fence and
fallback for unavailable storage or a second tab without the OPFS pool. Existing
user/session/company/branch/permission scoping, no-store rules, limits and server
transaction validation remain in force. This is a bounded read cache, not a full database
replica or an offline financial authority.

Favorites refresh when stale on revisit/focus instead of polling every 30 seconds.
Automatic record synchronization skips inactive views and checks stable reference data
every two minutes; explicit refresh and permission checks retain their behavior.
POS held bills poll only while open, native catalog refresh uses the shared cache, and
optional product follow-up/workspace/medicine options load on demand. POS catalog startup
loads at most one 200-row page; search is debounced and runs on the server, and Load more
explicitly requests additional pages. Checkout retains selected cart product information
and authoritative server validation.

Candidate source, deployment guard and regression evidence are retained under
`.local/srm-speed-20261118`. Live screenshots and verification are written to
`output/srm-standard-fast`. No backend or database schema change is included.

### HRMS employee hierarchy and mobile selectors — 2026-11-18
Deployed employee-taxonomy-20261118-v4 with scoped backend patches against downloaded production sources. New HRMS management: /hrms/employee-categories, linked from Employees and category assignment controls. Stores company-owned, versioned categories/children in existing suite_service_policies; no schema migration. Existing employee category names remain available. Existing managed names are immutable; archive instead of renaming/removing them. Updates require native employee_update permission or platform superuser authority, deny read-only writes, retain edit-version checks through background refresh, and produce access audits. Operational dropdowns use this registry, support multiple selections, filter active children by selected parents, and clear irrelevant selections after parent removal. Native service filters match parent categories to their HRMS children and exact selected child rules. The catalog remains two pages with two fields per row. Menu results use search and four-option pages only when needed. No live taxonomy/catalog records were saved during verification.
Validation: 14 backend tests; product and service flow checks across five mobile sizes (including filtering, multi-select, cleanup, search/pagination, popup bounds, saved native policy values and no duplicate retry); HRMS management across five sizes, including optimistic-conflict handling; TypeScript and production build passed. Live source-backed dropdown checked at 390x844; expanded HRMS management checked at 320x568, with zero editor overflow/clipped controls and both action buttons clear of mobile navigation. API health healthy.
Rollback: restore frontend/dist to the target in /srv/business-suite/shared/employee-taxonomy-20261118/previous-frontend.txt. Restore the six backend source files from backend-original.tar.gz in that directory, then restart business-suite.service. Existing settings records need no migration or removal. Final source and verification artifacts are retained alongside the backup.


Fast cached form startup also exposed an initial mount race in SmartCreationProvider.
Its identity cleanup now runs only after an actual identity change, preserving a child
dialog opened during the first effect pass. A regression checks that immediate creation
remains open and that changing the actor still clears it. Held bills revalidate on opening
and then poll while visible.

Final isolated checks use actual production APIs and cover all four routes at 360, 390
and 430 px. A separate 65-second idle check observed three maintenance reads (access,
setup readiness and notifications), no favorites/catalog/held-bill polling, and a stable
open product form. The user selected this chat's standard-menu version as the final frontend; see the deployment result below.


Final production release: `srm-standard-fast-20261118-v12` (18 November 2026).
Published with employee taxonomy v4 and stock alerts/reports v2 functional additions
retained. All 1,496 backend Python files match the pre-publication combined baseline.
The appointment modal footer avoids the standard dock offset, and the POS workspace
reserves the standard header/navigation area without clipping product names, prices or
purchase controls. All four requested routes passed production browser checks at
360/390/430 px; resource and populated appointment-form captures are included.
The 65-second idle check retained the product form and excluded favorites polling.
Existing booking request replay and conflict prevention passed; the original 20 bookings
and demo booking 35 remain unchanged. Temporary verification credentials were revoked.
Final evidence: `output/srm-standard-fast/verification.json` and adjacent reports/screenshots.


## Catalog category selection — 18 November 2026

Deployed `catalog-categories-20261118T135859` to BestERP. Product and service
editors use selection-only category and subcategory controls, with multiple
categories per item. Manage categories provides create, rename, and delete
operations; assigned choices must be unassigned before deletion. Existing
category names remain selectable. Stable IDs and category labels are stored in
product metadata, and the company taxonomy uses the existing versioned service
policy table. No schema migration was required. Renames update assigned labels;
filtering and grouped/list/card views include multiple category assignments.

Validation: shared catalog tests (26), taxonomy and selected business-pack tests
(57), six product/service browser scenarios at 320px, 390px, and desktop widths,
TypeScript, and the scoped production Vite build passed. The API health check
passed after restart, and SES remains disabled. Previous frontend:
`/srv/business-suite/suite-builds/pos-booking-qa-20261118-v4`. Scoped source backups,
activation manifest, and rollback information are retained under
`/srv/business-suite/shared/catalog-categories-20261118T135859`.


## Service scheduling and employee-category assignments — 18 November 2026

Deployed `service-category-scheduling-20261118T142409`, preserving the
`mobile-speed-sync-20261118-v1` performance release. Service editors keep base
pricing and optional additional prices in Basic details; Scheduling contains
appointment mode, duration, and eligible employee categories/subcategories.
New services save their item and scheduling policy atomically. Existing-item
revision conflicts roll back the item edit as well as scheduling changes.

HRMS Employee categories now displays and edits the services assigned to each
category/subcategory using the same branch/context-scoped booking policy.
Category and subcategory create, edit, archive and delete operations are
available. Names used by employees or services must be unassigned before being
renamed or deleted. Taxonomy and service-link changes commit together, with
both HRMS and scheduling permissions enforced. No schema migration is required.
Services configured for no booking remain saleable without an appointment,
while attempted bookings are rejected.

Validation passed 53 taxonomy/catalog/scheduling-options tests, 89 selected-pack
and checkout tests, the final five atomic scheduling regressions, desktop/mobile
CRUD workflows, TypeScript and the scoped production build. Production API
imports and health passed after restart; SES remains disabled. Scoped source
backups and activation metadata are retained under
`/srv/business-suite/shared/service-category-scheduling-20261118T142409`.

Live browser verification passed for service pricing/scheduling and desktop/mobile
HRMS category-service management. No catalog records were modified. The temporary
verification session was revoked and its credentials removed.
