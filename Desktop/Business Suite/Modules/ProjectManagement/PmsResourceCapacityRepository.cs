using System.Data;
using System.Globalization;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PmsCapacityWeek(DataTable Days, decimal? Override, string? Revision, bool CanSave);

internal sealed partial class PmsProjectRepository
{
    internal async Task<DataTable> ReadCapacityPeopleAsync(int project, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await GetWorkspaceActorAsync(db, tx, false, cancellation);
        await ReadProjectActionAccessAsync(db, tx, actor, project, false, cancellation);
        return await ReadProjectEligibleOwnersAsync(db, tx, actor, project, cancellation);
    }

    internal async Task<PmsCapacityWeek> ReadCapacityWeekAsync(int project, int person, DateTime monday,
        CancellationToken cancellation)
    {
        monday = monday.Date;
        ValidateCapacityWeek(monday);
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await GetWorkspaceActorAsync(db, tx, false, cancellation);
        await VerifyCapacityPersonAsync(db, tx, actor, project, person, cancellation);
        var (hours, revision) = await ReadCapacityOverrideAsync(db, tx, person, monday, false, cancellation);
        var normalHours = await ReadDailyHoursAsync(db, tx, person, cancellation);
        var availability = await ReadCapacityExceptionsAsync(db, tx, person, monday, cancellation);
        var days = new DataTable();
        days.Columns.Add("date", typeof(DateTime));
        days.Columns.Add("hours", typeof(decimal));
        days.Columns.Add("reason", typeof(string));
        decimal total = normalHours.Sum();
        for (int day = 0; day < 7; day++)
        {
            DateTime date = monday.AddDays(day);
            decimal planned = hours.HasValue && total != 0 ? hours.Value * normalHours[day] / total : normalHours[day];
            var exception = availability.Rows[day];
            bool holiday = exception.Field<bool>("holiday");
            bool approved = exception.Field<bool>("approved_leave");
            decimal available = holiday ? 0 : approved ? planned * (exception.Field<bool>("half_day") ? 0.5m : 0m) : planned;
            string reason = approved ? "Approved leave" : holiday ? "Holiday" : planned == 0 ? "Non-working day" : "";
            days.Rows.Add(date, decimal.Round(available, 2, MidpointRounding.ToEven), reason);
        }
        var identity = await settings.RequireActorAsync(db, tx, cancellation);
        return new(days, hours, revision, actor.OrganizationAdmin && actor.ModuleCanEdit && identity.CanWriteBranch);
    }

    internal async Task SaveCapacityWeekAsync(int project, int person, DateTime monday, decimal hours, string? revision,
        CancellationToken cancellation)
    {
        monday = monday.Date;
        ValidateCapacityWeek(monday);
        if (hours is < 0 or > 168 || decimal.Round(hours, 2) != hours)
            throw new InvalidOperationException("Enter weekly capacity from 0 to 168 hours, with at most two decimal places.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await GetWorkspaceActorAsync(db, tx, true, cancellation);
        if (!actor.OrganizationAdmin || !actor.ModuleCanEdit)
            throw new UnauthorizedAccessException("Organization administrator access is required to change dated capacity.");
        await VerifyCapacityPersonAsync(db, tx, actor, project, person, cancellation);
        var (previous, token) = await ReadCapacityOverrideAsync(db, tx, person, monday, true, cancellation);
        if (revision != token)
            throw new InvalidOperationException("Dated capacity changed. Refresh the week before saving.");
        if (previous == hours)
            return;
        using var change = new NpgsqlCommand(token is null
            ? @"INSERT INTO public.pms_user_capacity(organization_id,user_id,week_start_date,capacity_hours)
                VALUES(@organization,@person,@monday,@hours) ON CONFLICT ON CONSTRAINT uq_pms_user_capacity_week
                DO NOTHING RETURNING id"
            : @"UPDATE public.pms_user_capacity SET capacity_hours=@hours,updated_at=clock_timestamp()
                WHERE organization_id=@organization AND user_id=@person AND week_start_date=@monday
                    AND xmin::text=@revision RETURNING id", db, tx);
        SetBranch(change);
        change.Parameters.AddWithValue("person", person);
        change.Parameters.AddWithValue("monday", NpgsqlDbType.Date, monday);
        change.Parameters.AddWithValue("hours", hours);
        change.Parameters.Add("revision", NpgsqlDbType.Text).Value = (object?)token ?? DBNull.Value;
        if (await change.ExecuteScalarAsync(cancellation) is not int rowId)
            throw new InvalidOperationException("Dated capacity changed. Refresh the week before saving.");
        if (token is null)
            await RecordOwnershipAsync(db, tx, "pms_user_capacity", rowId, cancellation);

        using var audit = new NpgsqlCommand(@"
            INSERT INTO public.audit_logs(organization_id,user_id,actor_email,actor_authenticated,method,endpoint,status_code,
                entity_type,entity_id,action,description,module,project_id,old_values,new_values)
            SELECT @organization,id,left(email,100),true,'PUT','desktop/pms/management/capacity',200,
                'user',@person,'PMS_CAPACITY_UPDATED','Updated dated capacity','project_management',@project,@before,@after
            FROM public.users WHERE id=@actor RETURNING id", db, tx);
        SetBranch(audit);
        audit.Parameters.AddWithValue("person", person);
        audit.Parameters.AddWithValue("project", project);
        audit.Parameters.AddWithValue("actor", actor.UserId);
        audit.Parameters.AddWithValue("before", JsonSerializer.Serialize(new { capacity_hours = previous }));
        audit.Parameters.AddWithValue("after", JsonSerializer.Serialize(new
        {
            user_id = person, week_start_date = ScheduleDate(monday), capacity_hours = hours
        }));
        int auditId = (int)(await audit.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db, tx, "audit_logs", auditId, cancellation);
        await tx.CommitAsync(cancellation);
    }

    private async Task VerifyCapacityPersonAsync(NpgsqlConnection db, NpgsqlTransaction tx, PmsActor actor, int project,
        int person, CancellationToken cancellation)
    {
        await ReadProjectActionAccessAsync(db, tx, actor, project, false, cancellation);
        var people = await ReadProjectEligibleOwnersAsync(db, tx, actor, project, cancellation);
        if (!people.Rows.Cast<DataRow>().Any(row => row.Field<int>("id") == person))
            throw new UnauthorizedAccessException("Choose an active person in this project's scope.");
    }

    private async Task<(decimal? Hours, string? Revision)> ReadCapacityOverrideAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int person, DateTime monday, bool write, CancellationToken cancellation)
    {
        using var query = new NpgsqlCommand(@"
            SELECT c.capacity_hours,c.xmin::text,(@branch IS NULL OR EXISTS(
                SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='pms_user_capacity'
                    AND o.resource_key=c.id::text AND o.company_id=@organization AND o.branch_id=@branch))
            FROM public.pms_user_capacity c WHERE c.organization_id=@organization AND c.user_id=@person
                AND c.week_start_date=@monday" + (write ? " FOR UPDATE OF c" : ""), db, tx);
        SetBranch(query);
        query.Parameters.AddWithValue("person", person);
        query.Parameters.AddWithValue("monday", NpgsqlDbType.Date, monday);
        using var result = await query.ExecuteReaderAsync(cancellation);
        if (!await result.ReadAsync(cancellation))
            return (null, null);
        if (!result.GetBoolean(2))
            throw new UnauthorizedAccessException("The dated capacity belongs to another branch or has no branch ownership.");
        return (result.GetDecimal(0), result.GetString(1));
    }

    private static async Task<decimal[]> ReadDailyHoursAsync(NpgsqlConnection db, NpgsqlTransaction tx, int person,
        CancellationToken cancellation)
    {
        using var query = new NpgsqlCommand(@"SELECT payload::text FROM public.pms_planner_preferences WHERE user_id=@person", db, tx);
        query.Parameters.AddWithValue("person", person);
        var hours = new[] { 8m, 8m, 8m, 8m, 8m, 0m, 0m };
        if (await query.ExecuteScalarAsync(cancellation) is not string payload)
            return hours;
        var state = System.Text.Json.Nodes.JsonNode.Parse(payload) as System.Text.Json.Nodes.JsonObject
            ?? throw new InvalidOperationException("The person's saved work calendar is invalid.");
        return ParsePersonalWorkdays(state).Select(day => day.Enabled
            ? Math.Max(0, (day.End - day.Start).Ticks / (decimal)TimeSpan.TicksPerHour) : 0m).ToArray();
    }

    private async Task<DataTable> ReadCapacityExceptionsAsync(NpgsqlConnection db, NpgsqlTransaction tx, int person,
        DateTime monday, CancellationToken cancellation, int dayCount = 7)
    {
        using var query = new NpgsqlCommand(@"
            WITH employee AS (
                SELECT e.id,e.branch_id FROM public.employees e JOIN public.branches b ON b.id=e.branch_id
                WHERE e.user_id=@person AND e.deleted_at IS NULL AND b.company_id=@organization
                  AND (@branch IS NULL OR (e.branch_id=@branch AND EXISTS (
                    SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='employees' AND o.resource_key=e.id::text
                        AND o.company_id=@organization AND o.branch_id=@branch)))
                ORDER BY e.id LIMIT 1
            ), week AS (SELECT @monday+f.day_offset AS day FROM generate_series(0,@days-1) AS f(day_offset))
            SELECT EXISTS (
                SELECT 1 FROM public.holidays h WHERE h.is_active AND h.holiday_date=w.day
                   AND (nullif(trim(h.applicable_branches),'') IS NULL OR EXISTS (SELECT 1 FROM employee e
                    WHERE e.branch_id::text=ANY(regexp_split_to_array(trim(h.applicable_branches),' *, *'))))
                   AND (@branch IS NULL OR EXISTS (SELECT 1 FROM public.suite_branch_ownership o
                    WHERE o.resource_table='holidays' AND o.resource_key=h.id::text
                        AND o.company_id=@organization AND o.branch_id=@branch))
            ) AS holiday,coalesce(absence.approved,false) AS approved_leave,coalesce(absence.half_day,false) AS half_day
            FROM week w LEFT JOIN LATERAL (
                SELECT true AS approved,l.is_half_day AS half_day FROM public.leave_requests l JOIN employee e ON e.id=l.employee_id
                WHERE l.status='Approved' AND l.deleted_at IS NULL AND (l.company_id IS NULL OR l.company_id=@organization)
                  AND w.day BETWEEN l.from_date AND l.to_date AND (@branch IS NULL OR EXISTS (
                    SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='leave_requests' AND o.resource_key=l.id::text
                      AND o.company_id=@organization AND o.branch_id=@branch))
                ORDER BY l.id LIMIT 1
            ) absence ON true ORDER BY w.day", db, tx);
        SetBranch(query);
        query.Parameters.AddWithValue("person", person);
        query.Parameters.AddWithValue("monday", NpgsqlDbType.Date, monday);
        query.Parameters.AddWithValue("days", dayCount);
        return await ReadTableAsync(query, cancellation);
    }

    private static void ValidateCapacityWeek(DateTime monday)
    {
        if (monday.DayOfWeek != DayOfWeek.Monday || monday.Year is < 1900 or > 2200)
            throw new InvalidOperationException("Choose a Monday from 1900 through 2200.");
    }
}
