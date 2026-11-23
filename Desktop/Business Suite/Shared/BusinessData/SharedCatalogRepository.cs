using System.Data;
using Npgsql;

namespace Business_Suite;

internal sealed partial class SharedCatalogRepository(DesktopDatabaseSettings settings)
{
    internal const string ProductAndDetail = @"
        FROM public.srm_products p
        LEFT JOIN public.shared_catalog_details details ON details.organization_id=@company
            AND CASE WHEN p.product_type='service' THEN details.service_id=p.id ELSE details.product_id=p.id END";

    internal const string ProductVisibility = @"
        WHERE COALESCE(p.organization_id,1)=@company AND p.deleted_at IS NULL
            AND COALESCE((p.metadata_json->'catalog_branches'->'overrides'->>@branch_key)::boolean,
                (p.metadata_json->'catalog_branches'->>'default')::boolean,true)
            AND NOT EXISTS (SELECT 1 FROM public.business_pack_record_ownership ownership
                WHERE ownership.company_id=@company AND ownership.resource_table='srm_products'
                    AND ownership.resource_key=p.id::text)
            AND (details.workspace_id IS NULL OR @admin OR EXISTS (
                SELECT 1 FROM public.pms_workspace_members m JOIN public.pms_workspaces w ON w.id=m.workspace_id
                WHERE m.workspace_id=details.workspace_id AND m.user_id=@actor AND COALESCE(w.organization_id,1)=@company))";

    internal async Task<(DataTable Rows, bool CanExport, bool CanEdit, bool CanCreate)> ListAsync(string search, bool archived, CancellationToken cancellation)
    {
        if (settings.BranchId is not int branch)
            throw new InvalidOperationException("Choose a branch before opening Products and Services.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var transaction = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeAsync(db, transaction, branch, cancellation);
        bool canExport;
        try
        {
            await RequireExportAsync(db, transaction, branch, actor);
            canExport = true;
        }
        catch (UnauthorizedAccessException)
        {
            canExport = false;
        }
        bool canEdit = false;
        bool canCreate = false;
        if (actor.CanWriteBranch)
        {
            try
            {
                await RequireCatalogEditAsync(db, transaction, branch, actor);
                canEdit = true;
            }
            catch (UnauthorizedAccessException) { }
            try
            {
                await RequireCatalogEditAsync(db, transaction, branch, actor, "create");
                canCreate = true;
            }
            catch (UnauthorizedAccessException) { }
        }

        using var command = new NpgsqlCommand(@"
            SELECT p.id, p.xmin::text||':'||COALESCE(details.xmin::text,'-') AS revision,
                   details.workspace_id, p.active, p.sku, COALESCE(p.description,'') AS description,
                   (p.metadata_json->'catalog_category_ids')::text AS category_ids, p.category_name,
                   COALESCE(details.pricing_options::text,'[]') AS pricing_options,
                   COALESCE(p.barcode,'') AS barcode, COALESCE(p.hsn_code,'') AS hsn_code,
                   COALESCE(p.track_inventory,false) AS track_inventory,
                   COALESCE(p.purchase_rate,0) AS cost, COALESCE(p.mrp,0) AS mrp,
                   COALESCE(p.reorder_level,0) AS reorder_level,
                   p.item_name,
                   CASE WHEN p.product_type IN ('service','membership','subscription','bundle')
                        THEN initcap(p.product_type) ELSE 'Product' END AS kind,
                   COALESCE(categories.names, p.category_name, '') AS category,
                   COALESCE(details.unit,p.unit_code,'') AS unit,
                   COALESCE(p.sales_rate,0) AS price,
                   COALESCE(p.metadata_json->>'currency','INR') AS currency,
                   COALESCE(p.gst_rate,0) AS tax" + ProductAndDetail + @"
            LEFT JOIN LATERAL (
                SELECT string_agg(value, ', ' ORDER BY ordinality) AS names
                FROM jsonb_array_elements_text(CASE WHEN jsonb_typeof(p.metadata_json::jsonb->'catalog_categories')='array'
                    THEN p.metadata_json::jsonb->'catalog_categories' ELSE '[]'::jsonb END)
                WITH ORDINALITY AS labels(value, ordinality)
            ) categories ON true" + ProductVisibility + @"
                AND p.active=NOT @archived
                AND (@search='' OR strpos(lower(p.item_name),lower(@search))>0 OR strpos(lower(p.sku),lower(@search))>0
                    OR strpos(lower(COALESCE(p.description,'')),lower(@search))>0)
            ORDER BY lower(p.item_name),p.id LIMIT 500", db, transaction);
        BindProductScope(command, settings.OrganizationId, branch, actor);
        command.Parameters.AddWithValue("archived", archived);
        command.Parameters.AddWithValue("search", search.Trim());
        var table = new DataTable();
        using var reader = await command.ExecuteReaderAsync(cancellation);
        for (int index = 0; index < reader.FieldCount; index++)
            table.Columns.Add(reader.GetName(index), reader.GetFieldType(index));
        while (await reader.ReadAsync(cancellation))
        {
            var row = new object[reader.FieldCount];
            reader.GetValues(row);
            table.Rows.Add(row);
        }
        return (table, canExport, canEdit, canCreate);
    }

    private async Task<DesktopActor> AuthorizeAsync(NpgsqlConnection db, NpgsqlTransaction transaction,
        int branch, CancellationToken cancellation)
    {
        var actor = await settings.RequireActorAsync(db, transaction, cancellation);
        var grant = await DesktopModuleAccess.RequireAsync(db, transaction, settings.OrganizationId, branch,
            actor, "srm", "view", "srm_view", "srm_manage", "srm_admin");
        if (grant.Scope != "organization")
            throw new UnauthorizedAccessException("Products and Services requires organization catalog access.");
        return actor;
    }

    internal static void BindProductScope(NpgsqlCommand command, int company, int branch, DesktopActor actor)
    {
        command.Parameters.AddWithValue("company", company);
        command.Parameters.AddWithValue("branch_key", branch.ToString(System.Globalization.CultureInfo.InvariantCulture));
        command.Parameters.AddWithValue("admin", actor.IsSuperuser || actor.IsCompanyAdmin);
        command.Parameters.AddWithValue("actor", actor.Id);
    }
}
