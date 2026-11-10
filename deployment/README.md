# DigitalOcean Ubuntu Droplet

Production uses Ubuntu 24.04, PostgreSQL, Redis, Nginx, Python 3.12 and Node 22+.
The suite and Interns Hub are built from the same Git revision. One API worker
preserves the current in-process WebSocket behavior. Allow enough RAM and disk
for both frontend builds and retained releases.

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
