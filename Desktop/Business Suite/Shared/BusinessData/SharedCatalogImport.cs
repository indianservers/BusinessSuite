using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Npgsql;

namespace Business_Suite;

internal sealed record CatalogImportRow(CatalogOfferingDraft Offering, bool Active, string Category,
    string[] Tags, string[] Images, string CustomFields);

internal sealed partial class SharedCatalogRepository
{
    internal List<CatalogImportRow> PreviewMappedCatalog(CatalogImportTable table, string[] destinations, string defaultKind,
        CancellationToken cancellation) => ParseImport(table.Map(destinations, defaultKind, cancellation),
            settings.BranchId ?? throw new InvalidOperationException("Choose a branch before importing products and services."), cancellation);

    internal async Task<int> ImportCatalogRowsAsync(IReadOnlyList<CatalogImportRow> rows, CancellationToken cancellation)
    {
        if (settings.BranchId is not int branch)
            throw new InvalidOperationException("Choose a branch before importing products and services.");
        if (rows.Count is < 1 or > 500)
            throw new ArgumentException("Import 1 to 500 offerings at a time.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await settings.VerifyWriteTargetAsync(db, tx, cancellation);
        await RequireCatalogEditAsync(db, tx, branch, actor, "create");
        using (var company = new NpgsqlCommand("SELECT id FROM public.companies WHERE id=@company FOR UPDATE", db, tx))
        {
            company.Parameters.AddWithValue("company", settings.OrganizationId);
            await company.ExecuteScalarAsync(cancellation);
        }
        for (int index = 0; index < rows.Count; index++)
        {
            var row = rows[index];
            try
            {
                await WriteOfferingAsync(db, tx, branch, actor, null, null, row.Offering, row, cancellation);
            }
            catch (Exception error) when (error is ArgumentException or InvalidOperationException)
            {
                throw new InvalidOperationException($"Item {index + 1}: {error.Message} The batch was rolled back.", error);
            }
        }
        tx.Commit();
        return rows.Count;
    }

    private static List<CatalogImportRow> ParseImport(JsonArray array, int branch, CancellationToken cancellation)
    {
        if (array.Count is < 1 or > 500)
            throw new ArgumentException("Import 1 to 500 offerings at a time.");
        var result = new List<CatalogImportRow>();
        for (int index = 0; index < array.Count; index++)
        {
            cancellation.ThrowIfCancellationRequested();
            try
            {
                if (array[index] is not JsonObject row)
                    throw new ArgumentException("Expected an offering record.");
                result.Add(ParseImportRow(row, branch));
            }
            catch (Exception error) when (error is ArgumentException or JsonException or InvalidOperationException or FormatException)
            {
                throw new ArgumentException($"Item {index + 1}: {error.Message}", error);
            }
        }
        return result;
    }

    internal static string ReadImportText(string path)
    {
        const int limit = 2 * 1024 * 1024;
        using var file = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
        if (file.Length > limit)
            throw new ArgumentException("Import files must be at most 2 MB.");
        using var input = new StreamReader(file, new UTF8Encoding(false, true), detectEncodingFromByteOrderMarks: false);
        return input.ReadToEnd().TrimStart('\uFEFF');
    }

    private static CatalogImportRow ParseImportRow(JsonObject row, int branch)
    {
        foreach (var key in row.Select(value => value.Key).Except(CatalogImportTable.KnownFields, StringComparer.Ordinal))
            throw new ArgumentException($"Unknown column '{key}'.");
        foreach (string key in new[] { "workspace_id", "version", "plan", "bundle", "service_scheduling", "follow_up",
            "restaurant_modifiers", "pharma_lot_tracking", "pharma_warehouse_id" })
            if (!Blank(row[key]))
                throw new ArgumentException($"'{key}' requires a specialized import workflow.");
        if (Structured("branch_availability") is { } availability)
        {
            if (availability is not JsonObject branches)
                throw new ArgumentException("Branch availability must be an object.");
            var scope = TextValue(branches["scope"]);
            var ids = branches["branch_ids"] as JsonArray;
            if (scope != "current" && (scope != "selected" || ids is null || ids.Count != 1 ||
                !int.TryParse(ids[0]?.ToString(), out int owner) || owner != branch))
                throw new ArgumentException("This import can create offerings for the selected branch only.");
        }
        string kind = Text("kind") switch
        {
            "product" => "Product",
            "service" => "Service",
            _ => throw new ArgumentException("Choose product or service.")
        };
        string status = Text("status", "Active");
        if (status is not ("Active" or "Archived"))
            throw new ArgumentException("Status must be Active or Archived.");
        string category = Text("category");
        if (category.Length > 120)
            throw new ArgumentException("Category names may contain up to 120 characters.");
        var categories = Structured("category_ids")?.Deserialize<string[]>();
        if (categories is not null && (categories.Length > 100 || categories.Any(string.IsNullOrWhiteSpace)))
            throw new ArgumentException("Enter up to 100 valid category identifiers.");
        var labels = Structured("categories")?.Deserialize<string[]>() ?? [];
        if (labels.Length > 100 || labels.Any(label => label is null || label.Length > 260))
            throw new ArgumentException("Enter up to 100 valid category labels.");
        var tags = Structured("tags")?.Deserialize<string[]>() ?? [];
        if (tags.Length > 20 || tags.Any(tag => string.IsNullOrWhiteSpace(tag) || tag.Trim().Length > 40))
            throw new ArgumentException("Enter up to 20 tags of no more than 40 characters.");
        var images = Structured("images")?.Deserialize<string[]>() ?? [];
        if (images.Length > 20 || images.Any(value => value is null || value.Length > 500 ||
            !new[] { "https://", "http://", "/uploads/", "/api/" }.Any(prefix => value.StartsWith(prefix, StringComparison.Ordinal))))
            throw new ArgumentException("Enter up to 20 valid image URLs or uploaded asset paths.");
        var custom = Structured("custom_fields") ?? new JsonObject();
        if (custom is not JsonObject fields || fields.Count > 100 ||
            fields.Any(field => field.Value is JsonArray or JsonObject))
            throw new ArgumentException("Custom fields must contain up to 100 scalar values.");
        var pricing = Structured("pricing_options")?.Deserialize<CatalogPriceOption[]>();
        bool track = Blank(row["track_inventory"]) ? kind == "Product"
            : bool.TryParse(row["track_inventory"]?.ToString(), out bool value) ? value
                : throw new ArgumentException("track_inventory must be true or false.");
        var offering = new CatalogOfferingDraft(kind, Text("name"), Text("code"), Text("description"), Text("unit", "unit"),
            Text("currency", "INR"), Text("barcode"), Text("hsn_code"), Number("price"), Number("tax"), Number("cost"),
            Number("mrp"), Number("reorder_level"), track, categories, pricing);
        ValidateOffering(offering);
        return new(offering, status == "Active", category, tags.Select(tag => tag.Trim().ToLowerInvariant()).Distinct().ToArray(),
            images, custom.ToJsonString());

        string Text(string key, string fallback = "") => Blank(row[key]) ? fallback : TextValue(row[key]);
        decimal Number(string key)
        {
            if (Blank(row[key]))
                return 0;
            if (!decimal.TryParse(row[key]?.ToString(), NumberStyles.AllowLeadingSign | NumberStyles.AllowDecimalPoint |
                    NumberStyles.AllowExponent, CultureInfo.InvariantCulture, out decimal number))
                throw new ArgumentException($"'{key}' must be a number.");
            return number;
        }
        JsonNode? Structured(string key)
        {
            var node = row[key];
            return node is JsonValue item && item.TryGetValue(out string? text)
                ? string.IsNullOrWhiteSpace(text) ? null : JsonNode.Parse(text)
                : node;
        }
    }

    private static bool Blank(JsonNode? node) =>
        node is null || node is JsonValue value && value.TryGetValue(out string? text) && string.IsNullOrWhiteSpace(text);

    private static string TextValue(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out string? text) && text is not null ? text.Trim()
            : throw new ArgumentException("Expected text.");
}
