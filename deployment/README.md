# DigitalOcean Ubuntu Droplet

Production uses Ubuntu 24.04, PostgreSQL, Redis, Nginx, Python 3.12 and Node 22+.
The suite and Interns Hub are built from the same Git revision. One API worker
preserves the current in-process WebSocket behavior. Allow enough RAM and disk
for both frontend builds and retained releases.

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
