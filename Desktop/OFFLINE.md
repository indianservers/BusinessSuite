# Business Suite desktop deployment

The desktop executable connects directly to PostgreSQL. Schema setup runs as a separate, one-time command. Build and verify the package against an isolated database before distributing it. Track current coverage and role limitations in [Desktop parity](PARITY.md).

## Build the offline package

Use Windows with the .NET Framework 4.8 developer targeting pack, .NET SDK, installed Telerik WinForms assemblies referenced by the desktop project, a populated local NuGet cache, and the repository's existing 64-bit backend virtual environment and PostgreSQL binaries.

```powershell
dotnet restore 'Desktop/Business Suite/Business Suite.slnx' --ignore-failed-sources -p:PlatformTarget=x64 -p:NuGetAudit=false
./Desktop/Build-OfflinePackage.ps1
```

The script prints a new package directory under `.local/desktop-release`. Use `-OutputRoot 'D:\BusinessSuiteReleases'` to build the package on another volume. The solution build still needs space on the workspace volume. Copy the full directory to the target PC. The target needs Windows with .NET Framework 4.8 or later. The database server needs PostgreSQL and its Windows runtime prerequisites if you use the bundled binaries. Python is bundled for schema setup. The desktop executable uses the bundled Npgsql and Telerik runtime assemblies.

## Same-PC PostgreSQL

Use an existing local PostgreSQL service or initialize a dedicated cluster with the bundled binaries. Run the database under a Windows account with write access to its data directory. Keep that directory outside the application folder.

```powershell
$desktopPgData = Join-Path $env:LOCALAPPDATA 'Business Suite\postgres'
.\postgresql\bin\initdb.exe -D $desktopPgData -U suite_schema_admin --encoding=UTF8 --locale=C --auth=scram-sha-256 -W
.\postgresql\bin\pg_ctl.exe -D $desktopPgData -l "$desktopPgData\server.log" -o "-h 127.0.0.1 -p 15435 -c max_locks_per_transaction=256" -w start
```

Verify the destination before creating the database. Confirm that the query returns `postgres`, `suite_schema_admin`, `127.0.0.1` and `15435`.

```powershell
.\postgresql\bin\psql.exe -X -h 127.0.0.1 -p 15435 -U suite_schema_admin -d postgres -c 'SELECT current_database(), current_user, inet_server_addr(), inet_server_port()'
.\postgresql\bin\createdb.exe -h 127.0.0.1 -p 15435 -U suite_schema_admin business_suite
.\python\python.exe .\backend\Initialize-DesktopDatabase.py --host 127.0.0.1 --expected-address 127.0.0.1 --port 15435 --database business_suite --username suite_schema_admin --sslmode disable
```

The initializer prompts for a password, verifies the server identity, and runs the existing migrations on the verified connection. For an existing Business Suite database, use the same migration procedure to preserve established records.

On an empty database, a database administrator can provision the initial company, branch, and Suite administrator in the same command. First create a PostgreSQL LOGIN role named after the administrator's lower-case email and set its password securely with `psql`'s `\password` command. Run the initializer with `--bootstrap-admin admin@yourcompany.example --company-name "Your Company" --branch-name "Head Office"` in addition to the connection arguments. It prints the new company and branch IDs to use in the desktop environment file. Grant the PostgreSQL login the required application privileges before opening the desktop app.

For an existing schema initialized through migrations alone, append `--seed-permission-catalog` to the initializer command to add missing canonical permission definitions. This preserves existing definitions and role assignments. Assign the permissions to the appropriate roles through your existing access administration process. Initial company bootstrap includes the catalog.

## LAN PostgreSQL

The database administrator provisions the database on the LAN server, enables TLS with a certificate matching its hostname, configures the listening address and client subnet in PostgreSQL and the firewall, and runs the initializer using the verified server IP, `--sslmode verify-full` and `--sslrootcert` for the issuing CA where needed. Each workstation uses the certificate hostname for `Host`, the server IP for `BUSINESS_SUITE_POSTGRES_EXPECTED_ADDRESS`, and `SSL Mode=VerifyFull`. The issuing root must be trusted by Windows for the desktop process. On .NET Framework 4.8, Npgsql 8.0.9 builds its chain using Windows trust, even when a `Root Certificate` file is supplied. Use your existing enterprise PKI or ask your administrator to provision trust through the normal workstation policy. [Npgsql 8.0.9 certificate validation](https://github.com/npgsql/npgsql/blob/v8.0.9/src/Npgsql/Internal/NpgsqlConnector.cs#L1540-L1580)

## Desktop connection and identity

Copy `desktop.env.example` to `%LOCALAPPDATA%\Business Suite\.env`. Set the host, port, database, PostgreSQL application username and password, expected server IP, and existing company and branch IDs. Use the port you configured on the server. Per-process environment variables with the same keys take precedence over file values. Keep the environment file private to the Windows user. Open **Tools → Settings** and select **Test connection** to verify the endpoint. Choose an authorized company and branch and select **Apply** to use that scope for the current session.

The desktop maps the authenticated PostgreSQL login name to the exact email of an existing active Suite account. The database login uses privileges tailored to the available workflows. Keep SQL administration and schema ownership separate. Suite membership and branch checks in the executable govern its own queries. Database administrators must separately constrain access granted to any login that can connect directly through other clients. PostgreSQL application grants, ongoing account administration, Suite MFA and SSO sign-in, fresh-machine prerequisite verification, and physical LAN verification remain open.

Account for existing trigger dependencies when validating a restricted PostgreSQL writer. In isolated QA, accepting a workspace invitation inserted branch ownership records. The installed ownership guards also read `srm_pos_cash_movements` and `business_pack_record_ownership`, so the restricted test login needed those reads before the transaction could succeed. Validate the grants under your database policy for each enabled workflow.

CRM company and contact lists, exports and selectors, and the Communication Center draft recipient picker read `srm_anonymous_cash_accounts` and `suite_contact_identity_links` to keep dedicated POS walk-in identities private. Include those read dependencies when validating the corresponding permissions for restricted logins.

The composer’s **Check email opt-out** and **Consent history** actions read `communication_opt_outs`, `communication_consents`, and `security_resource_ownership`. Recording a choice also inserts its company ownership and branch audit. **Block email to address** inserts into both consent and opt-out tables. Validate these privileges for restricted composer and consent-manager logins.

Retained quotation PDFs use the same relative document paths on every workstation. On one PC the default document directory is `%LOCALAPPDATA%\Business Suite\uploads`. When multiple workstations share a database, set `BUSINESS_SUITE_UPLOAD_DIR` to the same absolute UNC path on each workstation. Grant the intended Windows accounts access to the share using your normal file-server policy. Include the document directory in the same backup schedule as the database.

In **Products and Services**, choose **Export** and select JSON, CSV, or Excel in **Save as type**. The desktop writes the file locally without requiring Microsoft Excel or a web connection. Excel limits cell text to 32,767 characters. JSON and CSV retain longer catalog descriptions.

If an appointment submission is interrupted, reopen Appointments under the same Windows account and database scope and select **Resume booking**. **Check request status** reads the existing confirmation from PostgreSQL. **Retry same booking** resends the original request when the booking was never committed. The saved request is protected by the Windows account and stored in that workstation's local profile.

In **Booking confirmation**, choose **Print appointment slip** to use a printer driver installed on the workstation. The print rendering was verified with Microsoft Print to PDF using the Windows preview controller.

## Verify a built package

The offline package builder runs the package check after staging the application and database tools and includes the verifier in the package. From the repository root, run the package check in 64-bit Windows PowerShell. Supply the package directory and executable from the corresponding Release build.

```powershell
powershell.exe -NoProfile -STA -File .\Desktop\Verify-OfflinePackage.ps1 -PackageDirectory "C:\BusinessSuitePackage" -ReleaseExecutable ".\Desktop\Business Suite\obj\Release\net48\Business Suite.exe"
```

From an extracted package, run `powershell.exe -NoProfile -STA -File .\Verify-OfflinePackage.ps1 -PackageDirectory .`. If you also supply `-ReleaseExecutable`, the verifier compares the executable hashes. It checks the installed .NET Framework release and the x64 executable, known embedded browser references and legacy web client types, rejects legacy web runtime entries, runs the bundled PostgreSQL and Python prerequisites, constructs the packaged WinForms in Windows STA, and verifies named Telerik grids and fixed columns using the packaged binding redirects. On an interactive Windows workstation, append `-VerifyLauncher` to start the packaged executable and close its launcher after the main window appears. To check the configured PostgreSQL connection, append `-VerifyDatabase`. This resolves the Suite actor in a read-only transaction using the desktop configuration and target checks. It compares the database revision with the bundled migration head. The connection role needs read access to public.alembic_version for this optional check. For a LAN connection, keep `SSL Mode=VerifyFull` in the desktop configuration and also pass `-RequireTls` to verify a TLS protocol was negotiated. Visual Studio Designer interaction and workflow writes have separate verification steps.