using Npgsql;
using NpgsqlTypes;
using System.Net;

namespace Business_Suite;

internal sealed record DesktopActor(int Id, bool IsSuperuser, bool IsCompanyAdmin, bool CanWriteBranch);
internal sealed record DesktopCompanyBranch(int CompanyId, string Company, int? BranchId, string? Branch);

internal sealed class DesktopDatabaseSettings
{
    internal static string EnvironmentPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Business Suite", ".env");

    internal string ConnectionString { get; }
    internal int OrganizationId { get; }
    internal int? BranchId { get; }
    internal string DocumentsRoot { get; }
    internal string ExpectedAddress => expectedAddress?.ToString() ?? "";
    private readonly string database;
    private readonly string username;
    private readonly int port;
    private readonly IPAddress? expectedAddress;
    private static DesktopDatabaseSettings? selectedScope;

    private DesktopDatabaseSettings(NpgsqlConnectionStringBuilder builder, int organizationId, int? branchId,
        IPAddress? expectedAddress, string documentsRoot)
    {
        ConnectionString = builder.ConnectionString;
        database = builder.Database!;
        username = builder.Username!;
        port = builder.Port;
        OrganizationId = organizationId;
        BranchId = branchId;
        this.expectedAddress = expectedAddress;
        DocumentsRoot = documentsRoot;
    }

    public static DesktopDatabaseSettings Load()
    {
        string path = EnvironmentPath;
        var settings = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (File.Exists(path))
        {
            foreach (string line in File.ReadLines(path))
            {
                string trimmed = line.Trim();
                int separator = trimmed.IndexOf('=');
                if (trimmed.StartsWith("#") || separator <= 0)
                    continue;
                string value = trimmed.Substring(separator + 1).Trim();
                if (value.Length > 1 && (value[0] == '"' || value[0] == '\'') && value[value.Length - 1] == value[0])
                    value = value.Substring(1, value.Length - 2);
                settings[trimmed.Substring(0, separator).Trim()] = value;
            }
        }

        string? GetValue(string key) => Environment.GetEnvironmentVariable(key)
            ?? (settings.TryGetValue(key, out string value) ? value : null);
        string connectionString = GetValue("BUSINESS_SUITE_POSTGRES")
            ?? throw new InvalidOperationException("Set BUSINESS_SUITE_POSTGRES in the desktop environment file.");
        NpgsqlConnectionStringBuilder builder;
        try
        {
            builder = new NpgsqlConnectionStringBuilder(connectionString);
        }
        catch (ArgumentException)
        {
            throw new ArgumentException("BUSINESS_SUITE_POSTGRES is not a valid PostgreSQL connection string.");
        }
        if (string.IsNullOrWhiteSpace(builder.Host) || builder.Host!.Contains(",")
            || string.IsNullOrWhiteSpace(builder.Database) || string.IsNullOrWhiteSpace(builder.Username))
            throw new ArgumentException("Specify one PostgreSQL host, a database and a username.");
        string? expected = GetValue("BUSINESS_SUITE_POSTGRES_EXPECTED_ADDRESS");
        IPAddress? address = null;
        if (!string.IsNullOrWhiteSpace(expected) && !IPAddress.TryParse(expected, out address))
            throw new ArgumentException("Enter a PostgreSQL server IP for BUSINESS_SUITE_POSTGRES_EXPECTED_ADDRESS.");

        if (!int.TryParse(GetValue("BUSINESS_SUITE_ORGANIZATION_ID") ?? "1", out int company) || company < 1)
            throw new ArgumentException("Enter a positive BUSINESS_SUITE_ORGANIZATION_ID.");
        string? branchValue = GetValue("BUSINESS_SUITE_BRANCH_ID");
        int? branch = null;
        if (!string.IsNullOrWhiteSpace(branchValue))
        {
            if (!int.TryParse(branchValue, out int parsed) || parsed < 1)
                throw new ArgumentException("Enter a positive BUSINESS_SUITE_BRANCH_ID.");
            branch = parsed;
        }
        string uploads = GetValue("BUSINESS_SUITE_UPLOAD_DIR") ??
            Path.Combine(Path.GetDirectoryName(EnvironmentPath)!, "uploads");
        uploads = NormalizeDocumentsRoot(uploads);
        if (selectedScope is { } selection && selection.ConnectionString == builder.ConnectionString
            && Equals(selection.expectedAddress, address))
            return new(builder, selection.OrganizationId, selection.BranchId, address, uploads);
        return new(builder, company, branch, address, uploads);
    }

    private static string NormalizeDocumentsRoot(string value)
    {
        string path = value.Replace('/', '\\');
        bool drive = path.Length >= 3 && char.IsLetter(path[0]) && path[1] == ':' && path[2] == '\\';
        bool share = false;
        if (path.StartsWith(@"\\", StringComparison.Ordinal))
        {
            string[] parts = path.Substring(2).Split('\\');
            share = parts.Length >= 2 && parts[0].Length > 0 && parts[1].Length > 0 &&
                parts[0] is not ("?" or ".") && parts[1] is not ("." or "..");
        }
        if (!drive && !share)
            throw new ArgumentException("Use an absolute drive folder or UNC share for BUSINESS_SUITE_UPLOAD_DIR.");
        return Path.GetFullPath(path);
    }

    internal DesktopDatabaseSettings ForScope(int company, int? branch) =>
        new(new NpgsqlConnectionStringBuilder(ConnectionString), company, branch, expectedAddress, DocumentsRoot);

    internal void SelectScope() => selectedScope = this;

    internal async Task<List<DesktopCompanyBranch>> ListScopesAsync(NpgsqlConnection connection, CancellationToken cancellation)
    {
        using var transaction = connection.BeginTransaction(System.Data.IsolationLevel.RepeatableRead);
        await VerifyEndpointAsync(connection, transaction, cancellation);
        using var command = new NpgsqlCommand(@"
            SELECT c.id, c.name, b.id, b.name
            FROM public.users u
            LEFT JOIN public.common_people person ON person.user_id=u.id
            CROSS JOIN public.companies c
            LEFT JOIN public.suite_access_memberships m ON m.user_id=u.id AND m.company_id=c.id
            LEFT JOIN public.suite_branch_policies p ON p.user_id=u.id AND p.company_id=c.id
            LEFT JOIN public.branches b ON b.company_id=c.id AND b.is_active
                AND NOT EXISTS (SELECT 1 FROM public.suite_branch_lifecycle l
                    WHERE l.branch_id=b.id AND l.deleted_at IS NOT NULL)
                AND (u.is_superuser OR (m.active AND m.is_admin) OR p.all_branches
                    OR EXISTS (SELECT 1 FROM public.suite_branch_grants g
                        WHERE g.user_id=u.id AND g.company_id=c.id AND g.branch_id=b.id)
                    OR (COALESCE(p.use_home_branch, true) AND EXISTS (SELECT 1 FROM public.employees e
                        WHERE e.user_id=u.id AND e.branch_id=b.id AND e.deleted_at IS NULL)))
            WHERE u.email=session_user::text AND current_user=session_user AND u.is_active AND c.is_active
                AND NOT COALESCE(u.mfa_enabled, false) AND u.mfa_enforced_at IS NULL AND u.sso_provider_id IS NULL
                AND (u.is_superuser OR m.active OR (m.id IS NULL AND (person.organization_id=c.id OR EXISTS (
                    SELECT 1 FROM public.employees e JOIN public.branches home ON home.id=e.branch_id
                    WHERE e.user_id=u.id AND e.deleted_at IS NULL AND home.company_id=c.id))))
                AND (b.id IS NOT NULL OR u.is_superuser OR (m.active AND m.is_admin) OR p.all_branches)
            ORDER BY c.name, c.id, b.name, b.id", connection, transaction);
        using var reader = await command.ExecuteReaderAsync(cancellation);
        var scopes = new List<DesktopCompanyBranch>();
        while (await reader.ReadAsync(cancellation))
            scopes.Add(new(reader.GetInt32(0), reader.GetString(1),
                reader.IsDBNull(2) ? null : reader.GetInt32(2), reader.IsDBNull(3) ? null : reader.GetString(3)));
        return scopes;
    }

    internal async Task<DesktopActor> VerifyWriteTargetAsync(NpgsqlConnection connection, NpgsqlTransaction transaction,
        CancellationToken cancellation)
    {
        if (transaction.Connection != connection)
            throw new InvalidOperationException("Verify the target inside the transaction that will save the changes.");
        var actor = await RequireActorAsync(connection, transaction, cancellation);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("Write access requires a writable branch.");
        return actor;
    }

    internal async Task<DesktopActor> RequireActorAsync(NpgsqlConnection connection, NpgsqlTransaction? transaction,
        CancellationToken cancellation)
    {
        await VerifyTargetAsync(connection, transaction, cancellation);
        using var command = new NpgsqlCommand(@"
            WITH actor AS (
                SELECT u.id, COALESCE(u.is_superuser, false) AS superuser,
                       COALESCE(m.active AND m.is_admin, false) AS company_admin,
                       COALESCE(p.all_branches, false) AS all_branches,
                       COALESCE(p.use_home_branch, true) AND EXISTS (
                           SELECT 1 FROM public.employees e WHERE e.user_id=u.id
                               AND e.branch_id=@branch AND e.deleted_at IS NULL
                       ) AS home_branch,
                       g.branch_id AS grant_branch, g.can_write
                FROM public.users u
                LEFT JOIN public.common_people person ON person.user_id=u.id
                LEFT JOIN public.suite_access_memberships m ON m.user_id=u.id AND m.company_id=@company
                LEFT JOIN public.suite_branch_policies p ON p.user_id=u.id AND p.company_id=@company
                LEFT JOIN public.suite_branch_grants g ON g.user_id=u.id AND g.company_id=@company
                    AND g.branch_id=@branch
                WHERE u.email=session_user::text AND current_user=session_user AND u.is_active
                    AND NOT COALESCE(u.mfa_enabled, false) AND u.mfa_enforced_at IS NULL
                    AND u.sso_provider_id IS NULL
                    AND (u.is_superuser OR m.active OR (m.id IS NULL AND (person.organization_id=@company OR EXISTS (
                        SELECT 1 FROM public.employees e JOIN public.branches home ON home.id=e.branch_id
                        WHERE e.user_id=u.id AND e.deleted_at IS NULL AND home.company_id=@company))))
            )
            SELECT id, superuser, company_admin,
                   CASE WHEN @branch IS NULL THEN NOT EXISTS (
                       SELECT 1 FROM public.branches b WHERE b.company_id=@company AND b.is_active
                           AND NOT EXISTS (SELECT 1 FROM public.suite_branch_lifecycle l
                               WHERE l.branch_id=b.id AND l.deleted_at IS NOT NULL)
                   ) ELSE superuser OR company_admin OR all_branches
                       OR COALESCE(can_write, home_branch) END
            FROM actor WHERE superuser OR company_admin OR all_branches
                OR (@branch IS NOT NULL AND (home_branch OR grant_branch IS NOT NULL))",
            connection, transaction);
        command.Parameters.AddWithValue("company", OrganizationId);
        command.Parameters.Add("branch", NpgsqlDbType.Integer).Value = (object?)BranchId ?? DBNull.Value;
        using var reader = await command.ExecuteReaderAsync(cancellation);
        if (!await reader.ReadAsync(cancellation))
            throw new UnauthorizedAccessException("The PostgreSQL login does not have an eligible Business Suite account for this company and branch.");
        return new(reader.GetInt32(0), reader.GetBoolean(1), reader.GetBoolean(2), reader.GetBoolean(3));
    }

    internal async Task<string> VerifyTargetAsync(NpgsqlConnection connection, NpgsqlTransaction? transaction,
        CancellationToken cancellation)
    {
        await VerifyEndpointAsync(connection, transaction, cancellation);

        using var scope = new NpgsqlCommand(@"SELECT c.name, b.name FROM public.companies c
            LEFT JOIN public.branches b ON b.company_id=c.id AND b.id=@branch AND b.is_active
                AND NOT EXISTS (SELECT 1 FROM public.suite_branch_lifecycle l
                    WHERE l.branch_id=b.id AND l.deleted_at IS NOT NULL)
            WHERE c.id=@company AND c.is_active AND (@branch IS NULL OR b.id IS NOT NULL)", connection, transaction);
        scope.Parameters.AddWithValue("company", OrganizationId);
        scope.Parameters.Add("branch", NpgsqlDbType.Integer).Value = (object?)BranchId ?? DBNull.Value;
        using var names = await scope.ExecuteReaderAsync(cancellation);
        if (!await names.ReadAsync(cancellation))
            throw new InvalidOperationException("The configured company or branch is unavailable on this database.");
        string company = names.GetString(0);
        string location = names.IsDBNull(1) ? company : $"{company} / {names.GetString(1)}";
        return $"{database} at {expectedAddress}:{port} · {location}";
    }

    private async Task VerifyEndpointAsync(NpgsqlConnection connection, NpgsqlTransaction? transaction,
        CancellationToken cancellation)
    {
        if (expectedAddress is null)
            throw new InvalidOperationException("Set BUSINESS_SUITE_POSTGRES_EXPECTED_ADDRESS to the verified server IP.");
        using var command = new NpgsqlCommand(@"SELECT current_database(), current_user,
            host(inet_server_addr()), inet_server_port()", connection, transaction);
        using var reader = await command.ExecuteReaderAsync(cancellation);
        if (!await reader.ReadAsync(cancellation) || reader.IsDBNull(2) || reader.IsDBNull(3)
            || reader.GetString(0) != database || reader.GetString(1) != username
            || !IPAddress.TryParse(reader.GetString(2), out var actualAddress)
            || !expectedAddress.Equals(actualAddress) || reader.GetInt32(3) != port)
            throw new InvalidOperationException("PostgreSQL did not match the configured database, username, IP and port.");
    }
}
