using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal static partial class LeadStore
{
    private sealed record LeadRuleAction(string Name,string Action,string Title,int DelayHours,int? Owner);

    private static async Task ApplyLeadWorkflowsAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        DesktopDatabaseSettings settings,int leadId,DataRow lead,DesktopActor actor,string trigger,DateTime now,
        CancellationToken cancellation)
    {
        using var config=Cmd(db,tx,@"SELECT settings_json->'workflows' FROM public.crm_lead_management_config
            WHERE organization_id=@org FOR SHARE",("org",NpgsqlDbType.Integer,settings.OrganizationId));
        if (await config.ExecuteScalarAsync(cancellation) is not string json)
            return;
        using var document=JsonDocument.Parse(json);
        if (document.RootElement.ValueKind==JsonValueKind.Null)
            return;
        if (document.RootElement.ValueKind!=JsonValueKind.Array)
            throw new InvalidOperationException("The configured Lead workflows could not be read.");
        var rules=new List<LeadRuleAction>();
        string currentStage=Text(lead,"status");
        foreach (var rule in document.RootElement.EnumerateArray())
        {
            if (rule.ValueKind!=JsonValueKind.Object)
                throw new InvalidOperationException("A configured Lead workflow could not be read.");
            string stage=WorkflowText(rule,"stage");
            if (WorkflowText(rule,"trigger")!=trigger || (stage.Length>0 && stage!=currentStage) ||
                (rule.TryGetProperty("enabled",out var enabled) && enabled.ValueKind==JsonValueKind.False))
                continue;
            string name=WorkflowText(rule,"name");
            string action=WorkflowText(rule,"action");
            string title=WorkflowText(rule,"title");
            if (action is not ("task" or "notify" or "assign"))
                throw new InvalidOperationException("This Lead has an unsupported workflow action.");
            int delay=0;
            if (name.Length is <1 or >120 || title.Length is <1 or >180 ||
                (rule.TryGetProperty("delayHours",out var hours) &&
                    (hours.ValueKind!=JsonValueKind.Number || !hours.TryGetInt32(out delay) || delay is <0 or >8760)))
                throw new InvalidOperationException("An enabled Lead workflow has invalid settings.");
            int? owner=null;
            if (action=="assign")
            {
                if (!rule.TryGetProperty("ownerId",out var value) || value.ValueKind!=JsonValueKind.Number ||
                    !value.TryGetInt32(out int id) || id<=0)
                    throw new InvalidOperationException("The Lead reassignment rule needs a valid owner.");
                owner=id;
            }
            rules.Add(new(name,action,title,delay,owner));
        }

        int org=settings.OrganizationId;
        int? branch=settings.BranchId??lead["branch_id"] as int?;
        foreach (var rule in rules)
        {
            if (rule.Action=="task")
                await AddLeadPendingTaskAsync(db,tx,settings,leadId,lead,actor.Id,rule.Title,
                    JsonSerializer.Serialize(new {workflow=rule.Name}),now.AddHours(rule.DelayHours),cancellation);
            else if (rule.Action=="notify")
                await NotifyLeadOwnerAsync(db,tx,org,branch,leadId,lead,actor.Id,"lead_workflow",rule.Title,
                    rule.Name+": "+Text(lead,"full_name"),cancellation);
            else if (rule.Owner is int newOwner)
                await AssignLeadWorkflowOwnerAsync(db,tx,settings,leadId,lead,actor,newOwner,cancellation);
            await AddLeadHistoryAsync(db,tx,org,leadId,branch,actor.Id,"automation",rule.Name,null,
                JsonSerializer.Serialize(new {action=rule.Action,trigger,ownerId=rule.Owner}),cancellation);
        }
    }

    private static string WorkflowText(JsonElement rule,string property) =>
        rule.TryGetProperty(property,out var value)&&value.ValueKind==JsonValueKind.String?value.GetString()??"":"";

    private static async Task AssignLeadWorkflowOwnerAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        DesktopDatabaseSettings settings,int leadId,DataRow lead,DesktopActor actor,int owner,CancellationToken cancellation)
    {
        await RequireLeadOwnerAsync(db,tx,settings,leadId,lead,actor,owner,cancellation);
        int? previous=lead["owner_user_id"] as int?;
        if (previous==owner)
            return;
        using var update=Cmd(db,tx,@"UPDATE public.crm_leads SET owner_user_id=@owner
            WHERE organization_id=@org AND id=@lead",
            ("org",NpgsqlDbType.Integer,settings.OrganizationId),("lead",NpgsqlDbType.Integer,leadId),("owner",NpgsqlDbType.Integer,owner));
        await update.ExecuteNonQueryAsync(cancellation);
        lead["owner_user_id"]=owner;
        await CrmDirectoryWrites.Audit(db,tx,"crm_leads",settings.OrganizationId,leadId,actor.Id,"UPDATE",cancellation,
            $"Configured Lead workflow owner changed from {previous?.ToString()??"unassigned"} to {owner}");
    }

    private static async Task<int> RequireLeadOwnerAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        DesktopDatabaseSettings settings,int leadId,DataRow lead,DesktopActor actor,int owner,CancellationToken cancellation,
        bool requireLeadVisibility=false)
    {
        int org=settings.OrganizationId;
        int branch=await LeadOwnerBranchAsync(db,tx,settings,leadId,lead,cancellation);
        if (owner!=actor.Id)
            await RequireLeadAssignGrantAsync(db,tx,org,branch,actor);
        var candidates=await LeadOwnerCandidatesAsync(db,tx,org,branch,owner,true,cancellation);
        if (candidates.Count!=1)
            throw new InvalidOperationException("The configured Lead owner is not an active assignee in this company and branch.");
        await RequireCandidateLeadAccessAsync(db,tx,org,branch,candidates[0].Actor,lead,requireLeadVisibility);
        return branch;
    }

    private static async Task<int> LeadOwnerBranchAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        DesktopDatabaseSettings settings,int leadId,DataRow lead,CancellationToken cancellation)
    {
        using var scope=Cmd(db,tx,@"SELECT COALESCE(@configured,
              (SELECT branch_id FROM public.suite_branch_ownership WHERE company_id=@org
                 AND resource_table='crm_leads' AND resource_key=@lead::text),@fallback)",
            ("configured",NpgsqlDbType.Integer,settings.BranchId),("org",NpgsqlDbType.Integer,settings.OrganizationId),
            ("lead",NpgsqlDbType.Integer,leadId),("fallback",NpgsqlDbType.Integer,lead["branch_id"] as int?));
        if (await scope.ExecuteScalarAsync(cancellation) is not int branch)
            throw new InvalidOperationException("The Lead needs a branch before assigning its work.");
        return branch;
    }

    private static async Task RequireLeadAssignGrantAsync(NpgsqlConnection db,NpgsqlTransaction tx,int org,int branch,DesktopActor actor)
    {
        var grant=await DesktopModuleAccess.RequireAsync(db,tx,org,branch,actor,"crm","assign",
            "crm_manage","crm_admin","crm_leads_manage");
        if (grant.Scope is not ("organization" or "branch"))
            throw new UnauthorizedAccessException("Assigning Lead work requires branch or organization assignment permission.");
        if (!actor.IsSuperuser && grant.IsLegacy && grant.LegacyRole is not ("admin" or "manager" or "super_admin"))
            await DesktopModuleAccess.RequireAsync(db,tx,org,branch,actor,"crm","assign","crm_admin");
    }

    internal static async Task<List<(DesktopActor Actor,string Name)>> LeadOwnerCandidatesAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        int org,int branch,int? owner,bool lockAccount,CancellationToken cancellation)
    {
        using var candidate=Cmd(db,tx,@"SELECT u.id,COALESCE(u.is_superuser,false),COALESCE(m.active AND m.is_admin,false),
                COALESCE(NULLIF(person.display_name,''),u.email) AS name
            FROM public.users u
            LEFT JOIN public.common_people person ON person.user_id=u.id
            LEFT JOIN public.suite_access_memberships m ON m.user_id=u.id AND m.company_id=@org
            LEFT JOIN public.suite_branch_policies p ON p.user_id=u.id AND p.company_id=@org
            LEFT JOIN LATERAL (SELECT e.id,e.branch_id,e.status,e.deleted_at FROM public.employees e
                WHERE e.user_id=u.id ORDER BY e.id LIMIT 1) employee ON true
            LEFT JOIN public.branches home ON home.id=employee.branch_id
            WHERE (@owner IS NULL OR u.id=@owner) AND u.is_active
              AND COALESCE(person.organization_id,home.company_id,CASE WHEN m.active THEN @org ELSE 1 END)=@org
              AND (m.id IS NULL OR m.active)
              AND lower(COALESCE(person.status,'active'))='active'
              AND (employee.id IS NULL OR (employee.deleted_at IS NULL AND lower(employee.status) IN ('active','probation')
                  AND (home.id IS NULL OR home.company_id=@org)))
              AND (u.is_superuser OR (m.active AND m.is_admin) OR p.all_branches
                  OR EXISTS (SELECT 1 FROM public.suite_branch_grants b WHERE b.company_id=@org AND b.user_id=u.id
                      AND b.branch_id=@branch)
                  OR (COALESCE(p.use_home_branch,true) AND employee.branch_id=@branch))
            ORDER BY name,u.id"+(lockAccount?" FOR SHARE OF u":""),
            ("org",NpgsqlDbType.Integer,org),("branch",NpgsqlDbType.Integer,branch),("owner",NpgsqlDbType.Integer,owner));
        var values=new List<(DesktopActor,string)>();
        using var row=await candidate.ExecuteReaderAsync(cancellation);
        while (await row.ReadAsync(cancellation))
            values.Add((new(row.GetInt32(0),row.GetBoolean(1),row.GetBoolean(2),false),row.GetString(3)));
        return values;
    }

    private static async Task RequireCandidateLeadAccessAsync(NpgsqlConnection db,NpgsqlTransaction tx,int org,int branch,
        DesktopActor assignee,DataRow lead,bool requireVisibility)
    {
        var grant=await DesktopModuleAccess.RequireAsync(db,tx,org,branch,assignee,"crm","view",
            "crm_view","crm_manage","crm_admin","crm_leads_view","crm_leads_manage");
        if (!requireVisibility)
            return;
        string scope=grant.IsLegacy&&!assignee.IsCompanyAdmin?"own":grant.Scope;
        if (!(scope is ("organization" or "branch") ||
            (scope is ("own" or "assigned") && (lead["owner_user_id"] as int?)==assignee.Id) ||
            (scope=="own" && (lead["created_by_user_id"] as int?)==assignee.Id)))
            throw new UnauthorizedAccessException("The selected teammate cannot view this Lead.");
    }

    private static async Task NotifyLeadOwnerAsync(NpgsqlConnection db,NpgsqlTransaction tx,int org,int? branch,
        int leadId,DataRow lead,int actor,string eventType,string title,string message,CancellationToken cancellation,
        int? ownerOverride=null,string priority="normal")
    {
        using var query=Cmd(db,tx,@"INSERT INTO public.notifications (company_id,user_id,title,message,module,event_type,
                related_entity_type,related_entity_id,action_url,priority,channels,is_read)
            SELECT @org,u.id,@title,@message,'crm',@event,'lead',@lead,@url,@priority,'[""in_app""]'::json,false
            FROM public.users u WHERE u.id=@owner AND u.is_active AND (u.id=@actor OR
                EXISTS (SELECT 1 FROM public.suite_access_memberships membership WHERE membership.company_id=@org
                    AND membership.user_id=u.id AND membership.active) OR
                EXISTS (SELECT 1 FROM public.common_people p WHERE p.organization_id=@org AND p.user_id=u.id) OR
                EXISTS (SELECT 1 FROM public.employees e JOIN public.branches b ON b.id=e.branch_id AND b.company_id=@org
                    WHERE e.user_id=u.id AND e.deleted_at IS NULL AND lower(e.status) IN ('active','probation')))
            RETURNING id",
            ("org",NpgsqlDbType.Integer,org),("owner",NpgsqlDbType.Integer,ownerOverride ?? lead["owner_user_id"] as int? ?? actor),
            ("actor",NpgsqlDbType.Integer,actor),("lead",NpgsqlDbType.Integer,leadId),("title",NpgsqlDbType.Text,title),
            ("event",NpgsqlDbType.Text,eventType),("message",NpgsqlDbType.Text,message),
            ("priority",NpgsqlDbType.Text,priority),
            ("url",NpgsqlDbType.Text,$"/crm/leads?lead={leadId}"));
        if (await query.ExecuteScalarAsync(cancellation) is not int notification)
            throw new InvalidOperationException("The action could not notify an active Lead owner in this company.");
        if (branch.HasValue)
            await AddOwnership(db,tx,org,"notifications",notification,branch.Value,cancellation);
    }
}
