using System.Data;
using System.Globalization;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PmsTaskDraft(string Title, string? Description, string? Status, string? Priority,
    DateTime? Start, DateTime? Due, decimal? EstimatedHours);

internal sealed partial class PmsProjectRepository
{
    private const string TaskBranchScope = @"
        (@branch IS NULL OR EXISTS (SELECT 1 FROM public.suite_branch_ownership o
            WHERE o.resource_table = 'pms_tasks' AND o.resource_key = t.id::text
              AND o.company_id = @organization AND o.branch_id = @branch))";

    private const string TaskEditAccess = @"
        (p.workspace_id IS NOT NULL AND w.id IS NOT NULL AND (@admin OR wm.role IN ('Owner','Admin','Member')))
        OR (p.workspace_id IS NULL AND (@global_task_edit OR p.manager_user_id = @actor
            OR pm.role IN ('Admin','Project Admin','Manager','Project Manager','Lead','Member','Team Member')))";

    private static readonly string[] TaskStatuses = {
        "Backlog", "To Do", "In Progress", "In Review", "Blocked", "Done", "Completed",
        "Closed", "Resolved", "Cancelled", "Canceled", "Rejected"
    };
    private static readonly string[] TaskPriorities = { "Low", "Medium", "High", "Urgent", "Critical" };
    private static bool TaskCompleted(string? status) => status is "Done" or "Completed" or "Closed" or "Resolved";

    // Match the web recovery snapshot, including canonical decimal strings and structural context.
    private const string TaskSnapshot = @"
        (jsonb_build_object(
            'title', t.title, 'description', t.description, 'status', t.status, 'priority', t.priority,
            'start_date', t.start_date, 'due_date', t.due_date, 'estimated_hours', trim_scale(t.estimated_hours)::text,
            'story_points', t.story_points, 'is_client_visible', t.is_client_visible, 'is_blocking', t.is_blocking,
            'position', t.position, 'deleted_at', t.deleted_at AT TIME ZONE 'UTC',
            'completed_at', t.completed_at AT TIME ZONE 'UTC', 'column_id', t.column_id, 'board_id', t.board_id,
            'assignee_user_id', t.assignee_user_id, 'assignee_user_ids', ARRAY(
                SELECT a.user_id FROM public.pms_task_assignees a WHERE a.task_id = t.id
                UNION SELECT t.assignee_user_id WHERE t.assignee_user_id IS NOT NULL ORDER BY 1),
            '_context', (to_jsonb(t) - ARRAY[
                'title','description','status','priority','start_date','due_date','estimated_hours','story_points',
                'is_client_visible','is_blocking','position','deleted_at','completed_at','column_id','board_id',
                'assignee_user_id','created_at','updated_at'
            ]) || jsonb_build_object('actual_hours', trim_scale(t.actual_hours)::text,
                 'original_estimate_hours', trim_scale(t.original_estimate_hours)::text,
                 'remaining_estimate_hours', trim_scale(t.remaining_estimate_hours)::text)
        ))::text";

    private static void ValidateTaskDraft(PmsTaskDraft draft)
    {
        if (string.IsNullOrWhiteSpace(draft.Title) || draft.Title.Length > 220)
            throw new InvalidOperationException("Enter a task title of 1 to 220 characters.");
        if (draft.Start > draft.Due)
            throw new InvalidOperationException("Start date cannot be after due date.");
        if (draft.EstimatedHours is < 0 or > 999999.99m)
            throw new InvalidOperationException("Enter estimated hours from 0 to 999,999.99.");
    }

    internal async Task SaveTaskAsync(int taskId, string revision, PmsTaskDraft draft, CancellationToken cancellation)
    {
        ValidateTaskDraft(draft);
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction();
        var identity = await settings.VerifyWriteTargetAsync(connection, transaction, cancellation);
        var actor = await ResolveActorAsync(settings, identity, connection, transaction, cancellation);
        await SaveTaskCoreAsync(connection,transaction,actor,taskId,revision,draft,null,null,null,cancellation);
        transaction.Commit();
    }

    internal static async Task CheckAppointmentTaskAsync(DesktopDatabaseSettings settings, NpgsqlConnection connection,
        NpgsqlTransaction transaction, DesktopActor identity, int projectId, int taskId, DateTime? date,
        CancellationToken cancellation)
    {
        var actor = await ResolveActorAsync(settings,identity,connection,transaction,cancellation);
        if (!actor.ModuleCanEdit)
            throw new UnauthorizedAccessException("Linked appointment rescheduling requires Project Management task edit access.");
        using var query = new NpgsqlCommand("SELECT " + TaskSnapshot + ",t.recurrence_rule" + TaskEditSelector,connection,transaction);
        query.Parameters.AddWithValue("task",taskId);
        query.Parameters.AddWithValue("expected_project",NpgsqlDbType.Integer,projectId);
        new PmsProjectRepository(settings,actor).SetActor(query,actor);
        using var row = await query.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            throw new UnauthorizedAccessException("The linked project task is unavailable for editing.");
        if (date.HasValue)
        {
            using var original = JsonDocument.Parse(row.GetString(0));
            ValidateTaskRecurrence(row.IsDBNull(1) ? null : row.GetString(1),original.RootElement,date);
        }
    }

    internal static async Task SaveAppointmentTaskAsync(DesktopDatabaseSettings settings, NpgsqlConnection connection,
        NpgsqlTransaction transaction, DesktopActor identity, int projectId, int taskId, DateTime date, decimal hours,
        CancellationToken cancellation)
    {
        var actor = await ResolveActorAsync(settings,identity,connection,transaction,cancellation);
        var repository = new PmsProjectRepository(settings,actor);
        await repository.SaveTaskCoreAsync(connection,transaction,actor,taskId,null,null,projectId,date,hours,cancellation);
    }

    private const string TaskEditSelector = ProjectJoins + @"
        JOIN public.pms_tasks t ON t.project_id = p.id
        WHERE " + ProjectAccess + " AND (" + TaskEditAccess + @")
            AND " + TaskBranchScope + @"
            AND p.deleted_at IS NULL AND t.deleted_at IS NULL AND t.id=@task
            AND (@expected_project IS NULL OR p.id=@expected_project)";

    private async Task SaveTaskCoreAsync(NpgsqlConnection connection,NpgsqlTransaction transaction,PmsActor actor,
        int taskId,string? revision,PmsTaskDraft? draft,int? expectedProject,DateTime? appointmentDate,decimal? appointmentHours,
        CancellationToken cancellation)
    {
        if (!actor.ModuleCanEdit)
            throw new UnauthorizedAccessException("Your access policy does not allow editing tasks.");

        int projectId;
        int? workspaceId;
        using (var lockProject = new NpgsqlCommand(
            "SELECT p.id, p.workspace_id" + TaskEditSelector + " FOR UPDATE OF p", connection, transaction))
        {
            lockProject.Parameters.AddWithValue("task", taskId);
            lockProject.Parameters.AddWithValue("expected_project",NpgsqlDbType.Integer,(object?)expectedProject ?? DBNull.Value);
            SetActor(lockProject, actor);
            using var row = await lockProject.ExecuteReaderAsync(cancellation);
            if (!await row.ReadAsync(cancellation))
                throw new UnauthorizedAccessException("This task is unavailable for editing.");
            projectId = row.GetInt32(0);
            workspaceId = row.IsDBNull(1) ? (int?)null : row.GetInt32(1);
        }

        if (workspaceId.HasValue)
        {
            using var lockWorkspace = new NpgsqlCommand(
                "SELECT id FROM public.pms_workspaces WHERE id = @workspace FOR UPDATE", connection, transaction);
            lockWorkspace.Parameters.AddWithValue("workspace", workspaceId.Value);
            await lockWorkspace.ExecuteScalarAsync(cancellation);
        }

        string before;
        string taskKey;
        int? parentTask;
        int? board;
        int position;
        int? assignee;
        int? sprint;
        string? repeat;
        using (var lockTask = new NpgsqlCommand(@"SELECT " + TaskSnapshot + @", t.task_key,
            t.parent_task_id, t.board_id, coalesce(t.position, 0), t.assignee_user_id,
            t.sprint_id, t.recurrence_rule" + TaskEditSelector + @"
            AND (@revision IS NULL OR t.xmin::text=@revision) FOR UPDATE OF t", connection, transaction))
        {
            actor = await ResolveActorAsync(settings,
                await settings.VerifyWriteTargetAsync(connection, transaction, cancellation),
                connection, transaction, cancellation);
            if (!actor.ModuleCanEdit)
                throw new UnauthorizedAccessException("Your task editing permission changed.");
            lockTask.Parameters.AddWithValue("task", taskId);
            lockTask.Parameters.AddWithValue("revision",NpgsqlDbType.Text,(object?)revision ?? DBNull.Value);
            lockTask.Parameters.AddWithValue("expected_project",NpgsqlDbType.Integer,(object?)expectedProject ?? DBNull.Value);
            SetActor(lockTask, actor);
            using var row = await lockTask.ExecuteReaderAsync(cancellation);
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("This task changed while you were editing. Refresh, then reopen the task.");
            before = row.GetString(0);
            taskKey = row.GetString(1);
            parentTask = row.IsDBNull(2) ? (int?)null : row.GetInt32(2);
            board = row.IsDBNull(3) ? (int?)null : row.GetInt32(3);
            position = row.GetInt32(4);
            assignee = row.IsDBNull(5) ? (int?)null : row.GetInt32(5);
            sprint = row.IsDBNull(6) ? null : row.GetInt32(6);
            repeat = row.IsDBNull(7) ? null : row.GetString(7);
        }

        using var oldState = JsonDocument.Parse(before);
        var original = oldState.RootElement;
        string? oldStatus = original.GetProperty("status").GetString();
        string? oldPriority = original.GetProperty("priority").GetString();
        if (draft is null)
        {
            draft = new PmsTaskDraft(original.GetProperty("title").GetString()!,original.GetProperty("description").GetString(),
                oldStatus,oldPriority,appointmentDate,appointmentDate,appointmentHours);
            ValidateTaskDraft(draft);
        }
        if (draft.Status != oldStatus && (draft.Status is null || !TaskStatuses.Contains(draft.Status)))
            throw new InvalidOperationException("Choose a valid task status.");
        if (draft.Priority != oldPriority && (draft.Priority is null || !TaskPriorities.Contains(draft.Priority)))
            throw new InvalidOperationException("Choose a valid task priority.");
        ValidateTaskRecurrence(repeat,original,draft.Due);

        bool changedStatus = draft.Status != oldStatus;
        string newStatus = draft.Status ?? "";
        int? column = null;
        if (changedStatus)
        {
            if (sprint.HasValue)
                throw new InvalidOperationException("This task belongs to a sprint. Update its status from the sprint workflow.");
            if (!string.IsNullOrEmpty(repeat) && TaskCompleted(draft.Status))
                throw new InvalidOperationException("Complete this recurring task from its recurrence workflow to schedule the next task.");

            var statusKey = newStatus == "To Do" ? "TODO" : newStatus.ToUpperInvariant().Replace(' ', '_');
            await CheckTaskTransitionAsync(connection, transaction, taskId, projectId, workspaceId,
                newStatus, statusKey, cancellation);
            if (board.HasValue)
                (column, position) = await MoveTaskColumnAsync(connection, transaction, taskId, projectId, board.Value,
                    newStatus, statusKey, position, cancellation);
        }

        using (var update = new NpgsqlCommand(@"
            UPDATE public.pms_tasks
            SET title = @title, description = @description, status = @status, priority = @priority,
                start_date = @start, due_date = @due, estimated_hours = @hours,
                completed_at = CASE WHEN NOT @transition THEN completed_at
                    WHEN @complete THEN coalesce(completed_at, clock_timestamp()) ELSE NULL END,
                column_id = coalesce(@column, column_id), position = CASE WHEN @column IS NULL THEN position ELSE @position END,
                updated_at = clock_timestamp()
            WHERE id = @task", connection, transaction))
        {
            update.Parameters.AddWithValue("task", taskId);
            update.Parameters.AddWithValue("title", draft.Title);
            update.Parameters.AddWithValue("description", NpgsqlDbType.Text, (object?)draft.Description ?? DBNull.Value);
            update.Parameters.AddWithValue("status", NpgsqlDbType.Varchar, (object?)draft.Status ?? DBNull.Value);
            update.Parameters.AddWithValue("priority", NpgsqlDbType.Varchar, (object?)draft.Priority ?? DBNull.Value);
            update.Parameters.AddWithValue("start", NpgsqlDbType.Date, (object?)draft.Start ?? DBNull.Value);
            update.Parameters.AddWithValue("due", NpgsqlDbType.Date, (object?)draft.Due ?? DBNull.Value);
            update.Parameters.AddWithValue("hours", NpgsqlDbType.Numeric, (object?)draft.EstimatedHours ?? DBNull.Value);
            update.Parameters.AddWithValue("transition", changedStatus);
            update.Parameters.AddWithValue("complete", TaskCompleted(draft.Status));
            update.Parameters.AddWithValue("column", NpgsqlDbType.Integer, (object?)column ?? DBNull.Value);
            update.Parameters.AddWithValue("position", position);
            await update.ExecuteNonQueryAsync(cancellation);
        }

        using var snapshot = new NpgsqlCommand(
            "SELECT " + TaskSnapshot + " FROM public.pms_tasks t WHERE t.id = @task", connection, transaction);
        snapshot.Parameters.AddWithValue("task", taskId);
        var after = (string)(await snapshot.ExecuteScalarAsync(cancellation))!;
        using var newState = JsonDocument.Parse(after);
        var updated = newState.RootElement;
        string[] editableFields = { "title", "description", "status", "priority", "start_date", "due_date", "estimated_hours" };
        var changes = editableFields.Where(field => original.GetProperty(field).GetRawText() != updated.GetProperty(field).GetRawText()).ToArray();
        if (changes.Length > 0)
        {
            foreach (var field in changes)
            {
                string? eventName = field switch
                {
                    "status" => "status.changed", "priority" => "priority.changed",
                    "due_date" => "due_date.changed", _ => null
                };
                if (eventName is not null)
                    await RecordTaskActivityAsync(connection, transaction, actor, projectId, taskId, taskId, eventName,
                        $"Changed {field.Replace('_', ' ')} on {taskKey}",
                        JsonSerializer.Serialize(new { field, old_value = original.GetProperty(field), new_value = updated.GetProperty(field) }),
                        cancellation);
            }

            await RecordTaskActivityAsync(connection, transaction, actor, projectId, taskId, taskId, "task.updated",
                $"Updated task {taskKey}", JsonSerializer.Serialize(new {
                    changed_fields = changes,
                    old_values = changes.ToDictionary(field => field, original.GetProperty),
                    new_values = changes.ToDictionary(field => field, updated.GetProperty)
                }), cancellation);
        }

        if (changedStatus)
        {
            await RecordStageEntryAsync(connection, transaction, actor, projectId, taskId, assignee, oldStatus ?? "None", newStatus, cancellation);
            if (parentTask.HasValue && TaskCompleted(draft.Status) && !TaskCompleted(oldStatus))
                await RecordTaskActivityAsync(connection, transaction, actor, projectId, parentTask.Value, taskId,
                    "subtask.completed", $"Completed sub-task {taskKey}",
                    JsonSerializer.Serialize(new { subtask_id = taskId, subtask_key = taskKey, title = draft.Title }), cancellation);
        }

        if (workspaceId.HasValue && before != after)
            await RecordTaskRecoveryAsync(connection, transaction, actor, workspaceId.Value, taskId, before, after,
                changedStatus && !string.IsNullOrEmpty(repeat), cancellation);
        if (appointmentDate.HasValue && sprint is int sprintId)
            await SyncAppointmentSprintAsync(connection,transaction,actor,projectId,sprintId,cancellation);
    }

    private static void ValidateTaskRecurrence(string? repeat,JsonElement original,DateTime? due)
    {
        if (string.IsNullOrEmpty(repeat))
            return;
        var context = original.GetProperty("_context");
        var until = context.GetProperty("recurrence_until");
        var interval = context.GetProperty("recurrence_interval");
        if (repeat is not ("daily" or "weekly" or "monthly") || !due.HasValue ||
            interval.ValueKind != JsonValueKind.Number || interval.GetInt32() is < 1 or > 365 ||
            (until.ValueKind == JsonValueKind.String &&
                DateTime.ParseExact(until.GetString()!,"yyyy-MM-dd",CultureInfo.InvariantCulture) < due.Value))
            throw new InvalidOperationException("Recurring tasks require a due date on or before recurrence end and a valid repeat interval.");
    }

    private async Task SyncAppointmentSprintAsync(NpgsqlConnection connection,NpgsqlTransaction transaction,PmsActor actor,
        int projectId,int sprintId,CancellationToken cancellation)
    {
        using var update = new NpgsqlCommand(@"WITH totals AS (
            SELECT count(*)::integer AS tasks,coalesce(sum(coalesce(story_points,0)) FILTER (
                WHERE status IN ('Done','Completed','Closed','Resolved')),0)::integer AS points
            FROM public.pms_tasks WHERE project_id=@project AND sprint_id=@sprint AND deleted_at IS NULL
        ) UPDATE public.pms_sprints s SET committed_task_count=coalesce(nullif(s.committed_task_count,0),totals.tasks),
            completed_story_points=CASE WHEN s.status='Completed' THEN totals.points ELSE s.completed_story_points END,
            velocity_points=CASE WHEN s.status='Completed' THEN totals.points ELSE s.velocity_points END
        FROM totals WHERE s.id=@sprint AND s.project_id=@project
            AND (@branch IS NULL OR EXISTS (SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='pms_sprints'
                AND o.resource_key=s.id::text AND o.branch_id=@branch AND o.company_id=@organization))",connection,transaction);
        update.Parameters.AddWithValue("project",projectId);
        update.Parameters.AddWithValue("sprint",sprintId);
        SetActor(update,actor);
        if (await update.ExecuteNonQueryAsync(cancellation)!=1)
            throw new InvalidOperationException("The linked task sprint is unavailable.");
    }

    private async Task CheckTaskTransitionAsync(NpgsqlConnection connection, NpgsqlTransaction transaction,
        int taskId, int projectId, int? workspace, string status, string statusKey, CancellationToken cancellation)
    {
        using var query = new NpgsqlCommand(@"
            SELECT CASE
                WHEN EXISTS (SELECT 1 FROM public.pms_workspace_entries e
                    WHERE e.workspace_id = @workspace AND e.kind = @workflow
                      AND CASE WHEN e.kind = @workflow THEN e.body::jsonb ->> 'enabled' END = 'true') THEN
                        'This project requires a configured workflow or approval for status changes.'
                WHEN EXISTS (SELECT 1 FROM public.pms_workspace_entries e
                    WHERE e.workspace_id = @workspace AND e.kind = 'auto_rule'
                      AND CASE WHEN e.kind = 'auto_rule' THEN e.body::jsonb END @>
                          jsonb_build_object('enabled', true, 'project_id', @project, 'trigger', 'task.status_changed')) THEN
                        'This project has a task status automation that the desktop cannot run.'
                WHEN (@complete OR @status = 'In Review') AND EXISTS (
                    SELECT 1 FROM public.pms_task_update_entries WHERE task_id = @task
                      AND kind = 'blocker' AND NOT resolved AND deleted_at IS NULL) THEN
                        'Resolve open task blockers before submitting or completing work.'
                WHEN @complete AND EXISTS (
                    SELECT 1 FROM public.pms_checklist_items WHERE task_id = @task AND NOT coalesce(is_completed, false)) THEN
                        'Complete all checklist items before completing this task.'
                WHEN @complete AND EXISTS (
                    SELECT 1 FROM public.pms_tasks WHERE parent_task_id = @task AND deleted_at IS NULL
                      AND status NOT IN ('Done','Completed','Closed','Resolved','Cancelled','Canceled')) THEN
                        'Complete open subtasks before completing this task.'
                WHEN @complete AND EXISTS (
                    SELECT 1 FROM public.pms_task_execution WHERE task_id = @task AND evidence_required
                      AND coalesce(btrim(evidence),'') = '') THEN
                        'Provide required completion evidence.'
                WHEN @complete AND EXISTS (
                    SELECT 1 FROM public.pms_task_assignees WHERE task_id = @task AND source_key IS NOT NULL
                      AND execution_status <> 'Done') THEN
                        'Approve each work submission before completing this task.'
                WHEN @status = 'Blocked' AND NOT EXISTS (
                    SELECT 1 FROM public.pms_task_execution WHERE task_id = @task AND responsible_user_id IS NOT NULL
                      AND review_date IS NOT NULL AND coalesce(btrim(blocked_reason),'') <> '') THEN
                        'Add a blocked reason, responsible person and next review date before blocking this task.'
                WHEN EXISTS (
                    SELECT 1 FROM public.pms_board_columns c JOIN public.pms_boards b ON b.id = c.board_id
                    WHERE b.project_id = @project AND c.status_key = @status_key AND c.wip_limit <= (
                        SELECT count(*) FROM public.pms_tasks t WHERE t.project_id = @project AND t.status = @status
                            AND t.deleted_at IS NULL AND t.id <> @task)) THEN 'The destination stage is at capacity.'
            END", connection, transaction);
        query.Parameters.AddWithValue("task", taskId);
        query.Parameters.AddWithValue("project", projectId);
        query.Parameters.AddWithValue("workspace", NpgsqlDbType.Integer, (object?)workspace ?? DBNull.Value);
        query.Parameters.AddWithValue("workflow", "wf" + projectId.ToString("x", CultureInfo.InvariantCulture));
        query.Parameters.AddWithValue("status", status);
        query.Parameters.AddWithValue("status_key", statusKey);
        query.Parameters.AddWithValue("complete", TaskCompleted(status));
        if (await query.ExecuteScalarAsync(cancellation) is string reason)
            throw new InvalidOperationException(reason);
    }

    private async Task<(int Column, int Position)> MoveTaskColumnAsync(NpgsqlConnection connection,
        NpgsqlTransaction transaction, int taskId, int projectId, int boardId, string status, string statusKey,
        int priorPosition, CancellationToken cancellation)
    {
        using var board = new NpgsqlCommand(@"
            SELECT b.id FROM public.pms_boards b WHERE b.project_id = @project AND b.id = @board
              AND (@branch IS NULL OR EXISTS (SELECT 1 FROM public.suite_branch_ownership o
                   WHERE o.resource_table = 'pms_boards' AND o.resource_key = b.id::text
                     AND o.company_id = @organization AND o.branch_id = @branch))
            FOR UPDATE OF b", connection, transaction);
        board.Parameters.AddWithValue("project", projectId);
        board.Parameters.AddWithValue("board", boardId);
        SetBranch(board);
        if (await board.ExecuteScalarAsync(cancellation) is null)
            throw new InvalidOperationException("The task board is no longer available.");

        int? columnId = null;
        using (var find = new NpgsqlCommand(@"
            SELECT c.id, @branch IS NULL OR EXISTS (SELECT 1 FROM public.suite_branch_ownership o
                WHERE o.resource_table = 'pms_board_columns' AND o.resource_key = c.id::text
                  AND o.company_id = @organization AND o.branch_id = @branch) AS available
            FROM public.pms_board_columns c WHERE c.board_id = @board AND c.status_key = @status_key
            ORDER BY c.id LIMIT 1", connection, transaction))
        {
            find.Parameters.AddWithValue("board", boardId);
            find.Parameters.AddWithValue("status_key", statusKey);
            SetBranch(find);
            using var row = await find.ExecuteReaderAsync(cancellation);
            if (await row.ReadAsync(cancellation))
            {
                if (!row.GetBoolean(1))
                    throw new InvalidOperationException("The destination board column is unavailable in this branch.");
                columnId = row.GetInt32(0);
            }
        }
        if (!columnId.HasValue)
        {
            using var create = new NpgsqlCommand(@"
                INSERT INTO public.pms_board_columns(board_id, name, status_key, position, is_collapsed)
                SELECT @board, @status, @status_key, count(*)::integer, false FROM public.pms_board_columns
                WHERE board_id = @board RETURNING id", connection, transaction);
            create.Parameters.AddWithValue("board", boardId);
            create.Parameters.AddWithValue("status", status);
            create.Parameters.AddWithValue("status_key", statusKey);
            columnId = (int)(await create.ExecuteScalarAsync(cancellation))!;
            await RecordOwnershipAsync(connection, transaction, "pms_board_columns", columnId.Value, cancellation);
        }

        using var move = new NpgsqlCommand(@"
            WITH siblings AS (
                SELECT id, (row_number() OVER (ORDER BY position, id) - 1)::int AS rank
                FROM public.pms_tasks t WHERE t.project_id = @project AND t.column_id = @column
                    AND t.id <> @task AND t.deleted_at IS NULL AND " + TaskBranchScope + @"
            ), destination AS (
                SELECT least(greatest(@prior, 0), count(*)::integer) AS slot FROM siblings
            ), reposition AS (
                UPDATE public.pms_tasks t SET position = s.rank + CASE WHEN s.rank >= d.slot THEN 1 ELSE 0 END,
                    updated_at = clock_timestamp()
                FROM siblings s CROSS JOIN destination d WHERE t.id = s.id
                    AND t.position IS DISTINCT FROM (s.rank + CASE WHEN s.rank >= d.slot THEN 1 ELSE 0 END)
            )
            SELECT slot FROM destination", connection, transaction);
        move.Parameters.AddWithValue("project", projectId);
        move.Parameters.AddWithValue("column", columnId.Value);
        move.Parameters.AddWithValue("task", taskId);
        move.Parameters.AddWithValue("prior", priorPosition);
        SetBranch(move);
        return (columnId.Value, (int)(await move.ExecuteScalarAsync(cancellation))!);
    }

    private void SetBranch(NpgsqlCommand command)
    {
        command.Parameters.AddWithValue("branch", NpgsqlDbType.Integer, (object?)settings.BranchId ?? DBNull.Value);
        command.Parameters.AddWithValue("organization", settings.OrganizationId);
    }

    private async Task RecordTaskActivityAsync(NpgsqlConnection connection, NpgsqlTransaction transaction, PmsActor actor,
        int project, int task, int entityId, string action, string summary, string metadata, CancellationToken cancellation,
        string entityType = "task")
    {
        using var insert = new NpgsqlCommand(@"
            INSERT INTO public.pms_activities (project_id, task_id, actor_user_id, action, entity_type, entity_id, summary, metadata_json)
            VALUES (@project, @task, @actor, @action, @entity_type, @entity, @summary, @metadata) RETURNING id", connection, transaction);
        insert.Parameters.AddWithValue("project", project);
        insert.Parameters.AddWithValue("task", task);
        insert.Parameters.AddWithValue("actor", actor.UserId);
        insert.Parameters.AddWithValue("action", action);
        insert.Parameters.AddWithValue("entity", entityId);
        insert.Parameters.AddWithValue("entity_type", entityType);
        insert.Parameters.AddWithValue("summary", summary);
        insert.Parameters.AddWithValue("metadata", metadata);
        var id = (int)(await insert.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(connection, transaction, "pms_activities", id, cancellation);
    }

    private async Task RecordTaskRecoveryAsync(NpgsqlConnection connection, NpgsqlTransaction transaction, PmsActor actor,
        int workspace, int taskId, string before, string after, bool recurringTransition, CancellationToken cancellation)
    {
        using var insert = new NpgsqlCommand(@"
            UPDATE public.pms_recovery_changes SET state = 'discarded'
            WHERE workspace_id = @workspace AND actor_id = @actor AND state = 'undone'
              AND (@branch IS NULL OR EXISTS (SELECT 1 FROM public.suite_branch_ownership o
                   WHERE o.resource_table = 'pms_recovery_changes'
                     AND o.resource_key = pms_recovery_changes.id::text
                     AND o.company_id = @organization AND o.branch_id = @branch));
            INSERT INTO public.pms_recovery_changes (workspace_id, task_id, actor_id, before, after, state)
            SELECT @workspace, @task, @actor, @old, @new, 'applied'
            WHERE NOT @recurring AND @old::jsonb -> '_context' = @new::jsonb -> '_context'
            RETURNING id", connection, transaction);
        insert.Parameters.AddWithValue("workspace", workspace);
        insert.Parameters.AddWithValue("task", taskId);
        insert.Parameters.AddWithValue("actor", actor.UserId);
        insert.Parameters.AddWithValue("old", NpgsqlDbType.Json, before);
        insert.Parameters.AddWithValue("new", NpgsqlDbType.Json, after);
        insert.Parameters.AddWithValue("recurring", recurringTransition);
        SetBranch(insert);
        if (await insert.ExecuteScalarAsync(cancellation) is int id)
            await RecordOwnershipAsync(connection, transaction, "pms_recovery_changes", id, cancellation);
    }

    private async Task RecordStageEntryAsync(NpgsqlConnection connection, NpgsqlTransaction transaction, PmsActor actor,
        int project, int task, int? assignee, string? oldStatus, string newStatus, CancellationToken cancellation)
    {
        using var insert = new NpgsqlCommand(@"
            INSERT INTO public.suite_service_events (organization_id, module_key, event_type, entity_type,
                entity_id, actor_id, request_key, payload_json, status)
            VALUES (@organization, 'project_management', 'pipeline.stage_entered', 'task', @task, @actor,
                @request, @payload, 'pending') RETURNING id", connection, transaction);
        insert.Parameters.AddWithValue("organization", settings.OrganizationId);
        insert.Parameters.AddWithValue("task", task);
        insert.Parameters.AddWithValue("actor", actor.UserId);
        insert.Parameters.AddWithValue("request", $"pipeline:project_management:{task}:{Guid.NewGuid():N}");
        insert.Parameters.AddWithValue("payload", NpgsqlDbType.Json, JsonSerializer.Serialize(new {
            origin = "pipeline_workspace", data = new {
                previous_stage = oldStatus ?? "None", stage = newStatus,
                previous_stage_name = oldStatus ?? "Created", stage_name = newStatus,
                owner_id = assignee, scope = $"project:{project}"
            }, depth = 0
        }));
        var id = (int)(await insert.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(connection, transaction, "suite_service_events", id, cancellation);
    }
}

