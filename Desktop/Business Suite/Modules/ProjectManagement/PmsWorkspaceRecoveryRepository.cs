using System.Data;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PmsWorkspaceRecoveryPreview(DataTable Records, string Fingerprint, int ActiveCount, bool CanChange);

internal sealed partial class PmsProjectRepository
{
    internal const string ResetWorkspaceConfirmation = "RESET ALL WORKSPACES";

    private const string RecoveryWorkspaceScope = @"coalesce(w.organization_id,1)=@organization
        AND (@branch IS NULL OR EXISTS (SELECT 1 FROM public.suite_branch_ownership o
            WHERE o.resource_table='pms_workspaces' AND o.resource_key=w.id::text
                AND o.company_id=@organization AND o.branch_id=@branch))";

    internal async Task<PmsWorkspaceRecoveryPreview> PreviewWorkspaceRecoveryAsync(CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await RequireRecoveryActorAsync(db,tx,false,cancellation);
        using var list = new NpgsqlCommand(@"
            SELECT w.id,w.name,
                (SELECT string_agg(u.email,', ' ORDER BY u.email) FROM public.pms_workspace_members wm
                    JOIN public.users u ON u.id=wm.user_id WHERE wm.workspace_id=w.id AND wm.role='Owner'
                    AND " + WorkspaceMemberScope + @") AS owners,
                a.deleted_at,a.restored_at,a.xmin::text AS revision
            FROM public.pms_workspaces w LEFT JOIN public.pms_workspace_archives a ON a.workspace_id=w.id
            WHERE " + RecoveryWorkspaceScope + @" ORDER BY w.id",db,tx);
        SetBranch(list);
        var rows = await ReadTableAsync(list,cancellation);
        var active = rows.Rows.Cast<DataRow>().Where(row => row.IsNull("deleted_at")).Select(row => row.Field<int>("id")).ToArray();
        return new PmsWorkspaceRecoveryPreview(rows, FingerprintWorkspaceIds(active), active.Length, actor.ModuleCanCreate);
    }

    internal async Task<int> ResetWorkspacesAsync(string confirmation, string fingerprint, CancellationToken cancellation)
    {
        if (confirmation != ResetWorkspaceConfirmation)
            throw new InvalidOperationException($"Type {ResetWorkspaceConfirmation} to confirm.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await RequireRecoveryActorAsync(db,tx,true,cancellation);
        var active = new List<int>();
        using (var lockScope = new NpgsqlCommand(
            "SELECT w.id FROM public.pms_workspaces w WHERE " + RecoveryWorkspaceScope + " ORDER BY w.id FOR UPDATE OF w",
            db, tx))
        {
            SetBranch(lockScope);
            await lockScope.ExecuteNonQueryAsync(cancellation);
        }
        using (var readScope = new NpgsqlCommand(@"
            SELECT w.id FROM public.pms_workspaces w WHERE " + RecoveryWorkspaceScope + @" AND NOT EXISTS (
                SELECT 1 FROM public.pms_workspace_archives a WHERE a.workspace_id=w.id AND a.deleted_at IS NOT NULL)
            ORDER BY w.id",db,tx))
        {
            SetBranch(readScope);
            using var rows = await readScope.ExecuteReaderAsync(cancellation);
            while (await rows.ReadAsync(cancellation))
                active.Add(rows.GetInt32(0));
        }

        if (FingerprintWorkspaceIds(active) != fingerprint)
            throw new InvalidOperationException("The workspace list changed. Refresh the preview before resetting.");
        if (active.Count == 0)
            return 0;
        actor = await RequireRecoveryActorAsync(db,tx,true,cancellation);
        var batch = Guid.NewGuid().ToString("N");
        using var archive = new NpgsqlCommand(@"
            WITH marked AS (
                INSERT INTO public.pms_workspace_archives(workspace_id,deleted_at,deleted_by,batch_key,restored_at)
                SELECT id,(clock_timestamp() AT TIME ZONE 'UTC'),@actor,@batch,NULL FROM unnest(@ids) id
                ON CONFLICT(workspace_id) DO UPDATE SET deleted_at=excluded.deleted_at,deleted_by=excluded.deleted_by,
                    batch_key=excluded.batch_key,restored_at=NULL
                RETURNING workspace_id
            )
            INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
            SELECT 'pms_workspace_archives',workspace_id::text,@organization,@branch,'validated-write'
            FROM marked WHERE @branch IS NOT NULL
            ON CONFLICT(resource_table,resource_key) DO NOTHING",db,tx);
        SetBranch(archive);
        archive.Parameters.AddWithValue("ids",NpgsqlDbType.Array | NpgsqlDbType.Integer,active.ToArray());
        archive.Parameters.AddWithValue("actor",actor.UserId);
        archive.Parameters.AddWithValue("batch",batch);
        await archive.ExecuteNonQueryAsync(cancellation);
        await AuditWorkspaceRecoveryAsync(db,tx,actor.UserId,null,"PMS_WORKSPACE_RESET","Archived workspaces in the selected scope",
            JsonSerializer.Serialize(new { batch, workspace_ids = active }),cancellation);
        await tx.CommitAsync(cancellation);
        return active.Count;
    }

    internal async Task RestoreWorkspaceAsync(int workspace, string revision, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await RequireRecoveryActorAsync(db,tx,true,cancellation);
        using (var scope = new NpgsqlCommand(
            "SELECT w.id FROM public.pms_workspaces w WHERE " + RecoveryWorkspaceScope
            + " AND w.id=@workspace FOR UPDATE OF w", db,tx))
        {
            SetBranch(scope);
            scope.Parameters.AddWithValue("workspace",workspace);
            if (await scope.ExecuteScalarAsync(cancellation) is not int)
                throw new UnauthorizedAccessException("This workspace is outside the selected scope.");
        }
        actor = await RequireRecoveryActorAsync(db,tx,true,cancellation);
        using var restore = new NpgsqlCommand(@"
            UPDATE public.pms_workspace_archives SET deleted_at=NULL,restored_at=(clock_timestamp() AT TIME ZONE 'UTC')
            WHERE workspace_id=@workspace AND deleted_at IS NOT NULL AND xmin::text=@revision RETURNING workspace_id",
            db,tx);
        restore.Parameters.AddWithValue("workspace",workspace);
        restore.Parameters.AddWithValue("revision",revision);
        if (await restore.ExecuteScalarAsync(cancellation) is not int)
            throw new InvalidOperationException("The workspace archive changed. Refresh the preview before restoring.");
        await AuditWorkspaceRecoveryAsync(db,tx,actor.UserId,workspace,"PMS_WORKSPACE_RESTORE","Restored workspace",
            "{}",cancellation);
        await tx.CommitAsync(cancellation);
    }

    private async Task<PmsActor> RequireRecoveryActorAsync(NpgsqlConnection db,NpgsqlTransaction tx,bool write,
        CancellationToken cancellation)
    {
        var actor = await GetWorkspaceActorAsync(db,tx,write,cancellation);
        if (!actor.IsPmsAdmin || (write && !actor.ModuleCanCreate))
            throw new UnauthorizedAccessException("Project Management administrator authority is required for workspace recovery.");
        return actor;
    }

    private async Task AuditWorkspaceRecoveryAsync(NpgsqlConnection db,NpgsqlTransaction tx,int actor,int? workspace,
        string action,string description,string metadata,CancellationToken cancellation)
    {
        using var audit = new NpgsqlCommand(@"
            INSERT INTO public.audit_logs(organization_id,user_id,actor_email,actor_authenticated,method,endpoint,
                module,entity_type,entity_id,action,description,new_values,workspace_id,status_code)
            SELECT @organization,u.id,left(u.email,100),true,'POST','desktop/project-management/workspace-recovery',
                'project_management','workspace',@workspace,@action,@description,@metadata,@workspace,200
            FROM public.users u WHERE u.id=@actor RETURNING id",db,tx);
        SetBranch(audit);
        audit.Parameters.AddWithValue("actor",actor);
        audit.Parameters.Add("workspace",NpgsqlDbType.Integer).Value=(object?)workspace ?? DBNull.Value;
        audit.Parameters.AddWithValue("action",action);
        audit.Parameters.AddWithValue("description",description);
        audit.Parameters.AddWithValue("metadata",metadata);
        var id=(int)(await audit.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db,tx,"audit_logs",id,cancellation);
    }

    private static string FingerprintWorkspaceIds(IEnumerable<int> workspaceIds)
    {
        using var sha = SHA256.Create();
        var json = "[" + string.Join(", ",workspaceIds.OrderBy(id=>id)) + "]";
        return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(json))).Replace("-","").ToLowerInvariant();
    }
}

