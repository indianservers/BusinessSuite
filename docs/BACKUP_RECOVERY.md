# BusinessSuite backup and recovery

Open **PMS → More → Backup & recovery**, **Settings → Backup & recovery**, or the workspace **Recovery** button.

## Admin workspace reset

**More → Workspace reset & restore** (also linked from PMS Admin) includes all workspaces in the Admin's organization, whether created by an administrator or a user. A workspace Owner/Admin membership alone does not grant the global reset permission; the actor needs the `pms_admin` permission or system-superuser status. Other organizations are excluded even for system superusers using this organization-scoped control.

The page previews the active workspaces and their owners. Type `RESET ALL WORKSPACES` to submit that preview. A changed workspace list returns a conflict and requires a new preview. Reset writes archive markers, preserving workspace IDs, projects, tasks, memberships, messages, files and financial records. Archived workspaces are excluded from normal workspace/project access, invitation acceptance, dashboard queries and unread messaging counts; automatic workspace savepoints skip them. Admins can restore each workspace with its original records and permissions from the same page. This feature does not reset users or delete business data. Apply migration **20261024_009 / pg_20261024_009** to install the archive-marker table after recovery migration 008.

## Recovery levels

- **Undo / redo**: durable, per-user workspace task history for normal task creation, safe content edits and soft-deletion. The workspace toolbar supports Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z and Ctrl+Y outside text inputs/dialogs. Text inputs retain native undo. A new edit discards that user's redo branch. Newer changes, lost permissions, missing board columns or removed assignees stop recovery with a conflict instead of overwriting data. Undoing creation soft-deletes the task; redo restores it.
- **Named savepoint**: workspace owners/admins can save and export workspace-owned PMS rows with a checksum. Private chat/assistant history, personal preferences, integration credentials, invitation tokens and private dashboard definitions are excluded from this workspace export. These records remain in the restricted full-system database archive. Workspace exports contain attachment metadata; full-system archives contain attachment bytes.
- **Restore task content from a savepoint**: preview changed/missing/new tasks, then type the workspace name to confirm. A current-state hash prevents stale previews. A safety savepoint is created in the same transaction before changes. Restore covers the displayed task fields, dates, status, assignments and soft-delete state; it preserves newer tasks, projects, comments, documents, memberships, financial records and integrations. It does not import arbitrary uploaded JSON or recreate permanently deleted tasks. Undo/redo history is invalidated after a savepoint restore.
- **Full-system archive**: system superusers only, since the archive contains every tenant and every module. SQLite uses its online backup API and an integrity check. PostgreSQL uses custom-format `pg_dump` and validates the archive listing. Database and authoritative uploads from the configured local directory, S3 prefix or private Vercel Blob prefix are streamed into a ZIP. Every member has a size and SHA-256 checksum; verification runs before atomic publication and again on download/restore. Provider failures do not publish a successful archive.

Undo does not reverse financial postings, sent messages, external integrations, project/sprint structure, time accounting or recurrence workflows. Recurring-task status changes that can spawn follow-up work are excluded from the single-task undo stack. Use module-native reversal controls or full offline recovery for those cases. Only newly recorded operations have undo history.

Workspace savepoints are stored in the application database. Download them or maintain full archives on separate storage for disaster recovery. Automatic retention removes only old automatic copies; manual and pre-restore copies are kept. Undo branch records remain as evidence.

## Install

Apply migration **20261024_008** (SQLite chain) / **pg_20261024_008** (PostgreSQL chain), following the project's existing migration deployment procedure. Both are additive and replayable; downgrade preserves recovery records.

Full archives require a durable server/worker with read access to the database, configured object store and a persistent private backup volume. Set in its environment or `backend/.env`:

```dotenv
SERVERLESS=false
BUSINESSSUITE_BACKUP_DIR=/private/durable/businesssuite-backups
BUSINESSSUITE_BACKUP_SCHEDULER=true
```

The backup volume must be separate from `UPLOAD_DIR`, outside the source checkout, accessible only to the service account and system backup administrators. Use encrypted persistent storage and retain off-host copies. Application encryption/signing keys and service configuration are deliberately not exported; store them separately in the organization's secret recovery system. Restore encrypted application credentials with the original keys.

Enable each workspace schedule and the full-system schedule in the Recovery page. Choose an interval from 1–720 hours and 2–90 retained automatic copies. Enabling a policy alone does not provision a worker. The optional long-running application worker checks every minute; overdue jobs run after restart. Multi-worker PostgreSQL deployments use row locks for workspace policies and filesystem leases for full archives on the same persistent volume. Full-archive policy updates use the same scheduler lease. Separate hosts must share the backup volume/leases or run one designated backup worker.

Alternatively, keep the in-process scheduler disabled and schedule this command every five minutes with cron, systemd or Windows Task Scheduler, using the backend working directory and the service account:

```sh
python scripts/data_recovery.py --due
```

The scheduler runs independently of browsers. Last successful automatic timestamps appear in Recovery; failures log through the server/worker logger and do not advance success timestamps. Workspace automatic policies recheck that their configuring user is still active and a workspace owner/admin. Re-save the schedule with an active admin after that user's access is removed.

Vercel/serverless instances intentionally return 503 for full local archive operations: temporary instance storage cannot protect the application. Configure a durable worker with the same database/storage configuration and `SERVERLESS=false` to execute the CLI. Workspace savepoints still work through the serverless API. Full archives created by an external worker can be managed/downloaded through a durable backend sharing that private backup volume; the serverless instance does not expose its local filesystem as if it were that volume.

## Manual full backup and restore drill

From `backend`, with the correct worker environment:

```sh
python scripts/data_recovery.py --backup
python scripts/data_recovery.py --verify /private/durable/businesssuite-backups/ARCHIVE_ID.zip
python scripts/data_recovery.py --restore /private/durable/businesssuite-backups/ARCHIVE_ID.zip --target-directory /private/recovery/drill-20261024
```

Restore requires a **new** target directory. It rejects unexpected members, path traversal, duplicate ZIP entries and checksum errors. It never overwrites a live database or upload directory. For SQLite, the extracted `database.sqlite3` is the recovered database. For PostgreSQL, configure an **empty** target database, then run the existing `python scripts/postgres_restore.py /private/recovery/drill-20261024/database.dump`. Restore `uploads/` together with that database, or republish it to the configured private S3/Vercel Blob prefix using the organization's storage recovery procedure. Verify authentication, important records and attachment downloads before switching traffic. Preserve the current database and storage before cutover.

Database snapshots are consistent within their database engine. Database and external file storage do not share a distributed transaction: pause application writers for a strict cross-store point-in-time backup and during cutover. Archive checksums detect corruption; they are not a cryptographic signature proving who created an externally supplied archive. Only restore trusted system backups.

A crashed process can leave `.backup.lock` in the backup root or `scheduler/`. Inspect the recorded PID/start time, verify no backup process is active, then remove that specific stale lock. Live leases are never automatically stolen. Corrupt archive metadata is shown as unreadable; an integrity failure blocks downloading/using the archive.

## Verification

`backend/tests/test_pms_recovery.py` covers API permissions, undo/redo ordering and branching, structural/concurrent conflicts, assignment revocation, preview hashes, safety checkpoints, retention, scheduler access rechecks, full SQLite/file restore, corruption, leases, S3 streaming/failure and replay of both migration functions. `playwright/pms-recovery-live.spec.ts` uses the real loopback API to create/edit a task, undo/redo, create/restore/export a savepoint and check the page at 375px width. Live PostgreSQL/cloud-provider acceptance remains a deployment restore-drill requirement; local tests use SQLite and a simulated S3 provider.
