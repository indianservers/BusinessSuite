using System.Data;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

internal sealed record WebformDetail(string Name, string Slug, string Target, bool Active, int? Rule,
    List<WebformDetailField> Fields);
internal sealed record WebformDetailField(string Key, string Label, string Type, string Mapping, bool Required);

internal sealed partial class CommunicationDraftRepository
{
    internal async Task<WebformDetail> OpenWebformAsync(int id)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        var grant = await AutoResponseGrantAsync(db, tx, branch, actor, "view");
        using var command = Scoped(@"SELECT f.name,f.public_slug,f.target_module,coalesce(f.active,false),
                f.auto_response_rule_id,coalesce(f.fields_json::text,'[]'),coalesce(f.mapping_json::text,'{}')
            FROM public.communication_webforms f
            WHERE f.id=@id AND f.organization_id=@company AND EXISTS (
                SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company AND b.branch_id=@branch
                  AND b.resource_table='communication_webforms' AND b.resource_key=f.id::text)
              AND (@scope='organization' OR EXISTS (
                SELECT 1 FROM public.communication_timeline_events e WHERE e.organization_id=@company
                  AND e.record_type='webform' AND e.record_id=f.id AND e.channel='webform'
                  AND e.event_type='created' AND e.actor_user_id=@actor))", db, tx, branch, actor.Id);
        command.Parameters.AddWithValue("id", id);
        command.Parameters.AddWithValue("scope", grant.Scope);
        using var record = await command.ExecuteReaderAsync();
        if (!await record.ReadAsync()) throw new InvalidOperationException("This webform is unavailable in the selected branch.");
        return new(record.GetString(0), record.GetString(1), record.GetString(2), record.GetBoolean(3),
            record.IsDBNull(4) ? null : record.GetInt32(4), ReadWebformFields(record.GetString(5), record.GetString(6)));
    }

    private static List<WebformDetailField> ReadWebformFields(string fields, string mapping)
    {
        using var fieldDocument = JsonDocument.Parse(fields);
        using var mappingDocument = JsonDocument.Parse(mapping);
        var mappings = mappingDocument.RootElement.ValueKind == JsonValueKind.Object
            ? mappingDocument.RootElement.EnumerateObject()
                .Where(entry => entry.Value.ValueKind == JsonValueKind.String)
                .ToLookup(entry => entry.Value.GetString() ?? "", entry => entry.Name, StringComparer.Ordinal)
            : Array.Empty<string>().ToLookup(value => value, StringComparer.Ordinal);
        var rows = new List<WebformDetailField>();
        var shownKeys = new HashSet<string>(StringComparer.Ordinal);
        if (fieldDocument.RootElement.ValueKind == JsonValueKind.Array)
        {
            foreach (var field in fieldDocument.RootElement.EnumerateArray())
            {
                if (field.ValueKind != JsonValueKind.Object) continue;
                string key = ReadWebformFieldString(field, "key");
                shownKeys.Add(key);
                rows.Add(new(key, ReadWebformFieldString(field, "label"), ReadWebformFieldString(field, "type"),
                    string.Join(", ", mappings[key]), field.TryGetProperty("required", out var required) &&
                    required.ValueKind == JsonValueKind.True));
            }
        }
        foreach (var unmappedField in mappings.Where(group => !shownKeys.Contains(group.Key)))
            rows.Add(new(unmappedField.Key, "", "", string.Join(", ", unmappedField), false));
        return rows;
    }

    private static string ReadWebformFieldString(JsonElement field, string name) =>
        field.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? "" : "";
}
