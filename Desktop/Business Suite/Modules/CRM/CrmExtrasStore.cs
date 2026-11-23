using System.Globalization;
using System.Net.Mail;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed class CrmCustomValue
{
    public int Id { get; set; }
    public string Label { get; set; } = "";
    public string Kind { get; set; } = "";
    public bool Required { get; set; }
    public JsonElement Options { get; set; }
    public string? Value { get; set; }
    public string? Revision { get; set; }

    public string Choices => string.Join(", ", AllowedChoices());

    internal string[] AllowedChoices()
    {
        JsonElement source = Options;
        if (source.ValueKind == JsonValueKind.Object && !source.TryGetProperty("values", out source))
            return [];
        if (source.ValueKind == JsonValueKind.String)
            return (source.GetString() ?? "").Split([',', '\n'], StringSplitOptions.RemoveEmptyEntries)
                .Select(value => value.Trim()).ToArray();
        return source.ValueKind == JsonValueKind.Array
            ? source.EnumerateArray().Where(value => value.ValueKind == JsonValueKind.String)
                .Select(value => value.GetString()!).ToArray()
            : [];
    }
}

internal sealed class CrmTaxRegistration
{
    public string Type { get; set; } = "GSTIN";
    public string Country { get; set; } = "IN";
    public string Number { get; set; } = "";
    [JsonExtensionData]
    public Dictionary<string, JsonElement>? OtherFields { get; set; }
}

internal sealed class CrmChannel
{
    public int? Id { get; set; }
    public string Kind { get; set; } = "email";
    public string Label { get; set; } = "Work";
    public string Value { get; set; } = "";
    public string? CountryCode { get; set; }
    public bool Primary { get; set; }
    public bool WhatsApp { get; set; }
    public string? Notes { get; set; }
    public string Verification { get; set; } = "unverified";
    public string? Revision { get; set; }
    public string? Normalized { get; set; }
}

internal sealed class CrmExtras
{
    public List<CrmCustomValue> Custom { get; set; } = new();
    public List<CrmTaxRegistration> Tax { get; set; } = new();
    public List<CrmChannel> Channels { get; set; } = new();
    public string? Gst { get; set; }
    public int? FinancialVersion { get; set; }

    [JsonIgnore] public string Snapshot { get; set; } = "";
    [JsonIgnore] public bool ChannelsEdited { get; set; }

    public CrmExtras Copy() => CrmExtrasStore.Decode(JsonSerializer.Serialize(this, CrmExtrasStore.Json), Snapshot, ChannelsEdited);
}

internal static class CrmExtrasStore
{
    internal static readonly JsonSerializerOptions Json = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        PropertyNameCaseInsensitive = true
    };

    internal static CrmExtras Decode(string json, string snapshot, bool channelsEdited = false)
    {
        CrmExtras data = JsonSerializer.Deserialize<CrmExtras>(json, Json)!;
        data.Snapshot = snapshot;
        data.ChannelsEdited = channelsEdited;
        return data;
    }

    public static async Task<CrmExtras> LoadAsync(CrmDirectoryKind kind, int? id, CancellationToken cancellation)
    {
        var settings = DesktopDatabaseSettings.Load();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(System.Data.IsolationLevel.RepeatableRead);
        await CrmDirectoryWrites.RequireCrmActorAsync(settings, db, tx, cancellation,
            CrmDirectoryWrites.PermissionEntity(kind), id.HasValue ? "edit" : "create");
        if (id.HasValue)
        {
            string table = kind == CrmDirectoryKind.Companies ? "crm_companies" : "crm_contacts";
            using var scope = new NpgsqlCommand($"SELECT id FROM public.{table} r WHERE organization_id=@org " +
                "AND id=@id AND deleted_at IS NULL AND " + CrmDirectoryWrites.BranchScope(table, "r"), db, tx);
            Param(scope, "org", NpgsqlDbType.Integer, settings.OrganizationId);
            Param(scope, "id", NpgsqlDbType.Integer, id);
            Param(scope, "scope_branch", NpgsqlDbType.Integer, settings.BranchId);
            if (await scope.ExecuteScalarAsync(cancellation) is null)
                throw new InvalidOperationException("Open this record from its owning branch to edit its details.");
        }
        string snapshot = await ReadSnapshot(db, tx, settings.OrganizationId, kind, id, cancellation);
        return Decode(snapshot, snapshot);
    }

    internal static async Task<string> ReadSnapshot(NpgsqlConnection db, NpgsqlTransaction? tx, int org,
        CrmDirectoryKind kind, int? id, CancellationToken cancellation)
    {
        bool company = kind == CrmDirectoryKind.Companies;
        string owner = company ? "account_id" : "contact_id";
        string tax = company
            ? "(SELECT tax_registrations FROM public.suite_company_master_details WHERE organization_id=@org AND account_id=@id)"
            : "NULL";
        string gst = company ? "NULL" :
            "(SELECT gst_number FROM public.crm_contact_financial_profiles WHERE organization_id=@org AND contact_id=@id)";
        string version = company ? "NULL" :
            "(SELECT version FROM public.crm_contact_financial_profiles WHERE organization_id=@org AND contact_id=@id)";

        using var cmd = new NpgsqlCommand($@"SELECT jsonb_build_object(
            'custom', COALESCE((
                SELECT jsonb_agg(jsonb_build_object('id', f.id, 'label', f.label, 'kind', COALESCE(f.field_type,'text'),
                    'required', COALESCE(f.is_required,false), 'options', f.options_json, 'revision', v.xmin::text,
                    'value', COALESCE(v.value_text, v.value_number::text, v.value_date::text, v.value_datetime::text,
                        v.value_boolean::text, v.value_json::text)) ORDER BY f.position, f.label, f.id)
                FROM public.crm_custom_fields f
                LEFT JOIN public.crm_custom_field_values v ON v.organization_id=@org AND v.entity=@entity
                    AND v.custom_field_id=f.id AND v.record_id=@id AND v.deleted_at IS NULL
                WHERE f.organization_id=@org AND f.entity=@entity AND f.is_active AND f.deleted_at IS NULL
            ), '[]'::jsonb),
            'channels', COALESCE((
                SELECT jsonb_agg(jsonb_build_object('id', c.id, 'kind', c.kind, 'label', c.label, 'value', c.value,
                    'countryCode', c.country_code, 'primary', c.is_primary, 'whatsApp', c.whatsapp,
                    'notes', c.notes, 'verification', c.verification_status, 'revision', c.xmin::text,
                    'normalized', c.normalized_value) ORDER BY c.id)
                FROM public.suite_contact_channels c WHERE c.organization_id=@org AND c.{owner}=@id
            ), '[]'::jsonb),
            'tax', COALESCE(({tax})::jsonb, '[]'::jsonb), 'gst', {gst}, 'financialVersion', {version}
        )::text", db, tx);
        Param(cmd, "org", NpgsqlDbType.Integer, org);
        Param(cmd, "id", NpgsqlDbType.Integer, id);
        Param(cmd, "entity", NpgsqlDbType.Text, company ? "companies" : "contacts");
        return (string)(await cmd.ExecuteScalarAsync(cancellation))!;
    }

    internal static void Param(NpgsqlCommand cmd, string key, NpgsqlDbType type, object? value) =>
        cmd.Parameters.Add(key, type).Value = value ?? DBNull.Value;

    internal static string NormalizeTax(string type, string country, string number)
    {
        string value = Regex.Replace(number, @"\s+", "").ToUpperInvariant();
        string kind = type.Replace(" ", "").ToUpperInvariant();
        if (kind == "GST") kind = "GSTIN";
        if (kind == "UAETRN") kind = "TRN";
        string? pattern = kind switch
        {
            "PAN" => "[A-Z]{5}[0-9]{4}[A-Z]",
            "GSTIN" => "[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]",
            "CIN" => "[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}",
            "LLPIN" => "(?:[A-Z]{3}-[0-9]{4}|F[A-Z]{2}-[0-9]{4})",
            "TRN" => "[0-9]{15}",
            _ => null
        };
        if (value.Length == 0 || value.Length > 100)
            throw new ArgumentException("Enter a tax registration number of up to 100 characters.");
        if (pattern is null)
            return value;
        string region = country.Trim().ToUpperInvariant();
        bool applicable = kind == "TRN" ? region is "AE" or "UNITED ARAB EMIRATES" or "UAE" : region is "IN" or "INDIA";
        if (!applicable || !Regex.IsMatch(value, "^(?:" + pattern + ")$"))
            throw new ArgumentException($"Enter a valid {kind} for its country.");
        if (kind == "GSTIN")
        {
            const string alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
            int sum = 0;
            for (int i = 0; i < 14; i++)
            {
                int n = alphabet.IndexOf(value[i]) * (1 + i % 2);
                sum += n / 36 + n % 36;
            }
            if (value[14] != alphabet[(36 - sum % 36) % 36])
                throw new ArgumentException("The GSTIN checksum is invalid.");
        }
        return value;
    }

    internal static void NormalizeChannels(List<CrmChannel> rows)
    {
        if (rows.Count > 30)
            throw new ArgumentException("Use at most 30 communication channels.");
        foreach (CrmChannel row in rows)
        {
            row.Kind = (row.Kind ?? "").Trim().ToLowerInvariant();
            row.Value = (row.Value ?? "").Trim();
            row.Label = (row.Label ?? "").Trim();
            row.CountryCode = row.CountryCode?.Trim();
            row.Notes = row.Notes?.Trim();
            if (row.Label.Length is < 1 or > 50 || row.Value.Length is < 1 or > 254 || (row.Notes?.Length ?? 0) > 500)
                throw new ArgumentException("Enter a channel value, a label up to 50 characters, and notes up to 500 characters.");
            if (row.Kind == "email")
            {
                try
                {
                    if (!new MailAddress(row.Value).Address.Equals(row.Value, StringComparison.OrdinalIgnoreCase))
                        throw new FormatException();
                }
                catch (FormatException) { throw new ArgumentException("Enter a valid channel email."); }
                row.Normalized = row.Value.ToLowerInvariant();
                row.CountryCode = null;
                row.WhatsApp = false;
            }
            else if (row.Kind == "phone")
            {
                CrmPhoneNumber number = CrmPhone.Normalize(row.Value, row.CountryCode);
                row.Value = number.National;
                row.Normalized = number.International;
            }
            else
                throw new ArgumentException("Channel kind must be email or phone.");
        }

        if (rows.GroupBy(row => (row.Kind, row.Normalized)).Any(group => group.Count() > 1))
            throw new ArgumentException("Remove duplicate channels for this record.");
        foreach (var group in rows.GroupBy(row => row.Kind))
        {
            int primary = group.Count(row => row.Primary);
            if (primary > 1)
                throw new ArgumentException($"Choose one primary {group.Key}.");
            if (primary == 0)
                group.First().Primary = true;
        }
    }

    internal static void ValidateTax(CrmExtras extras, bool company)
    {
        if (!company)
        {
            string gst = extras.Gst?.Trim() ?? "";
            extras.Gst = gst.Length == 0 ? null : NormalizeTax("GSTIN", "IN", gst);
            return;
        }

        if (extras.Tax.Count > 20)
            throw new ArgumentException("Use at most 20 company tax registrations.");
        foreach (CrmTaxRegistration item in extras.Tax)
        {
            item.Type = (item.Type ?? "").Trim();
            item.Country = (item.Country ?? "").Trim();
            if (item.Type.Length is < 1 or > 100 || item.Country.Length is < 1 or > 100)
                throw new ArgumentException("Enter a type and country for each tax registration.");
            item.Number = NormalizeTax(item.Type, item.Country, item.Number ?? "");
        }
        if (extras.Tax.GroupBy(item => item.Number, StringComparer.OrdinalIgnoreCase).Any(group => group.Count() > 1))
            throw new ArgumentException("Remove duplicate tax registration numbers.");
    }
}
