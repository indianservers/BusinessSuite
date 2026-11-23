using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class PmsProjectRepository
{
    internal async Task<int> CreateTaskAsync(int projectId, string key, PmsTaskDraft draft,
        CancellationToken cancellation)
    {
        ValidateTaskDraft(draft);
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction();
        var identity = await settings.VerifyWriteTargetAsync(connection,transaction,cancellation);
        var actor = await ResolveActorAsync(settings,identity,connection,transaction,cancellation);
        int created = await CreateTaskCoreAsync(connection,transaction,actor,projectId,key,draft,cancellation);
        await transaction.CommitAsync(cancellation);
        return created;
    }

    internal static async Task<int> CreateAppointmentTaskAsync(DesktopDatabaseSettings settings,NpgsqlConnection connection,
        NpgsqlTransaction transaction,DesktopActor identity,int project,string key,PmsTaskDraft draft,CancellationToken cancellation)
    {
        ValidateTaskDraft(draft);
        var actor = await ResolveActorAsync(settings,identity,connection,transaction,cancellation);
        if (!actor.ModuleCanEdit)
            throw new UnauthorizedAccessException("Linked booking requires Project Management task edit access.");
        var repository = new PmsProjectRepository(settings,actor);
        return await repository.CreateTaskCoreAsync(connection,transaction,actor,project,key,draft,cancellation);
    }

    internal static async Task<List<(int Id,string Name)>> ReadAppointmentProjectOptionsAsync(DesktopDatabaseSettings settings,
        NpgsqlConnection connection,NpgsqlTransaction transaction,DesktopActor identity,CancellationToken cancellation)
    {
        var actor = await ResolveActorAsync(settings,identity,connection,transaction,cancellation);
        var options = new List<(int,string)>();
        if (!actor.ModuleCanCreate || !actor.ModuleCanEdit)
            return options;
        var repository = new PmsProjectRepository(settings,actor);
        using var query = new NpgsqlCommand("SELECT p.id,concat(p.project_key,' · ',p.name)" + ProjectJoins +
            " WHERE " + ProjectScope + " AND (" + TaskEditAccess + ") ORDER BY p.name,p.id",connection,transaction);
        repository.SetActor(query,actor);
        SetScope(query,PmsProjectScope.Active);
        using var row = await query.ExecuteReaderAsync(cancellation);
        while (await row.ReadAsync(cancellation))
            options.Add((row.GetInt32(0),row.GetString(1)));
        return options;
    }

    private async Task<int> CreateTaskCoreAsync(NpgsqlConnection connection,NpgsqlTransaction transaction,PmsActor actor,
        int projectId,string key,PmsTaskDraft draft,CancellationToken cancellation)
    {
        if (draft.Status is null || !TaskStatuses.Contains(draft.Status) || draft.Status == "Blocked")
            throw new InvalidOperationException("Choose an initial status other than Blocked.");
        if (draft.Priority is null || !TaskPriorities.Contains(draft.Priority))
            throw new InvalidOperationException("Choose a task priority.");
        if (key.Length is < 1 or > 30 || key != key.ToUpperInvariant())
            throw new InvalidOperationException("The task identifier is invalid.");

        if (!actor.ModuleCanCreate)
            throw new UnauthorizedAccessException("Your access policy does not allow creating tasks.");

        int? workspace;
        bool assignSelf;
        using (var scope = new NpgsqlCommand(@"
            SELECT p.workspace_id, coalesce(p.manager_user_id = @actor OR
                CASE WHEN p.workspace_id IS NULL THEN pm.id IS NOT NULL
                     ELSE wm.role IN ('Owner','Admin','Member') END, false)" + ProjectJoins + @"
            WHERE " + ProjectScope + @" AND p.id = @project AND (" + TaskEditAccess + @")
            FOR UPDATE OF p", connection, transaction))
        {
            SetActor(scope, actor);
            SetScope(scope, PmsProjectScope.Active);
            scope.Parameters.AddWithValue("project", projectId);
            using var row = await scope.ExecuteReaderAsync(cancellation);
            if (!await row.ReadAsync(cancellation))
                throw new UnauthorizedAccessException("Choose an active project where you can manage tasks.");
            workspace = row.IsDBNull(0) ? null : row.GetInt32(0);
            assignSelf = row.GetBoolean(1);
        }

        var statusKey = draft.Status == "To Do" ? "TODO" : draft.Status.ToUpperInvariant().Replace(' ', '_');
        using (var rules = new NpgsqlCommand(@"
            SELECT CASE WHEN EXISTS (
                       SELECT 1 FROM public.pms_workspace_entries e
                       WHERE e.workspace_id = @workspace AND e.kind = 'auto_rule'
                        AND CASE WHEN e.kind = 'auto_rule' THEN e.body::jsonb END @>
                            jsonb_build_object('enabled', true, 'project_id', @project, 'trigger', 'task.created')
                   ) THEN 'This project has a task creation rule that the desktop cannot run.'
                   WHEN EXISTS (
                       SELECT 1 FROM public.pms_board_columns c JOIN public.pms_boards b ON b.id = c.board_id
                       WHERE b.project_id = @project AND c.status_key = @status_key AND c.wip_limit <= (
                           SELECT count(*) FROM public.pms_tasks t WHERE t.project_id = @project
                           AND t.status = @status AND t.deleted_at IS NULL)
                   ) THEN 'The destination stage is at capacity.' END", connection, transaction))
        {
            rules.Parameters.AddWithValue("workspace", NpgsqlDbType.Integer, (object?)workspace ?? DBNull.Value);
            rules.Parameters.AddWithValue("project", projectId);
            rules.Parameters.AddWithValue("status_key", statusKey);
            rules.Parameters.AddWithValue("status", draft.Status);
            if (await rules.ExecuteScalarAsync(cancellation) is string error)
                throw new InvalidOperationException(error);
        }

        var board = await GetOrCreateTaskBoardAsync(connection, transaction, projectId, cancellation);
        int? assignee = assignSelf ? actor.UserId : null;
        int taskId;
        using (var insert = new NpgsqlCommand(@"
            INSERT INTO public.pms_tasks (project_id, board_id, title, description, task_key, work_type, status,
                priority, start_date, due_date, estimated_hours, reporter_user_id, assignee_user_id,
                completed_at, rank, security_level, development_commits, development_prs, development_deployments,
                development_build, position, is_client_visible, is_blocking, recurrence_interval)
            SELECT @project, @board, @title, @description, @key, 'Task', @status, @priority, @start, @due, @hours,
                @actor, @assignee, CASE WHEN @complete THEN clock_timestamp() END,
                count(*)::int + 1, 'Internal', 0, 0, 0, 'Pending', 0, false, false, 1
            FROM public.pms_tasks WHERE project_id = @project AND deleted_at IS NULL
            ON CONFLICT (project_id, task_key) DO NOTHING RETURNING id", connection, transaction))
        {
            insert.Parameters.AddWithValue("project", projectId);
            insert.Parameters.AddWithValue("board", board);
            insert.Parameters.AddWithValue("title", draft.Title);
            insert.Parameters.AddWithValue("description", NpgsqlDbType.Text, (object?)draft.Description ?? DBNull.Value);
            insert.Parameters.AddWithValue("key", key);
            insert.Parameters.AddWithValue("status", draft.Status);
            insert.Parameters.AddWithValue("priority", draft.Priority);
            insert.Parameters.AddWithValue("start", NpgsqlDbType.Date, (object?)draft.Start ?? DBNull.Value);
            insert.Parameters.AddWithValue("due", NpgsqlDbType.Date, (object?)draft.Due ?? DBNull.Value);
            insert.Parameters.AddWithValue("hours", NpgsqlDbType.Numeric, (object?)draft.EstimatedHours ?? DBNull.Value);
            insert.Parameters.AddWithValue("actor", actor.UserId);
            insert.Parameters.AddWithValue("assignee", NpgsqlDbType.Integer, (object?)assignee ?? DBNull.Value);
            insert.Parameters.AddWithValue("complete", TaskCompleted(draft.Status));
            var inserted = await insert.ExecuteScalarAsync(cancellation);
            if (inserted is not int id)
                throw new InvalidOperationException("This task identifier already exists. Refresh the project before trying again.");
            taskId = id;
        }

        await RecordOwnershipAsync(connection, transaction, "pms_tasks", taskId, cancellation);
        var (column, position) = await MoveTaskColumnAsync(connection, transaction, taskId, projectId, board,
            draft.Status, statusKey, int.MaxValue, cancellation);
        using (var place = new NpgsqlCommand(
            "UPDATE public.pms_tasks SET column_id = @column, position = @position WHERE id = @task",
            connection, transaction))
        {
            place.Parameters.AddWithValue("column", column);
            place.Parameters.AddWithValue("position", position);
            place.Parameters.AddWithValue("task", taskId);
            await place.ExecuteNonQueryAsync(cancellation);
        }

        await RecordTaskActivityAsync(connection, transaction, actor, projectId, taskId, taskId, "task.created",
            $"Created task {key}", "{}", cancellation);
        await RecordStageEntryAsync(connection, transaction, actor, projectId, taskId, assignee, null, draft.Status, cancellation);
        if (workspace.HasValue)
        {
            using var snapshot = new NpgsqlCommand(@"WITH current AS (
                SELECT (" + TaskSnapshot + @")::jsonb AS state FROM public.pms_tasks t WHERE t.id = @task
            )
            SELECT jsonb_set(state, '{deleted_at}', to_jsonb(clock_timestamp() AT TIME ZONE 'UTC'))::text,
                state::text FROM current", connection, transaction);
            snapshot.Parameters.AddWithValue("task", taskId);
            string before;
            string after;
            using (var row = await snapshot.ExecuteReaderAsync(cancellation))
            {
                if (!await row.ReadAsync(cancellation))
                    throw new InvalidOperationException("Could not record the task history.");
                before = row.GetString(0);
                after = row.GetString(1);
            }
            await RecordTaskRecoveryAsync(connection, transaction, actor, workspace.Value, taskId,
                before, after, false, cancellation);
        }

        return taskId;
    }

    private async Task<int> GetOrCreateTaskBoardAsync(NpgsqlConnection connection, NpgsqlTransaction transaction,
        int projectId, CancellationToken cancellation)
    {
        using var lookup = new NpgsqlCommand(@"
            SELECT id FROM public.pms_boards WHERE project_id = @project ORDER BY id LIMIT 1",
            connection, transaction);
        lookup.Parameters.AddWithValue("project", projectId);
        var existing = await lookup.ExecuteScalarAsync(cancellation);
        if (existing is int board)
            return board;

        using var create = new NpgsqlCommand(@"
            INSERT INTO public.pms_boards (project_id, name, board_type)
            VALUES (@project, 'Default Board', 'Kanban') RETURNING id", connection, transaction);
        create.Parameters.AddWithValue("project", projectId);
        board = (int)(await create.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(connection, transaction, "pms_boards", board, cancellation);

        using var columns = new NpgsqlCommand(@"
            WITH added AS (
                INSERT INTO public.pms_board_columns (board_id,name,status_key,position,is_collapsed)
                SELECT @board, name, status_key, position, false
                FROM (VALUES ('Backlog','BACKLOG',0), ('To Do','TODO',1), ('In Progress','IN_PROGRESS',2),
                             ('In Review','IN_REVIEW',3), ('Done','DONE',4)) stages(name,status_key,position)
                RETURNING id
            )
            INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
            SELECT 'pms_board_columns', id::text, @organization, @branch, 'validated-write'
            FROM added WHERE @branch IS NOT NULL", connection, transaction);
        columns.Parameters.AddWithValue("board", board);
        SetBranch(columns);
        await columns.ExecuteNonQueryAsync(cancellation);
        return board;
    }
}

