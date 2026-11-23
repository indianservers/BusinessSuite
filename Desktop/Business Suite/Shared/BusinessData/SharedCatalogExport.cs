using System.Data;
using System.Text;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

internal sealed partial class SharedCatalogRepository
{
    private enum CatalogExportFormat { Json, Csv, Excel }
    private static readonly string[] ExportColumns =
    [
        "plan", "bundle", "service_scheduling", "branch_availability", "follow_up", "kind", "name", "code",
        "category", "category_ids", "categories", "tags", "description", "price", "currency", "tax", "unit",
        "barcode", "hsn_code", "cost", "mrp", "reorder_level", "track_inventory", "restaurant_modifiers",
        "pharma_lot_tracking", "pharma_warehouse_id", "status", "workspace_id", "images", "custom_fields", "pricing_options"
    ];

    internal Task<int> ExportJsonAsync(string path, CancellationToken cancellation) =>
        ExportCatalogAsync(path, CatalogExportFormat.Json, cancellation);
    internal Task<int> ExportCsvAsync(string path, CancellationToken cancellation) =>
        ExportCatalogAsync(path, CatalogExportFormat.Csv, cancellation);
    internal Task<int> ExportExcelAsync(string path, CancellationToken cancellation) =>
        ExportCatalogAsync(path, CatalogExportFormat.Excel, cancellation);

    private async Task<int> ExportCatalogAsync(string path, CatalogExportFormat format, CancellationToken cancellation)
    {
        if (settings.BranchId is not int branch)
            throw new InvalidOperationException("Choose a branch before exporting Products and Services.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var transaction = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeAsync(db, transaction, branch, cancellation);
        await RequireExportAsync(db, transaction, branch, actor);
        using var command = new NpgsqlCommand(@"
            SELECT (jsonb_build_object(
                'branch_availability', CASE WHEN COALESCE((attrs.value->'catalog_branches'->>'default')::boolean,true)
                    THEN NULL ELSE jsonb_build_object('scope','selected','branch_ids',COALESCE(branches.ids,'[]'::jsonb)) END,
                'follow_up',attrs.value->'follow_up',
                'kind',CASE WHEN p.product_type IN ('service','membership','subscription','bundle')
                            THEN p.product_type ELSE 'product' END,
                'name',p.item_name,'code',p.sku,'category_ids',attrs.value->'catalog_category_ids',
                'categories',COALESCE(attrs.value->'catalog_categories',
                    CASE WHEN coalesce(p.category_name,'')<>'' THEN jsonb_build_array(p.category_name) ELSE '[]'::jsonb END),
                'category',COALESCE(p.category_name,''),'tags',COALESCE(attrs.value->'catalog_tags','[]'::jsonb),
                'description',COALESCE(p.description,''),'price',COALESCE(p.sales_rate,0),
                'currency',COALESCE(attrs.value->>'currency','INR'),'tax',COALESCE(p.gst_rate,0),
                'unit',COALESCE(NULLIF(p.unit_code,''),'unit'),'barcode',COALESCE(p.barcode,''),
                'hsn_code',COALESCE(p.hsn_code,''),'cost',COALESCE(p.purchase_rate,0),
                'mrp',COALESCE(p.mrp,0),'reorder_level',COALESCE(p.reorder_level,0),
                'track_inventory',COALESCE(p.track_inventory,false),'status',CASE WHEN p.active THEN 'Active' ELSE 'Archived' END,
                'workspace_id',details.workspace_id,'images',COALESCE(attrs.value->'images',details.images::jsonb,'[]'::jsonb),
                'custom_fields',COALESCE(details.custom_fields::jsonb,'{}'::jsonb),
                'pricing_options',COALESCE(details.pricing_options::jsonb,'[]'::jsonb))
                || CASE WHEN attrs.value ? 'plan' THEN jsonb_build_object('plan',attrs.value->'plan') ELSE '{}'::jsonb END
                || CASE WHEN attrs.value ? 'bundle' THEN jsonb_build_object('bundle',attrs.value->'bundle') ELSE '{}'::jsonb END)::text"
            + ProductAndDetail + @"
            CROSS JOIN LATERAL (SELECT COALESCE(p.metadata_json::jsonb,'{}'::jsonb) AS value) attrs
            LEFT JOIN LATERAL (
                SELECT jsonb_agg(entry.key::int ORDER BY entry.key::int) FILTER (WHERE entry.enabled::boolean) AS ids
                FROM jsonb_each_text(COALESCE(attrs.value->'catalog_branches'->'overrides','{}'::jsonb)) entry(key,enabled)
            ) branches ON true" + ProductVisibility + " ORDER BY lower(p.item_name),p.id", db, transaction);
        BindProductScope(command, settings.OrganizationId, branch, actor);

        string destination = Path.GetFullPath(path);
        string temporary = Path.Combine(Path.GetDirectoryName(destination)!, $".catalog-{Guid.NewGuid():N}.tmp");
        int count = 0;
        try
        {
            using (var reader = await command.ExecuteReaderAsync(cancellation))
            using (var stream = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                count = format switch
                {
                    CatalogExportFormat.Csv => await WriteCatalogCsvAsync(reader, stream, cancellation),
                    CatalogExportFormat.Excel => await WriteCatalogExcelAsync(reader, stream, cancellation),
                    _ => await WriteCatalogJsonAsync(reader, stream, cancellation)
                };
            }
            cancellation.ThrowIfCancellationRequested();
            if (File.Exists(destination))
                File.Replace(temporary, destination, null);
            else
                File.Move(temporary, destination);
            return count;
        }
        finally
        {
            if (File.Exists(temporary))
                File.Delete(temporary);
        }
    }

    private static async Task<int> WriteCatalogJsonAsync(NpgsqlDataReader reader, Stream stream, CancellationToken cancellation)
    {
        using var writer = new Utf8JsonWriter(stream);
        int count = 0;
        writer.WriteStartArray();
        while (await reader.ReadAsync(cancellation))
        {
            using var item = JsonDocument.Parse(reader.GetString(0));
            item.WriteTo(writer);
            count++;
        }
        writer.WriteEndArray();
        await writer.FlushAsync(cancellation);
        return count;
    }

    private static async Task<int> WriteCatalogCsvAsync(NpgsqlDataReader reader, Stream stream, CancellationToken cancellation)
    {
        using var writer = new StreamWriter(stream, new UTF8Encoding(false));
        int count = 0;
        await writer.WriteLineAsync(string.Join(",", ExportColumns));
        while (await reader.ReadAsync(cancellation))
        {
            using var item = JsonDocument.Parse(reader.GetString(0));
            await writer.WriteLineAsync(string.Join(",", ExportColumns.Select(column => CatalogCsvCell(item.RootElement, column))));
            count++;
        }
        await writer.FlushAsync();
        return count;
    }

    private static string CatalogCsvCell(JsonElement item, string column)
    {
        if (!item.TryGetProperty(column, out var value) || value.ValueKind == JsonValueKind.Null)
            return "";
        string text = value.ValueKind == JsonValueKind.String ? value.GetString() ?? "" : value.GetRawText();
        return column is "name" or "code" or "category" or "description" or "unit"
            ? CrmCsv.Cell(text)
            : "\"" + text.Replace("\"", "\"\"") + "\"";
    }

    private static Task<int> WriteCatalogExcelAsync(NpgsqlDataReader reader, Stream stream, CancellationToken cancellation) =>
        TabularWorkbook.WriteAsync(stream, "Products and Services", ExportColumns, async append =>
        {
            while (await reader.ReadAsync(cancellation))
            {
                using var record = JsonDocument.Parse(reader.GetString(0));
                append(ExportColumns.Select(column => ExcelCell(record.RootElement, column)));
            }
        }, cancellation);

    private static object? ExcelCell(JsonElement record, string column)
    {
        if (!record.TryGetProperty(column, out var value))
            return null;
        return value.ValueKind switch
        {
            JsonValueKind.Null => null,
            JsonValueKind.String => value.GetString(),
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            JsonValueKind.Number when value.TryGetDecimal(out var number) => number,
            _ => value.GetRawText()
        };
    }

    private async Task RequireExportAsync(NpgsqlConnection db, NpgsqlTransaction transaction, int branch,
        DesktopActor actor)
    {
        var grant = await DesktopModuleAccess.RequireAsync(db, transaction, settings.OrganizationId, branch,
            actor, "srm", "export", "srm_view", "srm_manage", "srm_admin");
        if (grant.Scope != "organization")
            throw new UnauthorizedAccessException("Catalog export requires organization catalog access.");
    }
}
