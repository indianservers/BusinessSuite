using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal enum PmsChecklistAction { Add, Rename, Complete, Reopen, Delete, Reorder }
internal sealed record PmsChecklistList(DataTable Rows,string Revision,bool CanAdd,bool CanEdit,bool CanDelete);

internal sealed partial class PmsProjectRepository
{
    private const string LiveTaskScope = ProjectJoins + @" JOIN public.pms_tasks t ON t.project_id=p.id WHERE "
        + ProjectAccess + " AND " + TaskBranchScope + " AND p.deleted_at IS NULL AND t.deleted_at IS NULL AND t.id=@task";
    private const string ChecklistBranch = @"(@branch IS NULL OR EXISTS (
        SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='pms_checklist_items'
          AND o.resource_key=c.id::text AND o.company_id=@organization AND o.branch_id=@branch))";

    internal async Task<PmsChecklistList> ReadChecklistAsync(int task,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await GetWorkspaceActorAsync(db,tx,false,cancellation);
        var scope=await ReadTaskActionScopeAsync(db,tx,actor,task,false,cancellation);
        var rows=await ReadChecklistRowsAsync(db,tx,task,cancellation);
        return new PmsChecklistList(rows,ChecklistRevision(rows),scope.Manage&&actor.ModuleCanCreate,
            scope.Manage&&actor.ModuleCanEdit,scope.Manage&&actor.ModuleCanDelete);
    }

    internal async Task ChangeChecklistAsync(int task,string revision,PmsChecklistAction action,int? item,
        string? title,int[]? orderedItems,CancellationToken cancellation)
    {
        title=title?.Trim();
        if ((action is PmsChecklistAction.Add or PmsChecklistAction.Rename) && (title is null || title.Length is <1 or >220))
            throw new InvalidOperationException("Enter a checklist item of 1 to 220 characters.");
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await GetWorkspaceActorAsync(db,tx,true,cancellation);
        var scope=await ReadTaskActionScopeAsync(db,tx,actor,task,true,cancellation);
        actor=await GetWorkspaceActorAsync(db,tx,true,cancellation);
        scope=await ReadTaskActionScopeAsync(db,tx,actor,task,false,cancellation);
        bool allowed=action switch
        {
            PmsChecklistAction.Add=>actor.ModuleCanCreate,
            PmsChecklistAction.Delete=>actor.ModuleCanDelete,
            _=>actor.ModuleCanEdit
        };
        if (!scope.Manage || !allowed)
            throw new UnauthorizedAccessException("You do not have permission to change this task checklist.");

        var rows=await ReadChecklistRowsAsync(db,tx,task,cancellation);
        if (revision!=ChecklistRevision(rows))
            throw new InvalidOperationException("The checklist changed. Refresh before making changes.");
        var selected=rows.Rows.Cast<DataRow>().SingleOrDefault(row=>row.Field<int>("id")==item);
        if (action is not (PmsChecklistAction.Add or PmsChecklistAction.Reorder) && selected is null)
            throw new InvalidOperationException("Choose a checklist item from this task.");
        if (action==PmsChecklistAction.Reorder &&
            (orderedItems is null || orderedItems.Length!=rows.Rows.Count
             || !new HashSet<int>(orderedItems).SetEquals(rows.Rows.Cast<DataRow>().Select(row=>row.Field<int>("id")))))
            throw new InvalidOperationException("A checklist reorder must include every item exactly once.");

        string sql=action switch
        {
            PmsChecklistAction.Add=>@"INSERT INTO public.pms_checklist_items(task_id,title,is_completed,position)
                VALUES(@task,@title,false,@position) RETURNING id",
            PmsChecklistAction.Rename=>@"UPDATE public.pms_checklist_items SET title=@title,updated_at=clock_timestamp()
                WHERE id=@item",
            PmsChecklistAction.Complete or PmsChecklistAction.Reopen=>@"UPDATE public.pms_checklist_items
                SET is_completed=@complete,updated_at=clock_timestamp() WHERE id=@item",
            PmsChecklistAction.Delete=>@"DELETE FROM public.pms_checklist_items WHERE id=@item;
                DELETE FROM public.suite_branch_ownership WHERE resource_table='pms_checklist_items'
                    AND resource_key=@item::text AND company_id=@organization AND branch_id=@branch",
            PmsChecklistAction.Reorder=>@"UPDATE public.pms_checklist_items c SET position=(ordered.ordinal-1)::int,
                updated_at=clock_timestamp() FROM unnest(@order) WITH ORDINALITY AS ordered(id,ordinal)
                WHERE c.task_id=@task AND c.id=ordered.id",
            _=>throw new ArgumentOutOfRangeException(nameof(action))
        };
        using var change=new NpgsqlCommand(sql,db,tx);
        SetBranch(change);
        change.Parameters.AddWithValue("task",task);
        change.Parameters.Add("title",NpgsqlDbType.Text).Value=(object?)title??DBNull.Value;
        change.Parameters.Add("item",NpgsqlDbType.Integer).Value=(object?)item??DBNull.Value;
        change.Parameters.AddWithValue("complete",action==PmsChecklistAction.Complete);
        change.Parameters.AddWithValue("position",rows.Rows.Count==0?0:
            rows.Rows.Cast<DataRow>().Max(row=>row.Field<int>("position"))+1);
        change.Parameters.AddWithValue("order",NpgsqlDbType.Array|NpgsqlDbType.Integer,orderedItems??Array.Empty<int>());
        if (action==PmsChecklistAction.Add)
        {
            item=(int)(await change.ExecuteScalarAsync(cancellation))!;
            await RecordOwnershipAsync(db,tx,"pms_checklist_items",item.Value,cancellation);
        }
        else
            await change.ExecuteNonQueryAsync(cancellation);

        string activity=action switch
        {
            PmsChecklistAction.Add=>"checklist.item_added",
            PmsChecklistAction.Rename=>"checklist.item_updated",
            PmsChecklistAction.Complete=>"checklist.item_completed",
            PmsChecklistAction.Reopen=>"checklist.item_reopened",
            PmsChecklistAction.Delete=>"checklist.item_deleted",
            _=>"checklist.reordered"
        };
        using var audit=new NpgsqlCommand(@"
            INSERT INTO public.pms_activities(project_id,task_id,actor_user_id,action,entity_type,entity_id,summary,metadata_json)
            VALUES(@project,@task,@actor,@action,'checklist_item',@item,@summary,@metadata) RETURNING id",db,tx);
        audit.Parameters.AddWithValue("project",scope.Project);
        audit.Parameters.AddWithValue("task",task);
        audit.Parameters.AddWithValue("actor",actor.UserId);
        audit.Parameters.AddWithValue("action",activity);
        audit.Parameters.Add("item",NpgsqlDbType.Integer).Value=(object?)item??DBNull.Value;
        audit.Parameters.AddWithValue("summary",$"{action} checklist item on {scope.Key}");
        audit.Parameters.AddWithValue("metadata",JsonSerializer.Serialize(new { title,is_completed=action==PmsChecklistAction.Complete }));
        var auditId=(int)(await audit.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db,tx,"pms_activities",auditId,cancellation);
        await tx.CommitAsync(cancellation);
    }

    private async Task<(int Project,string Key,bool Manage,int? Workspace)> ReadTaskActionScopeAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        PmsActor actor,int task,bool locked,CancellationToken cancellation)
    {
        using var query=new NpgsqlCommand("SELECT p.id,t.task_key, coalesce((" + TaskEditAccess + "),false),p.workspace_id"
            + LiveTaskScope + (locked?" FOR UPDATE OF p,t":""),db,tx);
        SetActor(query,actor);
        query.Parameters.AddWithValue("task",task);
        using var row=await query.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            throw new UnauthorizedAccessException("This task is unavailable in your current scope.");
        return (row.GetInt32(0),row.GetString(1),row.GetBoolean(2),row.IsDBNull(3)?null:row.GetInt32(3));
    }

    private async Task<DataTable> ReadChecklistRowsAsync(NpgsqlConnection db,NpgsqlTransaction tx,int task,CancellationToken cancellation)
    {
        using var query=new NpgsqlCommand(@"
            SELECT c.id,c.title,coalesce(c.is_completed,false) AS is_completed,coalesce(c.position,0) AS position,
                c.xmin::text AS revision
            FROM public.pms_checklist_items c WHERE c.task_id=@task AND " + ChecklistBranch
            + " ORDER BY c.position,c.id",db,tx);
        SetBranch(query);
        query.Parameters.AddWithValue("task",task);
        return await ReadTableAsync(query,cancellation);
    }

    private static string ChecklistRevision(DataTable rows) =>
        string.Join("|",rows.Rows.Cast<DataRow>().Select(row=>$"{row["id"]}:{row["revision"]}"));
}


