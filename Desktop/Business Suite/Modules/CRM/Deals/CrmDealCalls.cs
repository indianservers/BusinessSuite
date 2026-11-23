using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record DealCallDraft(string Direction,string CallingCode,string Phone,DateTime CallTime,int? Duration,string Outcome,string Notes);

internal sealed partial class CrmDealRepository
{
    private const string CallBranchScope=@"(@scope_branch IS NULL OR NOT EXISTS (
        SELECT 1 FROM public.suite_branch_ownership o WHERE o.company_id=@org AND o.resource_table='crm_call_logs'
          AND o.resource_key=c.id::text AND o.branch_id<>@scope_branch))";

    internal async Task<DataTable> DealCallsAsync(int deal,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        await RequireDealActivityAccessAsync(db,tx,actor,"view");
        await LockableDealAsync(db,tx,deal,false,cancellation,requireOpen:false);
        using var query=Query(db,tx,@"SELECT c.id,c.xmin::text AS revision,c.direction,c.phone_number,c.phone_number_country_code,
            CASE WHEN c.phone_number LIKE '+%' OR c.phone_number_country_code IS NULL THEN c.phone_number
                ELSE c.phone_number_country_code||' '||c.phone_number END AS phone,
            c.call_time AT TIME ZONE 'UTC' AS occurred,c.duration_seconds,c.outcome,c.notes
            FROM public.crm_call_logs c WHERE c.organization_id=@org AND c.deal_id=@deal AND c.deleted_at IS NULL
            AND "+CallBranchScope+@"
            ORDER BY c.call_time DESC,c.id DESC LIMIT 200",("deal",NpgsqlDbType.Integer,deal));
        return await ReadAsync(query,cancellation);
    }

    internal async Task<int> AddDealCallAsync(int deal,DealCallDraft draft,CancellationToken cancellation)
    {
        draft=ValidateCallDraft(draft);
        string notes=draft.Notes,outcome=draft.Outcome;
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireDealActivityAccessAsync(db,tx,actor,"create");
        var parent=await LockableDealAsync(db,tx,deal,true,cancellation,requireOpen:false);
        int branch=parent["owning_branch"] as int? ?? throw new InvalidOperationException("The deal must belong to the writable branch.");
        using var insert=Query(db,tx,@"INSERT INTO public.crm_call_logs (organization_id,owner_user_id,direction,phone_number,
            phone_number_country_code,duration_seconds,outcome,notes,deal_id,call_time,created_by_user_id,updated_by_user_id)
            VALUES (@org,@actor,@direction,@phone,@code,@duration,NULLIF(@outcome,''),NULLIF(@notes,''),@deal,@time,@actor,@actor)
            RETURNING id",("actor",NpgsqlDbType.Integer,actor.Id),("deal",NpgsqlDbType.Integer,deal),
            ("direction",NpgsqlDbType.Text,draft.Direction),("phone",NpgsqlDbType.Text,draft.Phone),
            ("code",NpgsqlDbType.Text,draft.CallingCode),("duration",NpgsqlDbType.Integer,draft.Duration),
            ("outcome",NpgsqlDbType.Text,outcome),("notes",NpgsqlDbType.Text,notes),("time",NpgsqlDbType.TimestampTz,draft.CallTime));
        int id=(int)(await insert.ExecuteScalarAsync(cancellation))!;
        await WriteRecordedEngagementAsync(db,tx,actor,branch,deal,id,"calls","call","crm_call_logs",
            draft.Direction+" call logged",notes.Length==0?outcome:notes,cancellation);
        tx.Commit();
        return id;
    }

    private async Task WriteRecordedEngagementAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,
        int branch,int deal,int id,string entity,string eventType,string table,string title,string? body,CancellationToken cancellation)
    {
        string metadata=JsonSerializer.Serialize(new {sourceEntity=entity,sourceId=id});
        using var effects=Query(db,tx,@"WITH activity AS (
            INSERT INTO public.crm_activities (organization_id,branch_id,owner_user_id,entity_type,entity_id,deal_id,
                activity_type,title,subject,body,description,metadata_json,status,activity_date,created_by_user_id,updated_by_user_id)
            VALUES (@org,@branch,@actor,'deal',@deal,@deal,@event,@title,@title,@body,@body,@metadata,'Completed',now(),@actor,@actor)
            RETURNING id
        ), ownership AS (
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'crm_activities',id::text,@org,@branch,'desktop-crm' FROM activity
            UNION ALL SELECT @table,@id::text,@org,@branch,'desktop-crm'
        ), last_activity AS (
            UPDATE public.crm_deals SET last_activity_at=now(),updated_at=now(),updated_by_user_id=@actor,version=version+1
            WHERE organization_id=@org AND id=@deal
        ) INSERT INTO public.crm_timeline_events (organization_id,record_type,record_id,event_type,title,description,
            metadata_json,actor_user_id,occurred_at)
          VALUES (@org,'deal',@deal,@event,@title,@body,@metadata,@actor,now())",
            ("id",NpgsqlDbType.Integer,id),("deal",NpgsqlDbType.Integer,deal),("branch",NpgsqlDbType.Integer,branch),
            ("actor",NpgsqlDbType.Integer,actor.Id),("title",NpgsqlDbType.Text,title),("event",NpgsqlDbType.Text,eventType),
            ("table",NpgsqlDbType.Text,table),("body",NpgsqlDbType.Text,body),("metadata",NpgsqlDbType.Json,metadata));
        await effects.ExecuteNonQueryAsync(cancellation);
        await CrmDirectoryWrites.Audit(db,tx,entity,settings.OrganizationId,id,actor.Id,"CREATE",cancellation);
    }

    private static DealCallDraft ValidateCallDraft(DealCallDraft draft)
    {
        draft=draft with {Notes=draft.Notes.Trim(),Outcome=draft.Outcome.Trim()};
        if (draft.Direction is not ("Inbound" or "Outbound") || draft.CallTime.Kind!=DateTimeKind.Utc || draft.Duration<0
            || draft.Outcome.Length>160 || draft.Notes.Length>10000)
            throw new ArgumentException("Choose a call direction, time and nonnegative duration. Outcome and notes must fit their field limits.");
        var number=CrmPhone.Normalize(draft.Phone,draft.CallingCode);
        return draft with {Phone=number.National,CallingCode=number.CallingCode};
    }
}
