using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadFollowUpDraft(int Id,string Revision,string Title,string Kind,DateTime? Due,int? Owner=null);
internal sealed record LeadFollowUpOwners(int Preferred,List<CrmLookup> Choices);

internal static partial class LeadStore
{
    internal static async Task<LeadFollowUpOwners> FollowUpOwnersAsync(LeadKey key,int? pendingOwner,CancellationToken cancellation,
        bool requireAssign=true)
    {
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(System.Data.IsolationLevel.RepeatableRead);
        var actor=await CrmDirectoryWrites.RequireCrmActorAsync(settings,db,tx,cancellation,"leads","edit");
        var lead=await LockLead(db,tx,settings,key,false,cancellation,lockRecord:false);
        int org=settings.OrganizationId;
        int branch=await LeadOwnerBranchAsync(db,tx,settings,key.Id,lead,cancellation);
        bool canAssign=true;
        try { if (requireAssign) await RequireLeadAssignGrantAsync(db,tx,org,branch,actor); }
        catch(UnauthorizedAccessException) { canAssign=false; }
        var choices=new List<CrmLookup>();
        var candidates=await LeadOwnerCandidatesAsync(db,tx,org,branch,canAssign?null:actor.Id,false,cancellation);
        foreach (var candidate in candidates)
        {
            cancellation.ThrowIfCancellationRequested();
            try
            {
                await RequireCandidateLeadAccessAsync(db,tx,org,branch,candidate.Actor,lead,true);
                choices.Add(new(candidate.Actor.Id,candidate.Name));
            }
            catch(UnauthorizedAccessException) { }
        }
        int preferred=canAssign?pendingOwner ?? lead["owner_user_id"] as int? ?? actor.Id:actor.Id;
        return new(preferred,choices);
    }

    internal static async Task<int> ScheduleLeadFollowUpAsync(LeadKey key,string kind,string title,DateTime due,
        CancellationToken cancellation,LeadFollowUpDraft? existing=null,string? reason=null,int? selectedOwner=null)
    {
        title=title.Trim();
        if (kind is not ("call" or "email" or "meeting" or "task") || title.Length is <1 or >180)
            throw new ArgumentException("Choose a follow-up type and enter a title of up to 180 characters.");
        if (due.Kind!=DateTimeKind.Utc || due<=DateTime.UtcNow)
            throw new ArgumentException("Choose a future follow-up time in UTC.");
        reason=reason?.Trim();
        if (existing is not null && (reason is null || reason.Length is <3 or >1000))
            throw new ArgumentException("Explain why this follow-up is being rescheduled in 3 to 1,000 characters.");
        if (key.Potential)
            throw new InvalidOperationException("Choose an active Lead.");
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"leads","edit");
        var lead=await LockLead(db,tx,settings,key,false,cancellation);
        if (lead["is_converted"] is true || lead["status"] is "Lost" or "Converted")
            throw new InvalidOperationException("Reopen the Lead before scheduling follow-ups.");
        int owner=selectedOwner ?? lead["owner_user_id"] as int? ?? actor.Id;
        int org=settings.OrganizationId;
        int branch=await RequireLeadOwnerAsync(db,tx,settings,key.Id,lead,actor,owner,cancellation,requireLeadVisibility:true);
        using var time=Cmd(db,tx,"SELECT @due>clock_timestamp()",("due",NpgsqlDbType.TimestampTz,due));
        if (await time.ExecuteScalarAsync(cancellation) is not true)
            throw new ArgumentException("Choose a future follow-up time in UTC.");
        int task;
        DateTime? previous=null;
        if (existing is null)
            task=await AddLeadPendingTaskAsync(db,tx,settings.ForScope(org,branch),key.Id,lead,actor.Id,title,
                "{\"manualFollowUp\":true}",due,cancellation,kind,owner);
        else
        {
            task=existing.Id;
            previous=await RescheduleLeadFollowUpAsync(db,tx,org,branch,key.Id,owner,actor.Id,existing,kind,title,due,
                reason!,cancellation);
        }
        var details=ReadDetails(lead);
        await WriteState(db,tx,org,key.Id,details,key.StateRevision,cancellation);
        using var stamp=Cmd(db,tx,@"UPDATE public.crm_leads SET updated_at=now(),updated_by_user_id=@actor,
            next_follow_up_at=(SELECT min(a.due_date) FROM public.crm_activities a WHERE a.organization_id=@org
                AND a.lead_id=@lead AND a.status='Pending' AND a.deleted_at IS NULL AND "+LeadActivityScope(true)+@")
            WHERE organization_id=@org AND id=@lead",
            ("org",NpgsqlDbType.Integer,org),("lead",NpgsqlDbType.Integer,key.Id),("actor",NpgsqlDbType.Integer,actor.Id),
            ("scope_branch",NpgsqlDbType.Integer,branch));
        await stamp.ExecuteNonQueryAsync(cancellation);
        string action=existing is null?"Follow-up scheduled":"Follow-up rescheduled";
        await AddLeadHistoryAsync(db,tx,org,key.Id,branch,actor.Id,"follow_up_scheduled",action,title,
            JsonSerializer.Serialize(new {activityId=task,ownerId=owner,dueAt=due,previousCommitment=previous,reason}),cancellation);
        if (owner!=actor.Id)
            await NotifyLeadOwnerAsync(db,tx,org,branch,key.Id,lead,actor.Id,"lead_follow_up","Lead follow-up assigned",
                Text(lead,"full_name")+": "+title,cancellation,owner);
        tx.Commit();
        return task;
    }

    private static async Task<DateTime?> RescheduleLeadFollowUpAsync(NpgsqlConnection db,NpgsqlTransaction tx,int org,int branch,
        int lead,int owner,int actor,LeadFollowUpDraft expected,string kind,string title,DateTime due,string reason,
        CancellationToken cancellation)
    {
        using var current=Cmd(db,tx,@"SELECT a.due_date FROM public.crm_activities a
            WHERE a.organization_id=@org AND a.lead_id=@lead AND a.id=@id AND a.deleted_at IS NULL
              AND a.status='Pending' AND a.xmin::text=@revision AND "+LeadActivityScope(false)+" FOR UPDATE OF a",
            ("org",NpgsqlDbType.Integer,org),("lead",NpgsqlDbType.Integer,lead),("id",NpgsqlDbType.Integer,expected.Id),
            ("revision",NpgsqlDbType.Text,expected.Revision),("scope_branch",NpgsqlDbType.Integer,branch));
        var found=await current.ExecuteScalarAsync(cancellation);
        if (found is null)
            throw new InvalidOperationException("This follow-up changed, is outside your branch, or is no longer pending.");
        DateTime? previous=found as DateTime?;
        string commitment=JsonSerializer.Serialize(new[] { new {previous,@new=due,reason,actor} });
        using var update=Cmd(db,tx,@"UPDATE public.crm_activities a SET subject=@title,title=@title,due_date=@due,
            activity_date=@due,activity_type=@kind,owner_user_id=@owner,updated_at=now(),updated_by_user_id=@actor,
            metadata_json=((COALESCE(a.metadata_json::jsonb,'{}'::jsonb)-'followUpReminderAt')||
                jsonb_build_object('commitmentHistory',
                    COALESCE(a.metadata_json::jsonb->'commitmentHistory','[]'::jsonb)||@commitment::jsonb))::json
            WHERE a.organization_id=@org AND a.lead_id=@lead AND a.id=@id",
            ("org",NpgsqlDbType.Integer,org),("lead",NpgsqlDbType.Integer,lead),("id",NpgsqlDbType.Integer,expected.Id),
            ("owner",NpgsqlDbType.Integer,owner),("actor",NpgsqlDbType.Integer,actor),("title",NpgsqlDbType.Text,title),
            ("kind",NpgsqlDbType.Text,kind),("due",NpgsqlDbType.TimestampTz,due),("commitment",NpgsqlDbType.Json,commitment));
        await update.ExecuteNonQueryAsync(cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"crm_activities",org,expected.Id,actor,"UPDATE",cancellation,"Lead follow-up rescheduled");
        return previous;
    }
}
