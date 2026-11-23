using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadSelfAssignment(List<LeadSalesChoice> People,int? CurrentOwner);

internal static partial class LeadStore
{
    internal static async Task<LeadSelfAssignment> ReadLeadAssignmentAsync(LeadKey key,CancellationToken cancellation)
    {
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        var lead=await LockAssignmentLeadAsync(db,tx,settings,key,actor,cancellation,lockRecord:false);
        int branch=await LeadOwnerBranchAsync(db,tx,settings,key.Id,lead,cancellation);
        await RequireLeadAssignGrantAsync(db,tx,settings.OrganizationId,branch,actor);
        var eligible=new List<LeadSalesChoice>();
        foreach (var candidate in await LeadOwnerCandidatesAsync(db,tx,settings.OrganizationId,branch,null,false,cancellation))
            if (await CanReceiveRoutedLeadAsync(db,tx,settings.OrganizationId,branch,candidate.Actor))
                eligible.Add(new(candidate.Actor.Id,candidate.Name));
        return new(eligible,lead["owner_user_id"] as int?);
    }

    internal static async Task<List<LeadSalesChoice>> ReadLeadCaptureOwnersAsync(int selectedBranch,CancellationToken cancellation)
    {
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"leads","create");
        int branch=await CrmDirectoryWrites.CreationBranch(db,tx,settings,selectedBranch,cancellation);
        int org=settings.OrganizationId;
        int? actorOnly=null;
        try { await RequireLeadAssignGrantAsync(db,tx,org,branch,actor); }
        catch(UnauthorizedAccessException) { actorOnly=actor.Id; }
        var choices=new List<LeadSalesChoice>();
        foreach (var candidate in await LeadOwnerCandidatesAsync(db,tx,org,branch,actorOnly,false,cancellation))
            if (await CanReceiveRoutedLeadAsync(db,tx,org,branch,candidate.Actor))
                choices.Add(new(candidate.Actor.Id,candidate.Name));
        return choices;
    }

    private static async Task<string> ValidateLeadCaptureOwnerAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        DesktopDatabaseSettings settings,DesktopActor actor,int branch,int owner,CancellationToken cancellation)
    {
        int org=settings.OrganizationId;
        if (owner!=actor.Id)
            await RequireLeadAssignGrantAsync(db,tx,org,branch,actor);
        var candidates=await LeadOwnerCandidatesAsync(db,tx,org,branch,owner,true,cancellation);
        if (candidates.Count!=1 || !await CanReceiveRoutedLeadAsync(db,tx,org,branch,candidates[0].Actor))
            throw new InvalidOperationException("Choose an active owner with Lead access in this branch.");
        return candidates[0].Name;
    }

    internal static async Task AssignLeadAsync(LeadKey key,int? owner,string reason,CancellationToken cancellation)
    {
        reason=reason.Trim();
        if (owner<=0 || reason.Length>1000)
            throw new ArgumentException("Choose an eligible owner and use up to 1,000 characters for the reason.");
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        var lead=await LockAssignmentLeadAsync(db,tx,settings,key,actor,cancellation);
        int org=settings.OrganizationId;
        int branch=await LeadOwnerBranchAsync(db,tx,settings,key.Id,lead,cancellation);
        await RequireLeadAssignGrantAsync(db,tx,org,branch,actor);
        int? previous=lead["owner_user_id"] as int?;
        if (owner==previous) return;
        string label="Unassigned";
        if (owner is int assignee)
        {
            var candidates=await LeadOwnerCandidatesAsync(db,tx,org,branch,assignee,true,cancellation);
            if (candidates.Count!=1 || !await CanReceiveRoutedLeadAsync(db,tx,org,branch,candidates[0].Actor))
                throw new InvalidOperationException("Choose an active owner with Lead access in this branch.");
            label=candidates[0].Name;
        }
        foreach (string table in new[]{"crm_activities","crm_tasks"})
        {
            string filter="r.organization_id=@org AND r.lead_id=@lead "+(table=="crm_tasks"?"AND r.deleted_at IS NULL ":"")+
                "AND r.owner_user_id IS NOT DISTINCT FROM @previous AND r.status IN ('Pending','To Do','Open')";
            using var pending=Cmd(db,tx,$@"SELECT r.id,("+CrmDirectoryWrites.BranchScope(table,"r")+$@") AS writable
                FROM public.{table} r WHERE {filter} ORDER BY r.id FOR UPDATE OF r",
                ("org",NpgsqlDbType.Integer,org),("lead",NpgsqlDbType.Integer,key.Id),("previous",NpgsqlDbType.Integer,previous),
                ("scope_branch",NpgsqlDbType.Integer,branch));
            var rows=await pending.ExecuteReaderAsync(cancellation);
            var ids=new List<int>();
            using(rows)
                while (await rows.ReadAsync(cancellation))
                {
                    if (rows.IsDBNull(1) || !rows.GetBoolean(1))
                        throw new InvalidOperationException("Pending Lead work belongs to another branch. The assignment was cancelled.");
                    ids.Add(rows.GetInt32(0));
                }
            if (ids.Count==0) continue;
            using var transfer=Cmd(db,tx,$@"UPDATE public.{table} SET owner_user_id=@owner,updated_at=now(),updated_by_user_id=@actor
                WHERE organization_id=@org AND id=ANY(@ids)",
                ("org",NpgsqlDbType.Integer,org),("owner",NpgsqlDbType.Integer,owner),("actor",NpgsqlDbType.Integer,actor.Id),
                ("ids",NpgsqlDbType.Array|NpgsqlDbType.Integer,ids.ToArray()));
            await transfer.ExecuteNonQueryAsync(cancellation);
        }
        using var update=Cmd(db,tx,@"UPDATE public.crm_leads SET owner_user_id=@owner,updated_at=now(),updated_by_user_id=@actor
            WHERE organization_id=@org AND id=@id",
            ("org",NpgsqlDbType.Integer,org),("id",NpgsqlDbType.Integer,key.Id),("owner",NpgsqlDbType.Integer,owner),
            ("actor",NpgsqlDbType.Integer,actor.Id));
        await update.ExecuteNonQueryAsync(cancellation);
        var details=ReadDetails(lead);
        details["assignmentReason"]=reason;
        await WriteState(db,tx,org,key.Id,details,key.StateRevision,cancellation);
        string metadata=JsonSerializer.Serialize(new {reason=reason.Length==0?"Manual assignment":reason,previousOwnerId=previous,ownerId=owner});
        await AddLeadHistoryAsync(db,tx,org,key.Id,branch,actor.Id,"assignment",owner.HasValue?$"Assigned to {label}":"Unassigned",
            reason,metadata,cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"crm_leads",org,key.Id,actor.Id,"ASSIGNMENT_CHANGE",cancellation,
            $"Lead owner changed from {previous?.ToString()??"unassigned"} to {owner?.ToString()??"unassigned"}");
        if (owner.HasValue && owner!=actor.Id)
            await NotifyLeadOwnerAsync(db,tx,org,branch,key.Id,lead,actor.Id,"lead_assignment","Lead assigned to you",
                $"{Text(lead,"full_name")} has been assigned to you.",cancellation,owner);
        tx.Commit();
    }

    private static async Task<DataRow> LockAssignmentLeadAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopDatabaseSettings settings,
        LeadKey key,DesktopActor actor,CancellationToken cancellation,bool lockRecord=true)
    {
        if (key.Potential) throw new InvalidOperationException("Choose an active Lead.");
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"leads","view");
        return await LockLead(db,tx,settings,key,false,cancellation,lockRecord);
    }
}
