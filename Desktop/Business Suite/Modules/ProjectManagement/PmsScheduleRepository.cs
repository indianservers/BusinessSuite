using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class PmsProjectRepository
{
    internal async Task<DataTable> ReadProjectScheduleAsync(int project, string filter, CancellationToken cancellation)
    {
        if (filter is not ("" or "scheduled" or "unscheduled" or "conflicts"))
            throw new InvalidOperationException("Choose a schedule filter.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await GetWorkspaceActorAsync(db, tx, false, cancellation);
        await ReadProjectActionAccessAsync(db, tx, actor, project, false, cancellation);
        using var query = new NpgsqlCommand(@"
            WITH tasks AS (
                SELECT t.id,t.task_key,t.title,t.status,t.priority,t.start_date,t.due_date,t.xmin::text AS revision,
                    coalesce(@module_edit AND (" + TaskEditAccess + @"),false) AS can_edit "
                + ProjectJoins + @" JOIN public.pms_tasks t ON t.project_id=p.id
                WHERE " + ProjectAccess + " AND " + TaskBranchScope + @" AND p.id=@project
                  AND p.deleted_at IS NULL AND t.deleted_at IS NULL
            ), conflicts AS (
                SELECT d.id,source.id AS source_id,target.id AS target_id
                FROM public.pms_task_dependencies d JOIN tasks source ON source.id=d.depends_on_task_id
                JOIN tasks target ON target.id=d.task_id
                WHERE (" + DependencyDateConflict + @") IS TRUE
                  AND (@branch IS NULL OR EXISTS(SELECT 1 FROM public.suite_branch_ownership o
                      WHERE o.resource_table='pms_task_dependencies' AND o.resource_key=d.id::text
                          AND o.company_id=@organization AND o.branch_id=@branch))
            )
            SELECT t.id,t.task_key,t.title,t.status,t.priority,t.start_date::timestamp,t.due_date::timestamp,
                coalesce(t.due_date,t.start_date)-coalesce(t.start_date,t.due_date)+1 AS duration_days,
                (t.start_date IS NOT NULL OR t.due_date IS NOT NULL) AS scheduled,
                info.conflicts,t.revision,t.can_edit
            FROM tasks t CROSS JOIN LATERAL (SELECT count(*) AS conflicts FROM conflicts c
                WHERE c.source_id=t.id OR c.target_id=t.id) info
            WHERE @filter='' OR (@filter='scheduled' AND (t.start_date IS NOT NULL OR t.due_date IS NOT NULL))
                OR (@filter='unscheduled' AND t.start_date IS NULL AND t.due_date IS NULL)
                OR (@filter='conflicts' AND info.conflicts>0)
            ORDER BY coalesce(t.start_date,t.due_date) NULLS LAST,t.task_key,t.id", db, tx);
        SetActor(query, actor);
        query.Parameters.AddWithValue("filter", filter);
        query.Parameters.AddWithValue("project", project);
        return await ReadTableAsync(query, cancellation);
    }

    internal async Task RescheduleTaskAsync(int project, int task, string revision, DateTime? start, DateTime? due,
        CancellationToken cancellation)
    {
        if (start.HasValue && due.HasValue && due.Value.Date < start.Value.Date)
            throw new InvalidOperationException("Due date cannot be before start date.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await GetWorkspaceActorAsync(db, tx, true, cancellation);
        var scope = await ReadTaskActionScopeAsync(db, tx, actor, task, true, cancellation);
        if (scope.Project != project || !scope.Manage || !actor.ModuleCanEdit)
            throw new UnauthorizedAccessException("Task-management authority in the selected project is required to reschedule.");
        DateTime? beforeStart;
        DateTime? beforeDue;
        using (var select = new NpgsqlCommand(@"SELECT start_date::timestamp,due_date::timestamp FROM public.pms_tasks
            WHERE id=@task AND xmin::text=@revision", db, tx))
        {
            select.Parameters.AddWithValue("task", task);
            select.Parameters.AddWithValue("revision", revision);
            using var row = await select.ExecuteReaderAsync(cancellation);
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("The task changed. Refresh its schedule before saving.");
            beforeStart = row.IsDBNull(0) ? (DateTime?)null : row.GetDateTime(0);
            beforeDue = row.IsDBNull(1) ? (DateTime?)null : row.GetDateTime(1);
        }
        if (beforeStart == start?.Date && beforeDue == due?.Date)
            return;

        using var update = new NpgsqlCommand(@"UPDATE public.pms_tasks SET start_date=@start,due_date=@due,
            updated_at=clock_timestamp() WHERE id=@task", db, tx);
        update.Parameters.AddWithValue("task", task);
        update.Parameters.Add("start", NpgsqlDbType.Date).Value = (object?)start?.Date ?? DBNull.Value;
        update.Parameters.Add("due", NpgsqlDbType.Date).Value = (object?)due?.Date ?? DBNull.Value;
        await update.ExecuteNonQueryAsync(cancellation);
        await RecordTaskActivityAsync(db, tx, actor, project, task, task, "schedule.changed", $"Rescheduled {scope.Key}",
            JsonSerializer.Serialize(new
            {
                old_values = new { start_date = ScheduleDate(beforeStart), due_date = ScheduleDate(beforeDue) },
                new_values = new { start_date = ScheduleDate(start), due_date = ScheduleDate(due) }
            }), cancellation);
        await tx.CommitAsync(cancellation);
    }

    private static string? ScheduleDate(DateTime? value) =>
        value?.ToString("yyyy-MM-dd", System.Globalization.CultureInfo.InvariantCulture);
}
