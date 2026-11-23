using System.Globalization;
using System.Net.Mail;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal static class CrmExtrasWrites
{
    private static readonly CultureInfo Invariant = CultureInfo.InvariantCulture;

    internal static async Task EnsurePrimaryPhoneAsync(NpgsqlConnection db, NpgsqlTransaction tx, int org,
        int id, bool company, CrmPhoneNumber phone, CancellationToken cancellation)
    {
        string owner = company ? "account_id" : "contact_id";
        using var command = Command(db, tx, $@"INSERT INTO public.suite_contact_channels
            (organization_id,{owner},kind,label,value,normalized_value,country_code,is_primary,whatsapp,verification_status)
            SELECT @org,@id,'phone','Primary',@national,@international,@code,true,false,'unverified'
            WHERE NOT EXISTS (SELECT 1 FROM public.suite_contact_channels
                WHERE organization_id=@org AND {owner}=@id AND kind='phone')", org, id);
        Add(command, "national", NpgsqlDbType.Text, phone.National);
        Add(command, "international", NpgsqlDbType.Text, phone.International);
        Add(command, "code", NpgsqlDbType.Text, phone.CallingCode);
        await command.ExecuteNonQueryAsync(cancellation);
    }

    internal static async Task<bool> HasDuplicateAsync(NpgsqlConnection db, NpgsqlTransaction tx, int org,
        CrmDirectoryKind kind, int? id, CrmExtras extras, CrmExtras original, CancellationToken cancellation)
    {
        bool company = kind == CrmDirectoryKind.Companies;
        string owner = company ? "account_id" : "contact_id";
        string[] taxNumbers = company ? extras.Tax.Select(item => item.Number)
            .Except(original.Tax.Select(item => item.Number), StringComparer.OrdinalIgnoreCase).ToArray() : [];
        string[] channelValues = extras.ChannelsEdited ? extras.Channels
            .Where(item => !original.Channels.Any(previous => previous.Kind == item.Kind && previous.Normalized == item.Normalized))
            .Select(item => item.Normalized!).ToArray() : [];
        if (taxNumbers.Length == 0 && channelValues.Length == 0)
            return false;

        using var command = Command(db, tx, $@"SELECT EXISTS (
            SELECT 1 FROM public.suite_company_master_details d
            JOIN public.crm_companies c ON c.id=d.account_id AND c.organization_id=d.organization_id
            CROSS JOIN LATERAL json_array_elements(d.tax_registrations) r
            WHERE d.organization_id=@org AND c.deleted_at IS NULL AND d.account_id IS DISTINCT FROM @company_id
              AND upper(regexp_replace(r->>'number', '\s', '', 'g'))=ANY(@tax)
        ) OR EXISTS (
            SELECT 1 FROM public.suite_contact_channels x
            LEFT JOIN public.crm_companies c ON c.id=x.account_id AND c.organization_id=x.organization_id
            LEFT JOIN public.crm_contacts p ON p.id=x.contact_id AND p.organization_id=x.organization_id
            WHERE x.organization_id=@org AND (@id IS NULL OR x.{owner} IS DISTINCT FROM @id)
              AND ((c.id IS NOT NULL AND c.deleted_at IS NULL) OR (p.id IS NOT NULL AND p.deleted_at IS NULL))
              AND x.normalized_value=ANY(@channels)
              AND NOT EXISTS (SELECT 1 FROM public.suite_contact_identity_links link WHERE link.organization_id=@org AND
                ((@kind='company' AND link.account_id=@id AND link.contact_id=x.contact_id)
                 OR (@kind='contact' AND link.contact_id=@id AND link.account_id=x.account_id)))
        ) OR EXISTS (
            SELECT 1 FROM (
                SELECT c.id, 'company' AS kind, c.email, c.phone, c.phone_country_code
                    FROM public.crm_companies c WHERE c.organization_id=@org AND c.deleted_at IS NULL
                UNION ALL
                SELECT p.id, 'contact', p.email, p.phone, p.phone_country_code
                    FROM public.crm_contacts p WHERE p.organization_id=@org AND p.deleted_at IS NULL
            ) identities
            WHERE NOT (identities.id IS NOT DISTINCT FROM @id AND identities.kind=@kind)
              AND NOT EXISTS (SELECT 1 FROM public.suite_contact_identity_links link WHERE link.organization_id=@org AND
                ((@kind='company' AND identities.kind='contact' AND link.account_id=@id AND link.contact_id=identities.id)
                 OR (@kind='contact' AND identities.kind='company' AND link.contact_id=@id AND link.account_id=identities.id)))
              AND (lower(trim(email))=ANY(@channels)
                OR (CASE WHEN trim(phone) LIKE '+%' THEN regexp_replace(phone,'[ ().-]','','g')
                         WHEN phone_country_code IS NOT NULL THEN phone_country_code || regexp_replace(phone,'[ ().-]','','g')
                    END)=ANY(@channels))
        )", org, id);
        Add(command, "kind", NpgsqlDbType.Text, company ? "company" : "contact");
        Add(command, "company_id", NpgsqlDbType.Integer, company ? id : null);
        Add(command, "tax", NpgsqlDbType.Array | NpgsqlDbType.Text, taxNumbers);
        Add(command, "channels", NpgsqlDbType.Array | NpgsqlDbType.Text, channelValues);
        return (bool)(await command.ExecuteScalarAsync(cancellation))!;
    }

    internal static async Task SaveAsync(NpgsqlConnection db, NpgsqlTransaction tx, int org, int id,
        CrmDirectoryKind kind, CrmExtras extras, CrmExtras original, CancellationToken cancellation)
    {
        bool company = kind == CrmDirectoryKind.Companies;
        foreach (CrmCustomValue field in extras.Custom)
        {
            var previous = original.Custom.SingleOrDefault(item => item.Id == field.Id)
                ?? throw new InvalidOperationException("The custom field list changed. Reopen the editor.");
            if (field.Value != previous.Value)
                await SaveCustomAsync(db, tx, org, id, company ? "companies" : "contacts", previous, field.Value, cancellation);
        }

        if (company)
        {
            string tax = JsonSerializer.Serialize(extras.Tax, CrmExtrasStore.Json);
            if (tax != JsonSerializer.Serialize(original.Tax, CrmExtrasStore.Json))
            {
                using var command = Command(db, tx, @"UPDATE public.suite_company_master_details
                    SET tax_registrations=@tax WHERE organization_id=@org AND account_id=@id", org, id);
                Add(command, "tax", NpgsqlDbType.Json, tax);
                await command.ExecuteNonQueryAsync(cancellation);
            }
        }
        else if (extras.Gst != original.Gst)
        {
            using var command = Command(db, tx, original.FinancialVersion.HasValue
                ? @"UPDATE public.crm_contact_financial_profiles SET gst_number=@gst, version=version+1
                    WHERE organization_id=@org AND contact_id=@id AND version=@version"
                : @"INSERT INTO public.crm_contact_financial_profiles
                    (organization_id, contact_id, gst_number, bank_accounts, upi_ids, version)
                    VALUES (@org,@id,@gst,'[]'::json,'[]'::json,1) ON CONFLICT (contact_id) DO NOTHING", org, id);
            Add(command, "gst", NpgsqlDbType.Text, extras.Gst);
            Add(command, "version", NpgsqlDbType.Integer, original.FinancialVersion);
            if (await command.ExecuteNonQueryAsync(cancellation) != 1)
                throw new InvalidOperationException("The contact tax details changed. Reopen the editor.");
        }

        if (extras.ChannelsEdited)
            await SaveChannelsAsync(db, tx, org, id, company, extras.Channels, original.Channels, cancellation);
    }

    private static async Task SaveCustomAsync(NpgsqlConnection db, NpgsqlTransaction tx, int org, int id,
        string entity, CrmCustomValue field, string? input, CancellationToken cancellation)
    {
        var value = ParseCustom(field, input);
        using var command = Command(db, tx, @"INSERT INTO public.crm_custom_field_values
                (organization_id, entity, record_id, custom_field_id, value_text, value_number, value_date,
                 value_datetime, value_boolean, value_json, updated_at)
            VALUES (@org,@entity,@id,@field,@text,@number,@date,@datetime,@boolean,@json,now())
            ON CONFLICT (organization_id, custom_field_id, entity, record_id) DO UPDATE SET
                value_text=excluded.value_text, value_number=excluded.value_number, value_date=excluded.value_date,
                value_datetime=excluded.value_datetime, value_boolean=excluded.value_boolean, value_json=excluded.value_json,
                updated_at=now(), deleted_at=NULL
            WHERE crm_custom_field_values.xmin::text = @revision
               OR (@revision IS NULL AND crm_custom_field_values.deleted_at IS NOT NULL)", org, id);
        Add(command, "entity", NpgsqlDbType.Text, entity);
        Add(command, "field", NpgsqlDbType.Integer, field.Id);
        Add(command, "revision", NpgsqlDbType.Text, field.Revision);
        Add(command, "text", NpgsqlDbType.Text, value.Text);
        Add(command, "number", NpgsqlDbType.Numeric, value.Number);
        Add(command, "date", NpgsqlDbType.Date, value.Date);
        Add(command, "datetime", NpgsqlDbType.TimestampTz, value.DateTime);
        Add(command, "boolean", NpgsqlDbType.Boolean, value.Boolean);
        Add(command, "json", NpgsqlDbType.Json, value.Json);
        if (await command.ExecuteNonQueryAsync(cancellation) != 1)
            throw new InvalidOperationException($"Custom field {field.Label} changed. Reopen the editor.");
    }

    private sealed record Storage(string? Text = null, decimal? Number = null, DateTime? Date = null,
        DateTime? DateTime = null, bool? Boolean = null, string? Json = null);

    private static Storage ParseCustom(CrmCustomValue field, string? input)
    {
        string value = input?.Trim() ?? "";
        if (value.Length == 0)
        {
            if (field.Required)
                throw new ArgumentException($"{field.Label} is required.");
            return new();
        }
        if (value.Length > 10000)
            throw new ArgumentException($"{field.Label} is too long.");
        string[] options = field.AllowedChoices();
        switch (field.Kind)
        {
            case "number": case "currency": case "decimal": case "integer": case "user": case "owner":
                if (decimal.TryParse(value, NumberStyles.Number, Invariant, out decimal number)
                    && number > -100000000000000m && number < 100000000000000m
                    && (field.Kind is not ("integer" or "user" or "owner") || number == decimal.Truncate(number)))
                    return new(Number: number);
                break;
            case "date":
                if (System.DateTime.TryParseExact(value, "yyyy-MM-dd", Invariant, DateTimeStyles.None, out var date))
                    return new(Date: date);
                break;
            case "datetime": case "date_time":
                if (DateTimeOffset.TryParse(value, Invariant, DateTimeStyles.AssumeLocal, out var dateTime))
                    return new(DateTime: dateTime.UtcDateTime);
                break;
            case "boolean": case "checkbox":
                if (bool.TryParse(value, out bool flag)) return new(Boolean: flag);
                if (value is "1" or "yes" or "on") return new(Boolean: true);
                if (value is "0" or "no" or "off") return new(Boolean: false);
                break;
            case "dropdown": case "select": case "radio": case "combobox":
                if (options.Length == 0 || options.Contains(value)) return new(Text: value);
                break;
            case "multi_select":
                string[] selected = value.StartsWith("[") ? ParseSelections(value, field.Label) :
                    value.Split(',').Select(item => item.Trim()).Where(item => item.Length > 0).Distinct().ToArray();
                if ((selected.Length > 0 || !field.Required)
                    && (options.Length == 0 || selected.All(options.Contains)))
                    return new(Json: JsonSerializer.Serialize(selected));
                break;
            case "email":
                try
                {
                    if (new MailAddress(value).Address.Equals(value, StringComparison.OrdinalIgnoreCase))
                        return new(Text: value);
                }
                catch (FormatException) { }
                break;
            case "url":
                if (Uri.TryCreate(value, UriKind.Absolute, out Uri? uri) && uri.Scheme is "http" or "https" && uri.Host.Length > 0)
                    return new(Text: value);
                break;
            case "phone":
                try
                {
                    using var json = JsonDocument.Parse(value);
                    if (json.RootElement.ValueKind == JsonValueKind.Object &&
                        json.RootElement.TryGetProperty("national_number", out var phone) && phone.ValueKind == JsonValueKind.String &&
                        json.RootElement.TryGetProperty("country_code", out var code) && code.ValueKind == JsonValueKind.String)
                    {
                        var channel = new CrmChannel { Kind = "phone", Value = phone.GetString()!, CountryCode = code.GetString() };
                        CrmExtrasStore.NormalizeChannels([channel]);
                        return new(Json: JsonSerializer.Serialize(new { national_number = channel.Value, country_code = channel.CountryCode }));
                    }
                }
                catch (JsonException) { }
                break;
            case "json":
                try
                {
                    using var json = JsonDocument.Parse(value);
                    return new(Json: json.RootElement.GetRawText());
                }
                catch (JsonException) { }
                break;
            default: return new(Text: value);
        }
        throw new ArgumentException($"Enter a valid {field.Kind} value for {field.Label}.");
    }

    private static string[] ParseSelections(string value, string label)
    {
        try { return JsonSerializer.Deserialize<string[]>(value) ?? []; }
        catch (JsonException) { throw new ArgumentException($"Enter comma-separated choices for {label}."); }
    }

    private static async Task SaveChannelsAsync(NpgsqlConnection db, NpgsqlTransaction tx, int org, int id,
        bool company, List<CrmChannel> channels, List<CrmChannel> original, CancellationToken cancellation)
    {
        string owner = company ? "account_id" : "contact_id";
        // Clear flags first, so switching a primary also works with the partial unique index.
        using (var clear = Command(db, tx, $"UPDATE public.suite_contact_channels SET is_primary=false WHERE organization_id=@org AND {owner}=@id AND is_primary", org, id))
            await clear.ExecuteNonQueryAsync(cancellation);

        foreach (CrmChannel previous in original.Where(item => !channels.Any(next =>
                     next.Kind == item.Kind && next.Normalized == item.Normalized)))
        {
            using var remove = Command(db, tx, $"DELETE FROM public.suite_contact_channels WHERE organization_id=@org AND {owner}=@id AND id=@channel", org, id);
            Add(remove, "channel", NpgsqlDbType.Integer, previous.Id);
            await remove.ExecuteNonQueryAsync(cancellation);
        }

        foreach (CrmChannel next in channels)
        {
            CrmChannel? previous = original.FirstOrDefault(item => item.Kind == next.Kind && item.Normalized == next.Normalized);
            using var write = Command(db, tx, previous is null
                ? $@"INSERT INTO public.suite_contact_channels (organization_id,{owner},kind,label,value,normalized_value,
                        country_code,is_primary,whatsapp,notes,verification_status)
                     VALUES (@org,@id,@kind,@label,@value,@normalized,@code,@primary,@whatsapp,@notes,'unverified')"
                : $@"UPDATE public.suite_contact_channels SET label=@label,value=@value,country_code=@code,
                        is_primary=@primary,whatsapp=@whatsapp,notes=@notes,updated_at=now()
                     WHERE organization_id=@org AND {owner}=@id AND id=@channel", org, id);
            Add(write, "channel", NpgsqlDbType.Integer, previous?.Id);
            Add(write, "kind", NpgsqlDbType.Text, next.Kind);
            Add(write, "label", NpgsqlDbType.Text, next.Label);
            Add(write, "value", NpgsqlDbType.Text, next.Value);
            Add(write, "normalized", NpgsqlDbType.Text, next.Normalized);
            Add(write, "code", NpgsqlDbType.Text, next.CountryCode);
            Add(write, "primary", NpgsqlDbType.Boolean, next.Primary);
            Add(write, "whatsapp", NpgsqlDbType.Boolean, next.WhatsApp);
            Add(write, "notes", NpgsqlDbType.Text, next.Notes);
            if (await write.ExecuteNonQueryAsync(cancellation) != 1)
                throw new InvalidOperationException("Communication channels changed. Reopen the editor.");
        }
    }

    private static NpgsqlCommand Command(NpgsqlConnection db, NpgsqlTransaction tx, string sql, int org, int? id)
    {
        var command = new NpgsqlCommand(sql, db, tx);
        Add(command, "org", NpgsqlDbType.Integer, org);
        Add(command, "id", NpgsqlDbType.Integer, id);
        return command;
    }

    private static void Add(NpgsqlCommand command, string name, NpgsqlDbType type, object? value) =>
        CrmExtrasStore.Param(command, name, type, value);
}
