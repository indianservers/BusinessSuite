using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal static partial class LeadStore
{
    internal static async Task RecordLeadActivityAsync(LeadKey key,string kind,string outcome,DateTime? followUp,
        CancellationToken cancellation,bool responded=false)
    {
        outcome=outcome.Trim();
        if (kind is not ("call" or "email" or "meeting" or "note" or "task") || outcome.Length is <1 or >4000)
            throw new ArgumentException("Choose an activity type and enter an outcome of up to 4,000 characters.");
        if (followUp.HasValue && followUp.Value.Kind!=DateTimeKind.Utc)
            throw new ArgumentException("Enter the follow-up date and time in UTC.");
        if (key.Potential)
            throw new InvalidOperationException("Choose an active Lead.");
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"leads","edit");
        var lead=await LockLead(db,tx,settings,key,false,cancellation);
        int org=settings.OrganizationId;
        int? branch=settings.BranchId??lead["branch_id"] as int?;
        DateTime now=DateTime.UtcNow;
        var details=ReadDetails(lead);
        details["lastActivityAt"]=now;
        if (responded)
            await RecordLeadResponseAsync(db,tx,settings,key.Id,details,actor.Id,now,cancellation);
        bool contacted=kind is "call" or "email" or "meeting";
        if (contacted)
        {
            details["enquiryPending"]=false;
            if (!details.ContainsKey("firstContactAt"))
                details["firstContactAt"]=now;
            lead["last_contacted_at"]=now;
        }
        await AddLeadHistoryAsync(db,tx,org,key.Id,branch,actor.Id,kind,char.ToUpperInvariant(kind[0])+kind.Substring(1)+" outcome",
            outcome,JsonSerializer.Serialize(new {responded}),cancellation,completion:true);
        if (followUp is DateTime due)
        {
            int length=Math.Min(150,outcome.Length);
            if (char.IsHighSurrogate(outcome[length-1]))
                length--;
            await AddLeadPendingTaskAsync(db,tx,settings,key.Id,lead,actor.Id,"Follow up: "+outcome.Substring(0,length),
                "{}",due,cancellation);
            lead["next_follow_up_at"]=due;
        }
        if (contacted || followUp.HasValue)
        {
            using var stamp=Cmd(db,tx,@"UPDATE public.crm_leads
                SET last_contacted_at=CASE WHEN @contacted THEN @now ELSE last_contacted_at END,
                    next_follow_up_at=COALESCE(@due,next_follow_up_at)
                WHERE organization_id=@org AND id=@lead",
                ("org",NpgsqlDbType.Integer,org),("lead",NpgsqlDbType.Integer,key.Id),("contacted",NpgsqlDbType.Boolean,contacted),
                ("now",NpgsqlDbType.TimestampTz,now),("due",NpgsqlDbType.TimestampTz,followUp));
            await stamp.ExecuteNonQueryAsync(cancellation);
        }
        if (responded)
            await ApplyLeadWorkflowsAsync(db,tx,settings,key.Id,lead,actor,"responded",now,cancellation);
        await WriteState(db,tx,org,key.Id,details,key.StateRevision,cancellation);
        await RefreshLeadScoreAsync(db,tx,org,lead,actor.Id,now,cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"crm_leads",org,key.Id,actor.Id,"UPDATE",cancellation,"Lead activity recorded");
        tx.Commit();
    }

    private static async Task RecordLeadResponseAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        DesktopDatabaseSettings settings,int leadId,Dictionary<string,object?> details,
        int actor,DateTime now,CancellationToken cancellation)
    {
        details["lastResponseAt"]=now;
        details.Remove("proposalReminder");
        await CancelActiveSequenceAsync(db,tx,settings,leadId,details,actor,now,"Lead responded",cancellation);
    }

    private static async Task CancelActiveSequenceAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        DesktopDatabaseSettings settings,int leadId,Dictionary<string,object?> details,int actor,DateTime now,
        string reason,CancellationToken cancellation)
    {
        details.TryGetValue("sequence",out var current);
        if (current is not JsonElement sequence || Nested(sequence,"active") is not JsonElement active ||
            active.ValueKind!=JsonValueKind.True)
            return;
        if (Nested(sequence,"id") is not JsonElement identity)
            throw new InvalidOperationException("The active Lead sequence has no identifier.");

        using var cancel=Cmd(db,tx,@"WITH matching AS (
            SELECT a.id,"+LeadActivityScope(false)+@" AS writable FROM public.crm_activities a
            WHERE a.organization_id=@org AND a.lead_id=@lead AND a.status='Pending' AND a.deleted_at IS NULL
              AND (a.metadata_json->'sequenceId')::jsonb=@sequence::jsonb FOR UPDATE OF a
        ), cancelled AS (
            UPDATE public.crm_activities a SET status='Cancelled',updated_at=@now,updated_by_user_id=@actor
            FROM matching m WHERE a.id=m.id AND m.writable AND NOT EXISTS (SELECT 1 FROM matching blocked WHERE NOT blocked.writable)
            RETURNING a.id
        ) SELECT NOT EXISTS (SELECT 1 FROM matching WHERE NOT writable)",
            ("org",NpgsqlDbType.Integer,settings.OrganizationId),("lead",NpgsqlDbType.Integer,leadId),
            ("scope_branch",NpgsqlDbType.Integer,settings.BranchId),("sequence",NpgsqlDbType.Json,identity.GetRawText()),
            ("now",NpgsqlDbType.TimestampTz,now),("actor",NpgsqlDbType.Integer,actor));
        if (await cancel.ExecuteScalarAsync(cancellation) is not true)
            throw new InvalidOperationException("An active sequence task belongs to a different writable branch.");
        var ended=sequence.EnumerateObject().ToDictionary(item=>item.Name,item=>(object?)item.Value.Clone());
        ended["active"]=false;
        ended["stoppedAt"]=now;
        ended["stopReason"]=reason;
        details["sequence"]=ended;
    }
}
