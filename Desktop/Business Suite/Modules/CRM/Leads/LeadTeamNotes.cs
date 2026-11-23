using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal static partial class LeadStore
{
    internal static async Task<List<CrmLookup>> TeamNoteRecipientsAsync(LeadKey key,CancellationToken cancellation) =>
        (await FollowUpOwnersAsync(key,null,cancellation,requireAssign:false)).Choices;

    internal static async Task AddTeamNoteAsync(LeadKey key,string body,int[] mentioned,CancellationToken cancellation)
    {
        body=body.Trim();
        if (body.Length is <1 or >4000 || body.StartsWith("<!--suite-richtext:v1-->",StringComparison.Ordinal))
            throw new ArgumentException("Write a plain-text team update of up to 4,000 characters.");
        if (mentioned.Length>20 || mentioned.Any(id=>id<=0))
            throw new ArgumentException("Choose up to 20 teammates to notify.");
        int[] recipients=mentioned.Distinct().ToArray();
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"leads","edit");
        var lead=await LockLead(db,tx,settings,key,false,cancellation);
        int org=settings.OrganizationId;
        int branch=await LeadOwnerBranchAsync(db,tx,settings,key.Id,lead,cancellation);
        foreach(int recipient in recipients.OrderBy(id=>id))
        {
            var candidates=await LeadOwnerCandidatesAsync(db,tx,org,branch,recipient,true,cancellation);
            if (candidates.Count!=1)
                throw new InvalidOperationException("Mention only teammates with access to this Lead.");
            await RequireCandidateLeadAccessAsync(db,tx,org,branch,candidates[0].Actor,lead,true);
        }
        using var author=Cmd(db,tx,@"SELECT COALESCE(NULLIF(p.display_name,''),u.email)
            FROM public.users u LEFT JOIN public.common_people p ON p.organization_id=@org AND p.user_id=u.id
            WHERE u.id=@actor",("org",NpgsqlDbType.Integer,org),("actor",NpgsqlDbType.Integer,actor.Id));
        string authorName=await author.ExecuteScalarAsync(cancellation) as string??"User "+actor.Id;
        string metadata=JsonSerializer.Serialize(new {mentionIds=recipients,authorName});
        await AddLeadHistoryAsync(db,tx,org,key.Id,branch,actor.Id,"team_note","Team update",body,metadata,cancellation);
        foreach(int recipient in recipients.Where(id=>id!=actor.Id))
            await NotifyLeadOwnerAsync(db,tx,org,branch,key.Id,lead,actor.Id,"lead_team_mention","You were mentioned on a lead",
                "Team update on "+Text(lead,"full_name"),cancellation,recipient);
        await WriteState(db,tx,org,key.Id,ReadDetails(lead),key.StateRevision,cancellation);
        using var update=Cmd(db,tx,@"UPDATE public.crm_leads SET updated_at=now(),updated_by_user_id=@actor
            WHERE organization_id=@org AND id=@lead",
            ("org",NpgsqlDbType.Integer,org),("lead",NpgsqlDbType.Integer,key.Id),("actor",NpgsqlDbType.Integer,actor.Id));
        await update.ExecuteNonQueryAsync(cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"crm_leads",org,key.Id,actor.Id,"UPDATE",cancellation,"Lead team update posted");
        tx.Commit();
    }
}
