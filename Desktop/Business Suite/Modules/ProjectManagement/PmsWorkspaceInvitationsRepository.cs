using System.Data;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;
using Npgsql;

namespace Business_Suite;

internal sealed record PmsInvitationList(DataTable Records, bool CanIssue, bool CanRevoke, bool CanInviteAdmin);

internal sealed partial class PmsProjectRepository
{
    private const string InvitationScope = @"(@branch IS NULL OR EXISTS (
        SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='pms_workspace_invitations'
          AND o.resource_key=i.id::text AND o.company_id=@organization AND o.branch_id=@branch))";

    internal async Task<PmsInvitationList> ReadInvitationsAsync(int? workspace, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await GetWorkspaceActorAsync(db, tx, false, cancellation);
        string? role = null;
        if (workspace.HasValue)
        {
            (role, _) = await ReadWorkspaceRoleAsync(db, tx, actor, workspace.Value, false, cancellation);
            RequireInvitationManager(role);
        }
        using var list = new NpgsqlCommand(@"
            SELECT i.id,i.workspace_id,w.name AS workspace,i.email,i.role,i.expires_at,
                CASE WHEN i.status='pending' AND i.expires_at <= (clock_timestamp() AT TIME ZONE 'UTC')
                     THEN 'expired' ELSE i.status END AS status,i.xmin::text AS revision
            FROM public.pms_workspace_invitations i JOIN public.pms_workspaces w ON w.id=i.workspace_id
            WHERE " + InvitationScope + " AND " + VisibleWorkspace + @"
              AND CASE WHEN @workspace IS NOT NULL THEN w.id=@workspace ELSE
                  i.email=(SELECT lower(trim(u.email)) FROM public.users u WHERE u.id=@actor)
                  AND i.status='pending' AND i.expires_at>(clock_timestamp() AT TIME ZONE 'UTC') END
            ORDER BY i.id DESC", db, tx);
        SetActor(list, actor);
        list.Parameters.Add("workspace", NpgsqlTypes.NpgsqlDbType.Integer).Value = (object?)workspace ?? DBNull.Value;
        return new PmsInvitationList(await ReadTableAsync(list,cancellation), actor.ModuleCanCreate,
            actor.ModuleCanDelete, role == "Owner");
    }

    internal async Task UpdateWorkspaceInvitationAsync(int workspace, int? invitation, string? revision,
        string? email, string? role, bool revoke, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await GetWorkspaceActorAsync(db, tx, true, cancellation);
        var (actorRole, workspaceName) = await ReadWorkspaceRoleAsync(db, tx, actor, workspace, true, cancellation);
        actor = await GetWorkspaceActorAsync(db, tx, true, cancellation);
        (actorRole, _) = await ReadWorkspaceRoleAsync(db, tx, actor, workspace, false, cancellation);
        RequireInvitationManager(actorRole);
        if (!(revoke ? actor.ModuleCanDelete : actor.ModuleCanCreate))
            throw new UnauthorizedAccessException("Your policy does not allow this invitation action.");

        if (invitation.HasValue)
        {
            using var previous = new NpgsqlCommand(@"SELECT i.email,i.role,i.status FROM public.pms_workspace_invitations i
                WHERE i.id=@invitation AND i.workspace_id=@workspace AND i.xmin::text=@revision AND " + InvitationScope +
                " FOR UPDATE OF i", db, tx);
            SetActor(previous, actor);
            previous.Parameters.AddWithValue("invitation", invitation.Value);
            previous.Parameters.AddWithValue("workspace", workspace);
            previous.Parameters.AddWithValue("revision", revision!);
            using var row = await previous.ExecuteReaderAsync(cancellation);
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("This invitation changed. Refresh before trying again.");
            if (row.GetString(2) != "pending")
                throw new InvalidOperationException("Only pending or expired invitations can be changed.");
            email = row.GetString(0);
            role = row.GetString(1);
        }

        if (revoke)
        {
            if (!invitation.HasValue)
                throw new InvalidOperationException("Select an invitation to revoke.");
            using var update = new NpgsqlCommand(
                "UPDATE public.pms_workspace_invitations SET status='revoked' WHERE id=@invitation", db, tx);
            update.Parameters.AddWithValue("invitation", invitation.Value);
            await update.ExecuteNonQueryAsync(cancellation);
            await AuditInvitationAsync(db, tx, actor.UserId, workspace, invitation.Value, "PMS_INVITE_REVOKED",
                "Revoked workspace invitation", cancellation);
            await tx.CommitAsync(cancellation);
            return;
        }

        email = email?.Trim().ToLowerInvariant();
        if (email is null || email.Length > 100 || !Regex.IsMatch(email, @"\A[^\s@]+@[^\s@]+\.[^\s@]+\z"))
            throw new InvalidOperationException("Enter a valid email address of up to 100 characters.");
        if (role is not ("Admin" or "Member" or "Guest"))
            throw new InvalidOperationException("Choose Admin, Member or Guest.");
        if (role == "Admin" && actorRole != "Owner")
            throw new UnauthorizedAccessException("Only the workspace owner can invite administrators.");

        using (var member = new NpgsqlCommand(@"
            SELECT EXISTS (SELECT 1 FROM public.pms_workspace_members wm JOIN public.users u ON u.id=wm.user_id
                WHERE lower(u.email)=@email AND wm.workspace_id=@workspace)", db, tx))
        {
            member.Parameters.AddWithValue("workspace", workspace);
            member.Parameters.AddWithValue("email", email);
            if (Equals(await member.ExecuteScalarAsync(cancellation), true))
                throw new InvalidOperationException("This person is already a workspace member.");
        }

        using var issue = new NpgsqlCommand(@"
            UPDATE public.pms_workspace_invitations i SET status='revoked'
            WHERE workspace_id=@workspace AND lower(email)=@email AND status='pending' AND " + InvitationScope + @";
            INSERT INTO public.pms_workspace_invitations(workspace_id,email,role,token_hash,status,expires_at)
            VALUES(@workspace,@email,@role,@token_hash,'pending',(clock_timestamp() AT TIME ZONE 'UTC')+interval '7 days')
            RETURNING id", db, tx);
        SetActor(issue, actor);
        issue.Parameters.AddWithValue("workspace",workspace);
        issue.Parameters.AddWithValue("email",email);
        issue.Parameters.AddWithValue("role",role);
        issue.Parameters.AddWithValue("token_hash", CreateInvitationHash());
        var id = (int)(await issue.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db,tx,"pms_workspace_invitations",id,cancellation);
        await AuditInvitationAsync(db, tx, actor.UserId, workspace, id,
            invitation.HasValue ? "PMS_INVITE_REPLACED" : "PMS_INVITE_CREATED", "Issued a workspace invitation", cancellation);

        using var notice = new NpgsqlCommand(@"
            WITH recipient AS (SELECT u.id " + EligibleMember + @" AND lower(u.email)=@email ORDER BY u.id LIMIT 1),
                added AS (
                    INSERT INTO public.notifications(company_id,user_id,title,message,module,event_type,related_entity_type,
                        related_entity_id,action_url,priority,channels,is_read)
                    SELECT @organization,recipient.id,'Workspace invitation',@message,'project_management',
                        'workspace.invitation','workspace',@workspace,'/pms/workspaces','normal','[""in_app""]'::json,false
                    FROM recipient RETURNING id
                )
            INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
            SELECT 'notifications',id::text,@organization,@branch,'validated-write' FROM added WHERE @branch IS NOT NULL",
            db,tx);
        SetActor(notice, actor);
        notice.Parameters.AddWithValue("workspace",workspace);
        notice.Parameters.AddWithValue("email",email);
        notice.Parameters.AddWithValue("message",$"You were invited to {workspaceName} as {role}. Open My invitations to accept.");
        await notice.ExecuteNonQueryAsync(cancellation);
        await tx.CommitAsync(cancellation);
    }

    internal async Task<int> AcceptWorkspaceInvitationAsync(int invitation, string revision, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await GetWorkspaceActorAsync(db,tx,true,cancellation);
        if (!actor.ModuleCanCreate)
            throw new UnauthorizedAccessException("Your policy does not allow accepting invitations.");

        const string matchingInvitation = @" FROM public.pms_workspace_invitations i
            JOIN public.pms_workspaces w ON w.id=i.workspace_id
            WHERE i.id=@invitation AND i.xmin::text=@revision AND i.status='pending'
              AND i.expires_at>(clock_timestamp() AT TIME ZONE 'UTC')
              AND i.email=(SELECT lower(trim(email)) FROM public.users WHERE id=@actor AND is_active)
              AND " + VisibleWorkspace + " AND " + InvitationScope;
        int workspace;
        using (var find = new NpgsqlCommand("SELECT w.id" + matchingInvitation + " FOR UPDATE OF w", db, tx))
        {
            SetActor(find, actor);
            find.Parameters.AddWithValue("invitation", invitation);
            find.Parameters.AddWithValue("revision", revision);
            if (await find.ExecuteScalarAsync(cancellation) is not int matchingWorkspace)
                throw new InvalidOperationException("The invitation is invalid, expired, changed or addressed to another account.");
            workspace = matchingWorkspace;
        }

        actor = await GetWorkspaceActorAsync(db,tx,true,cancellation);
        if (!actor.ModuleCanCreate)
            throw new UnauthorizedAccessException("Your policy does not allow accepting invitations.");
        string role;
        using (var lockInvite = new NpgsqlCommand("SELECT i.role" + matchingInvitation + " FOR UPDATE OF i",db,tx))
        {
            SetActor(lockInvite,actor);
            lockInvite.Parameters.AddWithValue("invitation",invitation);
            lockInvite.Parameters.AddWithValue("revision",revision);
            role = await lockInvite.ExecuteScalarAsync(cancellation) as string
                ?? throw new InvalidOperationException("The invitation changed. Refresh and try again.");
        }
        if (role is not ("Admin" or "Member" or "Guest"))
            throw new InvalidOperationException("The invitation contains an invalid workspace role.");

        using var membership = new NpgsqlCommand(@"
            INSERT INTO public.pms_workspace_members(workspace_id,user_id,role)
            VALUES(@workspace,@actor,@role) ON CONFLICT(workspace_id,user_id) DO NOTHING RETURNING id",db,tx);
        membership.Parameters.AddWithValue("workspace",workspace);
        membership.Parameters.AddWithValue("actor",actor.UserId);
        membership.Parameters.AddWithValue("role",role);
        if (await membership.ExecuteScalarAsync(cancellation) is int member)
            await RecordOwnershipAsync(db,tx,"pms_workspace_members",member,cancellation);
        using var accept = new NpgsqlCommand("UPDATE public.pms_workspace_invitations SET status='accepted' WHERE id=@invite",db,tx);
        accept.Parameters.AddWithValue("invite",invitation);
        await accept.ExecuteNonQueryAsync(cancellation);
        await AuditInvitationAsync(db, tx, actor.UserId, workspace, invitation, "PMS_INVITE_ACCEPTED",
            "Accepted workspace invitation", cancellation);
        await tx.CommitAsync(cancellation);
        return workspace;
    }

    private async Task AuditInvitationAsync(NpgsqlConnection db,NpgsqlTransaction tx,int actor,int workspace,
        int invitation,string action,string description,CancellationToken cancellation)
    {
        using var audit = new NpgsqlCommand(@"
            INSERT INTO public.audit_logs(organization_id,user_id,actor_email,actor_authenticated,method,endpoint,
                module,entity_type,entity_id,action,description,workspace_id,status_code)
            SELECT @organization,u.id,left(u.email,100),true,@method,'desktop/project-management/workspace-invitations',
                'project_management','workspace_invitation',@invite,@action,@description,@workspace,200
            FROM public.users u WHERE u.id=@actor RETURNING id",db,tx);
        SetBranch(audit);
        audit.Parameters.AddWithValue("actor",actor);
        audit.Parameters.AddWithValue("workspace",workspace);
        audit.Parameters.AddWithValue("invite",invitation);
        audit.Parameters.AddWithValue("action",action);
        audit.Parameters.AddWithValue("method",action == "PMS_INVITE_REVOKED" ? "DELETE" : "POST");
        audit.Parameters.AddWithValue("description",description);
        var auditId = (int)(await audit.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db,tx,"audit_logs",auditId,cancellation);
    }

    private static void RequireInvitationManager(string role)
    {
        if (role is not ("Owner" or "Admin"))
            throw new UnauthorizedAccessException("Workspace owner or administrator access is required.");
    }

    private static string CreateInvitationHash()
    {
        var bytes = new byte[32];
        using var random = RandomNumberGenerator.Create();
        using var sha = SHA256.Create();
        random.GetBytes(bytes);
        return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
    }
}

