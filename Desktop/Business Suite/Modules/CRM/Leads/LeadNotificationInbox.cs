using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal static partial class LeadStore
{
    private const string LeadNotificationJoin=@"n.company_id=l.organization_id
        AND ((n.related_entity_type='lead' AND n.related_entity_id=l.id)
            OR (n.related_entity_id IS NULL AND n.action_url='/crm/leads?lead='||l.id::text))";

    private static readonly string LeadNotificationScope=@"n.company_id=@org AND n.user_id=@actor
        AND n.module='crm' AND n.event_type IN ('lead_workflow','lead_no_response','lead_proposal_due','lead_nurture_due',
            'lead_follow_up','lead_follow_up_due','lead_team_mention','lead_sla','lead_assignment')
        AND l.organization_id=@org AND l.deleted_at IS NULL
        AND COALESCE(s.data_json->>'archived','false')<>'true'
        AND (@visibility IN ('organization','branch') OR l.owner_user_id=@actor
            OR (@visibility='own' AND l.created_by_user_id=@actor))
        AND (@scope_branch IS NULL OR NOT EXISTS (
            SELECT 1 FROM public.suite_branch_ownership ownership
            WHERE ownership.company_id=@org AND ownership.resource_table='notifications'
              AND ownership.resource_key=n.id::text AND ownership.branch_id<>@scope_branch))
        AND "+CrmDirectoryWrites.BranchScope("crm_leads","l",includeShares:true);

    internal static async Task<DataTable> LeadNotificationInboxAsync(bool unread,CancellationToken cancellation)
    {
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        string scope=await LeadNotificationGrantAsync(db,tx,settings,actor);
        using var query=Cmd(db,tx,@"SELECT n.id,l.id AS lead_id,l.full_name AS lead_name,
                COALESCE(s.data_json->>'recordType','Lead')='Potential' AS potential,
                n.created_at AT TIME ZONE 'UTC' AS occurred,n.title,n.message,COALESCE(n.is_read,false) AS is_read,
                @history AS can_open_history
            FROM public.notifications n JOIN public.crm_leads l ON "+LeadNotificationJoin+@"
            LEFT JOIN public.crm_lead_operating_states s ON s.organization_id=l.organization_id AND s.lead_id=l.id
            WHERE "+LeadNotificationScope+@" AND (NOT @unread OR NOT COALESCE(n.is_read,false))
            ORDER BY n.created_at DESC NULLS LAST,n.id DESC LIMIT 100",
            ("org",NpgsqlDbType.Integer,settings.OrganizationId),("scope_branch",NpgsqlDbType.Integer,settings.BranchId),
            ("actor",NpgsqlDbType.Integer,actor.Id),("unread",NpgsqlDbType.Boolean,unread),("visibility",NpgsqlDbType.Text,scope),
            ("history",NpgsqlDbType.Boolean,(actor.IsSuperuser||actor.IsCompanyAdmin)&&scope is ("organization" or "branch")));
        using var rows=await query.ExecuteReaderAsync(cancellation);
        return await Table(rows,cancellation);
    }

    internal static async Task MarkLeadNotificationReadAsync(int notification,CancellationToken cancellation)
    {
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        string scope=await LeadNotificationGrantAsync(db,tx,settings,actor);
        using var query=Cmd(db,tx,@"UPDATE public.notifications n SET is_read=true,
                read_at=CASE WHEN COALESCE(n.is_read,false) THEN n.read_at ELSE now() END
            FROM public.crm_leads l LEFT JOIN public.crm_lead_operating_states s
                ON s.organization_id=l.organization_id AND s.lead_id=l.id
            WHERE n.id=@notification AND "+LeadNotificationJoin+" AND "+LeadNotificationScope+" RETURNING n.id",
            ("org",NpgsqlDbType.Integer,settings.OrganizationId),("scope_branch",NpgsqlDbType.Integer,settings.BranchId),
            ("actor",NpgsqlDbType.Integer,actor.Id),("notification",NpgsqlDbType.Integer,notification),
            ("visibility",NpgsqlDbType.Text,scope));
        if (await query.ExecuteScalarAsync(cancellation) is null)
            throw new InvalidOperationException("This Lead notification is unavailable in your inbox.");
        tx.Commit();
    }

    private static async Task<string> LeadNotificationGrantAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        DesktopDatabaseSettings settings,DesktopActor actor)
    {
        var grant=await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,settings.BranchId??0,actor,
            "crm","view","crm_view","crm_manage","crm_admin","crm_leads_view","crm_leads_manage");
        if (!actor.IsSuperuser && grant.IsLegacy && !actor.IsCompanyAdmin)
            return "own";
        if (grant.Scope is not ("organization" or "branch" or "own" or "assigned") ||
            (grant.Scope=="branch" && !settings.BranchId.HasValue))
            throw new UnauthorizedAccessException("Lead notifications require an accessible Lead scope.");
        return grant.Scope;
    }
}
