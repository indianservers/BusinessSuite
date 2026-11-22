# Business Suite offline for Windows

Open **Business Suite.exe** and choose **Open local workspace**. On first launch, enter an administrator email and set a password in the setup window. Business Suite starts PostgreSQL and the local API, runs the suite's database migrations, and opens the workspace in your default browser. Sign in with the credentials you set. Keep the setup window open while working. Press Ctrl+C in that window to stop the local workspace.

The desktop package includes the Windows app, browser UI, Python API, and PostgreSQL binaries. The API listens on 127.0.0.1:15434 and PostgreSQL listens on 127.0.0.1:15435. Your database, uploads, and instance secrets live under %LOCALAPPDATA%\Business Suite\workspace and persist across restarts and package updates. Keep a backup of this folder while the local workspace is stopped.

## Sync personal notes

Enter and save the HTTPS company website under **Remote**. Complete the company setup checklist in the local workspace. With the workspace running, open **Sync**, sign in to both accounts with the same email, and click **Sync notes**. Both installations must run a Business Suite version with the desktop notes sync API and its PostgreSQL migration.

Sync copies new standalone private personal notes. Any change that would overwrite an existing note, including moving it to or from trash, waits for review even if only one side changed. Select the note to compare both versions, then choose which version to keep. Notes linked to projects, tasks, or folders, shared notes, notes with attachments, and other business records are outside this sync flow. Features that call external providers require internet access.

## Compare existing business records

From **Sync**, select **Compare business records** to compare accessible customer profiles, projects, inventory item definitions, and ledger accounts. The preview looks for possible matches by customer GST number or email, project key, SKU, and ledger code. It shows selected fields from each side and flags unmatched and ambiguous records. The preview does not apply changes. Inventory movements, voucher postings, balances, and relationships are not included in the comparison.

## Build the portable package

From the repository root, run PowerShell with:

    ./Desktop/Build-OfflinePackage.ps1

The build uses the repository's backend virtual environment, frontend node_modules, .NET SDK, and the Windows PostgreSQL distribution under .local/postgresql/pgsql. Pass -Python and -PostgresRoot to use other build inputs. The script prints the package directory under .local/desktop-release. Distribute that whole directory together.
