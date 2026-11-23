using System.Text.Json.Nodes;
using Microsoft.VisualBasic.FileIO;

namespace Business_Suite;

internal sealed record CatalogImportTable(string[] Headers, List<JsonNode?[]> Rows)
{
    internal static readonly string[] KnownFields =
    [
        "name", "code", "kind", "category", "category_ids", "categories", "tags", "description", "price", "currency",
        "tax", "unit", "barcode", "hsn_code", "cost", "mrp", "reorder_level", "track_inventory", "status", "workspace_id",
        "images", "custom_fields", "pricing_options", "branch_availability", "version", "plan", "bundle",
        "service_scheduling", "follow_up", "restaurant_modifiers", "pharma_lot_tracking", "pharma_warehouse_id"
    ];

    private static readonly Dictionary<string, string[]> Aliases = new(StringComparer.Ordinal)
    {
        ["name"] = ["product name", "service name", "company name", "deal name"],
        ["code"] = ["sku", "product code", "service code", "SKU / Code"],
        ["description"] = ["narration", "particulars", "details"]
    };

    internal static CatalogImportTable Read(string content, CancellationToken cancellation, string delimiter = ",")
    {
        using var parser = new TextFieldParser(new StringReader(content))
        {
            HasFieldsEnclosedInQuotes = true, TrimWhiteSpace = false
        };
        parser.SetDelimiters(delimiter);
        string[] headers = parser.ReadFields()?.Select(value => value.Trim()).ToArray() ?? [];
        if (headers.Length is < 1 or > 500 || headers.Any(string.IsNullOrWhiteSpace) ||
            headers.Distinct(StringComparer.Ordinal).Count() != headers.Length)
            throw new ArgumentException("Use 1 to 500 named, unique columns.");
        var rows = new List<string[]>();
        while (!parser.EndOfData)
        {
            cancellation.ThrowIfCancellationRequested();
            if (rows.Count == 500)
                throw new ArgumentException("Import no more than 500 offerings at a time.");
            var values = parser.ReadFields();
            if (values is null || values.Length != headers.Length)
                throw new ArgumentException($"Item {rows.Count + 1} does not match the header.");
            rows.Add(values);
        }
        if (rows.Count == 0)
            throw new ArgumentException("The file contains a header and no offering records.");
        return FromText(headers, rows);
    }

    internal static CatalogImportTable FromText(string[] headers, List<string[]> rows) =>
        new(headers, rows.Select(row => row.Select(value => (JsonNode?)JsonValue.Create(value)).ToArray()).ToList());

    internal static CatalogImportTable ReadJson(string content, CancellationToken cancellation)
    {
        if (JsonNode.Parse(content) is not JsonArray source || source.Count is < 1 or > 500)
            throw new ArgumentException("The JSON file must contain an array of 1 to 500 offerings.");
        var records = new List<JsonObject>();
        var headers = new List<string>();
        var seen = new HashSet<string>(StringComparer.Ordinal);
        foreach (var value in source)
        {
            cancellation.ThrowIfCancellationRequested();
            if (value is not JsonObject record)
                throw new ArgumentException($"Item {records.Count + 1} must be a JSON object.");
            records.Add(record);
            foreach (var field in record)
            {
                if (field.Key.Trim().Length is < 1 or > 200)
                    throw new ArgumentException("Use named JSON fields of up to 200 characters.");
                if (seen.Add(field.Key))
                    headers.Add(field.Key);
                if (headers.Count > 150)
                    throw new ArgumentException("Use at most 150 JSON fields.");
            }
        }
        if (headers.Count == 0)
            throw new ArgumentException("The JSON file has no fields to map.");
        return new(headers.ToArray(), records.Select(record => headers.Select(key => record[key]).ToArray()).ToList());
    }

    internal string Sample(int column)
    {
        var value = Rows[0][column];
        return value is JsonValue text && text.TryGetValue(out string? literal) ? literal ?? ""
            : value?.ToJsonString() ?? "";
    }

    internal string[] SuggestDestinations()
    {
        var destinations = Enumerable.Repeat("", Headers.Length).ToArray();
        var normalized = Headers.Select(Normalize).ToArray();
        foreach (string field in KnownFields)
        {
            string canonical = Normalize(field);
            int index = Array.FindIndex(normalized, text => text == canonical);
            if (index < 0 && Aliases.TryGetValue(field, out var aliases))
                index = Array.FindIndex(normalized, text => aliases.Any(alias => text == Normalize(alias)));
            if (index >= 0 && destinations[index].Length == 0)
                destinations[index] = field;
        }
        return destinations;
    }

    internal JsonArray Map(string[] destinations, string defaultKind, CancellationToken cancellation)
    {
        if (destinations.Length != Headers.Length || destinations.Any(field => field.Length > 0 &&
            !KnownFields.Contains(field, StringComparer.Ordinal)) || defaultKind is not ("product" or "service"))
            throw new ArgumentException("Choose valid catalog fields.");
        var selected = destinations.Where(field => field.Length > 0).ToArray();
        if (selected.Distinct(StringComparer.Ordinal).Count() != selected.Length)
            throw new ArgumentException("Map each catalog field at most once.");
        if (!selected.Contains("name") || !selected.Contains("code"))
            throw new ArgumentException("Map both Name and SKU / Code before continuing.");
        var result = new JsonArray();
        foreach (var values in Rows)
        {
            cancellation.ThrowIfCancellationRequested();
            var row = new JsonObject();
            for (int index = 0; index < destinations.Length; index++)
            {
                string field = destinations[index];
                if (field.Length == 0)
                    continue;
                var value = values[index];
                if (field is "price" or "tax" or "cost" or "mrp" or "reorder_level" &&
                    value is JsonValue number && number.TryGetValue(out string? text) && text is not null)
                    row[field] = text.Replace(",", "");
                else
                    row[field] = value?.DeepClone();
            }
            if (!row.ContainsKey("kind"))
                row["kind"] = defaultKind;
            result.Add(row);
        }
        return result;
    }

    private static string Normalize(string value) => new(value.ToLowerInvariant()
        .Where(character => character is >= 'a' and <= 'z' or >= '0' and <= '9').ToArray());
}
