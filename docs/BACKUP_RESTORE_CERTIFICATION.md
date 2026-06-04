# Backup Restore Certification

Certification date: 2026-06-03  
Scope: Production release hardening - MySQL backup and restore  
Source database: `ai_hrms` and `ai_hrms_fresh_cert`  
Restore database: `ai_hrms_restore_cert`

## Executive Result

| Check | Result | Evidence |
|---|---|---|
| Timestamped backup script exists | PASS | `backend/scripts/mysql_backup.py` |
| Restore script exists | PASS | `backend/scripts/mysql_restore.py` |
| MySQL production database supported | PASS | Scripts read app MySQL settings and support target database override. |
| Backup file created | PASS | `backups/ai_hrms_backup_20260603_222538.sql` |
| Restore into clean database | PASS | `ai_hrms_restore_cert` recreated and restored. |
| Restored data verified | PASS | Master, attendance, leave, payroll, payslip-related, bank export, statutory export and audit data present. |

Final backup/restore status: **PASS**.

## Scripts Added

| Script | Purpose |
|---|---|
| `backend/scripts/mysql_backup.py` | Creates timestamped SQL backup files from a MySQL database. |
| `backend/scripts/mysql_restore.py` | Restores a SQL backup into a target MySQL database, with optional clean recreation. |

## Certified Commands

```powershell
python scripts\mysql_backup.py --database ai_hrms --output-dir backups
python scripts\mysql_restore.py --database ai_hrms_restore_cert --file backups\ai_hrms_backup_20260603_222538.sql --recreate
```

## Restore Verification

| Data Area | Table | Restored Count | Result |
|---|---|---:|---|
| Company | `companies` | 4 | PASS |
| Branch | `branches` | 3 | PASS |
| Department | `departments` | 2 | PASS |
| Designation | `designations` | 2 | PASS |
| Employee | `employees` | 28 | PASS |
| Attendance | `attendances` | 24 | PASS |
| Leave | `leave_requests` | 2 | PASS |
| Payroll run | `payroll_runs` | 4 | PASS |
| Payroll records / payslip base | `payroll_records` | 20 | PASS |
| Bank advice | `payroll_bank_exports` | 1 | PASS |
| Statutory exports | `statutory_exports` | 1 | PASS |
| Audit logs | `audit_logs` | 3407 | PASS |

## Notes

The environment did not depend on external `mysqldump` or `mysql` CLI binaries. The scripts use PyMySQL so the backup/restore path can run from the application runtime environment where Python dependencies are available.

## Certification Decision

Backup and restore is **certified PASS**.

