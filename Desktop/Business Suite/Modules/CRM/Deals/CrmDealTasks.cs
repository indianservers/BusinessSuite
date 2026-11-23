using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record DealTaskDraft(string Title,string Description,string Priority,DateTime? Due,DateTime? Reminder);
internal sealed record DealTaskOrigin(string Key,string Details,int? Lead,int? Contact,int? Company);
internal sealed record DealTaskSave(int Id,bool Created,bool Archived=false);

internal sealed partial class CrmDealRepository
{
    internal async Task<DataTable> DealTasksAsync(int dealId,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        await RequireDealActivityAccessAsync(db,tx,actor,"view");
        await LockableDealAsync(db,tx,dealId,false,cancellation,requireOpen:false);
        using var cmd=Query(db,tx,@"SELECT t.id,t.xmin::text AS revision,t.title,t.description,t.status,t.priority,
            t.due_date AT TIME ZONE 'UTC' AS due_date,t.reminder_at AT TIME ZONE 'UTC' AS reminder_at,t.completed_at,
            t.task_details->>'relatedRecord' AS related_record
            FROM public.crm_tasks t WHERE t.organization_id=@org AND t.deal_id=@deal
            AND t.deleted_at IS NULL AND "+CrmDirectoryWrites.BranchScope("crm_tasks","t")+@"
            ORDER BY t.due_date ASC NULLS LAST,t.id DESC LIMIT 200",("deal",NpgsqlDbType.Integer,dealId));
        return await ReadAsync(cmd,cancellation);
    }

    internal async Task<int> AddDealTaskAsync(int dealId,DealTaskDraft draft,CancellationToken cancellation)
    {
        draft=ValidateTaskDraft(draft);
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireDealActivityAccessAsync(db,tx,actor,"create");
        var deal=await LockableDealAsync(db,tx,dealId,true,cancellation,requireOpen:false);
        var result=await InsertDealTaskAsync(db,tx,actor,deal,draft,null,cancellation);
        tx.Commit();
        return result.Id;
    }

    private async Task<DealTaskSave> InsertDealTaskAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,DataRow deal,
        DealTaskDraft draft,DealTaskOrigin? origin,CancellationToken cancellation,int? owner=null)
    {
        int dealId=(int)deal["id"];
        int branch=deal["owning_branch"] as int? ?? throw new InvalidOperationException("The deal must belong to the writable branch.");
        using var cmd=Query(db,tx,@"INSERT INTO public.crm_tasks (organization_id,branch_id,deal_id,owner_user_id,title,
            description,status,priority,due_date,reminder_at,created_by_user_id,updated_by_user_id,
            import_key,task_details,lead_id,contact_id,company_id)
            VALUES (@org,@branch,@deal,@owner,@title,NULLIF(@description,''),'To Do',@priority,@due,@reminder,@actor,@actor,
                @key,@details,@lead,@contact,@company)
            ON CONFLICT (organization_id,created_by_user_id,import_key) DO NOTHING RETURNING id",
            ("branch",NpgsqlDbType.Integer,branch),("deal",NpgsqlDbType.Integer,dealId),("actor",NpgsqlDbType.Integer,actor.Id),
            ("owner",NpgsqlDbType.Integer,owner ?? actor.Id),("title",NpgsqlDbType.Text,draft.Title),("description",NpgsqlDbType.Text,draft.Description),("priority",NpgsqlDbType.Text,draft.Priority),
            ("due",NpgsqlDbType.TimestampTz,draft.Due),("reminder",NpgsqlDbType.TimestampTz,draft.Reminder),
            ("key",NpgsqlDbType.Text,origin?.Key),("details",NpgsqlDbType.Json,origin?.Details),("lead",NpgsqlDbType.Integer,origin?.Lead),
            ("contact",NpgsqlDbType.Integer,origin?.Contact),("company",NpgsqlDbType.Integer,origin?.Company));
        if (await cmd.ExecuteScalarAsync(cancellation) is not int taskId)
        {
            using var retry=Query(db,tx,@"SELECT t.id,(t.deleted_at IS NOT NULL) AS archived FROM public.crm_tasks t
                WHERE t.organization_id=@org AND t.created_by_user_id=@actor AND t.import_key=@key AND t.deal_id=@deal AND "+
                CrmDirectoryWrites.BranchScope("crm_tasks","t"),("actor",NpgsqlDbType.Integer,actor.Id),("key",NpgsqlDbType.Text,origin?.Key),
                ("deal",NpgsqlDbType.Integer,dealId));
            using var existing=await retry.ExecuteReaderAsync(cancellation);
            if (!await existing.ReadAsync(cancellation))
                throw new InvalidOperationException("The original follow-up cannot be opened in this branch.");
            return new(existing.GetInt32(0),false,existing.GetBoolean(1));
        }
        using var ownership=Query(db,tx,@"INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            VALUES ('crm_tasks',@id::text,@org,@branch,'desktop-crm')",
            ("id",NpgsqlDbType.Integer,taskId),("branch",NpgsqlDbType.Integer,branch));
        await ownership.ExecuteNonQueryAsync(cancellation);
        await WriteTaskHistoryAsync(db,tx,actor.Id,branch,dealId,taskId,false,draft.Title,draft.Description,cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"tasks",settings.OrganizationId,taskId,actor.Id,"CREATE",cancellation);
        return new(taskId,true);
    }

    private static DealTaskDraft ValidateTaskDraft(DealTaskDraft draft)
    {
        draft=draft with {Title=draft.Title.Trim(),Description=draft.Description.Trim()};
        if (draft.Title.Length is <1 or >220 || draft.Description.Length>10000 ||
            draft.Priority is not ("Low" or "Medium" or "High" or "Critical"))
            throw new ArgumentException("Enter a title up to 220 characters, description, and valid priority.");
        if ((draft.Due.HasValue && draft.Due.Value.Kind!=DateTimeKind.Utc) ||
            (draft.Reminder.HasValue && draft.Reminder.Value.Kind!=DateTimeKind.Utc) ||
            (draft.Reminder.HasValue && (!draft.Due.HasValue || draft.Reminder>draft.Due)))
            throw new ArgumentException("Set a task reminder on or before its due time.");
        return draft;
    }

    internal async Task CompleteDealTaskAsync(int dealId,int taskId,string revision,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireDealActivityAccessAsync(db,tx,actor,"edit");
        var deal=await LockableDealAsync(db,tx,dealId,true,cancellation,requireOpen:false);
        int branch=deal["owning_branch"] as int? ?? throw new InvalidOperationException("The deal must belong to the writable branch.");
        using var cmd=Query(db,tx,@"UPDATE public.crm_tasks t SET status='Completed',completed_at=now(),updated_at=now(),
            updated_by_user_id=@actor WHERE t.organization_id=@org AND t.deal_id=@deal AND t.id=@id
            AND t.deleted_at IS NULL AND t.xmin::text=@revision
            AND COALESCE(lower(t.status),'') NOT IN ('done','completed','complete','cancelled','canceled') AND "+
            CrmDirectoryWrites.BranchScope("crm_tasks","t")+" RETURNING title",
            ("deal",NpgsqlDbType.Integer,dealId),("id",NpgsqlDbType.Integer,taskId),
            ("actor",NpgsqlDbType.Integer,actor.Id),("revision",NpgsqlDbType.Text,revision));
        string? title=await cmd.ExecuteScalarAsync(cancellation) as string;
        if (title is null)
            throw new InvalidOperationException("The task changed or is unavailable. Refresh and try again.");
        await WriteTaskHistoryAsync(db,tx,actor.Id,branch,dealId,taskId,true,"Task completed",title,cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"tasks",settings.OrganizationId,taskId,actor.Id,"UPDATE",cancellation,"Task completed");
        tx.Commit();
    }

    private async Task RequireDealActivityAccessAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,string action)
    {
        await RequireDealsAsync(db,tx,actor,false);
        if (action!="view" && (!actor.IsSuperuser || !actor.CanWriteBranch || !settings.BranchId.HasValue))
            throw new UnauthorizedAccessException("Deal activity changes require a Suite superuser in a writable branch.");
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"activities",action);
    }

    private async Task<bool> CanReadTasksAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor)
    {
        try
        {
            await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"activities","view");
            return true;
        }
        catch(UnauthorizedAccessException) {return false;}
    }

    private async Task WriteTaskHistoryAsync(NpgsqlConnection db,NpgsqlTransaction tx,int actor,int branch,int deal,int task,
        bool complete,string title,string body,CancellationToken cancellation)
    {
        string metadata=JsonSerializer.Serialize(new {sourceEntity="tasks",sourceId=task,status=complete?"Completed":"To Do"});
        using var cmd=Query(db,tx,@"WITH activity AS (
            INSERT INTO public.crm_activities (organization_id,branch_id,owner_user_id,entity_type,entity_id,deal_id,activity_type,
                title,subject,body,description,metadata_json,status,activity_date,created_by_user_id,updated_by_user_id)
            VALUES (@org,@branch,@actor,'deal',@deal,@deal,@kind,@title,@title,@body,@body,@metadata,@activity_status,now(),@actor,@actor)
            RETURNING id
        ), ownership AS (
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'crm_activities',id::text,@org,@branch,'desktop-crm' FROM activity
        ), fresh AS (
            UPDATE public.crm_deals SET last_activity_at=now(),updated_at=now(),updated_by_user_id=@actor,version=version+1
            WHERE organization_id=@org AND id=@deal
        ) INSERT INTO public.crm_timeline_events (organization_id,record_type,record_id,event_type,title,description,metadata_json,
            actor_user_id,occurred_at)
          VALUES (@org,'deal',@deal,@kind,@title,@body,@metadata,@actor,now())",
            ("actor",NpgsqlDbType.Integer,actor),("branch",NpgsqlDbType.Integer,branch),("deal",NpgsqlDbType.Integer,deal),
            ("kind",NpgsqlDbType.Text,complete?"system":"task"),("activity_status",NpgsqlDbType.Text,complete?"Completed":"To Do"),
            ("title",NpgsqlDbType.Text,title),("body",NpgsqlDbType.Text,body),("metadata",NpgsqlDbType.Json,metadata));
        await cmd.ExecuteNonQueryAsync(cancellation);
    }
}
