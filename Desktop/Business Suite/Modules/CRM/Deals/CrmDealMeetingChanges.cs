using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class CrmDealRepository
{
    internal Task SaveDealMeetingAsync(int deal,int meeting,string revision,DealMeetingDraft draft,CancellationToken cancellation)=>
        ChangeDealMeetingAsync(deal,meeting,revision,ValidateMeetingDraft(draft),cancellation);

    internal Task ArchiveDealMeetingAsync(int deal,int meeting,string revision,CancellationToken cancellation)=>
        ChangeDealMeetingAsync(deal,meeting,revision,null,cancellation);

    private async Task ChangeDealMeetingAsync(int deal,int meeting,string revision,DealMeetingDraft? draft,
        CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireDealActivityAccessAsync(db,tx,actor,draft is null?"delete":"edit");
        var parent=await LockableDealAsync(db,tx,deal,true,cancellation,requireOpen:false);
        int branch=parent["owning_branch"] as int? ?? throw new InvalidOperationException("The deal must belong to the writable branch.");
        using var lookup=Query(db,tx,@"SELECT m.external_provider,m.external_event_id,m.sync_status,m.lead_id,m.status
            FROM public.crm_meetings m WHERE m.organization_id=@org AND m.deal_id=@deal AND m.id=@id AND m.deleted_at IS NULL
            AND m.xmin::text=@revision AND "+MeetingBranchScope+" FOR UPDATE OF m",
            ("deal",NpgsqlDbType.Integer,deal),("id",NpgsqlDbType.Integer,meeting),("revision",NpgsqlDbType.Text,revision));
        var current=await ReadAsync(lookup,cancellation);
        if (current.Rows.Count!=1)
            throw new InvalidOperationException("This meeting changed or is unavailable. Refresh and try again.");
        var row=current.Rows[0];
        if (!string.IsNullOrEmpty(row["external_provider"] as string) || !string.IsNullOrEmpty(row["external_event_id"] as string) ||
            (row["sync_status"] as string ?? "not_synced") is not ("" or "not_synced"))
            throw new InvalidOperationException("This meeting has external calendar state. Its calendar service is unavailable offline.");
        if (draft?.Status=="Completed" && (row["status"] as string)!="Completed" && row["lead_id"] is int)
            throw new InvalidOperationException("Completing this meeting can advance its linked lead. Use the CRM lead workflow.");
        string values=draft is null?"deleted_at=now()":@"title=@title,description=NULLIF(@description,''),location=NULLIF(@location,''),
            start_time=@start,end_time=@end,status=@status,outcome=NULLIF(@outcome,'')";
        using var update=Query(db,tx,@"WITH original AS (
            SELECT m.id,to_jsonb(m) AS old FROM public.crm_meetings m WHERE m.organization_id=@org AND m.id=@id
        ), changed AS (
            UPDATE public.crm_meetings m SET "+values+@",updated_by_user_id=@actor,updated_at=now()
            FROM original WHERE m.organization_id=@org AND m.id=original.id RETURNING original.old,to_jsonb(m) AS current
        ) INSERT INTO public.audit_logs (organization_id,user_id,actor_authenticated,method,entity_type,entity_id,action,
            description,module,old_values,new_values)
        SELECT @org,@actor,true,'CRM','meetings',@id,@action,@reason,'crm',old::text,current::text FROM changed
        RETURNING old_values,new_values",
            ("id",NpgsqlDbType.Integer,meeting),("actor",NpgsqlDbType.Integer,actor.Id),("title",NpgsqlDbType.Text,draft?.Title),
            ("description",NpgsqlDbType.Text,draft?.Description),("location",NpgsqlDbType.Text,draft?.Location),
            ("start",NpgsqlDbType.TimestampTz,draft?.Start),("end",NpgsqlDbType.TimestampTz,draft?.End),
            ("status",NpgsqlDbType.Text,draft?.Status),("outcome",NpgsqlDbType.Text,draft?.Outcome),
            ("action",NpgsqlDbType.Text,draft is null?"DELETE":"UPDATE"),
            ("reason",NpgsqlDbType.Text,draft is null?"CRM Deal meeting archived":"CRM Deal meeting revised"));
        var audit=await ReadAsync(update,cancellation);
        if (audit.Rows.Count!=1)
            throw new InvalidOperationException("This meeting changed or is unavailable. Refresh and try again.");
        if (draft is not null)
        {
            using var old=JsonDocument.Parse((string)audit.Rows[0]["old_values"]);
            using var fresh=JsonDocument.Parse((string)audit.Rows[0]["new_values"]);
            foreach(string field in new[] {"description","status"})
            {
                var before=old.RootElement.GetProperty(field).GetString();
                var after=fresh.RootElement.GetProperty(field).GetString();
                if (before!=after)
                    await WriteDealRelatedFieldHistoryAsync(db,tx,actor.Id,branch,deal,"meetings",meeting,field,before,after,cancellation);
            }
        }
        tx.Commit();
    }
}
