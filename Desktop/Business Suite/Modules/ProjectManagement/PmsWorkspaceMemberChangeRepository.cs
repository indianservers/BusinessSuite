using System.Text.Json;
using Npgsql;

namespace Business_Suite;

internal sealed partial class PmsProjectRepository
{
    internal async Task ChangeWorkspaceMemberAsync(int workspace, int member, string revision, string? role,
        CancellationToken cancellation)
    {
        if (role is not (null or "Admin" or "Member" or "Guest"))
            throw new InvalidOperationException("Choose Admin, Member or Guest.");
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction();
        var actor = await GetWorkspaceActorAsync(connection, transaction, true, cancellation);
        var (initialRole, _) = await ReadWorkspaceRoleAsync(connection, transaction, actor, workspace, false, cancellation);
        RequireMemberRole(actor, initialRole, role ?? "Member");

        // Task writers lock the project before the workspace.
        using (var projects = new NpgsqlCommand(@"
            SELECT p.id FROM public.pms_projects p WHERE p.workspace_id=@workspace
              AND coalesce(p.organization_id,1)=@organization AND (@branch IS NULL OR EXISTS (
                SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='pms_projects'
                  AND o.resource_key=p.id::text AND o.company_id=@organization AND o.branch_id=@branch))
            ORDER BY p.id FOR UPDATE OF p", connection, transaction))
        {
            SetBranch(projects);
            projects.Parameters.AddWithValue("workspace", workspace);
            await projects.ExecuteNonQueryAsync(cancellation);
        }
        await ReadWorkspaceRoleAsync(connection, transaction, actor, workspace, true, cancellation);
        actor = await GetWorkspaceActorAsync(connection, transaction, true, cancellation);
        var (actorRole, _) = await ReadWorkspaceRoleAsync(connection, transaction, actor, workspace, false, cancellation);
        RequireMemberRole(actor, actorRole, role ?? "Member");

        int person;
        string previousRole;
        using (var current = new NpgsqlCommand(@"
            SELECT wm.user_id,wm.role FROM public.pms_workspace_members wm
            WHERE wm.workspace_id=@workspace AND wm.id=@member AND wm.xmin::text=@revision AND " + WorkspaceMemberScope
            + " FOR UPDATE OF wm", connection, transaction))
        {
            SetBranch(current);
            current.Parameters.AddWithValue("workspace", workspace);
            current.Parameters.AddWithValue("member", member);
            current.Parameters.AddWithValue("revision", revision);
            using var row = await current.ExecuteReaderAsync(cancellation);
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("The workspace member changed. Refresh before trying again.");
            person = row.GetInt32(0);
            previousRole = row.GetString(1);
        }
        if (previousRole == "Owner" || (previousRole == "Admin" && actorRole != "Owner"))
            throw new UnauthorizedAccessException("The workspace owner is protected. Only the owner can manage other administrators.");
        if (previousRole == role)
            return;

        if (role is null or "Guest")
            await DetachWorkspaceDutiesAsync(connection, transaction, workspace, person, role is null, cancellation);

        if (role is null)
        {
            using var remove = new NpgsqlCommand(@"
                DELETE FROM public.pms_workspace_members WHERE id=@member;
                DELETE FROM public.suite_branch_ownership
                WHERE resource_table='pms_workspace_members' AND resource_key=@member::text
                  AND company_id=@organization AND branch_id=@branch", connection, transaction);
            SetBranch(remove);
            remove.Parameters.AddWithValue("member", member);
            await remove.ExecuteNonQueryAsync(cancellation);
        }
        else
        {
            using var update = new NpgsqlCommand("UPDATE public.pms_workspace_members SET role=@role WHERE id=@member",
                connection, transaction);
            update.Parameters.AddWithValue("member", member);
            update.Parameters.AddWithValue("role", role);
            await update.ExecuteNonQueryAsync(cancellation);
        }

        using var audit = new NpgsqlCommand(@"
            INSERT INTO public.audit_logs(organization_id,user_id,actor_email,actor_authenticated,method,endpoint,
                module,entity_type,entity_id,action,description,old_values,new_values,workspace_id,status_code)
            SELECT @organization,u.id,left(u.email,100),true,@method,@url,'project_management','user',@person,
                @action,@description,@before,@after,@workspace,200
            FROM public.users u WHERE u.id=@actor RETURNING id", connection, transaction);
        SetBranch(audit);
        audit.Parameters.AddWithValue("workspace", workspace);
        audit.Parameters.AddWithValue("actor", actor.UserId);
        audit.Parameters.AddWithValue("person", person);
        audit.Parameters.AddWithValue("method", role is null ? "DELETE" : "PATCH");
        audit.Parameters.AddWithValue("url", $"desktop/project-management/workspaces/{workspace}/members/{member}");
        audit.Parameters.AddWithValue("action", role is null ? "PMS_REMOVE_WORKSPACE" : "PMS_WORKSPACE_ROLE");
        audit.Parameters.AddWithValue("description", role is null ? "Removed from workspace" : "Workspace role updated");
        audit.Parameters.AddWithValue("before", JsonSerializer.Serialize(new { role = previousRole }));
        audit.Parameters.AddWithValue("after", NpgsqlTypes.NpgsqlDbType.Text,
            role is null ? DBNull.Value : (object)JsonSerializer.Serialize(new { role }));
        var auditId = (int)(await audit.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(connection, transaction, "audit_logs", auditId, cancellation);
        await transaction.CommitAsync(cancellation);
    }

    private async Task DetachWorkspaceDutiesAsync(NpgsqlConnection connection, NpgsqlTransaction transaction,
        int workspace, int person, bool removeMembership, CancellationToken cancellation)
    {
        const string workspaceProjects = @"SELECT p.id FROM public.pms_projects p
            WHERE p.workspace_id=@workspace AND coalesce(p.organization_id,1)=@organization
              AND (@branch IS NULL OR EXISTS (SELECT 1 FROM public.suite_branch_ownership o
                  WHERE o.resource_table='pms_projects' AND o.resource_key=p.id::text
                    AND o.company_id=@organization AND o.branch_id=@branch))";
        using (var guard = new NpgsqlCommand(@"
            WITH projects AS (" + workspaceProjects + @")
            SELECT CASE WHEN EXISTS (
                SELECT 1 FROM public.pms_task_assignees a JOIN public.pms_tasks t ON t.id=a.task_id
                WHERE t.project_id IN (SELECT id FROM projects) AND a.user_id=@person AND a.source_key IS NOT NULL
            ) THEN 'Move batch-controlled assignments through Batch controls before changing membership.'
            WHEN EXISTS (
                SELECT 1 FROM public.pms_projects p WHERE p.id IN (SELECT id FROM projects)
                  AND p.deleted_at IS NULL AND (p.owner_user_id=@person OR p.manager_user_id=@person)
            ) OR EXISTS (
                SELECT 1 FROM public.pms_tasks t WHERE t.project_id IN (SELECT id FROM projects)
                  AND t.deleted_at IS NULL AND lower(coalesce(t.status,'')) NOT IN
                    ('done','completed','closed','resolved','cancelled','canceled','rejected','approved')
                  AND (t.assignee_user_id=@person OR EXISTS (
                      SELECT 1 FROM public.pms_task_assignees a WHERE a.task_id=t.id AND a.user_id=@person))
            ) OR EXISTS (
                SELECT 1 FROM public.pms_client_approvals a WHERE a.project_id IN (SELECT id FROM projects)
                  AND a.client_user_id=@person AND lower(coalesce(a.status,'')) NOT IN
                    ('done','completed','closed','resolved','cancelled','canceled','rejected','approved')
            ) THEN 'Transfer open tasks, project ownership and pending approvals before changing membership.' END",
            connection, transaction))
        {
            SetBranch(guard);
            guard.Parameters.AddWithValue("workspace", workspace);
            guard.Parameters.AddWithValue("person", person);
            if (await guard.ExecuteScalarAsync(cancellation) is string blocker)
                throw new InvalidOperationException(blocker);
        }

        using var cleanup = new NpgsqlCommand(@"
            WITH projects AS (" + workspaceProjects + @"), removed AS (
                DELETE FROM public.pms_task_assignees a
                USING public.pms_tasks t
                WHERE t.id=a.task_id AND t.project_id IN (SELECT id FROM projects)
                    AND a.user_id=@person AND a.source_key IS NULL
                RETURNING a.task_id,a.user_id
            ), adjusted AS (
                UPDATE public.pms_tasks t SET assignee_user_id=CASE WHEN t.assignee_user_id<>@person
                    THEN t.assignee_user_id ELSE (SELECT min(a.user_id) FROM public.pms_task_assignees a
                        WHERE a.task_id=t.id AND a.user_id<>@person) END, updated_at=clock_timestamp()
                WHERE t.project_id IN (SELECT id FROM projects) AND
                    (t.assignee_user_id=@person OR t.id IN (SELECT task_id FROM removed))
                RETURNING t.id
            )
            DELETE FROM public.suite_branch_ownership o USING removed r
            WHERE o.resource_table='pms_task_assignees' AND o.company_id=@organization AND o.branch_id=@branch
                AND o.resource_key=concat(length(r.task_id::text),':',r.task_id,':',length(r.user_id::text),':',r.user_id);

            WITH removed AS (
                DELETE FROM public.pms_workspace_team_members m USING public.pms_workspace_teams t
                WHERE t.id=m.team_id AND t.workspace_id=@workspace AND m.user_id=@person
                RETURNING m.team_id,m.user_id
            )
            DELETE FROM public.suite_branch_ownership o USING removed r
            WHERE o.resource_table='pms_workspace_team_members'
                AND o.resource_key=concat(length(r.team_id::text),':',r.team_id,':',length(r.user_id::text),':',r.user_id)
                AND o.company_id=@organization AND o.branch_id=@branch;

            UPDATE public.pms_workspace_teams t SET lead_user_id=CASE WHEN lead_user_id=@person THEN NULL ELSE lead_user_id END,
                member_ids_json=(SELECT coalesce(jsonb_agg(id ORDER BY position),'[]'::jsonb)::text
                    FROM jsonb_array_elements(t.member_ids_json::jsonb) WITH ORDINALITY AS listed(id,position)
                    WHERE id <> to_jsonb(@person))
            WHERE t.workspace_id=@workspace AND (lead_user_id=@person OR t.member_ids_json::jsonb @> jsonb_build_array(@person));

            WITH removed AS (
                DELETE FROM public.pms_project_members WHERE @remove AND user_id=@person
                    AND project_id IN (" + workspaceProjects + @") RETURNING id
            )
            DELETE FROM public.suite_branch_ownership o USING removed r
            WHERE o.resource_table='pms_project_members' AND o.resource_key=r.id::text
                AND o.company_id=@organization AND o.branch_id=@branch",
            connection, transaction);
        SetBranch(cleanup);
        cleanup.Parameters.AddWithValue("workspace", workspace);
        cleanup.Parameters.AddWithValue("person", person);
        cleanup.Parameters.AddWithValue("remove", removeMembership);
        await cleanup.ExecuteNonQueryAsync(cancellation);
    }
}

