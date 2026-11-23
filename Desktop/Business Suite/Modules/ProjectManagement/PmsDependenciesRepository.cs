using System.Data;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

internal sealed record PmsDependencyList(DataTable Rows, DataTable Candidates, string Revision, bool CanEdit);

internal sealed partial class PmsProjectRepository
{
    private static readonly HashSet<string> DependencyTypes = new(StringComparer.Ordinal)
    {
        "Finish To Start", "Start To Start", "Finish To Finish", "Start To Finish"
    };

    private const string DependencyDateConflict = @"CASE lower(replace(replace(trim(coalesce(d.dependency_type,'Finish To Start')), '-', ' '),'_',' '))
                    WHEN 'finish to start' THEN target.start_date-coalesce(source.due_date,source.start_date)<coalesce(d.lag_days,0)
                    WHEN 'fs' THEN target.start_date-coalesce(source.due_date,source.start_date)<coalesce(d.lag_days,0)
                    WHEN 'start to start' THEN target.start_date-source.start_date<coalesce(d.lag_days,0)
                    WHEN 'ss' THEN target.start_date-source.start_date<coalesce(d.lag_days,0)
                    WHEN 'finish to finish' THEN coalesce(target.due_date,target.start_date)-coalesce(source.due_date,source.start_date)<coalesce(d.lag_days,0)
                    WHEN 'ff' THEN coalesce(target.due_date,target.start_date)-coalesce(source.due_date,source.start_date)<coalesce(d.lag_days,0)
                    WHEN 'start to finish' THEN coalesce(target.due_date,target.start_date)-source.start_date<coalesce(d.lag_days,0)
                    WHEN 'sf' THEN coalesce(target.due_date,target.start_date)-source.start_date<coalesce(d.lag_days,0)
                 END";

    private const string DependencyRows = @"
        FROM public.pms_task_dependencies d
        JOIN public.pms_tasks source ON source.id=d.depends_on_task_id AND source.project_id=@project AND source.deleted_at IS NULL
        JOIN public.pms_tasks target ON target.id=d.task_id AND target.project_id=@project AND target.deleted_at IS NULL
        WHERE (d.task_id=@task OR d.depends_on_task_id=@task)
          AND (@branch IS NULL OR (
                EXISTS(SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='pms_tasks' AND o.resource_key=source.id::text
                    AND o.company_id=@organization AND o.branch_id=@branch)
                AND EXISTS(SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='pms_tasks' AND o.resource_key=target.id::text
                    AND o.company_id=@organization AND o.branch_id=@branch)
                AND EXISTS(SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='pms_task_dependencies'
                    AND o.resource_key=d.id::text AND o.company_id=@organization AND o.branch_id=@branch)))";

    internal async Task<PmsDependencyList> ReadDependenciesAsync(int task, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await GetWorkspaceActorAsync(db, tx, false, cancellation);
        var scope = await ReadTaskActionScopeAsync(db, tx, actor, task, false, cancellation);
        var rows = await ReadDependencyRowsAsync(db, tx, scope.Project, task, cancellation);
        using var candidates = new NpgsqlCommand(@"
            SELECT t.id,t.task_key||' · '||t.title AS label
            FROM public.pms_tasks t WHERE t.project_id=@project AND t.id<>@task AND t.deleted_at IS NULL AND "
            + TaskBranchScope + " ORDER BY t.task_key,t.id", db, tx);
        SetBranch(candidates);
        candidates.Parameters.AddWithValue("project", scope.Project);
        candidates.Parameters.AddWithValue("task", task);
        bool editable = scope.Manage && actor.ModuleCanEdit;
        return new(rows, editable ? await ReadTableAsync(candidates, cancellation) : new DataTable(),
            await ReadTaskListRevisionAsync(db, tx, task, rows, cancellation), editable);
    }

    internal async Task<int> ChangeDependencyAsync(int task, string revision, int related, bool relatedIsPredecessor,
        string type, int lag, int? removeId, CancellationToken cancellation)
    {
        if (!removeId.HasValue && !DependencyTypes.Contains(type))
            throw new InvalidOperationException("Choose a dependency type.");
        if (!removeId.HasValue && related == task)
            throw new InvalidOperationException("A task cannot depend on itself.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await GetWorkspaceActorAsync(db, tx, true, cancellation);
        var scope = await ReadTaskActionScopeAsync(db, tx, actor, task, true, cancellation);
        if (!scope.Manage || !actor.ModuleCanEdit)
            throw new UnauthorizedAccessException("Task-management authority is required to change dependencies.");
        var rows = await ReadDependencyRowsAsync(db, tx, scope.Project, task, cancellation);
        if (revision != await ReadTaskListRevisionAsync(db, tx, task, rows, cancellation))
            throw new InvalidOperationException("The task or its dependency list changed. Refresh before saving.");

        int source;
        int target;
        int id;
        string targetKey;
        string sourceKey;
        if (removeId.HasValue)
        {
            var edge = rows.Rows.Cast<DataRow>().SingleOrDefault(row => row.Field<int>("id") == removeId.Value)
                ?? throw new InvalidOperationException("The dependency is unavailable.");
            source = edge.Field<int>("source_id");
            target = edge.Field<int>("target_id");
            targetKey = edge.Field<string>("target_key")!;
            sourceKey = edge.Field<string>("source_key")!;
            id = removeId.Value;
            using var remove = new NpgsqlCommand("DELETE FROM public.pms_task_dependencies WHERE id=@id AND xmin::text=@revision", db, tx);
            remove.Parameters.AddWithValue("id", id);
            remove.Parameters.AddWithValue("revision", edge.Field<string>("revision")!);
            if (await remove.ExecuteNonQueryAsync(cancellation) != 1)
                throw new InvalidOperationException("The dependency changed. Refresh before removing.");
            using var ownership = new NpgsqlCommand(@"DELETE FROM public.suite_branch_ownership WHERE resource_table='pms_task_dependencies'
                AND resource_key=@id::text AND company_id=@organization AND branch_id=@branch", db, tx);
            SetBranch(ownership);
            ownership.Parameters.AddWithValue("id", id);
            await ownership.ExecuteNonQueryAsync(cancellation);
        }
        else
        {
            using var other = new NpgsqlCommand(@"SELECT t.task_key FROM public.pms_tasks t
                WHERE t.id=@related AND t.project_id=@project AND t.deleted_at IS NULL AND " + TaskBranchScope + " FOR UPDATE OF t", db, tx);
            SetBranch(other);
            other.Parameters.AddWithValue("related", related);
            other.Parameters.AddWithValue("project", scope.Project);
            if (await other.ExecuteScalarAsync(cancellation) is not string relatedKey)
                throw new InvalidOperationException("Choose an active task in the current project and branch.");
            (source, target) = relatedIsPredecessor ? (related, task) : (task, related);
            (sourceKey, targetKey) = relatedIsPredecessor ? (relatedKey, scope.Key) : (scope.Key, relatedKey);
            using var check = new NpgsqlCommand(@"
                WITH RECURSIVE successors(id) AS (
                    SELECT @target UNION
                    SELECT d.task_id FROM successors prior JOIN public.pms_task_dependencies d ON d.depends_on_task_id=prior.id
                    JOIN public.pms_tasks t ON t.id=d.task_id AND t.project_id=@project AND t.deleted_at IS NULL
                )
                SELECT CASE WHEN EXISTS(SELECT 1 FROM successors WHERE id=@source) THEN 'cycle'
                    WHEN EXISTS(SELECT 1 FROM public.pms_task_dependencies WHERE task_id=@target AND depends_on_task_id=@source)
                    THEN 'duplicate' ELSE '' END", db, tx);
            check.Parameters.AddWithValue("target", target);
            check.Parameters.AddWithValue("source", source);
            check.Parameters.AddWithValue("project", scope.Project);
            string error = (string)(await check.ExecuteScalarAsync(cancellation))!;
            if (error.Length > 0)
                throw new InvalidOperationException(error == "cycle" ? "The dependency would create a circular relationship."
                    : "The dependency already exists.");

            using var add = new NpgsqlCommand(@"
                INSERT INTO public.pms_task_dependencies(task_id,depends_on_task_id,dependency_type,lag_days)
                VALUES(@target,@source,@type,@lag) ON CONFLICT ON CONSTRAINT uq_pms_task_dependency DO NOTHING RETURNING id", db, tx);
            add.Parameters.AddWithValue("source", source);
            add.Parameters.AddWithValue("target", target);
            add.Parameters.AddWithValue("type", type);
            add.Parameters.AddWithValue("lag", lag);
            id = await add.ExecuteScalarAsync(cancellation) is int key ? key
                : throw new InvalidOperationException("The dependency already exists.");
            await RecordOwnershipAsync(db, tx, "pms_task_dependencies", id, cancellation);
        }

        using var blocking = new NpgsqlCommand(@"
            UPDATE public.pms_tasks SET is_blocking=EXISTS(
                SELECT 1 FROM public.pms_task_dependencies WHERE depends_on_task_id=@source),
                updated_at=clock_timestamp() WHERE id=@source", db, tx);
        blocking.Parameters.AddWithValue("source", source);
        await blocking.ExecuteNonQueryAsync(cancellation);
        var metadata = JsonSerializer.Serialize(new { source_task_id=source,target_task_id=target,dependency_type=type,lag_days=lag });
        await RecordTaskActivityAsync(db, tx, actor, scope.Project, target, id,
            removeId.HasValue ? "dependency.removed" : "dependency.added",
            removeId.HasValue ? $"Removed dependency for {targetKey}" : $"{sourceKey} now blocks {targetKey}",
            removeId.HasValue ? "{}" : metadata, cancellation, "task_dependency");
        await tx.CommitAsync(cancellation);
        return id;
    }

    private async Task<DataTable> ReadDependencyRowsAsync(NpgsqlConnection db, NpgsqlTransaction tx, int project, int task,
        CancellationToken cancellation)
    {
        using var query = new NpgsqlCommand(@"
            SELECT d.id,d.xmin::text AS revision,source.id AS source_id,target.id AS target_id,
                source.task_key AS source_key,target.task_key AS target_key,
                source.task_key||' · '||source.title AS predecessor,target.task_key||' · '||target.title AS successor,
                coalesce(d.dependency_type,'Finish To Start') AS dependency_type,coalesce(d.lag_days,0) AS lag_days,
                (" + DependencyDateConflict + @") IS TRUE AS date_conflict" + DependencyRows + " ORDER BY d.id", db, tx);
        SetBranch(query);
        query.Parameters.AddWithValue("project", project);
        query.Parameters.AddWithValue("task", task);
        return await ReadTableAsync(query, cancellation);
    }
}
