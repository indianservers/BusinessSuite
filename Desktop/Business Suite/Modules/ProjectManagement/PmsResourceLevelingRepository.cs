using System.Data;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class PmsProjectRepository
{
    private sealed record ResourceTask(int Id, int[] Assignees, decimal Effort);

    private async Task<PmsSchedulePlan> LevelSchedulePlanAsync(NpgsqlConnection db, NpgsqlTransaction tx, PmsActor actor,
        int project, BaselineState state, PmsSchedulePlan plan, PmsScheduleMove? move, CancellationToken cancellation)
    {
        if (!plan.CanEditCalendar)
            throw new UnauthorizedAccessException("Task-management authority is required for resource leveling.");
        if (plan.Rows.Rows.Count is < 1 or > 200)
            throw new InvalidOperationException("Resource leveling supports from 1 to 200 active tasks.");
        if (plan.MissingDates > 0 || !plan.Finish.HasValue)
            throw new InvalidOperationException("Date every task and resolve incomplete dependencies before leveling.");

        var tasks = await ReadResourceTasksAsync(db, tx, state, cancellation);
        int[] assignees = tasks.SelectMany(task => task.Assignees).Distinct().OrderBy(id => id).ToArray();
        if (assignees.Length > 50)
            throw new InvalidOperationException("Resource leveling supports up to 50 assignees.");
        var people = await ReadProjectEligibleOwnersAsync(db, tx, actor, project, cancellation);
        var eligible = people.Rows.Cast<DataRow>().GroupBy(row => row.Field<int>("id"))
            .ToDictionary(group => group.Key, group => group.First().Field<string>("name") ?? $"User {group.Key}");
        if (assignees.Any(id => !eligible.ContainsKey(id)))
            throw new InvalidOperationException("Resolve unavailable or out-of-scope task assignees before leveling.");
        var rows = plan.Rows.Rows.Cast<DataRow>().ToDictionary(row => row.Field<int>("id"));
        var originalAnchor = rows.Values.Min(row => move?.Task == row.Field<int>("id") ?
            move.Start.Date : row.Field<DateTime>("start_date"));
        var anchor = rows.Values.Min(row => row.Field<DateTime>("planned_start"));
        if ((plan.Finish.Value - anchor).Days > 365)
            throw new InvalidOperationException("All task dates must fit within the 366-day leveling horizon.");
        var days = Enumerable.Range(0, 366).Select(day => anchor.AddDays(day))
            .Where(day => day.Year <= 2200 && plan.Calendar.Weekdays.Contains(((int)day.DayOfWeek + 6) % 7)
                && !plan.Calendar.Holidays.Contains(day)).ToArray();
        var capacity = new SortedDictionary<int, decimal[]>();
        foreach (var person in assignees)
            capacity.Add(person, await ReadLevelingCapacityAsync(db, tx, person, originalAnchor, cancellation));

        var incoming = state.Dependencies.Rows.Cast<DataRow>().ToLookup(row => row.Field<int>("task_id"));
        var pending = new HashSet<int>(rows.Keys);
        var dates = new Dictionary<int, (int Start, int Due)>();
        var used = new Dictionary<(int Person, int Day), decimal>();
        var inputs = tasks.ToDictionary(task => task.Id);
        var allocations = new DataTable();
        allocations.Columns.Add("task_id", typeof(int));
        allocations.Columns.Add("task_key", typeof(string));
        allocations.Columns.Add("title", typeof(string));
        allocations.Columns.Add("user_id", typeof(int));
        allocations.Columns.Add("person", typeof(string));
        allocations.Columns.Add("date", typeof(DateTime));
        allocations.Columns.Add("hours", typeof(decimal));
        const decimal epsilon = 0.000001m;
        while (pending.Count > 0)
        {
            cancellation.ThrowIfCancellationRequested();
            int id = pending.Where(task => incoming[task].All(edge => dates.ContainsKey(edge.Field<int>("depends_on_task_id"))))
                .OrderBy(task => rows[task].Field<DateTime>("planned_start")).ThenBy(task => task).FirstOrDefault();
            if (id == 0)
                throw new InvalidOperationException("A dependency cycle prevents resource leveling.");
            DataRow row = rows[id];
            long earliest = WorkdayIndex(days, row.Field<DateTime>("planned_start"));
            long dueFloor = WorkdayIndex(days, row.Field<DateTime>("planned_due"));
            foreach (DataRow edge in incoming[id])
            {
                var predecessor = dates[edge.Field<int>("depends_on_task_id")];
                long lag = edge.Field<int?>("lag_days") ?? 0;
                switch (edge.Field<string>("dependency_type"))
                {
                    case "Finish To Start": earliest = Math.Max(earliest, predecessor.Due + 1 + lag); break;
                    case "Start To Start": earliest = Math.Max(earliest, predecessor.Start + lag); break;
                    case "Finish To Finish": dueFloor = Math.Max(dueFloor, predecessor.Due + lag); break;
                    case "Start To Finish": dueFloor = Math.Max(dueFloor, predecessor.Start + lag); break;
                }
            }

            if (row.Field<string>("status") is "Done" or "Completed" or "Cancelled" or "Canceled" or "Closed")
            {
                var oldStart = row.Field<DateTime?>("start_date");
                var oldDue = row.Field<DateTime?>("due_date");
                if (!oldStart.HasValue || !oldDue.HasValue)
                    throw new InvalidOperationException("Resource leveling cannot move a completed or canceled task.");
                int first = WorkdayIndex(days, oldStart.Value);
                int last = WorkdayIndex(days, oldDue.Value);
                if (first >= days.Length || last >= days.Length || earliest > first || dueFloor > last
                    || days[first] != oldStart.Value || days[last] != oldDue.Value)
                    throw new InvalidOperationException("Resource leveling cannot move a completed or canceled task.");
                dates.Add(id, (first, last));
                pending.Remove(id);
                continue;
            }

            var resource = inputs[id];
            if (resource.Assignees.Length == 0 || resource.Effort <= 0)
                throw new InvalidOperationException("Every open task needs assignees and a positive remaining or unspent estimate.");
            var remaining = resource.Assignees.ToDictionary(person => person, _ => resource.Effort / resource.Assignees.Length);
            int? allocatedFirst = null;
            int allocatedLast = 0;
            if (earliest < days.Length && dueFloor < days.Length)
                for (int day = (int)Math.Max(0, earliest); day < days.Length; day++)
                {
                    int capacityDay = (days[day] - originalAnchor).Days;
                    if (capacityDay is < 0 or > 365)
                        continue;
                    foreach (int assignee in resource.Assignees)
                    {
                        var key = (assignee, day);
                        used.TryGetValue(key, out decimal committed);
                        decimal hours = Math.Min(remaining[assignee], Math.Max(0, capacity[assignee][capacityDay] - committed));
                        if (hours <= epsilon)
                            continue;
                        used[key] = committed + hours;
                        remaining[assignee] -= hours;
                        allocations.Rows.Add(id, row["task_key"], row["title"], assignee, eligible[assignee], days[day],
                            decimal.Round(hours, 4, MidpointRounding.ToEven));
                        allocatedFirst ??= day;
                        allocatedLast = day;
                    }
                    if (remaining.Values.All(hours => hours <= epsilon))
                        break;
                }
            if (!allocatedFirst.HasValue || remaining.Values.Any(hours => hours > epsilon))
                throw new InvalidOperationException("Insufficient capacity within the 366-day leveling horizon.");
            dates.Add(id, (allocatedFirst.Value, Math.Max(allocatedLast, (int)dueFloor)));
            pending.Remove(id);
        }

        int changed = 0;
        foreach (var item in dates)
        {
            var row = rows[item.Key];
            DateTime start = days[item.Value.Start];
            DateTime due = days[item.Value.Due];
            bool moved = start != row.Field<DateTime?>("start_date") || due != row.Field<DateTime?>("due_date");
            row["planned_start"] = start;
            row["planned_due"] = due;
            row["duration"] = item.Value.Due - item.Value.Start + 1;
            row["slack"] = DBNull.Value;
            row["changed"] = moved;
            if (moved)
                changed++;
        }
        using var sha = SHA256.Create();
        string inputsJson = JsonSerializer.Serialize(new { tasks, capacity });
        string revision = BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(plan.Revision + "|" + inputsJson))).Replace("-", "");
        return plan with { Finish = days[dates.Values.Max(value => value.Due)], Changed = changed, Revision = revision,
            CanApply = changed > 0 || plan.CalendarChanged, ResourceLeveling = true, Allocations = allocations };
    }

    private async Task<ResourceTask[]> ReadResourceTasksAsync(NpgsqlConnection db, NpgsqlTransaction tx, BaselineState state,
        CancellationToken cancellation)
    {
        using var query = new NpgsqlCommand(@"
            SELECT t.id,COALESCE(t.remaining_estimate_hours,greatest(0,coalesce(t.estimated_hours,0)-coalesce(t.actual_hours,0))),
                ARRAY(SELECT joined.user_id FROM (
                    SELECT a.user_id FROM public.pms_task_assignees a WHERE a.task_id=t.id
                    UNION SELECT t.assignee_user_id WHERE t.assignee_user_id IS NOT NULL
                ) joined ORDER BY joined.user_id),
                EXISTS(SELECT 1 FROM public.pms_task_assignees a WHERE a.task_id=t.id AND @branch IS NOT NULL AND NOT EXISTS(
                    SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='pms_task_assignees'
                       AND o.resource_key=concat(length(a.task_id::text),':',a.task_id,':',length(a.user_id::text),':',a.user_id)
                       AND o.company_id=@organization AND o.branch_id=@branch))
            FROM public.pms_tasks t WHERE t.id=ANY(@tasks) ORDER BY t.id", db, tx);
        SetBranch(query);
        query.Parameters.AddWithValue("tasks", NpgsqlDbType.Array | NpgsqlDbType.Integer,
            state.Tasks.Rows.Cast<DataRow>().Select(row => row.Field<int>("id")).ToArray());
        using var reader = await query.ExecuteReaderAsync(cancellation);
        var tasks = new List<ResourceTask>();
        while (await reader.ReadAsync(cancellation))
        {
            if (reader.GetBoolean(3))
                throw new UnauthorizedAccessException("The project has assignments outside this branch.");
            tasks.Add(new ResourceTask(reader.GetInt32(0), reader.GetFieldValue<int[]>(2), reader.GetDecimal(1)));
        }
        return tasks.ToArray();
    }

    private async Task<decimal[]> ReadLevelingCapacityAsync(NpgsqlConnection db, NpgsqlTransaction tx, int person,
        DateTime start, CancellationToken cancellation)
    {
        var baseline = await ReadDailyHoursAsync(db, tx, person, cancellation);
        var exceptions = await ReadCapacityExceptionsAsync(db, tx, person, start, cancellation, 366);
        var overrides = new Dictionary<DateTime, decimal>();
        using (var query = new NpgsqlCommand(@"
            SELECT c.week_start_date::timestamp,c.capacity_hours,(@branch IS NULL OR EXISTS(
                SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='pms_user_capacity'
                    AND o.resource_key=c.id::text AND o.company_id=@organization AND o.branch_id=@branch))
            FROM public.pms_user_capacity c WHERE c.organization_id=@organization AND c.user_id=@person
                AND c.week_start_date BETWEEN @start-6 AND @start+365", db, tx))
        {
            SetBranch(query);
            query.Parameters.AddWithValue("person", person);
            query.Parameters.AddWithValue("start", NpgsqlDbType.Date, start);
            using var reader = await query.ExecuteReaderAsync(cancellation);
            while (await reader.ReadAsync(cancellation))
            {
                if (!reader.GetBoolean(2))
                    throw new UnauthorizedAccessException("The project has assignee capacity outside this branch.");
                overrides.Add(reader.GetDateTime(0), reader.GetDecimal(1));
            }
        }

        var availability = new decimal[366];
        decimal weekly = baseline.Sum();
        for (int offset = 0; offset < availability.Length; offset++)
        {
            var date = start.AddDays(offset);
            int day = ((int)date.DayOfWeek + 6) % 7;
            decimal hours = baseline[day];
            if (weekly > 0 && overrides.TryGetValue(date.AddDays(-day), out decimal configured))
                hours = configured * hours / weekly;
            var exception = exceptions.Rows[offset];
            if (exception.Field<bool>("holiday"))
                hours = 0;
            else if (exception.Field<bool>("approved_leave"))
                hours *= exception.Field<bool>("half_day") ? 0.5m : 0m;
            availability[offset] = decimal.Round(hours, 2, MidpointRounding.ToEven);
        }
        return availability;
    }
}
