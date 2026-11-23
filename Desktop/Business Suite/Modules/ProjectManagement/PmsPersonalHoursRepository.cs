using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PmsPersonalWorkday(int Day, bool Enabled, TimeSpan Start, TimeSpan End);
internal sealed record PmsPersonalHours(int Revision, PmsPersonalWorkday[] Workdays, bool CanSave);

internal sealed partial class PmsProjectRepository
{
    internal async Task<PmsPersonalHours> ReadMyWorkHoursAsync(CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(System.Data.IsolationLevel.RepeatableRead);
        var actor = await GetWorkspaceActorAsync(db, tx, false, cancellation);
        var identity = await settings.RequireActorAsync(db, tx, cancellation);
        var (revision, state) = await ReadPersonalCalendarAsync(db, tx, actor.UserId, false, cancellation);
        return new(revision, ParsePersonalWorkdays(state), identity.CanWriteBranch);
    }

    internal async Task SaveMyWorkHoursAsync(int revision, PmsPersonalWorkday[] workdays, CancellationToken cancellation)
    {
        if (workdays.Length != 7 || !new HashSet<int>(workdays.Select(day => day.Day)).SetEquals(Enumerable.Range(0, 7)))
            throw new InvalidOperationException("Supply each weekday once.");
        if (workdays.Any(day => !ValidWorkdayTime(day.Start) || !ValidWorkdayTime(day.End) || (day.Enabled && day.End <= day.Start)))
            throw new InvalidOperationException("Working days require a start and a later end time.");

        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await GetWorkspaceActorAsync(db, tx, true, cancellation);
        var (current, state) = await ReadPersonalCalendarAsync(db, tx, actor.UserId, true, cancellation);
        if (current != revision)
            throw new InvalidOperationException("Calendar preferences changed. Reload before saving.");
        JsonNode? original = state["workdays"];
        JsonNode? replacement = JsonSerializer.SerializeToNode(workdays.OrderBy(day => day.Day).Select(day => new
        {
            day = day.Day, enabled = day.Enabled, start = WorkdayClock(day.Start), end = WorkdayClock(day.End)
        }).ToArray());
        state["workdays"] = replacement;
        using var update = new NpgsqlCommand(revision == 0
            ? @"INSERT INTO public.pms_planner_preferences(user_id,revision,payload)
                VALUES(@actor,1,@body) ON CONFLICT (user_id) DO NOTHING"
            : @"UPDATE public.pms_planner_preferences SET revision=revision+1,payload=@body
                WHERE user_id=@actor AND revision=@revision", db, tx);
        update.Parameters.AddWithValue("actor", actor.UserId);
        update.Parameters.AddWithValue("revision", revision);
        update.Parameters.AddWithValue("body", NpgsqlDbType.Json, state.ToJsonString());
        if (await update.ExecuteNonQueryAsync(cancellation) != 1)
            throw new InvalidOperationException("Calendar preferences changed. Reload before saving.");
        using var audit = new NpgsqlCommand(@"
            INSERT INTO public.audit_logs(organization_id,user_id,actor_email,actor_authenticated,method,endpoint,status_code,
                entity_type,entity_id,action,description,module,old_values,new_values)
            SELECT @organization,id,left(email,100),true,'PUT','desktop/pms/planner/preferences',200,
                'user',id,'PMS_WORK_HOURS_UPDATED','Updated personal working hours','project_management',@before,@after
            FROM public.users WHERE id=@actor RETURNING id", db, tx);
        SetBranch(audit);
        audit.Parameters.AddWithValue("actor", actor.UserId);
        audit.Parameters.AddWithValue("before", JsonSerializer.Serialize(new { workdays = original }));
        audit.Parameters.AddWithValue("after", JsonSerializer.Serialize(new { workdays = replacement }));
        int auditId = (int)(await audit.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db, tx, "audit_logs", auditId, cancellation);
        await tx.CommitAsync(cancellation);
    }

    private async Task<(int Revision, JsonObject State)> ReadPersonalCalendarAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int user, bool write, CancellationToken cancellation)
    {
        using (var query = new NpgsqlCommand("SELECT revision,payload::text FROM public.pms_planner_preferences WHERE user_id=@user"
            + (write ? " FOR UPDATE" : ""), db, tx))
        {
            query.Parameters.AddWithValue("user", user);
            using var row = await query.ExecuteReaderAsync(cancellation);
            if (await row.ReadAsync(cancellation))
                return (row.GetInt32(0), JsonNode.Parse(row.GetString(1)) as JsonObject
                    ?? throw new InvalidOperationException("Saved calendar preferences are unavailable."));
        }

        using var defaults = new NpgsqlCommand(@"
            WITH form AS (
                SELECT v.values_json::jsonb AS defaults_json,v.scope_key=ANY(@keys) AS supported,
                    array_position(@keys,v.scope_key) AS precedence
                FROM public.suite_service_policies v WHERE v.organization_id=@organization AND v.kind='form_defaults'
            )
            SELECT coalesce((SELECT defaults_json->>'timezone' FROM form WHERE supported AND defaults_json ? 'timezone' ORDER BY precedence DESC LIMIT 1),
                    nullif(c.default_timezone,''),'Asia/Kolkata') AS timezone,
                coalesce((SELECT (defaults_json->>'week_start')::int FROM form WHERE supported AND defaults_json ? 'week_start' ORDER BY precedence DESC LIMIT 1),0),
                (SELECT (defaults_json->'working_days')::text FROM form WHERE supported AND defaults_json ? 'working_days' ORDER BY precedence DESC LIMIT 1),
                coalesce(nullif(c.working_days_per_week,0),5)
            FROM public.companies c WHERE c.id=@organization", db, tx);
        string company = $"form-defaults:company:{settings.OrganizationId}";
        string branch = $"{company}:branch:{settings.BranchId}";
        string[] keys = settings.BranchId.HasValue
            ? new[] { company, company + ":module:project_management", branch, branch + ":module:project_management" }
            : new[] { company, company + ":module:project_management" };
        SetBranch(defaults);
        defaults.Parameters.AddWithValue("keys", NpgsqlDbType.Array | NpgsqlDbType.Text, keys);
        using var data = await defaults.ExecuteReaderAsync(cancellation);
        if (!await data.ReadAsync(cancellation))
            throw new InvalidOperationException("Company calendar defaults are unavailable.");
        var days = data.IsDBNull(2) ? new HashSet<int>(Enumerable.Range(0, Math.Max(0, Math.Min(data.GetInt32(3), 7))))
            : new HashSet<int>(JsonSerializer.Deserialize<int[]>(data.GetString(2))!.Select(day => (day + 6) % 7));
        return (0, (JsonObject)JsonSerializer.SerializeToNode(new
        {
            timezone = data.GetString(0), week_start = data.GetInt32(1),
            workdays = Enumerable.Range(0, 7).Select(day => new { day, enabled = days.Contains(day), start = "09:00", end = "17:00" })
        })!);
    }

    private static PmsPersonalWorkday[] ParsePersonalWorkdays(JsonObject state)
    {
        var result = Enumerable.Range(0, 7).Select(day => new PmsPersonalWorkday(day, day < 5,
            TimeSpan.FromHours(9), TimeSpan.FromHours(17))).ToArray();
        if (state["workdays"] is null)
            return result;
        if (state["workdays"] is not JsonArray workdays)
            throw new InvalidOperationException("The person's saved work calendar is invalid.");
        foreach (var day in workdays)
        {
            if (day is not JsonObject entry || entry["day"] is not JsonValue key || !key.TryGetValue<int>(out int index)
                || index is < 0 or > 6 || entry["enabled"] is not JsonValue value || !value.TryGetValue<bool>(out bool enabled)
                || !TimeSpan.TryParseExact(entry["start"]?.GetValue<string>(), @"hh\:mm", CultureInfo.InvariantCulture, out var start)
                || !TimeSpan.TryParseExact(entry["end"]?.GetValue<string>(), @"hh\:mm", CultureInfo.InvariantCulture, out var end))
                throw new InvalidOperationException("The person's saved work calendar is invalid.");
            result[index] = new(index, enabled, start, end);
        }
        return result;
    }

    private static bool ValidWorkdayTime(TimeSpan time) => time >= TimeSpan.Zero && time < TimeSpan.FromDays(1)
        && time.Ticks % TimeSpan.TicksPerMinute == 0;

    private static string WorkdayClock(TimeSpan time) => time.ToString(@"hh\:mm", CultureInfo.InvariantCulture);
}
