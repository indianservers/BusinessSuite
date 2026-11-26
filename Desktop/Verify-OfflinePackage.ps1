#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PackageDirectory,
    [string]$ReleaseExecutable,
    [switch]$VerifyLauncher,
    [switch]$VerifyDatabase,
    [switch]$RequireTls
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSEdition -ne 'Desktop' -or -not [Environment]::Is64BitProcess -or
    [Threading.Thread]::CurrentThread.GetApartmentState() -ne 'STA') {
    throw 'Run this verification from 64-bit Windows PowerShell with -STA.'
}

$frameworkKey = 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full'
$framework = Get-ItemProperty -LiteralPath $frameworkKey -Name Release -ErrorAction SilentlyContinue
if ($null -eq $framework -or $framework.Release -lt 528040) {
    throw 'The desktop package requires .NET Framework 4.8 or later.'
}
Write-Output "Installed .NET Framework Release $($framework.Release) meets the 4.8 minimum."

if ($RequireTls -and !$VerifyDatabase) {
    throw '-RequireTls requires -VerifyDatabase.'
}

$package = (Resolve-Path -LiteralPath $PackageDirectory).Path
$executable = Join-Path $package 'Business Suite.exe'
$configuration = "$executable.config"
if (!(Test-Path -LiteralPath $executable -PathType Leaf) -or
    !(Test-Path -LiteralPath $configuration -PathType Leaf)) {
    throw 'The package must contain Business Suite.exe and its configuration file.'
}

foreach ($legacy in 'Start Local Workspace.cmd', 'local_workspace.py', 'frontend') {
    if (Test-Path -LiteralPath (Join-Path $package $legacy)) {
        throw "The native package contains a legacy web runtime entry: $legacy."
    }
}

$prerequisites = @(
    'desktop.env.example',
    'backend\Initialize-DesktopDatabase.py',
    'backend\alembic.ini',
    'backend\alembic_postgresql\env.py',
    'postgresql\bin\postgres.exe',
    'postgresql\bin\initdb.exe',
    'postgresql\bin\pg_ctl.exe',
    'postgresql\bin\psql.exe',
    'python\python.exe'
)
foreach ($relativePath in $prerequisites) {
    if (!(Test-Path -LiteralPath (Join-Path $package $relativePath) -PathType Leaf)) {
        throw "The offline package is missing $relativePath."
    }
}

$hash = (Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash
if ($ReleaseExecutable -and (Get-FileHash -LiteralPath $ReleaseExecutable -Algorithm SHA256).Hash -ne $hash) {
    throw 'The package executable differs from the supplied Release executable.'
}
Write-Output "Package executable SHA-256 $hash"

$postgres = Join-Path $package 'postgresql\bin\postgres.exe'
& $postgres --version
if ($LASTEXITCODE -ne 0) {
    throw 'The bundled PostgreSQL executable did not start.'
}

$python = Join-Path $package 'python\python.exe'
& $python -I -B -c 'import alembic, psycopg, sqlalchemy'
if ($LASTEXITCODE -ne 0) {
    throw 'The bundled Python could not load the schema initializer dependencies.'
}

$initializer = Join-Path $package 'backend\Initialize-DesktopDatabase.py'
& $python -I -B $initializer --help | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'The bundled schema initializer did not start.'
}
Write-Output 'Bundled database tools and initializer prerequisites passed.'

$migrationConfig = Join-Path $package 'backend\alembic.ini'
$revisionProbe = @'
import sys
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory

path = Path(sys.argv[1])
sys.path.insert(0, str(path.parent))
config = Config(str(path))
config.set_main_option("prepend_sys_path", "")
print(ScriptDirectory.from_config(config).get_current_head())
'@
$packageRevision = $revisionProbe | & $python -I -B - $migrationConfig
if ($LASTEXITCODE -ne 0 -or $packageRevision -notmatch '^[A-Za-z0-9_]+$' -or $packageRevision -eq 'None') {
    throw 'Could not determine the bundled PostgreSQL migration head.'
}
Write-Output "Bundled PostgreSQL migration head $packageRevision"

if ($VerifyLauncher) {
    $start = New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName = $executable
    $start.WorkingDirectory = $package
    $start.UseShellExecute = $false
    $start.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Minimized
    $process = [System.Diagnostics.Process]::Start($start)
    try {
        if (!$process.WaitForInputIdle(8000)) {
            throw 'The packaged launcher did not enter its message loop.'
        }
        $deadline = [DateTime]::UtcNow.AddSeconds(5)
        do {
            $process.Refresh()
            if ($process.MainWindowTitle -eq 'Business Suite') { break }
            Start-Sleep -Milliseconds 100
        } while (!$process.HasExited -and [DateTime]::UtcNow -lt $deadline)
        if ($process.HasExited -or $process.MainWindowTitle -ne 'Business Suite') {
            throw 'The packaged launcher did not open the Business Suite window.'
        }
        if (!$process.CloseMainWindow() -or !$process.WaitForExit(6000) -or $process.ExitCode -ne 0) {
            throw 'The packaged launcher did not close cleanly.'
        }
        Write-Output 'Packaged launcher opened and closed cleanly.'
    }
    finally {
        if (!$process.HasExited) { $process.Kill() }
        $process.Dispose()
    }
}

$source = @"
using System;
using System.Collections;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data.Common;
using System.Linq;
using System.Reflection;
using System.Security.Authentication;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

public sealed class BusinessSuitePackageProbe : MarshalByRefObject
{
    private int grids;
    private int columns;

    public int Verify(string executable)
    {
        Assembly application = Assembly.LoadFrom(executable);
        VerifyNativeAssembly(application);
        int forms = 0;
        int failures = 0;
        foreach (Type formType in application.GetTypes().Where(type =>
            !type.IsAbstract && typeof(Form).IsAssignableFrom(type) &&
            type.GetConstructor(Type.EmptyTypes) != null).OrderBy(type => type.FullName))
        {
            try
            {
                using (var form = (Form)Activator.CreateInstance(formType))
                {
                    forms++;
                    Inspect(form);
                }
            }
            catch (Exception error)
            {
                failures++;
                Console.Error.WriteLine(formType.FullName + ": " + error.GetBaseException().Message);
            }
        }

        Console.WriteLine("{0} form constructors, {1} Telerik grids, {2} fixed columns, {3} failures.",
            forms, grids, columns, failures);
        return failures == 0 && forms > 0 && grids > 0 && columns > 0 ? 0 : 1;
    }

    private static void VerifyNativeAssembly(Assembly application)
    {
        PortableExecutableKinds format;
        ImageFileMachine architecture;
        application.ManifestModule.GetPEKind(out format, out architecture);
        if (architecture != ImageFileMachine.AMD64 || (format & PortableExecutableKinds.PE32Plus) == 0)
            throw new InvalidOperationException("The managed desktop executable is not an x64 build.");

        var framework = (System.Runtime.Versioning.TargetFrameworkAttribute)Attribute.GetCustomAttribute(
            application, typeof(System.Runtime.Versioning.TargetFrameworkAttribute));
        if (framework == null || framework.FrameworkName != ".NETFramework,Version=v4.8")
            throw new InvalidOperationException("The desktop executable does not target .NET Framework 4.8.");

        AssemblyName[] references = application.GetReferencedAssemblies();
        if (!references.Any(reference => reference.Name == "Npgsql") ||
            !references.Any(reference => reference.Name == "System.Windows.Forms"))
            throw new InvalidOperationException("The desktop executable is missing its Npgsql or WinForms reference.");

        foreach (AssemblyName reference in references)
        {
            string name = reference.Name;
            if (name.StartsWith("Microsoft.Web.WebView2", StringComparison.OrdinalIgnoreCase) ||
                name.StartsWith("CefSharp", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("The desktop executable references an embedded browser: " + name + ".");
        }

        foreach (string type in new[] { "NoteApi", "NoteSync", "BusinessComparison", "ConnectionSettings" })
            if (application.GetType("Business_Suite." + type, false) != null)
                throw new InvalidOperationException("The desktop executable includes a legacy web client: " + type + ".");

        Console.WriteLine("x64 .NET Framework 4.8 executable and native dependency checks passed.");
    }

    public void VerifyDatabase(string executable, bool requireTls, string expectedRevision)
    {
        const BindingFlags internalInstance = BindingFlags.Instance | BindingFlags.NonPublic;
        var application = Assembly.LoadFrom(executable);
        var configuration = application.GetType("Business_Suite.DesktopDatabaseSettings", true);
        string tlsProtocol;
        string databaseRevisions;
        try
        {
            var settings = configuration.GetMethod("Load").Invoke(null, null);
            string connectionString = (string)configuration.GetProperty("ConnectionString", internalInstance)
                .GetValue(settings, null);
            var connectionType = Assembly.Load("Npgsql").GetType("Npgsql.NpgsqlConnection", true);
            using (var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(15)))
            using (var connection = (DbConnection)Activator.CreateInstance(connectionType, new object[] { connectionString }))
            {
                connection.OpenAsync(deadline.Token).GetAwaiter().GetResult();
                using (var transaction = connection.BeginTransaction())
                using (var command = connection.CreateCommand())
                {
                    command.Transaction = transaction;
                    command.CommandText = "SET TRANSACTION READ ONLY";
                    command.ExecuteNonQueryAsync(deadline.Token).GetAwaiter().GetResult();
                    var authorize = (Task)configuration.GetMethod("RequireActorAsync", internalInstance)
                        .Invoke(settings, new object[] { connection, transaction, deadline.Token });
                    authorize.GetAwaiter().GetResult();
                    command.CommandText = "SELECT CASE WHEN ssl THEN version ELSE '' END " +
                        "FROM pg_catalog.pg_stat_ssl WHERE pid = pg_backend_pid()";
                    tlsProtocol = command.ExecuteScalarAsync(deadline.Token).GetAwaiter().GetResult() as string;
                    command.CommandText = "SELECT pg_catalog.to_regclass('public.alembic_version') IS NOT NULL";
                    databaseRevisions = "";
                    if ((bool)command.ExecuteScalarAsync(deadline.Token).GetAwaiter().GetResult())
                    {
                        command.CommandText = "SELECT string_agg(version_num, ',' ORDER BY version_num) FROM public.alembic_version";
                        databaseRevisions = command.ExecuteScalarAsync(deadline.Token).GetAwaiter().GetResult() as string ?? "";
                    }
                }
            }
        }
        catch (Exception error)
        {
            Exception cause = error.GetBaseException();
            if (cause is AuthenticationException)
                throw new InvalidOperationException("PostgreSQL certificate validation failed. Check the server name and Windows certificate trust.");
            if (cause is UnauthorizedAccessException)
                throw new InvalidOperationException("The PostgreSQL login could not resolve an eligible Suite actor for the selected company and branch.");
            if (cause.Message.StartsWith("PostgreSQL did not match the configured", StringComparison.Ordinal))
                throw new InvalidOperationException("The connected PostgreSQL target did not match the desktop configuration.");
            throw new InvalidOperationException("Could not verify PostgreSQL endpoint, credentials or Suite actor scope. Check BUSINESS_SUITE_POSTGRES, the expected server address, and active company/branch membership.");
        }

        if (requireTls && string.IsNullOrEmpty(tlsProtocol))
            throw new InvalidOperationException("The authorized PostgreSQL session did not negotiate TLS.");

        if (!string.Equals(databaseRevisions, expectedRevision, StringComparison.Ordinal))
            throw new InvalidOperationException("The verified PostgreSQL database is not at the bundled migration head.");

        Console.WriteLine("Verified PostgreSQL schema revision " + expectedRevision + ".");
        Console.WriteLine(string.IsNullOrEmpty(tlsProtocol)
            ? "Read-only PostgreSQL target and Suite actor verified. TLS was not negotiated."
            : "Read-only PostgreSQL target and Suite actor verified over " + tlsProtocol + ".");
    }

    private void Inspect(Control control)
    {
        for (Type type = control.GetType(); type != null; type = type.BaseType)
        {
            if (type.FullName != "Telerik.WinControls.UI.RadGridView")
                continue;
            InspectGrid(control, type);
            break;
        }

        foreach (Control child in control.Controls)
            Inspect(child);
    }

    private void InspectGrid(Control grid, Type gridType)
    {
        if (string.IsNullOrWhiteSpace(grid.Name))
            throw new InvalidOperationException("A Telerik grid is unnamed.");

        object template = gridType.GetProperty("MasterTemplate").GetValue(grid, null);
        PropertyDescriptorCollection properties = TypeDescriptor.GetProperties(template);
        if ((bool)properties["AutoGenerateColumns"].GetValue(template))
            throw new InvalidOperationException(grid.Name + " enables automatic column generation.");

        PropertyDescriptor collection = properties["Columns"];
        if (collection == null || collection.SerializationVisibility == DesignerSerializationVisibility.Hidden)
            throw new InvalidOperationException(grid.Name + " does not expose its columns.");

        var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (object column in (IEnumerable)collection.GetValue(template))
        {
            PropertyDescriptorCollection columnProperties = TypeDescriptor.GetProperties(column);
            string name = columnProperties["Name"].GetValue(column) as string;
            if (string.IsNullOrWhiteSpace(name) || !names.Add(name) || columnProperties["HeaderText"].IsReadOnly)
                throw new InvalidOperationException(grid.Name + " has an unnamed or duplicate column, or a read-only header.");
        }
        if (names.Count == 0)
            throw new InvalidOperationException(grid.Name + " has no fixed columns.");

        grids++;
        columns += names.Count;
    }
}
"@

$probeFile = Join-Path ([IO.Path]::GetTempPath()) ("BusinessSuitePackageProbe-" + [guid]::NewGuid().ToString('N') + '.dll')
$setup = New-Object System.AppDomainSetup
$setup.ApplicationBase = $package
$setup.ConfigurationFile = $configuration
$domain = [AppDomain]::CreateDomain('Business Suite package verification', $null, $setup)
try {
    Add-Type -TypeDefinition $source -OutputAssembly $probeFile -ReferencedAssemblies 'System.Windows.Forms.dll', 'System.Data.dll'
    [Reflection.Assembly]::Load([IO.File]::ReadAllBytes($probeFile)) | Out-Null
    $probe = [BusinessSuitePackageProbe]$domain.CreateInstanceFromAndUnwrap($probeFile, 'BusinessSuitePackageProbe')
    if ($probe.Verify($executable) -ne 0) {
        throw 'The package failed WinForms verification.'
    }
    if ($VerifyDatabase) {
        $probe.VerifyDatabase($executable, $RequireTls.IsPresent, $packageRevision)
    }
}
finally {
    [AppDomain]::Unload($domain)
    if (Test-Path -LiteralPath $probeFile) {
        Remove-Item -LiteralPath $probeFile
    }
}
