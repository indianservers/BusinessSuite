using System.Text.Json;
using Npgsql;

namespace Business_Suite;

internal sealed partial class PmsProjectRepository
{
    internal async Task ChangeTaskTrashAsync(int task, string revision, bool restore, CancellationToken cancellation)
    {
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction();
        var actor = await GetTaskTrashActorAsync(connection, transaction, restore, cancellation);
        var selector = ProjectJoins + " JOIN public.pms_tasks t ON t.project_id=p.id WHERE "
            + ProjectAccess + " AND (" + TaskEditAccess + ") AND " + TaskBranchScope + @"
            AND p.deleted_at IS NULL AND (t.deleted_at IS NOT NULL) = @restore AND t.id=@task";

        int project;
        int? workspace;
        using (var scope = new NpgsqlCommand(
            "SELECT p.id, p.workspace_id" + selector + " FOR UPDATE OF p", connection, transaction))
        {
            SetTaskTrashParameters(scope, actor, task, restore);
            using var row = await scope.ExecuteReaderAsync(cancellation);
            if (!await row.ReadAsync(cancellation))
                throw new UnauthorizedAccessException("The task is unavailable for this action.");
            project = row.GetInt32(0);
            workspace = row.IsDBNull(1) ? null : row.GetInt32(1);
        }

        if (workspace.HasValue)
        {
            using var lockWorkspace = new NpgsqlCommand(
                "SELECT id FROM public.pms_workspaces WHERE id=@workspace FOR UPDATE", connection, transaction);
            lockWorkspace.Parameters.AddWithValue("workspace", workspace.Value);
            await lockWorkspace.ExecuteScalarAsync(cancellation);
        }

        actor = await GetTaskTrashActorAsync(connection, transaction, restore, cancellation);
        string before;
        string key;
        string title;
        int? parent;
        using (var state = new NpgsqlCommand("SELECT " + TaskSnapshot + ", t.task_key, t.title, t.parent_task_id"
            + selector + " AND t.xmin::text = @revision FOR UPDATE OF t", connection, transaction))
        {
            SetTaskTrashParameters(state, actor, task, restore);
            state.Parameters.AddWithValue("revision", revision);
            using var row = await state.ExecuteReaderAsync(cancellation);
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("This task changed. Refresh the list before trying again.");
            before = row.GetString(0);
            key = row.GetString(1);
            title = row.GetString(2);
            parent = row.IsDBNull(3) ? null : row.GetInt32(3);
        }

        if (restore && parent.HasValue)
        {
            using var parentCheck = new NpgsqlCommand(@"
                SELECT t.id FROM public.pms_tasks t
                WHERE t.id=@parent AND t.project_id=@project AND t.deleted_at IS NULL
                    AND " + TaskBranchScope + " FOR UPDATE OF t", connection, transaction);
            SetBranch(parentCheck);
            parentCheck.Parameters.AddWithValue("parent", parent.Value);
            parentCheck.Parameters.AddWithValue("project", project);
            if (await parentCheck.ExecuteScalarAsync(cancellation) is not int)
                throw new InvalidOperationException("Restore the parent task first.");
        }

        using (var update = new NpgsqlCommand(@"
            UPDATE public.pms_tasks
            SET deleted_at = CASE WHEN @restore THEN NULL ELSE clock_timestamp() END, updated_at=clock_timestamp()
            WHERE id=@task", connection, transaction))
        {
            update.Parameters.AddWithValue("task", task);
            update.Parameters.AddWithValue("restore", restore);
            await update.ExecuteNonQueryAsync(cancellation);
        }

        await RecordTaskActivityAsync(connection, transaction, actor, project, task, task,
            restore ? "task.restored" : "task.deleted", (restore ? "Restored task " : "Deleted task ") + key,
            "{}", cancellation);
        if (!restore && parent.HasValue)
        {
            await RecordTaskActivityAsync(connection, transaction, actor, project, parent.Value, task,
                "subtask.deleted", $"Deleted sub-task {key}",
                JsonSerializer.Serialize(new { subtask_id = task, subtask_key = key, title }), cancellation);
        }

        if (!restore && workspace.HasValue)
        {
            using var snapshot = new NpgsqlCommand("SELECT " + TaskSnapshot + " FROM public.pms_tasks t WHERE t.id=@task",
                connection, transaction);
            snapshot.Parameters.AddWithValue("task", task);
            var after = (string)(await snapshot.ExecuteScalarAsync(cancellation))!;
            await RecordTaskRecoveryAsync(connection, transaction, actor, workspace.Value, task, before, after, false,
                cancellation);
        }
        await transaction.CommitAsync(cancellation);
    }

    private async Task<PmsActor> GetTaskTrashActorAsync(NpgsqlConnection connection, NpgsqlTransaction transaction,
        bool restore, CancellationToken cancellation)
    {
        var actor = await ResolveActorAsync(settings,
            await settings.VerifyWriteTargetAsync(connection, transaction, cancellation), connection, transaction, cancellation);
        if (!(restore ? actor.ModuleCanCreate : actor.ModuleCanDelete))
            throw new UnauthorizedAccessException("Your access policy does not allow this task action.");
        return actor;
    }

    private void SetTaskTrashParameters(NpgsqlCommand command, PmsActor actor, int task, bool restore)
    {
        SetActor(command, actor);
        command.Parameters.AddWithValue("task", task);
        command.Parameters.AddWithValue("restore", restore);
    }
}

