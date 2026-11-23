using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadNurtureConsent(bool Allowed,string Evidence);

internal static partial class LeadStore
{
    internal static LeadNurtureConsent ReadNurtureConsent(DataRow row)
    {
        var details=ReadDetails(row);
        details.TryGetValue("nurtureConsent",out var consent);
        bool allowed=Nested(consent,"allowed") is JsonElement grant&&grant.ValueKind==JsonValueKind.True;
        string evidence=Nested(consent,"evidence") is JsonElement text&&text.ValueKind==JsonValueKind.String
            ?text.GetString()??"":"";
        return new(allowed,evidence);
    }

    internal static async Task SaveNurtureConsentAsync(LeadKey key,LeadNurtureConsent consent,CancellationToken cancellation)
    {
        string evidence=consent.Evidence.Trim();
        if (evidence.Length==0 || evidence.Length>1000)
            throw new ArgumentException("Record permission evidence or a withdrawal reason of up to 1,000 characters.");
        if (key.Potential)
            throw new InvalidOperationException("Choose a Lead to record nurture permission.");
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"leads","edit");
        var current=await LockLead(db,tx,settings,key,false,cancellation);
        var details=ReadDetails(current);
        details["nurtureConsent"]=new { allowed=consent.Allowed,evidence,recordedAt=DateTimeOffset.UtcNow,recordedBy=actor.Id };
        await WriteState(db,tx,settings.OrganizationId,key.Id,details,key.StateRevision,cancellation);
        string title=consent.Allowed?"Nurture permission recorded":"Nurture permission withdrawn";
        await AddLeadHistoryAsync(db,tx,settings.OrganizationId,key.Id,current["branch_id"] as int?,actor.Id,
            "consent",title,null,"{}",cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"crm_leads",settings.OrganizationId,key.Id,actor.Id,"UPDATE",cancellation,title);
        tx.Commit();
    }

    private static async Task AddLeadHistoryAsync(NpgsqlConnection db,NpgsqlTransaction tx,int org,int lead,int? branch,
        int actor,string kind,string title,string? body,string metadata,CancellationToken cancellation,bool completion=false)
    {
        using var history=Cmd(db,tx,@"WITH activity AS (
                INSERT INTO public.crm_activities (organization_id,branch_id,entity_type,entity_id,lead_id,activity_type,
                    title,subject,body,description,status,activity_date,metadata_json,owner_user_id,created_by_user_id,updated_by_user_id,
                    completed_at,outcome)
                VALUES (@org,@branch,'lead',@id,@id,@kind,@title,@title,@body,@body,'Completed',now(),@metadata,@actor,@actor,@actor,
                    CASE WHEN @completion THEN now() END,CASE WHEN @completion THEN @body END)
                RETURNING id
            ), timeline AS (
                INSERT INTO public.crm_timeline_events (organization_id,record_type,record_id,event_type,title,
                    description,metadata_json,actor_user_id,occurred_at)
                VALUES (@org,'lead',@id,@kind,@title,@body,@metadata,@actor,now())
            ) SELECT id FROM activity",
            ("org",NpgsqlDbType.Integer,org),("branch",NpgsqlDbType.Integer,branch),
            ("actor",NpgsqlDbType.Integer,actor),("id",NpgsqlDbType.Integer,lead),("title",NpgsqlDbType.Text,title),
            ("kind",NpgsqlDbType.Text,kind),("body",NpgsqlDbType.Text,body),("metadata",NpgsqlDbType.Json,metadata),
            ("completion",NpgsqlDbType.Boolean,completion));
        int activityId=(int)(await history.ExecuteScalarAsync(cancellation))!;
        if (branch.HasValue)
            await AddOwnership(db,tx,org,"crm_activities",activityId,branch.Value,cancellation);
    }
}
