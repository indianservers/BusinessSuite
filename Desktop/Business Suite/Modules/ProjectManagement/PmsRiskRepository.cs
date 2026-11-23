using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PmsRiskList(DataTable Rows, DataTable Owners, DataTable Tasks,
    bool CanCreate, bool CanEdit, bool CanDelete);
internal sealed record PmsRiskDraft(string Title, string? Category, int Probability, int Impact, string Status,
    DateTime? Due, string? Description, string? Mitigation, string? Contingency, int? Owner, int? LinkedTask);

internal sealed partial class PmsProjectRepository
{
    private const string RiskBranch = @"(@branch IS NULL OR EXISTS (
        SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='pms_risks'
          AND o.resource_key=r.id::text AND o.company_id=@organization AND o.branch_id=@branch))";

    internal async Task<PmsRiskList> ListRisksAsync(int project,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await GetWorkspaceActorAsync(db,tx,false,cancellation);
        bool manage=(await ReadProjectActionAccessAsync(db,tx,actor,project,false,cancellation)).Manage;
        using var query=new NpgsqlCommand(@"
            SELECT r.id,r.title,r.category,r.probability,r.impact,r.risk_score,initcap(r.status) AS status_display,r.status,
                CASE WHEN r.risk_score>=15 THEN 'High' WHEN r.risk_score>=8 THEN 'Medium' ELSE 'Low' END AS severity,
                r.due_date::timestamp,r.description,r.mitigation_plan,r.contingency_plan,r.xmin::text AS revision,
                r.owner_user_id,r.linked_task_id,
                coalesce(nullif(person.display_name,''),account.email) AS owner_name,
                task.task_key AS linked_key
            FROM public.pms_risks r
            LEFT JOIN public.users account ON account.id=r.owner_user_id
            LEFT JOIN public.common_people person ON person.user_id=account.id
            LEFT JOIN public.pms_tasks task ON task.id=r.linked_task_id AND task.project_id=r.project_id
            WHERE r.project_id=@project AND coalesce(r.organization_id,1)=@organization AND r.deleted_at IS NULL AND "
            + RiskBranch + " ORDER BY r.risk_score DESC,r.due_date NULLS LAST,r.created_at DESC",db,tx);
        SetBranch(query);
        query.Parameters.AddWithValue("project",project);
        var rows=await ReadTableAsync(query,cancellation);
        if (!manage || !(actor.ModuleCanCreate||actor.ModuleCanEdit))
            return new PmsRiskList(rows,new DataTable(),new DataTable(),false,false,manage && actor.ModuleCanDelete);
        var owners=await ReadProjectEligibleOwnersAsync(db,tx,actor,project,cancellation);
        using var taskList=new NpgsqlCommand(@"
            SELECT t.id,t.task_key || ' · ' || t.title AS name FROM public.pms_tasks t
            WHERE t.project_id=@project AND t.deleted_at IS NULL AND " + TaskBranchScope + " ORDER BY t.task_key",db,tx);
        SetBranch(taskList);
        taskList.Parameters.AddWithValue("project",project);
        return new PmsRiskList(rows,owners,await ReadTableAsync(taskList,cancellation),
            actor.ModuleCanCreate,actor.ModuleCanEdit,actor.ModuleCanDelete);
    }

    internal async Task<int> SaveRiskAsync(int project,int? risk,string? revision,PmsRiskDraft draft,
        CancellationToken cancellation)
    {
        var title=draft.Title.Trim();
        if (title.Length is < 1 or > 220)
            throw new InvalidOperationException("Enter a risk title of 1 to 220 characters.");
        if (draft.Category?.Length>80)
            throw new InvalidOperationException("Use 80 or fewer characters for the category.");
        if (draft.Probability is <1 or >5 || draft.Impact is <1 or >5)
            throw new InvalidOperationException("Probability and impact must both be between 1 and 5.");
        if (draft.Status is not ("open" or "mitigating" or "closed"))
            throw new InvalidOperationException("Choose Open, Mitigating or Closed.");

        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await GetWorkspaceActorAsync(db,tx,true,cancellation);
        if (!(risk.HasValue?actor.ModuleCanEdit:actor.ModuleCanCreate) ||
            !(await ReadProjectActionAccessAsync(db,tx,actor,project,true,cancellation)).Manage)
            throw new UnauthorizedAccessException("You do not have permission to change risks for this project.");
        int? oldOwner=null;
        if (risk.HasValue)
            oldOwner=(await LockRiskAsync(db,tx,project,risk.Value,revision!,cancellation)).Owner;
        if (draft.Owner.HasValue && draft.Owner != oldOwner)
        {
            var owners=await ReadProjectEligibleOwnersAsync(db,tx,actor,project,cancellation);
            if (!owners.Rows.Cast<DataRow>().Any(row=>row.Field<int>("id")==draft.Owner.Value))
                throw new InvalidOperationException("Choose an active eligible project owner.");
        }
        if (draft.LinkedTask.HasValue)
        {
            using var link=new NpgsqlCommand(@"
                SELECT t.id FROM public.pms_tasks t WHERE t.id=@task AND t.project_id=@project
                    AND t.deleted_at IS NULL AND " + TaskBranchScope,db,tx);
            SetBranch(link);
            link.Parameters.AddWithValue("project",project);
            link.Parameters.AddWithValue("task",draft.LinkedTask.Value);
            if (await link.ExecuteScalarAsync(cancellation) is not int)
                throw new InvalidOperationException("The linked task must belong to this project and be active.");
        }

        var score=draft.Probability*draft.Impact;
        string sql=risk.HasValue?@"
            UPDATE public.pms_risks SET title=@title,description=@description,category=@category,
                probability=@probability,impact=@impact,risk_score=@score,status=@status,owner_user_id=@owner,
                linked_task_id=@task,mitigation_plan=@mitigation,contingency_plan=@contingency,due_date=@due,
                updated_at=clock_timestamp() WHERE id=@risk RETURNING id":@"
            INSERT INTO public.pms_risks(organization_id,project_id,title,description,category,probability,impact,
                risk_score,status,owner_user_id,linked_task_id,mitigation_plan,contingency_plan,due_date)
            VALUES(@organization,@project,@title,@description,@category,@probability,@impact,@score,@status,
                @owner,@task,@mitigation,@contingency,@due) RETURNING id";
        using var save=new NpgsqlCommand(sql,db,tx);
        SetBranch(save);
        save.Parameters.AddWithValue("project",project);
        save.Parameters.AddWithValue("title",title);
        save.Parameters.AddWithValue("description",NpgsqlDbType.Text,(object?)draft.Description??DBNull.Value);
        save.Parameters.AddWithValue("category",NpgsqlDbType.Text,(object?)draft.Category??DBNull.Value);
        save.Parameters.AddWithValue("probability",draft.Probability);
        save.Parameters.AddWithValue("impact",draft.Impact);
        save.Parameters.AddWithValue("score",score);
        save.Parameters.AddWithValue("status",draft.Status);
        save.Parameters.AddWithValue("owner",NpgsqlDbType.Integer,(object?)draft.Owner??DBNull.Value);
        save.Parameters.AddWithValue("task",NpgsqlDbType.Integer,(object?)draft.LinkedTask??DBNull.Value);
        save.Parameters.AddWithValue("mitigation",NpgsqlDbType.Text,(object?)draft.Mitigation??DBNull.Value);
        save.Parameters.AddWithValue("contingency",NpgsqlDbType.Text,(object?)draft.Contingency??DBNull.Value);
        save.Parameters.AddWithValue("due",NpgsqlDbType.Date,(object?)draft.Due??DBNull.Value);
        if (risk.HasValue) save.Parameters.AddWithValue("risk",risk.Value);
        var id=(int)(await save.ExecuteScalarAsync(cancellation))!;
        if (!risk.HasValue)
            await RecordOwnershipAsync(db,tx,"pms_risks",id,cancellation);
        await RecordRiskActivityAsync(db,tx,actor,project,id,draft.LinkedTask,risk.HasValue?"risk.updated":"risk.created",
            (risk.HasValue?"Updated risk ":"Created risk ")+title,JsonSerializer.Serialize(new
            {
                risk_score=score,severity=score>=15?"high":score>=8?"medium":"low",status=draft.Status
            }),cancellation);
        await tx.CommitAsync(cancellation);
        return id;
    }

    internal async Task DeleteRiskAsync(int project,int risk,string revision,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await GetWorkspaceActorAsync(db,tx,true,cancellation);
        if (!actor.ModuleCanDelete || !(await ReadProjectActionAccessAsync(db,tx,actor,project,true,cancellation)).Manage)
            throw new UnauthorizedAccessException("You do not have permission to delete risks for this project.");
        var current=await LockRiskAsync(db,tx,project,risk,revision,cancellation);
        using var remove=new NpgsqlCommand(
            "UPDATE public.pms_risks SET deleted_at=clock_timestamp(),updated_at=clock_timestamp() WHERE id=@risk",db,tx);
        remove.Parameters.AddWithValue("risk",risk);
        await remove.ExecuteNonQueryAsync(cancellation);
        await RecordRiskActivityAsync(db,tx,actor,project,risk,current.Task,"risk.deleted",
            "Deleted risk "+current.Title,"{}",cancellation);
        await tx.CommitAsync(cancellation);
    }

    private async Task<(int? Owner,int? Task,string Title)> LockRiskAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        int project,int risk,string revision,CancellationToken cancellation)
    {
        using var get=new NpgsqlCommand(@"
            SELECT r.owner_user_id,r.linked_task_id,r.title FROM public.pms_risks r
            WHERE r.project_id=@project AND coalesce(r.organization_id,1)=@organization AND r.id=@risk
              AND r.deleted_at IS NULL AND r.xmin::text=@revision AND " + RiskBranch + " FOR UPDATE OF r",db,tx);
        SetBranch(get);
        get.Parameters.AddWithValue("project",project);
        get.Parameters.AddWithValue("risk",risk);
        get.Parameters.AddWithValue("revision",revision);
        using var row=await get.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            throw new InvalidOperationException("This risk changed or is unavailable. Refresh and try again.");
        return (row.IsDBNull(0)?null:row.GetInt32(0),row.IsDBNull(1)?null:row.GetInt32(1),row.GetString(2));
    }

    private async Task RecordRiskActivityAsync(NpgsqlConnection db,NpgsqlTransaction tx,PmsActor actor,int project,
        int risk,int? task,string action,string summary,string metadata,CancellationToken cancellation)
    {
        using var audit=new NpgsqlCommand(@"
            INSERT INTO public.pms_activities(project_id,task_id,actor_user_id,action,entity_type,entity_id,summary,metadata_json)
            VALUES(@project,@task,@actor,@action,'risk',@risk,@summary,@metadata) RETURNING id",db,tx);
        audit.Parameters.AddWithValue("project",project);
        audit.Parameters.AddWithValue("task",NpgsqlDbType.Integer,(object?)task??DBNull.Value);
        audit.Parameters.AddWithValue("actor",actor.UserId);
        audit.Parameters.AddWithValue("action",action);
        audit.Parameters.AddWithValue("risk",risk);
        audit.Parameters.AddWithValue("summary",summary);
        audit.Parameters.AddWithValue("metadata",metadata);
        var id=(int)(await audit.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db,tx,"pms_activities",id,cancellation);
    }
}

