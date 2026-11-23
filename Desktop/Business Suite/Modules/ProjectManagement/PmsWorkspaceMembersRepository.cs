using System.Data;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

internal sealed record PmsWorkspaceMembers(DataTable Records, bool CanAdd, bool CanAppointAdmin);

internal sealed partial class PmsProjectRepository
{
    private const string WorkspaceAccess = @"
        FROM public.pms_workspaces w
        LEFT JOIN public.pms_workspace_members wm ON wm.workspace_id=w.id AND wm.user_id=@actor AND " +
        WorkspaceMemberScope + @"
        WHERE " + VisibleWorkspace + @" AND w.id=@workspace AND
            (@admin OR wm.role IN ('Owner','Admin','Member','Guest'))";

    private const string EligibleMember = @"
        FROM public.users u
        LEFT JOIN public.common_people p ON p.user_id=u.id
        LEFT JOIN public.employees e ON e.user_id=u.id AND e.deleted_at IS NULL
        LEFT JOIN public.branches b ON b.id=e.branch_id
        WHERE u.is_active AND coalesce(p.status,'active')='active'
          AND coalesce(p.organization_id,b.company_id,1)=@organization
          AND NOT EXISTS (SELECT 1 FROM public.suite_access_memberships m
                          WHERE m.user_id=u.id AND m.company_id=@organization AND NOT m.active)
          AND (@branch IS NULL OR e.branch_id=@branch
               OR EXISTS (SELECT 1 FROM public.suite_branch_grants g
                          WHERE g.user_id=u.id AND g.company_id=@organization AND g.branch_id=@branch)
               OR EXISTS (SELECT 1 FROM public.suite_branch_policies bp
                          WHERE bp.user_id=u.id AND bp.company_id=@organization AND bp.all_branches)
               OR EXISTS (SELECT 1 FROM public.suite_access_memberships a
                          WHERE a.user_id=u.id AND a.company_id=@organization AND a.active AND a.is_admin))";

    internal async Task<PmsWorkspaceMembers> ReadWorkspaceMembersAsync(int workspace, CancellationToken cancellation)
    {
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await GetWorkspaceActorAsync(connection, transaction, false, cancellation);
        var (role, _) = await ReadWorkspaceRoleAsync(connection, transaction, actor, workspace, false, cancellation);
        using var members = new NpgsqlCommand(@"
            SELECT wm.id, wm.xmin::text AS revision,
                   coalesce(nullif(p.display_name,''), split_part(u.email,'@',1)) AS name, u.email,
                   wm.role, CASE WHEN u.is_active THEN 'Active' WHEN p.status='terminated'
                       OR last_action.action='ACCOUNT_TERMINATE' THEN 'Terminated' ELSE 'Suspended' END AS status
            FROM public.pms_workspace_members wm JOIN public.users u ON u.id=wm.user_id
            LEFT JOIN public.common_people p ON p.user_id=u.id
            LEFT JOIN LATERAL (SELECT a.action FROM public.audit_logs a
                WHERE a.entity_type='user' AND a.entity_id=u.id AND a.organization_id=@organization
                  AND a.action IN ('ACCOUNT_SUSPEND','ACCOUNT_TERMINATE','ACCOUNT_ACTIVATE')
                ORDER BY a.id DESC LIMIT 1) last_action ON true
            WHERE wm.workspace_id=@workspace AND " + WorkspaceMemberScope + @"
            ORDER BY CASE wm.role WHEN 'Owner' THEN 0 WHEN 'Admin' THEN 1 ELSE 2 END, lower(u.email)",
            connection, transaction);
        SetActor(members, actor);
        members.Parameters.AddWithValue("workspace", workspace);
        var records = await ReadTableAsync(members, cancellation);
        bool canAdd = actor.ModuleCanAssign && role is ("Owner" or "Admin");
        return new PmsWorkspaceMembers(records, canAdd, canAdd && role == "Owner");
    }

    internal async Task<DataTable> ReadEligibleWorkspaceMembersAsync(int workspace, string search, CancellationToken cancellation)
    {
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await GetWorkspaceActorAsync(connection, transaction, false, cancellation);
        var (role, _) = await ReadWorkspaceRoleAsync(connection, transaction, actor, workspace, false, cancellation);
        RequireMemberRole(actor, role, "Member");
        using var eligible = new NpgsqlCommand(@"
            SELECT u.id, coalesce(nullif(p.display_name,''),split_part(u.email,'@',1)) AS name, u.email " + EligibleMember + @"
             AND NOT EXISTS (SELECT 1 FROM public.pms_workspace_members already
                             WHERE already.workspace_id=@workspace AND already.user_id=u.id)
             AND (@search='' OR strpos(lower(u.email),lower(@search))>0
                  OR strpos(lower(p.display_name),lower(@search))>0)
            ORDER BY lower(u.email),u.id LIMIT 250", connection, transaction);
        SetActor(eligible, actor);
        eligible.Parameters.AddWithValue("workspace", workspace);
        eligible.Parameters.AddWithValue("search", search.Trim());
        return await ReadTableAsync(eligible, cancellation);
    }

    internal async Task AddWorkspaceMemberAsync(int workspace, int target, string role, CancellationToken cancellation)
    {
        if (role is not ("Admin" or "Member" or "Guest"))
            throw new InvalidOperationException("Choose Admin, Member or Guest.");
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction();
        var actor = await GetWorkspaceActorAsync(connection, transaction, true, cancellation);
        var (actorRole, _) = await ReadWorkspaceRoleAsync(connection, transaction, actor, workspace, true, cancellation);
        RequireMemberRole(actor, actorRole, role);
        actor = await GetWorkspaceActorAsync(connection, transaction, true, cancellation);
        var (updatedRole, workspaceName) = await ReadWorkspaceRoleAsync(connection, transaction, actor, workspace, false, cancellation);
        RequireMemberRole(actor, updatedRole, role);

        using var targetQuery = new NpgsqlCommand(
            "SELECT u.email " + EligibleMember + " AND u.id=@target FOR UPDATE OF u", connection, transaction);
        SetActor(targetQuery, actor);
        targetQuery.Parameters.AddWithValue("target", target);
        if (await targetQuery.ExecuteScalarAsync(cancellation) is not string email)
            throw new InvalidOperationException("Choose an active person in this company and branch.");

        using var insert = new NpgsqlCommand(@"
            INSERT INTO public.pms_workspace_members (workspace_id,user_id,role)
            VALUES(@workspace,@target,@role) ON CONFLICT (workspace_id,user_id) DO NOTHING RETURNING id",
            connection, transaction);
        insert.Parameters.AddWithValue("workspace", workspace);
        insert.Parameters.AddWithValue("target", target);
        insert.Parameters.AddWithValue("role", role);
        if (await insert.ExecuteScalarAsync(cancellation) is not int memberId)
            throw new InvalidOperationException("This person is already a workspace member.");
        await RecordOwnershipAsync(connection, transaction, "pms_workspace_members", memberId, cancellation);

        using var invite = new NpgsqlCommand(@"
            UPDATE public.pms_workspace_invitations i SET status='accepted'
            WHERE workspace_id=@workspace AND lower(email)=lower(@email) AND status='pending'
              AND (@branch IS NULL OR EXISTS(SELECT 1 FROM public.suite_branch_ownership o
                  WHERE o.resource_table='pms_workspace_invitations' AND o.resource_key=i.id::text
                    AND o.company_id=@organization AND o.branch_id=@branch))", connection, transaction);
        SetBranch(invite);
        invite.Parameters.AddWithValue("workspace", workspace);
        invite.Parameters.AddWithValue("email", email);
        await invite.ExecuteNonQueryAsync(cancellation);

        using var audit = new NpgsqlCommand(@"
            INSERT INTO public.audit_logs(organization_id,user_id,actor_email,actor_authenticated,method,endpoint,
                module,entity_type,entity_id,action,description,new_values,workspace_id,status_code)
            SELECT @organization,u.id,left(u.email,100),true,'POST',@url,'project_management','user',@target,
                'PMS_WORKSPACE_ADDED','Added existing person directly',@values,@workspace,200
            FROM public.users u WHERE u.id=@actor RETURNING id", connection, transaction);
        SetBranch(audit);
        audit.Parameters.AddWithValue("workspace", workspace);
        audit.Parameters.AddWithValue("actor", actor.UserId);
        audit.Parameters.AddWithValue("target", target);
        audit.Parameters.AddWithValue("url", $"desktop/project-management/workspaces/{workspace}/members");
        audit.Parameters.AddWithValue("values", JsonSerializer.Serialize(new { role }));
        var auditId = (int)(await audit.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(connection, transaction, "audit_logs", auditId, cancellation);

        using var notice = new NpgsqlCommand(@"
            INSERT INTO public.notifications(company_id,user_id,title,message,module,event_type,related_entity_type,
                related_entity_id,action_url,priority,channels,is_read)
            VALUES(@organization,@target,'Added to workspace',@message,'project_management','workspace.member_added',
                'workspace',@workspace,@url,'normal','[""in_app""]'::json,false) RETURNING id", connection, transaction);
        SetBranch(notice);
        notice.Parameters.AddWithValue("target", target);
        notice.Parameters.AddWithValue("workspace", workspace);
        notice.Parameters.AddWithValue("message", $"You were added to {workspaceName} as {role}.");
        notice.Parameters.AddWithValue("url", $"/pms/workspaces?workspace={workspace}");
        var notificationId = (int)(await notice.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(connection, transaction, "notifications", notificationId, cancellation);
        await transaction.CommitAsync(cancellation);
    }

    private async Task<(string Role, string Name)> ReadWorkspaceRoleAsync(NpgsqlConnection connection,
        NpgsqlTransaction transaction, PmsActor actor, int workspace, bool locked, CancellationToken cancellation)
    {
        using var query = new NpgsqlCommand("SELECT CASE WHEN @admin AND coalesce(wm.role,'') NOT IN ('Owner','Admin')"
            + " THEN 'Admin' ELSE wm.role END, w.name" + WorkspaceAccess
            + (locked ? " FOR UPDATE OF w" : ""), connection, transaction);
        SetActor(query, actor);
        query.Parameters.AddWithValue("workspace", workspace);
        using var row = await query.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            throw new UnauthorizedAccessException("This workspace is outside your current access.");
        return (row.GetString(0), row.GetString(1));
    }

    private async Task<PmsActor> GetWorkspaceActorAsync(NpgsqlConnection connection, NpgsqlTransaction transaction,
        bool write, CancellationToken cancellation)
    {
        var identity = write ? await settings.VerifyWriteTargetAsync(connection, transaction, cancellation)
            : await settings.RequireActorAsync(connection, transaction, cancellation);
        return await ResolveActorAsync(settings, identity, connection, transaction, cancellation);
    }

    private static void RequireMemberRole(PmsActor actor, string actorRole, string role)
    {
        if (!actor.ModuleCanAssign || actorRole is not ("Owner" or "Admin"))
            throw new UnauthorizedAccessException("Workspace owner or administrator access is required to add people.");
        if (role == "Admin" && actorRole != "Owner")
            throw new UnauthorizedAccessException("Only the workspace owner can appoint administrators.");
    }
}

