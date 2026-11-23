using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PmsActor(int UserId, bool OrganizationAdmin, bool CanViewOrganizationProjects,
    bool CanManageOrganizationProjects, bool CanManageOrganizationTasks,
    bool ModuleCanCreate, bool ModuleCanEdit, bool ModuleCanDelete, bool ModuleCanExport, bool ModuleCanAssign, bool IsPmsAdmin,
    bool ModuleCanApprove, bool CanApproveOrganizationProjects,
    int? DepartmentId, int? EmployeeBranchId, string PersonScope);

internal sealed record PmsWorkspaceChoice(int Id, string Name, bool CanManage, string Role,
    long MemberCount, long ProjectCount, long TaskCount, long CompletedTaskCount, DateTime? CreatedAt);

internal enum PmsProjectScope { Active, Archived, Trash }
internal enum PmsProjectAction { Archive, Unarchive, Trash, Restore }

internal sealed record PmsProjectDraft(int WorkspaceId, string ProjectKey, string Name, string Description,
    string Status, string Priority, DateTime? StartDate, DateTime? DueDate, decimal? Budget);

internal sealed partial class PmsProjectRepository
{
    private const string VisibleWorkspace = @"
        coalesce(w.organization_id, 1) = @organization
        AND (@branch IS NULL OR EXISTS (SELECT 1 FROM public.suite_branch_ownership b
             WHERE b.resource_table = 'pms_workspaces' AND b.resource_key = w.id::text
               AND b.company_id = @organization AND b.branch_id = @branch))
        AND NOT EXISTS (SELECT 1 FROM public.pms_workspace_archives a
                        WHERE a.workspace_id = w.id AND a.deleted_at IS NOT NULL)";

    private const string WorkspaceMemberScope = @"
        (@branch IS NULL OR EXISTS (SELECT 1 FROM public.suite_branch_ownership o
            WHERE o.resource_table = 'pms_workspace_members' AND o.resource_key = wm.id::text
              AND o.company_id = @organization AND o.branch_id = @branch))";

    private const string ProjectJoins = @"
        FROM public.pms_projects p
        LEFT JOIN public.pms_workspaces w ON w.id = p.workspace_id AND (" + VisibleWorkspace + @")
        LEFT JOIN public.pms_workspace_members wm ON wm.workspace_id = w.id AND wm.user_id = @actor
             AND " + WorkspaceMemberScope + @"
        LEFT JOIN public.pms_project_members pm ON pm.project_id = p.id AND pm.user_id = @actor
             AND (@branch IS NULL OR EXISTS (SELECT 1 FROM public.suite_branch_ownership o
                 WHERE o.resource_table = 'pms_project_members' AND o.resource_key = pm.id::text
                   AND o.company_id = @organization AND o.branch_id = @branch))";

    private const string ProjectAccess = @"
        coalesce(p.organization_id, 1) = @organization
        AND (@branch IS NULL OR (
             (p.branch_id IS NULL OR p.branch_id = @branch)
             AND EXISTS (SELECT 1 FROM public.suite_branch_ownership b
                 WHERE b.resource_table = 'pms_projects' AND b.resource_key = p.id::text
                   AND b.company_id = @organization AND b.branch_id = @branch)))
        AND (
            (p.workspace_id IS NOT NULL AND w.id IS NOT NULL AND (@admin OR wm.role IN ('Owner','Admin','Member','Guest')))
            OR (p.workspace_id IS NULL AND (
                @global_view OR p.manager_user_id = @actor OR p.owner_user_id = @actor
                OR p.department_id = @department OR p.branch_id = @employee_branch
                OR pm.role IN ('Admin','Project Admin','Manager','Project Manager','Lead','Member','Team Member','Viewer')
                OR (p.is_client_visible AND pm.role IN ('Client Viewer','Client'))))
        )";

    private const string ProjectScope = ProjectAccess + @"
        AND NOT p.is_task_collection
        AND (p.deleted_at IS NOT NULL) = @trash
        AND (@trash OR coalesce(p.is_archived, false) = @archived)";

    private const string ProjectEdit = @"
        coalesce((
            (p.workspace_id IS NOT NULL AND w.id IS NOT NULL AND (@admin OR wm.role IN ('Owner','Admin')))
            OR (p.workspace_id IS NULL AND (@global_edit OR p.manager_user_id = @actor
                OR pm.role IN ('Admin','Project Admin','Manager','Project Manager')))
        ), false)";

    private readonly DesktopDatabaseSettings settings;
    private readonly PmsActor actor;

    private PmsProjectRepository(DesktopDatabaseSettings settings, PmsActor actor)
    {
        this.settings = settings;
        this.actor = actor;
    }

    public bool CanExport => actor.ModuleCanExport;
    public bool CanCreate => actor.ModuleCanCreate;
    public bool CanCreateWorkspace => actor.ModuleCanCreate && actor.CanManageOrganizationProjects;
    internal bool CanOpenWorkspaceRecovery => actor.IsPmsAdmin;

    public static async Task<PmsProjectRepository> OpenAsync(DesktopDatabaseSettings settings, CancellationToken cancellation)
    {
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        var identity = await settings.RequireActorAsync(connection, null, cancellation);
        var actor = await ResolveActorAsync(settings, identity, connection, null, cancellation);
        return new PmsProjectRepository(settings, actor);
    }

    internal static async Task RequireLinkedProjectVisibleAsync(DesktopDatabaseSettings settings,NpgsqlConnection connection,
        NpgsqlTransaction transaction,DesktopActor identity,int project,CancellationToken cancellation)
    {
        var actor = await ResolveActorAsync(settings,identity,connection,transaction,cancellation);
        var repository = new PmsProjectRepository(settings,actor);
        using var query = new NpgsqlCommand("SELECT 1" + ProjectJoins + " WHERE " + ProjectAccess +
            " AND p.id=@project AND NOT p.is_task_collection AND p.deleted_at IS NULL",connection,transaction);
        repository.SetActor(query,actor);
        query.Parameters.AddWithValue("project",project);
        if (await query.ExecuteScalarAsync(cancellation) is null)
            throw new UnauthorizedAccessException("The linked project is outside your permitted scope.");
    }

    private static async Task<PmsActor> ResolveActorAsync(DesktopDatabaseSettings settings, DesktopActor identity,
        NpgsqlConnection connection, NpgsqlTransaction? transaction, CancellationToken cancellation)
    {
        using var query = new NpgsqlCommand(@"
            WITH source AS (
                SELECT p.id AS policy_id, p.status,
                       p.grants::jsonb -> 'project_management' AS company_grant,
                       g.module_grants IS NOT NULL AS has_branch_rule,
                       g.module_grants::jsonb -> 'project_management' AS branch_grant,
                       r.name AS legacy_role, u.role_id, employee.employment_type, employee.department_id, employee.branch_id
                FROM public.users u
                LEFT JOIN public.roles r ON r.id = u.role_id
                LEFT JOIN public.suite_access_policies p ON p.user_id = u.id AND p.company_id = @organization
                LEFT JOIN public.suite_branch_grants g ON g.user_id = u.id AND g.company_id = @organization AND g.branch_id = @branch
                LEFT JOIN LATERAL (
                    SELECT e.employment_type, e.department_id, e.branch_id
                    FROM public.employees e JOIN public.branches b ON b.id = e.branch_id
                    WHERE e.user_id = u.id AND e.deleted_at IS NULL AND b.company_id = @organization
                    ORDER BY e.id LIMIT 1
                ) employee ON true
                WHERE u.id = @actor
            ), grants AS (
                SELECT s.*, cr.id AS company_role_id, br.id AS branch_role_id,
                       coalesce(cr.permissions::jsonb, company_grant -> 'permissions', '[]'::jsonb) AS company_permissions,
                       coalesce(br.permissions::jsonb, branch_grant -> 'permissions', '[]'::jsonb) AS branch_permissions,
                       coalesce(cr.actions::jsonb, company_grant -> 'actions', '[]'::jsonb) AS company_actions,
                       coalesce(br.actions::jsonb, branch_grant -> 'actions', '[]'::jsonb) AS branch_actions,
                       coalesce(company_grant ->> 'scope', cr.scope, 'own') AS company_scope,
                       coalesce(branch_grant ->> 'scope', br.scope, 'own') AS branch_scope,
                       coalesce((SELECT jsonb_agg(p.name)
                           FROM public.role_permissions rp JOIN public.permissions p ON p.id = rp.permission_id
                           WHERE rp.role_id = s.role_id), '[]'::jsonb) AS legacy_permissions
                FROM source s
                LEFT JOIN public.suite_access_roles cr ON cr.id::text = company_grant ->> 'roleId'
                    AND cr.active AND cr.company_id = @organization AND cr.module_key = 'project_management'
                LEFT JOIN public.suite_access_roles br ON br.id::text = branch_grant ->> 'roleId'
                    AND br.active AND br.company_id = @organization AND br.module_key = 'project_management'
            ), subscription AS (
                SELECT s.status, plan.id AS plan_id,
                       coalesce(plan.config_json::jsonb, '{}'::jsonb) || coalesce(s.config_json::jsonb, '{}'::jsonb) AS config
                FROM public.tenant_subscriptions s LEFT JOIN public.tenant_subscription_plans plan ON plan.id = s.plan_id
                WHERE s.company_id = @organization
            ), license AS (
                SELECT s.status, s.plan_id, s.config ||
                    CASE WHEN (s.config #>> '{scheduled_change,effective_at}')::timestamptz <= now()
                         THEN coalesce(target.config_json::jsonb, '{}'::jsonb) ELSE '{}'::jsonb END AS config
                FROM subscription s LEFT JOIN public.tenant_subscription_plans target
                    ON target.id::text = s.config #>> '{scheduled_change,plan_id}'
            )
            SELECT g.department_id, g.branch_id,
                   NOT EXISTS (SELECT 1 FROM public.bos_enabled_modules m WHERE m.company_id = @organization
                       AND m.module_key = 'project_management' AND NOT m.enabled)
                   AND NOT EXISTS (SELECT 1 FROM license l WHERE plan_id IS NULL OR
                       (l.config ->> 'enforce' = 'true' AND (
                         l.status = 'suspended' OR (l.config ->> 'expiry_policy' = 'restrict'
                             AND (l.config ->> 'grace_until')::timestamptz < now())
                         OR NOT coalesce(jsonb_exists(l.config -> 'modules', 'project_management'), false))))
                   AND (@superuser OR NOT EXISTS (
                        SELECT 1 FROM public.suite_service_policies policy
                        WHERE policy.organization_id = @organization AND policy.kind = 'governance'
                          AND policy.values_json ->> 'module' = 'project_management'
                          AND policy.values_json ->> 'classification' = 'restricted'
                          AND NOT coalesce(policy.values_json::jsonb -> 'allowedRoles' @> jsonb_build_array(g.role_id), false)
                   )) AS licensed,
                   policy_id IS NOT NULL AS managed,
                   coalesce(status = 'active' AND company_grant ->> 'enabled' = 'true'
                      AND (company_grant ->> 'roleId' IS NULL OR company_role_id IS NOT NULL)
                      AND jsonb_exists(company_actions, 'view'), false) AS company_enabled,
                   NOT EXISTS (SELECT 1 FROM public.suite_branch_grants other
                       WHERE @branch IS NULL AND other.user_id = @actor AND other.company_id = @organization
                         AND other.module_grants IS NOT NULL) AS branch_selected,
                   has_branch_rule,
                   coalesce(branch_grant ->> 'enabled' = 'true'
                      AND (branch_grant ->> 'roleId' IS NULL OR branch_role_id IS NOT NULL)
                      AND jsonb_exists(branch_actions, 'view')
                      AND (company_scope IN ('organization','all') OR company_scope = branch_scope
                         OR branch_scope IN ('organization','all')
                         OR (branch_scope = 'own' AND company_scope IN ('team','department','branch'))), false) AS branch_enabled,
                   ARRAY(SELECT jsonb_array_elements_text(CASE WHEN policy_id IS NULL THEN legacy_permissions
                        ELSE company_permissions END)) AS permissions,
                   ARRAY(SELECT jsonb_array_elements_text(company_actions)) AS actions,
                   ARRAY(SELECT jsonb_array_elements_text(branch_permissions)) AS branch_permissions,
                   ARRAY(SELECT jsonb_array_elements_text(branch_actions)) AS branch_actions,
                   company_scope, branch_scope,
                   lower(replace(coalesce(legacy_role, ''), ' ', '_')) AS legacy_role,
                   lower(coalesce(employment_type, '')) AS employment_type
            FROM grants g", connection, transaction);
        query.Parameters.AddWithValue("organization", settings.OrganizationId);
        query.Parameters.AddWithValue("actor", identity.Id);
        query.Parameters.AddWithValue("superuser", identity.IsSuperuser);
        query.Parameters.Add("branch", NpgsqlDbType.Integer).Value = (object?)settings.BranchId ?? DBNull.Value;
        using var reader = await query.ExecuteReaderAsync(cancellation);
        if (!await reader.ReadAsync(cancellation) || !reader.GetBoolean(2))
            throw new UnauthorizedAccessException("Project Management is unavailable for this company.");

        var department = reader.IsDBNull(0) ? (int?)null : reader.GetInt32(0);
        var employeeBranch = reader.IsDBNull(1) ? (int?)null : reader.GetInt32(1);
        if (identity.IsSuperuser)
            return new PmsActor(identity.Id, true, true, true, true, identity.CanWriteBranch, identity.CanWriteBranch,
                identity.CanWriteBranch, true, identity.CanWriteBranch, true, identity.CanWriteBranch, true,
                department, employeeBranch, "organization");

        bool managed = reader.GetBoolean(3);
        bool branchRestricted = reader.GetBoolean(6);
        string legacyRole = reader.GetString(14);
        if (!reader.GetBoolean(5) || (managed && !reader.GetBoolean(4))
            || (branchRestricted && !reader.GetBoolean(7)) || legacyRole == "intern" || reader.GetString(15) == "intern")
            throw new UnauthorizedAccessException("Your access policy does not allow Project Management in this branch.");

        var permissions = reader.GetFieldValue<string[]>(8);
        var actions = reader.GetFieldValue<string[]>(9);
        if (branchRestricted)
        {
            permissions = permissions.Intersect(reader.GetFieldValue<string[]>(10), StringComparer.Ordinal).ToArray();
            actions = (managed ? actions.Intersect(reader.GetFieldValue<string[]>(11), StringComparer.Ordinal)
                : reader.GetFieldValue<string[]>(11)).ToArray();
        }

        bool companyWide = !managed || reader.GetString(12) is "all" or "organization" or "company";
        bool branchWide = !branchRestricted || reader.GetString(13) is "all" or "organization" or "company" or "branch";
        bool admin = companyWide && branchWide && (identity.IsCompanyAdmin
            || (legacyRole is "admin" or "super_admin" or "hr" or "hr_admin" or "hr_company_admin" or "pms_super_admin" or "pms_org_admin"
                && (!managed || actions.Contains("assign") || actions.Contains("configure"))));
        bool unrestricted = !managed && !branchRestricted;
        bool manage = companyWide && branchWide && permissions.Any(p => p is "pms_manage_projects" or "pms_admin");
        bool view = companyWide && branchWide
            && permissions.Any(p => p is "pms_view" or "pms_manage_projects" or "pms_manage_tasks" or "pms_time_manage" or "pms_admin");
        return new PmsActor(identity.Id, admin, view, manage,
            manage || (companyWide && branchWide && permissions.Contains("pms_manage_tasks")),
            identity.CanWriteBranch && (unrestricted || actions.Contains("create")),
            identity.CanWriteBranch && (unrestricted || actions.Contains("edit")),
            identity.CanWriteBranch && (unrestricted || actions.Contains("delete")),
            unrestricted || actions.Contains("export"), identity.CanWriteBranch && (unrestricted || actions.Contains("assign")),
            companyWide && branchWide && permissions.Contains("pms_admin"),
            identity.CanWriteBranch && (unrestricted || actions.Contains("approve")),
            companyWide && branchWide && permissions.Any(p => p is "pms_client_portal" or "pms_manage_projects" or "pms_admin"),
            department, employeeBranch,
            !companyWide ? reader.GetString(12) : !branchWide || branchRestricted ? reader.GetString(13) : "organization");
    }

    public async Task<List<PmsWorkspaceChoice>> ListWorkspacesAsync(CancellationToken cancellation)
    {
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var query = new NpgsqlCommand(@"
            SELECT w.id, w.name, coalesce(@admin OR wm.role IN ('Owner','Admin'), false),
                   coalesce(wm.role, 'Admin'), members.member_count,
                   work.project_count, work.task_count, work.completed_count, w.created_at
            FROM public.pms_workspaces w
            LEFT JOIN public.pms_workspace_members wm ON wm.workspace_id = w.id AND wm.user_id = @actor
                AND " + WorkspaceMemberScope + @"
            CROSS JOIN LATERAL (
                SELECT count(*) AS member_count FROM public.pms_workspace_members m
                WHERE m.workspace_id = w.id AND (@branch IS NULL OR EXISTS (
                    SELECT 1 FROM public.suite_branch_ownership b
                    WHERE b.resource_table = 'pms_workspace_members' AND b.resource_key = m.id::text
                      AND b.company_id = @organization AND b.branch_id = @branch))
            ) members
            CROSS JOIN LATERAL (
                SELECT count(DISTINCT p.id) FILTER (WHERE NOT p.is_task_collection) AS project_count,
                       count(t.id) AS task_count,
                       count(t.id) FILTER (WHERE t.status IN ('Done','Completed','Closed','Resolved')) AS completed_count
                FROM public.pms_projects p
                LEFT JOIN public.pms_tasks t ON t.project_id = p.id AND t.deleted_at IS NULL
                    AND (@branch IS NULL OR EXISTS (
                        SELECT 1 FROM public.suite_branch_ownership b
                        WHERE b.resource_table = 'pms_tasks' AND b.resource_key = t.id::text
                          AND b.company_id = @organization AND b.branch_id = @branch))
                WHERE p.workspace_id = w.id AND p.deleted_at IS NULL
                  AND coalesce(p.organization_id, 1) = @organization
                  AND (@branch IS NULL OR EXISTS (
                       SELECT 1 FROM public.suite_branch_ownership b
                       WHERE b.resource_table = 'pms_projects' AND b.resource_key = p.id::text
                         AND b.company_id = @organization AND b.branch_id = @branch))
            ) work
            WHERE " + VisibleWorkspace + @"
              AND (@admin OR wm.role IN ('Owner','Admin','Member','Guest'))
              AND EXISTS (SELECT 1 FROM public.users WHERE id = @actor AND is_active)
            ORDER BY lower(w.name), w.id", connection);
        var currentActor = await settings.RequireActorAsync(connection, null, cancellation);
        SetActor(query, await ResolveActorAsync(settings, currentActor, connection, null, cancellation));
        using var reader = await query.ExecuteReaderAsync(cancellation);
        var workspaces = new List<PmsWorkspaceChoice>();
        while (await reader.ReadAsync(cancellation))
            workspaces.Add(new PmsWorkspaceChoice(reader.GetInt32(0), reader.GetString(1), reader.GetBoolean(2),
                reader.GetString(3), reader.GetInt64(4), reader.GetInt64(5), reader.GetInt64(6), reader.GetInt64(7),
                reader.IsDBNull(8) ? (DateTime?)null : reader.GetDateTime(8)));
        return workspaces;
    }

    public async Task<int> CreateWorkspaceAsync(string name, CancellationToken cancellation)
    {
        name = name.Trim();
        if (string.IsNullOrEmpty(name) || name.Length > 180)
            throw new InvalidOperationException("Enter a workspace name of 1 to 180 characters.");

        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction();
        var identity = await settings.VerifyWriteTargetAsync(connection, transaction, cancellation);
        var actor = await ResolveActorAsync(settings, identity, connection, transaction, cancellation);
        if (!actor.CanManageOrganizationProjects || !actor.ModuleCanCreate)
            throw new UnauthorizedAccessException("You do not have permission to create a workspace.");

        using var insert = new NpgsqlCommand(@"
            INSERT INTO public.pms_workspaces (organization_id, name)
            VALUES (@organization, @name) RETURNING id", connection, transaction);
        insert.Parameters.AddWithValue("organization", settings.OrganizationId);
        insert.Parameters.AddWithValue("name", name);
        var workspaceId = (int)(await insert.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(connection, transaction, "pms_workspaces", workspaceId, cancellation);

        using var membership = new NpgsqlCommand(@"
            INSERT INTO public.pms_workspace_members (workspace_id, user_id, role)
            VALUES (@workspace, @actor, 'Owner') RETURNING id", connection, transaction);
        membership.Parameters.AddWithValue("workspace", workspaceId);
        membership.Parameters.AddWithValue("actor", actor.UserId);
        var membershipId = (int)(await membership.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(connection, transaction, "pms_workspace_members", membershipId, cancellation);
        transaction.Commit();
        return workspaceId;
    }

    public Task<DataTable> ListProjectsAsync(int workspaceId,PmsProjectScope scope,CancellationToken cancellation) =>
        ReadProjectsAsync(workspaceId,scope,null,cancellation);

    private async Task<DataTable> ReadProjectsAsync(int workspaceId,PmsProjectScope scope,int[]? selected,CancellationToken cancellation)
    {
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var query = new NpgsqlCommand(@"
            SELECT p.id, p.project_key, p.name, w.name AS workspace, p.workspace_id, p.description,
                   p.status, p.priority, p.start_date::timestamp, p.due_date::timestamp, p.budget_amount,
                   p.xmin::text AS revision,
                   capabilities.can_manage AND @module_edit AS can_edit,
                   capabilities.can_manage AND @module_create AS can_archive,
                   capabilities.can_manage AND @module_delete AS can_trash,
                   capabilities.can_manage AND @module_create AS can_restore,
                   @module_create AND (" + TaskEditAccess + @") AND NOT @trash AND NOT @archived AS can_create_task,
                   stats.task_count, coalesce(
                        round(stats.completed::numeric * 100 / nullif(stats.task_count, 0), 1),
                        p.progress_percent) AS progress" +
            (selected is null ? "" : @",
                   coalesce(nullif(client.company_name,''),client.name) AS client_name,
                   coalesce(nullif(person.display_name,''),account.email) AS owner_name,
                   CASE WHEN stats.blocked>0 OR p.health='Blocked' THEN 'Blocked'
                        WHEN p.due_date<current_date AND NOT coalesce(p.is_archived,false)
                             AND p.status NOT IN ('Completed','Cancelled','Archived') THEN 'Off Track'
                        WHEN stats.overdue>0 OR p.health IN ('At Risk','Critical') THEN 'At Risk'
                        ELSE 'On Track' END AS health") + ProjectJoins +
            (selected is null ? "" : @"
            LEFT JOIN public.pms_clients client ON client.id=p.client_id AND coalesce(client.organization_id,1)=@organization
            LEFT JOIN public.users account ON account.id=coalesce(p.owner_user_id,p.manager_user_id)
            LEFT JOIN LATERAL (SELECT display_name FROM public.common_people
                WHERE user_id=account.id ORDER BY id LIMIT 1) person ON true") + @"
            CROSS JOIN LATERAL (SELECT " + ProjectEdit + @" AS can_manage) capabilities
            CROSS JOIN LATERAL (
                SELECT count(*) AS task_count,
                       count(*) FILTER (WHERE t.status IN ('Done','Completed','Closed','Resolved')) AS completed,
                       count(*) FILTER (WHERE t.status='Blocked') AS blocked,
                       count(*) FILTER (WHERE t.due_date<current_date
                           AND t.status NOT IN ('Done','Completed','Closed','Resolved','Cancelled')) AS overdue
                FROM public.pms_tasks t
                WHERE t.project_id = p.id AND t.deleted_at IS NULL
                  AND (@branch IS NULL OR EXISTS (SELECT 1 FROM public.suite_branch_ownership b
                      WHERE b.resource_table = 'pms_tasks' AND b.resource_key = t.id::text
                        AND b.company_id = @organization AND b.branch_id = @branch))
            ) stats
            WHERE " + ProjectScope + @"
              AND (@workspace = 0 OR p.workspace_id = @workspace)
              AND EXISTS (SELECT 1 FROM public.users WHERE id = @actor AND is_active)" +
            (selected is null ? "" : " AND p.id=ANY(@selected)") + " ORDER BY lower(p.name), p.id", connection);
        var currentActor = await settings.RequireActorAsync(connection, null, cancellation);
        var current=await ResolveActorAsync(settings,currentActor,connection,null,cancellation);
        if(selected is not null)
        {
            if(!current.ModuleCanExport)
                throw new UnauthorizedAccessException("You do not have permission to export projects.");
            query.Parameters.AddWithValue("selected",NpgsqlDbType.Array|NpgsqlDbType.Integer,selected);
        }
        SetActor(query,current);
        SetScope(query, scope);
        query.Parameters.AddWithValue("workspace", workspaceId);
        return await ReadTableAsync(query, cancellation);
    }

    public async Task<DataTable> ListWorkAsync(string view, string search, bool overdueOnly,
        int workspaceId, CancellationToken cancellation)
    {
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        var identity = await settings.RequireActorAsync(connection, null, cancellation);
        var actor = await ResolveActorAsync(settings, identity, connection, null, cancellation);
        using var query = new NpgsqlCommand(@"
            SELECT t.id, t.task_key, t.title, t.description, p.name AS project, w.name AS workspace, t.work_type,
                   t.status, t.priority, t.start_date::timestamp, t.due_date::timestamp,
                   t.estimated_hours, t.completed_at, t.updated_at, t.deleted_at, t.xmin::text AS revision,
                   t.deleted_at IS NULL AND @module_edit AND (" + TaskEditAccess + @") AS can_edit,
                   (CASE WHEN t.deleted_at IS NULL THEN @module_delete ELSE @module_create END)
                       AND (" + TaskEditAccess + @") AS can_change_trash" + ProjectJoins + @"
            JOIN public.pms_tasks t ON t.project_id = p.id
            WHERE " + ProjectAccess + @"
                AND p.deleted_at IS NULL AND (t.deleted_at IS NOT NULL) = (@view = 'trash')
                AND " + TaskBranchScope + @"
                AND (@workspace = 0 OR p.workspace_id = @workspace)
                AND CASE @view
                    WHEN 'mine' THEN t.assignee_user_id = @actor OR EXISTS (
                        SELECT 1 FROM public.pms_task_assignees a WHERE a.task_id = t.id AND a.user_id = @actor)
                    WHEN 'unassigned' THEN t.assignee_user_id IS NULL AND NOT EXISTS (
                        SELECT 1 FROM public.pms_task_assignees a WHERE a.task_id = t.id) AND NOT EXISTS (
                        SELECT 1 FROM public.pms_task_group_targets g WHERE g.task_id = t.id)
                    WHEN 'teams' THEN EXISTS (
                        SELECT 1 FROM public.pms_task_group_targets g WHERE g.task_id = t.id AND g.kind = 'teams')
                    WHEN 'batches' THEN EXISTS (
                        SELECT 1 FROM public.pms_task_group_targets g WHERE g.task_id = t.id AND g.kind = 'batches')
                    WHEN 'completed' THEN t.status IN ('Done','Completed','Closed','Resolved')
                    WHEN 'approvals' THEN t.status = 'In Review'
                    WHEN 'all' THEN true
                    WHEN 'trash' THEN true
                    ELSE false END
                AND (@view = 'trash' OR NOT @overdue OR (t.due_date < @today
                    AND t.status NOT IN ('Done','Completed','Closed','Resolved','Cancelled','Canceled','Rejected')))
                AND (@search = '' OR strpos(lower(t.title), lower(@search)) > 0
                     OR strpos(lower(t.task_key), lower(@search)) > 0
                     OR strpos(lower(t.description), lower(@search)) > 0
                     OR strpos(lower(p.name), lower(@search)) > 0
                     OR strpos(lower(p.project_key), lower(@search)) > 0)
            ORDER BY t.deleted_at DESC NULLS LAST, t.due_date NULLS LAST, t.id", connection);
        SetActor(query, actor);
        query.Parameters.AddWithValue("workspace", workspaceId);
        query.Parameters.AddWithValue("view", view);
        query.Parameters.AddWithValue("search", search.Trim());
        query.Parameters.AddWithValue("overdue", overdueOnly);
        query.Parameters.AddWithValue("today", NpgsqlDbType.Date, DateTime.Today);
        return await ReadTableAsync(query, cancellation);
    }

    private static async Task<DataTable> ReadTableAsync(NpgsqlCommand query, CancellationToken cancellation)
    {
        using var reader = await query.ExecuteReaderAsync(cancellation);
        var table = new DataTable();
        for (var index = 0; index < reader.FieldCount; index++)
            table.Columns.Add(reader.GetName(index), reader.GetFieldType(index));
        while (await reader.ReadAsync(cancellation))
        {
            var values = new object[reader.FieldCount];
            reader.GetValues(values);
            table.Rows.Add(values);
        }
        return table;
    }

    public async Task SaveAsync(PmsProjectDraft draft, int? projectId, string? revision,
        PmsProjectScope scope, CancellationToken cancellation)
    {
        Validate(draft, projectId.HasValue);
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction();
        var identity = await settings.VerifyWriteTargetAsync(connection, transaction, cancellation);
        var actor = await ResolveActorAsync(settings, identity, connection, transaction, cancellation);

        if (projectId is null)
        {
            if (!actor.ModuleCanCreate)
                throw new InvalidOperationException("You do not have permission to create a project.");
            using var create = new NpgsqlCommand(@"
                INSERT INTO public.pms_projects (
                    organization_id, branch_id, workspace_id, project_key, name, description, status, priority,
                    start_date, due_date, budget_amount, owner_user_id, health, billing_status,
                    progress_percent, is_client_visible, is_template, is_archived)
                SELECT @organization, @branch, w.id, @key, @name, @description, @status, @priority,
                       @start, @due, @budget, @actor, 'Good', 'Unbilled', 0, false, false, false
                FROM public.pms_workspaces w
                LEFT JOIN public.pms_workspace_members wm ON wm.workspace_id = w.id AND wm.user_id = @actor
                    AND " + WorkspaceMemberScope + @"
                WHERE w.id = @workspace AND " + VisibleWorkspace + @"
                    AND (@admin OR wm.role IN ('Owner','Admin'))
                    AND EXISTS (SELECT 1 FROM public.users WHERE id = @actor AND is_active)
                RETURNING id", connection, transaction);
            SetActor(create, actor);
            SetDraft(create, draft);
            try
            {
                var id = await create.ExecuteScalarAsync(cancellation);
                if (id is null)
                    throw new InvalidOperationException("Choose a workspace you can manage.");
                projectId = (int)id;
            }
            catch (PostgresException error) when (error.SqlState == PostgresErrorCodes.UniqueViolation
                && error.ConstraintName == "uq_pms_project_org_key")
            {
                throw new InvalidOperationException("Project key already exists.");
            }

            await RecordOwnershipAsync(connection, transaction, "pms_projects", projectId.Value, cancellation);
            using var member = new NpgsqlCommand(@"
                INSERT INTO public.pms_project_members(project_id, user_id, role)
                VALUES (@id, @actor, 'Manager') RETURNING id", connection, transaction);
            member.Parameters.AddWithValue("id", projectId.Value);
            member.Parameters.AddWithValue("actor", actor.UserId);
            var membershipId = (int)(await member.ExecuteScalarAsync(cancellation))!;
            await RecordOwnershipAsync(connection, transaction, "pms_project_members", membershipId, cancellation);
            await RecordActivityAsync(connection, transaction, projectId.Value, "project.created",
                "Created project " + draft.ProjectKey, null, cancellation);
        }
        else
        {
            if (!actor.ModuleCanEdit || scope == PmsProjectScope.Trash)
                throw new UnauthorizedAccessException("You do not have permission to edit this project.");
            await LockEditableProjectAsync(connection, transaction, actor, projectId.Value, revision!, scope, cancellation);
            using var update = new NpgsqlCommand(@"
                WITH previous AS (
                    SELECT id, name, description, status, priority, start_date, due_date, budget_amount
                    FROM public.pms_projects WHERE id = @id
                ), changed AS (
                    UPDATE public.pms_projects
                    SET name = @name, description = @description, status = @status, priority = @priority,
                        start_date = @start, due_date = @due, budget_amount = @budget, updated_at = now(),
                        actual_start_date = CASE WHEN @status = 'Active' AND actual_start_date IS NULL
                                                 THEN current_date ELSE actual_start_date END,
                        actual_end_date = CASE WHEN @status IN ('Completed','Cancelled') AND actual_end_date IS NULL
                                               THEN current_date ELSE actual_end_date END
                    WHERE id = @id
                    RETURNING id, name, description, status, priority, start_date, due_date, budget_amount
                )
                SELECT jsonb_build_object('old_values', to_jsonb(previous) - 'id',
                                          'changed_fields', to_jsonb(changed) - 'id')::text,
                       CASE WHEN previous.status IS DISTINCT FROM changed.status
                            THEN jsonb_build_object('old_value', previous.status, 'new_value', changed.status)::text END,
                       CASE WHEN previous.budget_amount IS DISTINCT FROM changed.budget_amount
                            THEN jsonb_build_object('old_values', jsonb_build_object('budget_amount', previous.budget_amount),
                                                    'new_values', jsonb_build_object('budget_amount', changed.budget_amount))::text END
                FROM previous JOIN changed USING (id)", connection, transaction);
            update.Parameters.AddWithValue("id", projectId.Value);
            SetDraft(update, draft);

            string metadata;
            string? statusChange;
            string? budgetChange;
            using (var reader = await update.ExecuteReaderAsync(cancellation))
            {
                if (!await reader.ReadAsync(cancellation))
                    throw new InvalidOperationException("The project is no longer available.");
                metadata = reader.GetString(0);
                statusChange = reader.IsDBNull(1) ? null : reader.GetString(1);
                budgetChange = reader.IsDBNull(2) ? null : reader.GetString(2);
            }

            await RecordActivityAsync(connection, transaction, projectId.Value, "project.updated",
                "Updated project " + draft.ProjectKey, metadata, cancellation);
            if (statusChange is not null)
                await RecordActivityAsync(connection, transaction, projectId.Value, "project.status_changed",
                    "Changed project status to " + draft.Status, statusChange, cancellation);
            if (budgetChange is not null)
                await RecordActivityAsync(connection, transaction, projectId.Value, "project.budget_changed",
                    "Changed project budget for " + draft.ProjectKey, budgetChange, cancellation);
        }

        transaction.Commit();
    }

    public async Task ApplyActionAsync(int projectId, string revision, PmsProjectScope scope,
        PmsProjectAction action, CancellationToken cancellation)
    {
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction();
        var identity = await settings.VerifyWriteTargetAsync(connection, transaction, cancellation);
        var actor = await ResolveActorAsync(settings, identity, connection, transaction, cancellation);
        await ApplyProjectLifecycleAsync(connection,transaction,actor,projectId,revision,scope,action,false,cancellation);
        transaction.Commit();
    }

    private async Task ApplyProjectLifecycleAsync(NpgsqlConnection connection,NpgsqlTransaction transaction,PmsActor actor,
        int projectId,string revision,PmsProjectScope scope,PmsProjectAction action,bool activateArchive,CancellationToken cancellation)
    {
        var (assignment, eventName, caption) = action switch
        {
            PmsProjectAction.Archive when scope == PmsProjectScope.Active =>
                ("is_archived = true", "project.archived", "Archived"),
            PmsProjectAction.Unarchive when scope == PmsProjectScope.Archived =>
                ("is_archived = false", "project.unarchived", "Unarchived"),
            PmsProjectAction.Trash when scope != PmsProjectScope.Trash =>
                ("deleted_at = now()", "project.deleted", "Deleted"),
            PmsProjectAction.Restore when scope == PmsProjectScope.Trash =>
                ("deleted_at = NULL", "project.restored", "Restored"),
            _ => throw new InvalidOperationException("This action is unavailable for the selected project.")
        };

        if (!(action == PmsProjectAction.Trash ? actor.ModuleCanDelete : actor.ModuleCanCreate))
            throw new UnauthorizedAccessException("You do not have permission to change this project.");
        var projectKey = await LockEditableProjectAsync(connection, transaction, actor, projectId, revision, scope, cancellation);
        string? statusChange=null;
        if(activateArchive)
        {
            using var status=new NpgsqlCommand(@"SELECT jsonb_build_object('old_value',status,'new_value','Active')::text
                FROM public.pms_projects WHERE id=@id AND (start_date IS NULL OR due_date IS NULL OR start_date<=due_date)",connection,transaction);
            status.Parameters.AddWithValue("id",projectId);
            statusChange=await status.ExecuteScalarAsync(cancellation) as string ??
                throw new InvalidOperationException("Start date cannot be after the deadline.");
            assignment+=", status='Active', actual_start_date=coalesce(actual_start_date,current_date)";
        }
        using var update = new NpgsqlCommand(
            "UPDATE public.pms_projects SET " + assignment + ", updated_at = now() WHERE id = @id", connection, transaction);
        update.Parameters.AddWithValue("id", projectId);
        await update.ExecuteNonQueryAsync(cancellation);
        await RecordActivityAsync(connection, transaction, projectId, eventName, caption + " project " + projectKey,
            null, cancellation);
        if(statusChange is not null)
            await RecordActivityAsync(connection,transaction,projectId,"project.status_changed","Changed project status to Active",
                statusChange,cancellation);
    }

    private async Task<string> LockEditableProjectAsync(NpgsqlConnection connection, NpgsqlTransaction transaction,
        PmsActor actor, int projectId, string revision, PmsProjectScope scope, CancellationToken cancellation)
    {
        using var query = new NpgsqlCommand("SELECT p.project_key" + ProjectJoins + " WHERE " + ProjectScope + @"
            AND p.id = @id AND p.xmin::text = @revision AND " + ProjectEdit + @"
            AND EXISTS (SELECT 1 FROM public.users WHERE id = @actor AND is_active)
            FOR UPDATE OF p", connection, transaction);
        SetActor(query, actor);
        SetScope(query, scope);
        query.Parameters.AddWithValue("id", projectId);
        query.Parameters.AddWithValue("revision", revision);
        return await query.ExecuteScalarAsync(cancellation) as string
            ?? throw new InvalidOperationException("The project changed, was removed, or is no longer editable. Refresh the list.");
    }

    private async Task RecordActivityAsync(NpgsqlConnection connection, NpgsqlTransaction transaction,
        int projectId, string action, string summary, string? metadata, CancellationToken cancellation)
    {
        using var insert = new NpgsqlCommand(@"
            INSERT INTO public.pms_activities(project_id, actor_user_id, action, entity_type, entity_id, summary, metadata_json)
            VALUES (@id, @actor, @action, 'project', @id, @summary, @metadata) RETURNING id", connection, transaction);
        insert.Parameters.AddWithValue("id", projectId);
        insert.Parameters.AddWithValue("actor", actor.UserId);
        insert.Parameters.AddWithValue("action", action);
        insert.Parameters.AddWithValue("summary", summary);
        insert.Parameters.AddWithValue("metadata", NpgsqlDbType.Text, (object?)metadata ?? DBNull.Value);
        var activityId = (int)(await insert.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(connection, transaction, "pms_activities", activityId, cancellation);
    }

    private async Task RecordOwnershipAsync(NpgsqlConnection connection, NpgsqlTransaction transaction,
        string table, int id, CancellationToken cancellation)
    {
        if (!settings.BranchId.HasValue)
            return;
        using var insert = new NpgsqlCommand(@"
            INSERT INTO public.suite_branch_ownership(resource_table, resource_key, company_id, branch_id, source)
            VALUES (@table, @resource, @organization, @branch, 'validated-write')", connection, transaction);
        insert.Parameters.AddWithValue("table", table);
        insert.Parameters.AddWithValue("resource", id.ToString(System.Globalization.CultureInfo.InvariantCulture));
        insert.Parameters.AddWithValue("organization", settings.OrganizationId);
        insert.Parameters.AddWithValue("branch", settings.BranchId.Value);
        await insert.ExecuteNonQueryAsync(cancellation);
    }

    private static void Validate(PmsProjectDraft draft, bool editing)
    {
        if (draft.Name.Length is < 1 or > 180 || string.IsNullOrWhiteSpace(draft.Name))
            throw new InvalidOperationException("Enter a project name of 1 to 180 characters.");
        if (!editing && !System.Text.RegularExpressions.Regex.IsMatch(draft.ProjectKey, @"\A[A-Z0-9]{2,10}\z"))
            throw new InvalidOperationException("Use a project key of 2 to 10 uppercase letters or digits.");
        if (!editing && draft.WorkspaceId < 1)
            throw new InvalidOperationException("Choose a workspace.");
        if (!new[] { "Draft", "Planned", "Active", "On Hold", "Completed", "Cancelled", "Archived" }.Contains(draft.Status))
            throw new InvalidOperationException("Select a valid project status.");
        if (!new[] { "Low", "Medium", "High", "Critical" }.Contains(draft.Priority))
            throw new InvalidOperationException("Select a valid project priority.");
        if (draft.StartDate > draft.DueDate)
            throw new InvalidOperationException("Start date cannot be after due date.");
        if (draft.Budget is < 0 or > 9999999999.99m)
            throw new InvalidOperationException("Enter a budget from 0 to 9,999,999,999.99.");
    }

    private static void SetDraft(NpgsqlCommand query, PmsProjectDraft draft)
    {
        query.Parameters.AddWithValue("workspace", draft.WorkspaceId);
        query.Parameters.AddWithValue("key", draft.ProjectKey);
        query.Parameters.AddWithValue("name", draft.Name);
        query.Parameters.AddWithValue("description", draft.Description);
        query.Parameters.AddWithValue("status", draft.Status);
        query.Parameters.AddWithValue("priority", draft.Priority);
        query.Parameters.AddWithValue("start", NpgsqlDbType.Date, (object?)draft.StartDate ?? DBNull.Value);
        query.Parameters.AddWithValue("due", NpgsqlDbType.Date, (object?)draft.DueDate ?? DBNull.Value);
        query.Parameters.AddWithValue("budget", NpgsqlDbType.Numeric, (object?)draft.Budget ?? DBNull.Value);
    }

    private void SetActor(NpgsqlCommand query, PmsActor actor)
    {
        query.Parameters.AddWithValue("organization", settings.OrganizationId);
        query.Parameters.AddWithValue("branch", NpgsqlDbType.Integer, (object?)settings.BranchId ?? DBNull.Value);
        query.Parameters.AddWithValue("actor", actor.UserId);
        query.Parameters.AddWithValue("admin", actor.OrganizationAdmin);
        query.Parameters.AddWithValue("global_view", actor.CanViewOrganizationProjects || actor.CanManageOrganizationProjects);
        query.Parameters.AddWithValue("global_edit", actor.CanManageOrganizationProjects);
        query.Parameters.AddWithValue("global_task_edit", actor.CanManageOrganizationTasks);
        query.Parameters.AddWithValue("module_edit", actor.ModuleCanEdit);
        query.Parameters.AddWithValue("module_create", actor.ModuleCanCreate);
        query.Parameters.AddWithValue("module_delete", actor.ModuleCanDelete);
        query.Parameters.AddWithValue("department", NpgsqlDbType.Integer, (object?)actor.DepartmentId ?? DBNull.Value);
        query.Parameters.AddWithValue("employee_branch", NpgsqlDbType.Integer, (object?)actor.EmployeeBranchId ?? DBNull.Value);
    }

    private static void SetScope(NpgsqlCommand query, PmsProjectScope scope)
    {
        query.Parameters.AddWithValue("trash", scope == PmsProjectScope.Trash);
        query.Parameters.AddWithValue("archived", scope == PmsProjectScope.Archived);
    }
}
