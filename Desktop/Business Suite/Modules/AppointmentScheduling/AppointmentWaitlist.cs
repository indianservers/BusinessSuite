using System.Data;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record WaitlistDraft(Guid Request, int Customer, int Service, DateTime From, DateTime Until,
    TimeSpan Opens, TimeSpan Closes, string Zone, int? Provider, int[] Resources,
    bool FlexibleProvider, bool FlexibleResources, string Notes);
internal sealed record WaitlistEntry(int Id, int Revision, string Customer, string Service,
    string From, string Until, string Zone);

internal sealed partial class AppointmentRepository
{
    private const string WaitlistTitle = "Service waitlist preference";
    private const string WaitlistScope = @" WHERE organization_id=@org AND branch_id=@branch
        AND kind='prebooking_waitlist' AND created_by=@actor AND status='waiting'";

    internal SalesIntentJournal<WaitlistDraft> WaitlistJournal() =>
        new(settings, "Appointment waitlist", settings.ExpectedAddress, ValidateWaitlistShape,
            "The saved waitlist preference could not be read.");

    internal async Task<List<WaitlistEntry>> WaitlistAsync(CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeAsync(db, tx, "view", cancellation);
        using var command = Query(db, tx, @"SELECT id,revision,data->>'customer_name',data->>'service_name',
              data->>'from_date',data->>'until_date',data->>'timezone'
              FROM public.srm_industry_records" + WaitlistScope + " ORDER BY id DESC LIMIT 20",
            ("actor", NpgsqlDbType.Integer, actor.Id));
        using var reader = await command.ExecuteReaderAsync(cancellation);
        var entries = new List<WaitlistEntry>();
        while (await reader.ReadAsync(cancellation))
            entries.Add(new(reader.GetInt32(0), reader.GetInt32(1), reader.GetString(2), reader.GetString(3),
                reader.GetString(4), reader.GetString(5), reader.GetString(6)));
        return entries;
    }

    internal async Task<int> SaveWaitlistAsync(WaitlistDraft draft, CancellationToken cancellation)
    {
        ValidateWaitlistShape(draft);
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeAsync(db, tx, "create", cancellation);
        if (await FindWaitlistAsync(db, tx, actor, draft, cancellation) is int existing)
            return existing;
        using var zone = Query(db, tx, "SELECT EXISTS (SELECT 1 FROM pg_timezone_names WHERE name=@zone)",
            ("zone", NpgsqlDbType.Text, draft.Zone));
        if (await zone.ExecuteScalarAsync(cancellation) is not true)
            throw new ArgumentException("Choose a valid waitlist timezone.");
        var now = DateTime.UtcNow;
        var today = (await LocalAsync(db, tx, now, draft.Zone, cancellation)).Date;
        if (draft.From.Date < today || draft.Until.Date > today.AddDays(90))
            throw new ArgumentException("Choose a date range within the next 90 days in the selected timezone.");
        using var customerCommand = Query(db, tx, Customers + " AND c.id=@customer",
            ("customer", NpgsqlDbType.Integer, draft.Customer));
        string customer;
        using (var row = await customerCommand.ExecuteReaderAsync(cancellation))
        {
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("The selected customer is unavailable in this branch.");
            customer = row.GetString(1);
        }
        var service = await ReadServiceAsync(db, tx, draft.Service, cancellation);
        using var policy = Query(db, tx, @"SELECT id,employee_categories::text FROM public.srm_service_booking_policies
            WHERE organization_id=@org AND branch_id=@branch AND pack_context_id IS NULL
              AND service_product_id=@service AND active FOR SHARE",
            ("service", NpgsqlDbType.Integer, draft.Service));
        int policyId;
        string[] categories;
        using (var row = await policy.ExecuteReaderAsync(cancellation))
        {
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("Choose an actively scheduled service.");
            policyId = row.GetInt32(0);
            categories = row.IsDBNull(1) ? [] : JsonSerializer.Deserialize<string[]>(row.GetString(1)) ?? [];
        }
        int[] ids = draft.Provider is int id ? [id, .. draft.Resources] : draft.Resources;
        var resources = await ResourcesAsync(db, tx, ids, true, cancellation);
        var provider = resources.SingleOrDefault(resource => resource.Id == draft.Provider);
        if (resources.Any(resource => resource.Status != "active" || (resource != provider &&
                resource.Kind is not ("room" or "chair" or "equipment" or "location"))))
            throw new InvalidOperationException("Choose current additional resources in this branch.");
        if (provider is not null)
        {
            if (!provider.IsProvider || provider.Employee is not int employee)
                throw new InvalidOperationException("Choose a qualified provider.");
            var providerToday = (await LocalAsync(db, tx, now, provider.Zone, cancellation)).Date;
            using var eligibility = Query(db, tx, @"SELECT h.work_categories::text FROM public.srm_service_specialist_eligibility e
                JOIN public.employees h ON h.id=@employee AND h.branch_id=@branch AND h.deleted_at IS NULL
                  AND h.status IN ('Active','Probation','On Leave') AND (h.date_of_exit IS NULL OR h.date_of_exit>@today)
                WHERE e.organization_id=@org AND e.branch_id=@branch AND e.pack_context_id IS NULL AND e.active
                  AND e.booking_policy_id=@policy AND e.service_product_id=@service AND e.provider_resource_id=@provider
                  AND (e.effective_from IS NULL OR e.effective_from<=@now) AND (e.effective_until IS NULL OR e.effective_until>@now)",
                ("employee", NpgsqlDbType.Integer, employee), ("today", NpgsqlDbType.Date, providerToday),
                ("now", NpgsqlDbType.TimestampTz, now),
                ("policy", NpgsqlDbType.Integer, policyId), ("service", NpgsqlDbType.Integer, draft.Service),
                ("provider", NpgsqlDbType.Integer, provider.Id));
            using var staff = await eligibility.ExecuteReaderAsync(cancellation);
            if (!await staff.ReadAsync(cancellation))
                throw new InvalidOperationException("Choose a currently qualified provider.");
            if (categories.Length > 0)
            {
                string[] values = staff.IsDBNull(0) ? [] : JsonSerializer.Deserialize<string[]>(staff.GetString(0)) ?? [];
                if (!values.Any(value => categories.Any(category => value.Equals(category, StringComparison.OrdinalIgnoreCase)
                    || value.StartsWith(category + " > ", StringComparison.OrdinalIgnoreCase))))
                    throw new InvalidOperationException("The preferred provider is outside the service's employee categories.");
            }
        }
        var required = service.Metadata["service_resource_requirements"]?[policyId.ToString(CultureInfo.InvariantCulture)]?.AsArray();
        if (!draft.FlexibleResources && required is not null &&
            required.Any(kind => !resources.Any(resource => resource.Kind == kind?.GetValue<string>())))
            throw new InvalidOperationException("Choose the required resources or allow alternatives.");
        var payload = WaitlistData(draft, provider?.Employee);
        var data = JsonSerializer.SerializeToNode(payload)!.AsObject();
        data.Remove("request_id");
        data.Remove("title");
        data["_request_digest"] = WaitlistDigest(payload);
        data["_desktop_provider_resource"] = draft.Provider;
        data["customer_name"] = customer;
        data["service_name"] = service.Name;
        using var insert = Query(db, tx, @"INSERT INTO public.srm_industry_records
            (organization_id,branch_id,kind,title,status,revision,request_id,created_by,customer_id,data)
            VALUES (@org,@branch,'prebooking_waitlist',@title,'waiting',1,@request,@actor,@customer,@data)
            RETURNING id", ("title", NpgsqlDbType.Text, WaitlistTitle), ("request", NpgsqlDbType.Text, draft.Request.ToString()),
            ("actor", NpgsqlDbType.Integer, actor.Id), ("customer", NpgsqlDbType.Integer, draft.Customer),
            ("data", NpgsqlDbType.Json, data.ToJsonString()));
        int record = (int)(await insert.ExecuteScalarAsync(cancellation))!;
        await AuditWaitlistAsync(db, tx, actor.Id, record, "created", "draft", 1, data, cancellation);
        tx.Commit();
        return record;
    }

    internal async Task<int?> CheckWaitlistAsync(WaitlistDraft draft, CancellationToken cancellation)
    {
        ValidateWaitlistShape(draft);
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeAsync(db, tx, "view", cancellation);
        return await FindWaitlistAsync(db, tx, actor, draft, cancellation, exactScope: true);
    }

    private async Task<int?> FindWaitlistAsync(NpgsqlConnection db, NpgsqlTransaction tx, DesktopActor actor,
        WaitlistDraft draft, CancellationToken cancellation, bool exactScope = false)
    {
        using var prior = Query(db, tx, @"SELECT id,kind,branch_id,created_by,data::text FROM public.srm_industry_records
            WHERE organization_id=@org AND request_id=@request" +
            (exactScope ? " AND branch_id=@branch AND created_by=@actor AND kind='prebooking_waitlist'" : ""),
            ("request", NpgsqlDbType.Text, draft.Request.ToString()), ("actor", NpgsqlDbType.Integer, actor.Id));
        using var row = await prior.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            return null;
        if (row.GetString(1) != "prebooking_waitlist" || row.GetInt32(2) != Branch ||
            row.IsDBNull(3) || row.GetInt32(3) != actor.Id)
            throw new InvalidOperationException("This request ID is unavailable for a waitlist preference.");
        var saved = JsonNode.Parse(row.GetString(4))!;
        int? employee = saved["employee_id"]?.GetValue<int>();
        if (draft.Provider != saved["_desktop_provider_resource"]?.GetValue<int>() ||
            (string?)saved["_request_digest"] != WaitlistDigest(WaitlistData(draft, employee)))
            throw new InvalidOperationException("This request was saved with different waitlist details.");
        return row.GetInt32(0);
    }

    internal async Task CancelWaitlistAsync(int id, int revision, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeAsync(db, tx, "create", cancellation);
        using var update = Query(db, tx, @"UPDATE public.srm_industry_records SET status='cancelled',
            revision=revision+1,updated_at=now()" + WaitlistScope + " AND id=@id AND revision=@revision RETURNING data::text",
            ("actor", NpgsqlDbType.Integer, actor.Id), ("id", NpgsqlDbType.Integer, id), ("revision", NpgsqlDbType.Integer, revision));
        if (await update.ExecuteScalarAsync(cancellation) is not string json)
            throw new InvalidOperationException("The waiting preference changed or is out of scope. Refresh and try again.");
        await AuditWaitlistAsync(db, tx, actor.Id, id, "waitlist_cancelled", "cancelled", revision + 1,
            JsonNode.Parse(json)!.AsObject(), cancellation);
        tx.Commit();
    }

    private async Task AuditWaitlistAsync(NpgsqlConnection db, NpgsqlTransaction tx, int actor, int id,
        string action, string status, int revision, JsonObject data, CancellationToken cancellation)
    {
        using var audit = Query(db, tx, @"INSERT INTO public.srm_audit_logs
            (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
            VALUES (@org,'industry_prebooking_waitlist',@id,@action,@actor,@after)",
            ("id", NpgsqlDbType.Integer, id), ("action", NpgsqlDbType.Text, action), ("actor", NpgsqlDbType.Integer, actor),
            ("after", NpgsqlDbType.Json, JsonSerializer.Serialize(new { revision, status, data })));
        await audit.ExecuteNonQueryAsync(cancellation);
    }

    private static void ValidateWaitlistShape(WaitlistDraft draft)
    {
        if (draft.Request == Guid.Empty || draft.Customer <= 0 || draft.Service <= 0 ||
            draft.From.Date > draft.Until.Date || draft.Opens < TimeSpan.Zero || draft.Closes >= TimeSpan.FromDays(1) ||
            draft.Closes <= draft.Opens || draft.Opens.Ticks % TimeSpan.TicksPerSecond != 0 ||
            draft.Closes.Ticks % TimeSpan.TicksPerSecond != 0 || draft.Zone is null || draft.Zone.Length is < 1 or > 100 ||
            draft.Notes is null || draft.Notes.Length > 1000 || draft.Resources is null || draft.Resources.Length > 9 ||
            draft.Resources.Any(id => id <= 0 || id == draft.Provider) || draft.Resources.Distinct().Count() != draft.Resources.Length ||
            draft.Provider <= 0 || (!draft.FlexibleProvider && draft.Provider is null))
            throw new ArgumentException("Check the date range, time window, provider, resources and notes.");
    }

    private static SortedDictionary<string, object?> WaitlistData(WaitlistDraft draft, int? employee) => new(StringComparer.Ordinal)
    {
        ["customer_id"] = draft.Customer, ["employee_id"] = employee, ["flexible_employee"] = draft.FlexibleProvider,
        ["flexible_resources"] = draft.FlexibleResources, ["from_date"] = draft.From.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture),
        ["notes"] = draft.Notes, ["request_id"] = draft.Request.ToString(), ["resource_ids"] = draft.Resources,
        ["service_id"] = draft.Service, ["timezone"] = draft.Zone, ["title"] = WaitlistTitle,
        ["until_date"] = draft.Until.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture),
        ["window_from"] = draft.Opens.ToString(@"hh\:mm\:ss", CultureInfo.InvariantCulture),
        ["window_until"] = draft.Closes.ToString(@"hh\:mm\:ss", CultureInfo.InvariantCulture)
    };

    private static string WaitlistDigest(SortedDictionary<string, object?> payload)
    {
        // The web endpoint hashes the Python JSON defaults, including spaces and ASCII escapes.
        var json = string.Join(", ", payload.Select(pair => $"\"{pair.Key}\": {PythonValue(pair.Value)}"));
        using var hash = SHA256.Create();
        return BitConverter.ToString(hash.ComputeHash(Encoding.ASCII.GetBytes("{" + json + "}"))).Replace("-", "").ToLowerInvariant();

        static string PythonValue(object? value) => value switch
        {
            string text => PythonString(text),
            int[] ids => "[" + string.Join(", ", ids.Select(id => id.ToString(CultureInfo.InvariantCulture))) + "]",
            _ => JsonSerializer.Serialize(value)
        };

        static string PythonString(string text)
        {
            var escaped = new StringBuilder().Append('"');
            foreach (char character in text)
                escaped.Append(character switch
                {
                    '"' => "\\\"",
                    '\\' => "\\\\",
                    '\b' => "\\b",
                    '\f' => "\\f",
                    '\n' => "\\n",
                    '\r' => "\\r",
                    '\t' => "\\t",
                    < ' ' or > '~' => "\\u" + ((int)character).ToString("x4", CultureInfo.InvariantCulture),
                    _ => character.ToString()
                });
            return escaped.Append('"').ToString();
        }
    }
}
