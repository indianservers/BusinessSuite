using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class CrmDealRepository
{
    internal Task SaveDealTaskAsync(int deal,int id,string revision,DealTaskDraft draft,CancellationToken cancellation)=>
        ChangeDealTaskAsync(deal,id,revision,ValidateTaskDraft(draft),cancellation);

    internal Task ArchiveDealTaskAsync(int deal,int id,string revision,CancellationToken cancellation)=>
        ChangeDealTaskAsync(deal,id,revision,null,cancellation);

    private async Task ChangeDealTaskAsync(int deal,int id,string revision,DealTaskDraft? draft,
        CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireDealActivityAccessAsync(db,tx,actor,draft is null?"delete":"edit");
        var parent=await LockableDealAsync(db,tx,deal,true,cancellation,requireOpen:false);
        int branch=parent["owning_branch"] as int? ?? throw new InvalidOperationException("The deal must belong to the writable branch.");
        string values=draft is not null
            ? "title=@title,description=NULLIF(@description,''),priority=@priority,due_date=@due,reminder_at=@reminder"
            : "deleted_at=now()";
        using var update=Query(db,tx,@"WITH original AS (
            SELECT t.id,to_jsonb(t) AS snapshot FROM public.crm_tasks t WHERE t.organization_id=@org
                AND t.deal_id=@deal AND t.id=@id AND t.deleted_at IS NULL
                AND t.xmin::text=@revision AND "+CrmDirectoryWrites.BranchScope("crm_tasks","t")+
                (draft is null?"":" AND COALESCE(lower(t.status),'') NOT IN ('done','completed','complete','cancelled','canceled')")+@"
            FOR UPDATE OF t
        ), changed AS (
            UPDATE public.crm_tasks t SET "+values+@",updated_by_user_id=@actor,updated_at=now()
            FROM original WHERE t.id=original.id AND t.organization_id=@org RETURNING original.snapshot,to_jsonb(t) AS current
        )
        INSERT INTO public.audit_logs (organization_id,user_id,actor_authenticated,method,entity_type,entity_id,action,
            description,module,old_values,new_values)
        SELECT @org,@actor,true,'CRM','tasks',@id,@action,@reason,'crm',snapshot::text,current::text FROM changed
        RETURNING old_values,new_values",
            ("deal",NpgsqlDbType.Integer,deal),("id",NpgsqlDbType.Integer,id),("actor",NpgsqlDbType.Integer,actor.Id),
            ("revision",NpgsqlDbType.Text,revision),("title",NpgsqlDbType.Text,draft?.Title),
            ("description",NpgsqlDbType.Text,draft?.Description),("priority",NpgsqlDbType.Text,draft?.Priority),
            ("due",NpgsqlDbType.TimestampTz,draft?.Due),("reminder",NpgsqlDbType.TimestampTz,draft?.Reminder),
            ("action",NpgsqlDbType.Text,draft is not null?"UPDATE":"DELETE"),
            ("reason",NpgsqlDbType.Text,draft is not null?"CRM Deal task revised":"CRM Deal task archived"));
        var audit=await ReadAsync(update,cancellation);
        if (audit.Rows.Count!=1)
            throw new InvalidOperationException("The task changed or is unavailable. Refresh and try again.");
        if (draft is not null)
        {
            using var old=JsonDocument.Parse((string)audit.Rows[0]["old_values"]);
            using var current=JsonDocument.Parse((string)audit.Rows[0]["new_values"]);
            foreach (string field in new[] {"description","priority"})
            {
                string? before=old.RootElement.GetProperty(field).GetString();
                string? after=current.RootElement.GetProperty(field).GetString();
                if (before!=after)
                    await WriteDealRelatedFieldHistoryAsync(db,tx,actor.Id,branch,deal,"tasks",id,field,before,after,cancellation);
            }
        }
        tx.Commit();
    }

    private async Task WriteDealRelatedFieldHistoryAsync(NpgsqlConnection db,NpgsqlTransaction tx,int actor,int branch,int deal,string entity,int id,
        string field,string? before,string? after,CancellationToken cancellation)
    {
        string metadata=JsonSerializer.Serialize(new {sourceEntity=entity,sourceId=id,field,old=before,@new=after});
        string title=field switch {"priority"=>"Priority updated","status"=>$"Status changed to {after}",_=>"Description updated"};
        string kind=field=="status"?"status_change":"field_change";
        using var command=Query(db,tx,@"WITH activity AS (
            INSERT INTO public.crm_activities (organization_id,branch_id,owner_user_id,entity_type,entity_id,deal_id,activity_type,
                title,subject,body,description,metadata_json,status,activity_date,created_by_user_id,updated_by_user_id)
            VALUES (@org,@branch,@actor,'deal',@deal,@deal,@kind,@title,@title,@body,@body,@meta,'Completed',now(),@actor,@actor)
            RETURNING id
        ), ownership AS (
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'crm_activities',id::text,@org,@branch,'desktop-crm' FROM activity
        ) INSERT INTO public.crm_timeline_events (organization_id,record_type,record_id,event_type,title,description,metadata_json,
            actor_user_id,occurred_at) VALUES (@org,'deal',@deal,@kind,@title,@body,@meta,@actor,now())",
            ("actor",NpgsqlDbType.Integer,actor),("branch",NpgsqlDbType.Integer,branch),("deal",NpgsqlDbType.Integer,deal),
            ("title",NpgsqlDbType.Text,title),("body",NpgsqlDbType.Text,$"{field} changed from {before ?? "-"} to {after ?? "-"}"),
            ("kind",NpgsqlDbType.Text,kind),("meta",NpgsqlDbType.Json,metadata));
        await command.ExecuteNonQueryAsync(cancellation);
    }
}
