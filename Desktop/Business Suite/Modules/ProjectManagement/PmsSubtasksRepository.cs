using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PmsSubtaskList(DataTable Rows,string Revision,bool CanCreate,bool CanEdit,bool CanDelete);
internal sealed record PmsSubtaskDraft(string Title,string Priority,DateTime? Due,bool InheritAssignees);

internal sealed partial class PmsProjectRepository
{
    internal async Task<PmsSubtaskList> ListSubtasksAsync(int parent,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await GetWorkspaceActorAsync(db,tx,false,cancellation);
        var scope=await ReadTaskActionScopeAsync(db,tx,actor,parent,false,cancellation);
        var rows=await ReadSubtaskRowsAsync(db,tx,parent,scope.Project,cancellation);
        return new PmsSubtaskList(rows,await ReadTaskListRevisionAsync(db,tx,parent,rows,cancellation),
            scope.Manage&&actor.ModuleCanCreate,scope.Manage&&actor.ModuleCanEdit,scope.Manage&&actor.ModuleCanDelete);
    }

    internal async Task<int> CreateSubtaskAsync(int parent,string revision,PmsSubtaskDraft draft,CancellationToken cancellation)
    {
        var title=draft.Title.Trim();
        if (title.Length is <1 or >220)
            throw new InvalidOperationException("Enter a subtask title of 1 to 220 characters.");
        if (!TaskPriorities.Contains(draft.Priority))
            throw new InvalidOperationException("Choose a priority.");
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await GetWorkspaceActorAsync(db,tx,true,cancellation);
        if (!actor.ModuleCanCreate)
            throw new UnauthorizedAccessException("Your access policy does not allow creating subtasks.");
        var scope=await ReadTaskActionScopeAsync(db,tx,actor,parent,true,cancellation);
        if (!scope.Manage)
            throw new UnauthorizedAccessException("Task-management authority is required to create subtasks.");
        var rows=await ReadSubtaskRowsAsync(db,tx,parent,scope.Project,cancellation);
        if (revision!=await ReadTaskListRevisionAsync(db,tx,parent,rows,cancellation))
            throw new InvalidOperationException("The parent or subtask list changed. Refresh before creating another subtask.");

        int[] assignees=Array.Empty<int>();
        if (draft.InheritAssignees)
        {
            var choices=await ReadAssignmentPeopleAsync(db,tx,actor,parent,scope.Project,scope.Workspace,cancellation);
            var assigned=choices.Rows.Cast<DataRow>().Where(person=>person.Field<bool>("assigned")).ToArray();
            if (assigned.Any(person=>!person.Field<bool>("eligible")) || assigned.Length>100)
                throw new InvalidOperationException("Some parent assignees cannot receive this subtask. Create it without inheriting assignees.");
            assignees=assigned.Select(person=>person.Field<int>("id")).OrderBy(id=>id).ToArray();
        }

        using var insert=new NpgsqlCommand(@"
            WITH total AS (
                SELECT count(*) AS n,count(*) FILTER (WHERE parent_task_id=@parent) AS siblings
                FROM public.pms_tasks WHERE project_id=@project
            ), candidate AS (
                SELECT val AS ordinal,upper(left(p.task_key,least(24,28-length(val::text))) || '-S' || val) AS key
                FROM public.pms_tasks p CROSS JOIN total
                CROSS JOIN LATERAL generate_series(total.siblings+1,total.siblings+total.n+1) val
                WHERE p.id=@parent
            ), unique_key AS (
                SELECT key FROM candidate WHERE NOT EXISTS (SELECT 1 FROM public.pms_tasks prior
                    WHERE prior.project_id=@project AND prior.task_key=candidate.key)
                ORDER BY ordinal LIMIT 1
            )
            INSERT INTO public.pms_tasks(project_id,board_id,column_id,milestone_id,sprint_id,epic_id,component_id,
                release_id,parent_task_id,reporter_user_id,title,task_key,work_type,status,priority,due_date,
                position,rank,security_level,is_client_visible,is_blocking,development_commits,development_prs,
                development_deployments,development_build,recurrence_interval)
            SELECT p.project_id,p.board_id,p.column_id,p.milestone_id,p.sprint_id,p.epic_id,p.component_id,p.release_id,
                p.id,@actor,@title,k.key,'Sub-task','To Do',@priority,@due,@position,@position+1,p.security_level,
                p.is_client_visible,false,0,0,0,'Pending',1
            FROM public.pms_tasks p CROSS JOIN unique_key k WHERE p.id=@parent
            RETURNING id,task_key",db,tx);
        insert.Parameters.AddWithValue("parent",parent);
        insert.Parameters.AddWithValue("project",scope.Project);
        insert.Parameters.AddWithValue("actor",actor.UserId);
        insert.Parameters.AddWithValue("title",title);
        insert.Parameters.AddWithValue("priority",draft.Priority);
        insert.Parameters.Add("due",NpgsqlDbType.Date).Value=(object?)draft.Due??DBNull.Value;
        insert.Parameters.AddWithValue("position",rows.Rows.Count);
        int id;
        string taskKey;
        using (var result=await insert.ExecuteReaderAsync(cancellation))
        {
            if (!await result.ReadAsync(cancellation))
                throw new InvalidOperationException("A unique subtask identifier could not be allocated.");
            id=result.GetInt32(0);
            taskKey=result.GetString(1);
        }

        await RecordOwnershipAsync(db,tx,"pms_tasks",id,cancellation);
        if (assignees.Length>0)
        {
            using var assign=new NpgsqlCommand(@"
                WITH added AS (
                    INSERT INTO public.pms_task_assignees(task_id,user_id)
                    SELECT @task,id FROM unnest(@people) id RETURNING task_id,user_id
                )
                INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
                SELECT 'pms_task_assignees',concat(length(task_id::text),':',task_id,':',length(user_id::text),':',user_id),
                    @organization,@branch,'validated-write' FROM added WHERE @branch IS NOT NULL",db,tx);
            SetBranch(assign);
            assign.Parameters.AddWithValue("task",id);
            assign.Parameters.AddWithValue("people",NpgsqlDbType.Array|NpgsqlDbType.Integer,assignees);
            await assign.ExecuteNonQueryAsync(cancellation);
        }
        await RecordTaskActivityAsync(db,tx,actor,scope.Project,id,id,"task.created",$"Created task {taskKey}","{}",cancellation);
        await RecordTaskActivityAsync(db,tx,actor,scope.Project,parent,id,"subtask.created",$"Created sub-task {taskKey}",
            JsonSerializer.Serialize(new { subtask_id=id,subtask_key=taskKey,title }),cancellation);
        await tx.CommitAsync(cancellation);
        return id;
    }

    internal async Task ReorderSubtasksAsync(int parent,string revision,int[] ids,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await GetWorkspaceActorAsync(db,tx,true,cancellation);
        if (!actor.ModuleCanEdit)
            throw new UnauthorizedAccessException("Your access policy does not allow reordering subtasks.");
        var scope=await ReadTaskActionScopeAsync(db,tx,actor,parent,true,cancellation);
        if (!scope.Manage)
            throw new UnauthorizedAccessException("Task-management authority is required to reorder subtasks.");
        var rows=await ReadSubtaskRowsAsync(db,tx,parent,scope.Project,cancellation);
        if (revision!=await ReadTaskListRevisionAsync(db,tx,parent,rows,cancellation))
            throw new InvalidOperationException("The parent or subtask list changed. Refresh before reordering.");
        if (ids.Length!=rows.Rows.Count || !new HashSet<int>(ids).SetEquals(rows.Rows.Cast<DataRow>().Select(row=>row.Field<int>("id"))))
            throw new InvalidOperationException("Include every current subtask exactly once.");

        using var move=new NpgsqlCommand(@"
            UPDATE public.pms_tasks t SET position=(item.ordinal-1)::int,rank=item.ordinal::int,
               updated_at=clock_timestamp()
            FROM unnest(@ids) WITH ORDINALITY item(id,ordinal) WHERE t.id=item.id AND t.parent_task_id=@parent
               AND t.project_id=@project AND t.deleted_at IS NULL AND " + TaskBranchScope,db,tx);
        SetBranch(move);
        move.Parameters.AddWithValue("ids",NpgsqlDbType.Array|NpgsqlDbType.Integer,ids);
        move.Parameters.AddWithValue("parent",parent);
        move.Parameters.AddWithValue("project",scope.Project);
        await move.ExecuteNonQueryAsync(cancellation);
        await RecordTaskActivityAsync(db,tx,actor,scope.Project,parent,parent,"subtask.reordered","Reordered subtasks",
            JsonSerializer.Serialize(new { item_ids=ids }),cancellation);
        await tx.CommitAsync(cancellation);
    }

    private async Task<DataTable> ReadSubtaskRowsAsync(NpgsqlConnection db,NpgsqlTransaction tx,int parent,
        int project,CancellationToken cancellation)
    {
        using var query=new NpgsqlCommand(@"
            SELECT t.id,t.task_key,t.title,t.description,t.status,t.priority,t.start_date::timestamp,t.due_date::timestamp,
                t.estimated_hours,t.position,t.xmin::text AS revision
            FROM public.pms_tasks t WHERE t.parent_task_id=@parent AND t.project_id=@project AND t.deleted_at IS NULL
              AND " + TaskBranchScope + " ORDER BY t.position,t.id",db,tx);
        SetBranch(query);
        query.Parameters.AddWithValue("parent",parent);
        query.Parameters.AddWithValue("project",project);
        return await ReadTableAsync(query,cancellation);
    }

    private static async Task<string> ReadTaskListRevisionAsync(NpgsqlConnection db,NpgsqlTransaction tx,int parent,
        DataTable rows,CancellationToken cancellation)
    {
        using var query=new NpgsqlCommand("SELECT xmin::text FROM public.pms_tasks WHERE id=@parent",db,tx);
        query.Parameters.AddWithValue("parent",parent);
        var revision=(string)(await query.ExecuteScalarAsync(cancellation))!;
        return revision+"|"+string.Join("|",rows.Rows.Cast<DataRow>().Select(row=>$"{row["id"]}:{row["revision"]}"));
    }
}

