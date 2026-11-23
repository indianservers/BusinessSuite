using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record DealCollaboratorData(DataTable Rows,List<DealCaptureChoice> Candidates,int Actor,bool CanAssign);

internal sealed partial class CrmDealRepository
{
    internal async Task<DealCollaboratorData> CollaboratorsAsync(int id,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        await RequireDealsAsync(db,tx,actor,false);
        var deal=await LockableDealAsync(db,tx,id,false,cancellation,requireOpen:false);
        var scoped=CollaboratorScope(deal);
        bool assign=await scoped.CanAssignCollaboratorsAsync(db,tx,actor);
        using var cmd=Query(db,tx,@"SELECT c.user_id,u.email,c.role,c.watching,c.xmin::text AS revision
            FROM public.crm_deal_collaborators c JOIN public.users u ON u.id=c.user_id
            WHERE c.organization_id=@org AND c.deal_id=@id ORDER BY u.email,c.id",("id",NpgsqlDbType.Integer,id));
        var rows=await ReadAsync(cmd,cancellation);
        var choices=await scoped.CollaboratorCandidatesAsync(db,tx,assign?null:actor.Id,false,cancellation);
        return new(rows,choices,actor.Id,assign);
    }

    internal async Task SaveCollaboratorAsync(int dealId,int user,string? role,bool watching,string? revision,CancellationToken cancellation)
    {
        if (user<=0 || role is not (null or "Collaborator" or "Secondary Owner" or "Lead Originator" or "Watcher"))
            throw new ArgumentException("Choose an eligible person and collaboration role.");
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireDealsAsync(db,tx,actor,false);
        var deal=await LockableDealAsync(db,tx,dealId,true,cancellation,requireOpen:false);
        var scoped=CollaboratorScope(deal);
        bool canAssign=await scoped.CanAssignCollaboratorsAsync(db,tx,actor);
        if (!canAssign && (actor.Id!=user || role is not (null or "Watcher")))
            throw new UnauthorizedAccessException("An assign grant is required to manage other collaborators or roles.");
        if (role is not null && (await scoped.CollaboratorCandidatesAsync(db,tx,user,true,cancellation)).Count!=1)
            throw new InvalidOperationException("Choose an active person with access to this Deal.");
        using var current=Query(db,tx,@"SELECT xmin::text FROM public.crm_deal_collaborators
            WHERE organization_id=@org AND deal_id=@deal AND user_id=@user FOR UPDATE",
            ("deal",NpgsqlDbType.Integer,dealId),("user",NpgsqlDbType.Integer,user));
        var actual=await current.ExecuteScalarAsync(cancellation) as string;
        if (!string.Equals(actual,revision,StringComparison.Ordinal) || (role is null && actual is null))
            throw new InvalidOperationException("The collaborator changed. Refresh the list and try again.");
        string sql=role is null ? @"DELETE FROM public.crm_deal_collaborators
                WHERE organization_id=@org AND deal_id=@deal AND user_id=@user RETURNING id" :
            @"INSERT INTO public.crm_deal_collaborators(organization_id,deal_id,user_id,role,watching,created_by_user_id)
                VALUES (@org,@deal,@user,@role,@watching,@actor)
                ON CONFLICT(deal_id,user_id) DO UPDATE SET role=excluded.role,watching=excluded.watching
                WHERE crm_deal_collaborators.organization_id=@org RETURNING id";
        using var save=Query(db,tx,sql,("deal",NpgsqlDbType.Integer,dealId),("user",NpgsqlDbType.Integer,user),
            ("role",NpgsqlDbType.Text,role),("watching",NpgsqlDbType.Boolean,watching),("actor",NpgsqlDbType.Integer,actor.Id));
        if (await save.ExecuteScalarAsync(cancellation) is not int collaborator)
            throw new InvalidOperationException("The collaborator is unavailable in this company.");
        string title=role is null?"Collaborator removed":role+" updated";
        string detail=role is null?$"User #{user}":$"User #{user}; notifications {(watching?"enabled":"disabled")}";
        using var history=Query(db,tx,@"INSERT INTO public.crm_timeline_events
            (organization_id,record_type,record_id,event_type,title,description,actor_user_id,occurred_at)
            VALUES (@org,'deal',@deal,'collaborator_change',@title,@detail,@actor,now())",
            ("deal",NpgsqlDbType.Integer,dealId),("title",NpgsqlDbType.Text,title),("detail",NpgsqlDbType.Text,detail),
            ("actor",NpgsqlDbType.Integer,actor.Id));
        await history.ExecuteNonQueryAsync(cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"crm_deal_collaborators",settings.OrganizationId,collaborator,actor.Id,
            role is null?"DELETE":actual is null?"CREATE":"UPDATE",cancellation,title);
        tx.Commit();
    }

    private CrmDealRepository CollaboratorScope(DataRow deal) => deal["owning_branch"] as int? == settings.BranchId
        ?this:new CrmDealRepository(settings.ForScope(settings.OrganizationId,deal["owning_branch"] as int?));

    private async Task<bool> CanAssignCollaboratorsAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor)
    {
        try
        {
            var grant=await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,settings.BranchId ?? 0,
                actor,"crm","assign","crm_view","crm_manage","crm_admin",DealPermission,ManageDeals);
            if (!grant.IsLegacy) return grant.Scope is "organization" or "branch";
            if (grant.LegacyRole is "admin" or "manager" or "super_admin") return true;
            await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,settings.BranchId ?? 0,actor,"crm","assign","crm_admin");
            return true;
        }
        catch (UnauthorizedAccessException) { return false; }
    }

    private async Task<List<DealCaptureChoice>> CollaboratorCandidatesAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        int? user,bool locked,CancellationToken cancellation)
    {
        var candidates=await LeadStore.LeadOwnerCandidatesAsync(db,tx,settings.OrganizationId,settings.BranchId ?? 0,user,locked,cancellation);
        var choices=new List<DealCaptureChoice>();
        foreach (var candidate in candidates)
        {
            try
            {
                await RequireDealsAsync(db,tx,candidate.Actor,false);
                choices.Add(new(candidate.Actor.Id,candidate.Name));
            }
            catch (UnauthorizedAccessException) { }
        }
        return choices;
    }
}
