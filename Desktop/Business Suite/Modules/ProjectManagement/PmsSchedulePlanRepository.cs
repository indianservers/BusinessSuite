using System.Data;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PmsCalendarDraft(int[] Weekdays, DateTime[] Holidays);
internal sealed record PmsScheduleMove(int Task, DateTime Start, DateTime Due);
internal sealed record PmsSchedulePlan(DataTable Rows, DateTime? Finish, int MissingDates, string Revision,
    bool CanApply, int Changed, PmsCalendarDraft Calendar, bool CanEditCalendar, bool CalendarChanged, bool ResourceLeveling = false,
    DataTable? Allocations = null);

internal sealed partial class PmsProjectRepository
{
    internal async Task<PmsSchedulePlan> PreviewSchedulePlanAsync(int project, CancellationToken cancellation,
        PmsCalendarDraft? proposed = null, PmsScheduleMove? move = null, bool levelResources = false)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await GetWorkspaceActorAsync(db, tx, false, cancellation);
        var state = await ReadBaselineStateAsync(db, tx, actor, project, false, cancellation);
        var dependency = CalculateSchedulePlan(state, state.Workspace.HasValue && state.Manage && actor.ModuleCanEdit &&
            !state.Archived, proposed, move);
        return levelResources ? await LevelSchedulePlanAsync(db, tx, actor, project, state, dependency, move, cancellation) : dependency;
    }

    internal async Task<int> ApplySchedulePlanAsync(int project, string revision, CancellationToken cancellation,
        PmsCalendarDraft? proposed = null, PmsScheduleMove? move = null, bool levelResources = false)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await GetWorkspaceActorAsync(db, tx, true, cancellation);
        var state = await ReadBaselineStateAsync(db, tx, actor, project, true, cancellation);
        if (state.Archived || state.Workspace is null)
            throw new InvalidOperationException("Apply scheduling plans from an active workspace project.");
        var plan = CalculateSchedulePlan(state, true, proposed, move);
        if (levelResources)
            plan = await LevelSchedulePlanAsync(db, tx, actor, project, state, plan, move, cancellation);
        if (plan.Revision != revision)
            throw new InvalidOperationException("The schedule or plan draft changed. Refresh the plan before applying.");
        if (plan.MissingDates > 0 || !plan.Finish.HasValue)
            throw new InvalidOperationException("Date every active task before applying a complete dependency plan.");
        if (!plan.CanApply && plan.Changed > 0)
            throw new InvalidOperationException("The plan would move a completed or canceled task.");
        foreach (DataRow row in plan.Rows.Rows)
        {
            if (!row.Field<bool>("changed"))
                continue;
            int id = row.Field<int>("id");
            var start = row.Field<DateTime>("planned_start");
            var due = row.Field<DateTime>("planned_due");
            using var update = new NpgsqlCommand(@"UPDATE public.pms_tasks SET start_date=@start,due_date=@due,
                updated_at=clock_timestamp() WHERE id=@task", db, tx);
            update.Parameters.AddWithValue("task", id);
            update.Parameters.AddWithValue("start", NpgsqlDbType.Date, start);
            update.Parameters.AddWithValue("due", NpgsqlDbType.Date, due);
            await update.ExecuteNonQueryAsync(cancellation);
            await RecordTaskActivityAsync(db, tx, actor, project, id, id, "schedule.changed",
                $"Applied {(levelResources ? "resource" : "dependency")} plan to {row["task_key"]}", JsonSerializer.Serialize(new
                {
                    id, task_key = row["task_key"], title = row["title"],
                    start_date = ScheduleDate(start), due_date = ScheduleDate(due),
                    old_start_date = ScheduleDate(row.Field<DateTime?>("start_date")), old_due_date = ScheduleDate(row.Field<DateTime?>("due_date")),
                    duration_workdays = row.Field<int>("duration"), slack_workdays = row.Field<int?>("slack")
                }), cancellation);
        }
        if (plan.CalendarChanged)
            state.Document["calendar"] = CalendarJson(plan.Calendar);
        if (plan.CalendarChanged || (!state.Row.HasValue && plan.Changed > 0))
        {
            using var create = new NpgsqlCommand(state.Row.HasValue
                ? "UPDATE public.pms_workspace_entries SET body=@body WHERE id=@entry RETURNING id"
                : @"INSERT INTO public.pms_workspace_entries(workspace_id,author_id,kind,body)
                    VALUES(@workspace,@actor,@kind,@body) RETURNING id", db, tx);
            create.Parameters.AddWithValue("workspace", state.Workspace.Value);
            create.Parameters.AddWithValue("actor", actor.UserId);
            create.Parameters.AddWithValue("kind", BaselineEntryKind(project));
            create.Parameters.AddWithValue("body", state.Document.ToJsonString());
            create.Parameters.Add("entry", NpgsqlDbType.Integer).Value = (object?)state.Row ?? DBNull.Value;
            int stateId = (int)(await create.ExecuteScalarAsync(cancellation))!;
            if (!state.Row.HasValue)
                await RecordOwnershipAsync(db, tx, "pms_workspace_entries", stateId, cancellation);
            if (plan.CalendarChanged)
                await RecordActivityAsync(db, tx, project, "schedule.calendar_changed", "Updated the project work calendar",
                    CalendarJson(plan.Calendar)!.ToJsonString(), cancellation);
        }
        await tx.CommitAsync(cancellation);
        return plan.Changed;
    }

    private static PmsSchedulePlan CalculateSchedulePlan(BaselineState state, bool writable, PmsCalendarDraft? proposed, PmsScheduleMove? move)
    {
        bool canEditCalendar = writable;
        if ((proposed is not null || move is not null) && !canEditCalendar)
            throw new UnauthorizedAccessException("Task-management authority is required to preview project schedule changes.");
        var saved = ReadCalendar(state.Document);
        PmsCalendarDraft calendar = proposed is null ? saved : ValidateCalendar(proposed);
        bool calendarChanged = !calendar.Weekdays.SequenceEqual(saved.Weekdays) || !calendar.Holidays.SequenceEqual(saved.Holidays);
        string revision = PlanRevision(state.Revision, proposed is null ? null : calendar, move);
        var rows = state.Tasks.Copy();
        rows.Columns.Add("planned_start", typeof(DateTime));
        rows.Columns.Add("planned_due", typeof(DateTime));
        rows.Columns.Add("duration", typeof(int));
        rows.Columns.Add("slack", typeof(int));
        rows.Columns.Add("changed", typeof(bool));
        var schedules = rows.Rows.Cast<DataRow>().ToDictionary(row => row.Field<int>("id"), row =>
            (Start: row.Field<DateTime?>("start_date"), Due: row.Field<DateTime?>("due_date")));
        if (move is not null)
        {
            if (!schedules.ContainsKey(move.Task))
                throw new InvalidOperationException("Choose an active task in this project.");
            if (move.Due.Date < move.Start.Date)
                throw new InvalidOperationException("A proposed move requires a due date on or after its start.");
            schedules[move.Task] = (move.Start.Date, move.Due.Date);
        }
        var tasks = rows.Rows.Cast<DataRow>().Where(row => schedules[row.Field<int>("id")] is { Start: not null, Due: not null })
            .ToDictionary(row => row.Field<int>("id"));
        int missing = rows.Rows.Count - tasks.Count;
        if (tasks.Count == 0)
            return new(rows, null, missing, revision, false, 0, calendar, canEditCalendar, calendarChanged);

        var earliest = tasks.Keys.Min(id => schedules[id].Start!.Value);
        var latest = tasks.Keys.Max(id => schedules[id].Due!.Value);
        if (earliest.Year < 1900 || latest.Year > 2200)
            throw new InvalidOperationException("Advanced planning supports task dates from 1900 through 2200.");
        if ((latest - earliest).Days > 7300)
            throw new InvalidOperationException("The planning horizon is limited to 20 years.");
        var days = Enumerable.Range(0, 7301).Select(day => earliest.AddDays(day))
            .Where(day => calendar.Weekdays.Contains(((int)day.DayOfWeek + 6) % 7) && !calendar.Holidays.Contains(day)).ToArray();
        var starts = new Dictionary<int, long>();
        var duration = new Dictionary<int, int>();
        var degree = new Dictionary<int, int>();
        var outgoing = new Dictionary<int, List<(int Next, long Offset)>>();
        foreach (var item in tasks)
        {
            DateTime start = schedules[item.Key].Start!.Value;
            DateTime end = schedules[item.Key].Due!.Value;
            if (end < start)
                throw new InvalidOperationException("Fix inverted task dates before planning.");
            int first = WorkdayIndex(days, start);
            starts.Add(item.Key, first);
            duration.Add(item.Key, Math.Max(1, WorkdayIndex(days, end.AddDays(1)) - first));
            degree.Add(item.Key, 0);
            outgoing.Add(item.Key, new());
        }

        foreach (DataRow edge in state.Dependencies.Rows)
        {
            int from = edge.Field<int>("depends_on_task_id");
            int to = edge.Field<int>("task_id");
            if (!tasks.ContainsKey(from) || !tasks.ContainsKey(to))
                continue;
            long lag = edge.Field<int?>("lag_days") ?? 0;
            long offset = edge.Field<string>("dependency_type") switch
            {
                "Finish To Start" => duration[from] + lag,
                "Start To Start" => lag,
                "Finish To Finish" => duration[from] - duration[to] + lag,
                "Start To Finish" => 1 - duration[to] + lag,
                _ => throw new InvalidOperationException("Fix the unsupported dependency type before planning.")
            };
            outgoing[from].Add((to, offset));
            degree[to]++;
        }

        var order = new List<int>(tasks.Count);
        var ready = new Queue<int>(degree.Where(pair => pair.Value == 0).Select(pair => pair.Key));
        while (ready.Count > 0)
        {
            int id = ready.Dequeue();
            order.Add(id);
            foreach (var (successor, offset) in outgoing[id])
            {
                starts[successor] = Math.Max(starts[successor], starts[id] + offset);
                if (--degree[successor] == 0)
                    ready.Enqueue(successor);
            }
        }
        if (order.Count != tasks.Count)
            throw new InvalidOperationException("A dependency cycle prevents schedule planning.");
        long finish = order.Max(id => starts[id] + duration[id]);
        if (finish > days.Length || days[(int)finish - 1].Year > 2200)
            throw new InvalidOperationException("The computed schedule exceeds the supported planning horizon.");
        var latestStart = order.ToDictionary(id => id, id => finish - duration[id]);
        for (int index = order.Count - 1; index >= 0; index--)
            foreach (var (successor, offset) in outgoing[order[index]])
                latestStart[order[index]] = Math.Min(latestStart[order[index]], latestStart[successor] - offset);

        int changes = 0;
        foreach (int id in order)
        {
            var row = tasks[id];
            var proposedStart = days[(int)starts[id]];
            var proposedDue = days[(int)starts[id] + duration[id] - 1];
            bool changed = proposedStart != row.Field<DateTime?>("start_date") || proposedDue != row.Field<DateTime?>("due_date");
            row["planned_start"] = proposedStart;
            row["planned_due"] = proposedDue;
            row["duration"] = duration[id];
            row["slack"] = latestStart[id] - starts[id];
            row["changed"] = changed;
            if (!changed)
                continue;
            changes++;
            if (row.Field<string>("status") is "Done" or "Completed" or "Cancelled" or "Canceled" or "Closed")
                writable = false;
        }
        return new(rows, days[(int)finish - 1], missing, revision,
            writable && missing == 0 && (changes > 0 || calendarChanged), changes, calendar, canEditCalendar, calendarChanged);
    }

    private static PmsCalendarDraft ReadCalendar(JsonObject state)
    {
        if (state["calendar"] is not JsonObject calendar || calendar["weekdays"] is not JsonArray weekdays ||
            calendar["holidays"] is not JsonArray holidays)
            throw new InvalidOperationException("The stored project calendar is unavailable.");
        return ValidateCalendar(new PmsCalendarDraft(
            weekdays.Select(day => day!.GetValue<int>()).ToArray(),
            holidays.Select(day => DateTime.ParseExact(day!.GetValue<string>(), "yyyy-MM-dd", CultureInfo.InvariantCulture)).ToArray()));
    }

    private static PmsCalendarDraft ValidateCalendar(PmsCalendarDraft calendar)
    {
        if (calendar.Weekdays.Length is < 1 or > 7 || calendar.Weekdays.Any(day => day is < 0 or > 6)
            || calendar.Weekdays.Distinct().Count() != calendar.Weekdays.Length)
            throw new InvalidOperationException("Select at least one unique working weekday.");
        if (calendar.Holidays.Length > 365)
            throw new InvalidOperationException("A project calendar can contain at most 365 holiday dates.");
        return new(calendar.Weekdays.OrderBy(day => day).ToArray(),
            calendar.Holidays.Select(day => day.Date).Distinct().OrderBy(day => day).ToArray());
    }

    private static JsonNode? CalendarJson(PmsCalendarDraft calendar) =>
        JsonSerializer.SerializeToNode(new { weekdays = calendar.Weekdays, holidays = calendar.Holidays.Select(day => ScheduleDate(day)) });

    private static string PlanRevision(string stateRevision, PmsCalendarDraft? calendar, PmsScheduleMove? move)
    {
        if (calendar is null && move is null)
            return stateRevision;
        string payload = JsonSerializer.Serialize(new { calendar = calendar is null ? null : CalendarJson(calendar),
            move = move is null ? null : new { task = move.Task, start_date = ScheduleDate(move.Start), due_date = ScheduleDate(move.Due) } });
        using var sha = SHA256.Create();
        return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(stateRevision + "|" + payload))).Replace("-", "");
    }

    private static int WorkdayIndex(DateTime[] days, DateTime date)
    {
        int index = Array.BinarySearch(days, date);
        return index >= 0 ? index : ~index;
    }
}
