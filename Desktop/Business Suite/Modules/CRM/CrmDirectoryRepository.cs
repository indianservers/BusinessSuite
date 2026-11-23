using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal enum CrmDirectoryKind { Companies, Contacts }

internal sealed record CrmDirectoryPage(DataTable Records, long Total);

internal static class CrmDirectoryRepository
{
    public const int PageSize = 50;
    public const int ExportLimit = 10000;

    private static readonly string Companies = @"
        SELECT c.id, c.name, c.email, c.phone, c.city, c.country, c.status,
               COALESCE(NULLIF(r.roles, ''), c.account_type) AS classification,
               c.industry AS context, c.website, c.address, c.state, c.tags_text AS tags,
               d.legal_name AS detail_name, c.xmin::text AS revision, d.version AS details_revision,
               NULL::text AS first_name, NULL::text AS last_name, NULL::integer AS company_id,
               c.phone_country_code, c.notes, c.deleted_at,
               " + CrmDirectoryWrites.BranchScope("crm_companies", "c") + @" AS can_write,
               CASE WHEN trim(c.phone) LIKE '+%' OR c.phone_country_code IS NULL THEN c.phone
                    ELSE c.phone_country_code || ' ' || c.phone END AS phone_display
        FROM public.crm_companies c
        LEFT JOIN public.suite_company_master_details d ON d.account_id = c.id AND d.organization_id = @company
        LEFT JOIN LATERAL (
            SELECT string_agg(DISTINCT b.role, ', ' ORDER BY b.role) AS roles
            FROM public.suite_business_relationships b
            WHERE b.organization_id = @company AND b.account_id = c.id
        ) r ON true
        WHERE c.organization_id = @company
          AND " + CrmDirectoryWrites.BranchScope("crm_companies", "c", includeShares: true) + @"
          AND (c.deleted_at IS NOT NULL) = @archived
          AND (@role = '' OR c.account_type = @role OR (@role = 'Vendor' AND c.account_type = 'Supplier')
               OR EXISTS (
                    SELECT 1 FROM public.suite_business_relationships b
                    WHERE b.organization_id = @company AND b.account_id = c.id
                      AND (b.role = @role OR (@role = 'Vendor' AND b.role = 'Supplier'))
               ))";

    private static readonly string Contacts = @"
        SELECT p.id, p.full_name AS name, p.email, p.phone, p.city, p.country, p.status,
               p.lifecycle_stage AS classification,
               CASE WHEN p.company_id IS NULL THEN p.company_name ELSE c.name END AS context, p.website, p.address, p.state, p.tags_text AS tags,
               p.job_title AS detail_name, p.xmin::text AS revision, NULL::integer AS details_revision,
               p.first_name, p.last_name, p.company_id, p.phone_country_code, p.notes, p.deleted_at,
               " + CrmDirectoryWrites.BranchScope("crm_contacts", "p") + @" AS can_write,
               CASE WHEN trim(p.phone) LIKE '+%' OR p.phone_country_code IS NULL THEN p.phone
                    ELSE p.phone_country_code || ' ' || p.phone END AS phone_display
        FROM public.crm_contacts p
        LEFT JOIN public.crm_companies c ON c.id = p.company_id
            AND @show_company AND c.organization_id = @company AND c.deleted_at IS NULL
            AND " + CrmDirectoryWrites.BranchScope("crm_companies", "c", includeShares: true) + @"
        WHERE p.organization_id = @company
          AND " + CrmDirectoryWrites.BranchScope("crm_contacts", "p", includeShares: true) + @"
          AND (p.deleted_at IS NOT NULL) = @archived";

    public static async Task<CrmDirectoryPage> LoadAsync(CrmDirectoryKind kind, string search, string role,
        bool archived, int page, CancellationToken cancellation, bool exporting = false)
    {
        var settings = DesktopDatabaseSettings.Load();
        string query = kind == CrmDirectoryKind.Companies ? Companies : Contacts;
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var mode = new NpgsqlCommand("SET TRANSACTION READ ONLY", connection, transaction))
            await mode.ExecuteNonQueryAsync(cancellation);
        var actor = await CrmDirectoryWrites.RequireCrmActorAsync(settings, connection, transaction, cancellation,
            CrmDirectoryWrites.PermissionEntity(kind), exporting ? "export" : "view");
        bool showCompany = false;
        if (kind == CrmDirectoryKind.Contacts)
        {
            try
            {
                await CrmDirectoryWrites.RequireCrmAccessAsync(settings, connection, transaction, actor, "accounts", "view");
                showCompany = true;
            }
            catch (UnauthorizedAccessException) { }
        }

        string scope = " FROM (" + query + @") records
            WHERE @search = '' OR strpos(lower(name), lower(@search)) > 0
               OR strpos(lower(email), lower(@search)) > 0
               OR strpos(lower(context), lower(@search)) > 0
               OR strpos(lower(phone_display), lower(@search)) > 0
               OR (regexp_replace(@search,'[ ().-]','','g') ~ '^\+?[0-9]+$'
                   AND strpos(regexp_replace(phone_display,'[ ().-]','','g'),
                       regexp_replace(@search,'[ ().-]','','g')) > 0)";

        using var count = new NpgsqlCommand("SELECT count(*)" + scope, connection, transaction);
        SetFilters(count);
        long total = (long)(await count.ExecuteScalarAsync(cancellation))!;

        if (exporting && total > ExportLimit)
            throw new InvalidOperationException($"Narrow the search to {ExportLimit:N0} records before exporting.");

        using var list = new NpgsqlCommand("SELECT *" + scope + " ORDER BY name, id LIMIT @limit OFFSET @offset",
            connection, transaction);
        SetFilters(list);
        list.Parameters.AddWithValue("limit", NpgsqlDbType.Integer, exporting ? ExportLimit : PageSize);
        list.Parameters.AddWithValue("offset", NpgsqlDbType.Bigint, (long)page * PageSize);
        using var reader = await list.ExecuteReaderAsync(cancellation);
        var table = new DataTable();
        for (int index = 0; index < reader.FieldCount; index++)
            table.Columns.Add(reader.GetName(index), reader.GetFieldType(index));
        while (await reader.ReadAsync(cancellation))
        {
            var values = new object[reader.FieldCount];
            reader.GetValues(values);
            table.Rows.Add(values);
        }
        return new(table, total);

        void SetFilters(NpgsqlCommand command)
        {
            command.Parameters.AddWithValue("company", NpgsqlDbType.Integer, settings.OrganizationId);
            CrmExtrasStore.Param(command, "scope_branch", NpgsqlDbType.Integer, settings.BranchId);
            command.Parameters.AddWithValue("archived", NpgsqlDbType.Boolean, archived);
            command.Parameters.AddWithValue("search", NpgsqlDbType.Text, search);
            if (kind == CrmDirectoryKind.Companies)
                command.Parameters.AddWithValue("role", NpgsqlDbType.Text, role);
            else
                command.Parameters.AddWithValue("show_company", NpgsqlDbType.Boolean, showCompany);
        }
    }
}
