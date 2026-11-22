using System.Net.Http;
using System.Text.Json;

namespace Business_Suite;

internal sealed record ComparisonRow(string Area, string Key, string Status, string Local, string Server);
internal sealed record ComparisonResult(List<ComparisonRow> Rows, List<string> Unavailable);

internal static class BusinessComparison
{
    private sealed record Field(string Key, string Label);
    private sealed record Area(string Name, string Path, string[] Keys, Field[] Fields, bool Paged = false);

    private static readonly Area[] Areas =
    [
        new("Customers", "master-data/companies?source=crm&role=Customer", ["gstNumber", "email"],
            [new("name", "Name"), new("email", "Email"), new("phone", "Phone"), new("country", "Country"),
             new("gstNumber", "GST number"), new("status", "Status")], true),
        new("Projects", "project-management/projects", ["project_key"],
            [new("name", "Name"), new("status", "Status"), new("start_date", "Start date"),
             new("due_date", "Due date"), new("priority", "Priority")], true),
        new("Inventory items", "fam/inventory/items", ["sku"],
            [new("item_name", "Name"), new("hsn_code", "HSN code"), new("barcode", "Barcode"),
             new("valuation_method", "Valuation"), new("active", "Active")]),
        new("Ledger accounts", "fam/ledgers", ["ledger_code"],
            [new("ledger_name", "Name"), new("nature", "Nature"), new("ledger_type", "Type"),
             new("gstin", "GST number"), new("active", "Active")])
    ];

    public static async Task<ComparisonResult> CompareAsync(NoteApi local, NoteApi server,
        CancellationToken cancellation)
    {
        var rows = new List<ComparisonRow>();
        var errors = new List<string>();
        foreach (Area area in Areas)
        {
            try
            {
                Task<List<JsonElement>> left = ReadAsync(local, area, cancellation);
                Task<List<JsonElement>> right = ReadAsync(server, area, cancellation);
                await Task.WhenAll(left, right);
                rows.AddRange(Compare(area, await left, await right));
            }
            catch (Exception error) when (error is HttpRequestException or JsonException)
            {
                errors.Add($"{area.Name} — {error.Message}");
            }
        }

        return new(rows, errors);
    }

    private static async Task<List<JsonElement>> ReadAsync(NoteApi api, Area area, CancellationToken cancellation)
    {
        const int pageSize = 100;
        bool projects = area.Path == "project-management/projects";
        var output = new List<JsonElement>();
        for (int page = 0; ; page++)
        {
            if (page >= 100)
                throw new JsonException("Too many records to compare in one preview.");

            string path = area.Path;
            if (area.Paged)
                path += projects ? $"?skip={page * pageSize}&limit={pageSize}" : $"&page={page + 1}&per_page={pageSize}";

            JsonElement response = await api.GetAsync(path, cancellation);
            JsonElement items = response;
            if (response.ValueKind == JsonValueKind.Object && !response.TryGetProperty("items", out items))
                throw new JsonException("The record list was missing.");

            if (items.ValueKind != JsonValueKind.Array)
                throw new JsonException("The server returned an invalid record list.");

            output.AddRange(items.EnumerateArray());
            if (!area.Paged || items.GetArrayLength() < pageSize)
                return output;
        }
    }

    private static IEnumerable<ComparisonRow> Compare(Area area, List<JsonElement> local, List<JsonElement> server)
    {
        var left = local.ToLookup(record => Key(area, record), StringComparer.OrdinalIgnoreCase);
        var right = server.ToLookup(record => Key(area, record), StringComparer.OrdinalIgnoreCase);
        foreach (string key in left.Select(group => group.Key).Union(right.Select(group => group.Key), StringComparer.OrdinalIgnoreCase))
        {
            JsonElement[] a = left[key].ToArray();
            JsonElement[] b = right[key].ToArray();
            if (key.Length == 0)
            {
                foreach (JsonElement row in a)
                    yield return new(area.Name, "", "Local record needs a match", Describe(area, [row]), "");
                foreach (JsonElement row in b)
                    yield return new(area.Name, "", "Server record needs a match", "", Describe(area, [row]));
                continue;
            }

            string localFields = Describe(area, a);
            string serverFields = Describe(area, b);
            string status = (a.Length, b.Length) switch
            {
                (1, 0) => "Only found locally",
                (0, 1) => "Only found on server",
                (1, 1) when localFields == serverFields => "Preview fields agree",
                (1, 1) => "Possible match with differences",
                _ => "Multiple records share this key"
            };
            yield return new(area.Name, key, status, localFields, serverFields);
        }
    }

    private static string Key(Area area, JsonElement record)
    {
        foreach (string field in area.Keys)
        {
            string value = Value(record, field).Trim();
            if (value.Length != 0)
                return $"{field}: {value}";
        }
        return "";
    }

    private static string Describe(Area area, IEnumerable<JsonElement> rows) =>
        string.Join("\r\n\r\n", rows.Select(row => string.Join("\r\n",
            area.Fields.Select(field => $"{field.Label}: {Value(row, field.Key)}"))));

    private static string Value(JsonElement record, string key)
    {
        if (record.ValueKind != JsonValueKind.Object || !record.TryGetProperty(key, out JsonElement value))
            return "";
        return value.ValueKind is JsonValueKind.String or JsonValueKind.Number or JsonValueKind.True or JsonValueKind.False
            ? value.ToString()
            : "";
    }
}
