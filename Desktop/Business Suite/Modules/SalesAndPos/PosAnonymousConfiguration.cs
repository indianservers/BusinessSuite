using System.Data;
using Npgsql;

namespace Business_Suite;

internal sealed record PosAnonymousConfiguration(int Id, string Label, string Country, int Revision, bool Enabled, int CustomerId);

internal sealed partial class SalesOrderRepository
{
    internal async Task<PosAnonymousConfiguration?> LoadPosAnonymousConfigurationAsync()
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to view the counter account.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor);
        await RequireNativeRegisterBranchAsync(db, tx, branch, "counter account settings");
        var account = await ReadPosAnonymousConfigurationAsync(db, tx, branch, actor.Id, false);
        tx.Commit();
        return account;
    }

    internal async Task<PosAnonymousConfiguration> SetPosAnonymousStatusAsync(int revision, bool enabled, string reason)
    {
        reason = reason.Trim();
        if (revision < 1 || reason.Length is < 8 or > 1000)
            throw new ArgumentException("Enter a reason of 8 to 1,000 characters and reload the account revision.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to configure the counter account.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if ((!actor.IsSuperuser && !actor.IsCompanyAdmin) || !actor.CanWriteBranch)
            throw new UnauthorizedAccessException("A company administrator with branch write access is required.");
        await RequireRegisterWriterAsync(db, tx, branch, actor);
        await RequireNativeRegisterBranchAsync(db, tx, branch, "counter account settings");
        var current = await ReadPosAnonymousConfigurationAsync(db, tx, branch, actor.Id, true);
        if (current is null || current.Revision != revision)
            throw new InvalidOperationException("Counter account revision changed. Reload the settings.");
        if (enabled && await ResolveAnonymousCheckoutBuyerAsync(db, tx, branch, actor.Id, lockRows: true, requireActive: false) is null)
            throw new InvalidOperationException("The account has invalid private ledger details and cannot be enabled.");

        using var write = RegisterCommand(@"
            WITH changed AS (
                UPDATE public.srm_anonymous_cash_accounts SET active=@active,
                    revision=revision+CASE WHEN active IS DISTINCT FROM @active THEN 1 ELSE 0 END,
                    updated_at=CASE WHEN active IS DISTINCT FROM @active THEN now() ELSE updated_at END
                WHERE id=@id AND organization_id=@company AND branch_id=@branch
                    AND pack_context_id IS NULL AND revision=@revision
                RETURNING id,customer_id,revision,active
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'anonymous_cash_account',id,'configured',@actor,
                    json_build_object('id',id,'revision',revision,'active',active,'customer_id',customer_id,'reason',@reason)
                FROM changed RETURNING id
            ), stamped AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit RETURNING resource_key
            )
            SELECT revision FROM changed WHERE (SELECT count(*) FROM stamped)=1", db, tx, branch, actor.Id);
        write.Parameters.AddWithValue("id", current.Id);
        write.Parameters.AddWithValue("revision", revision);
        write.Parameters.AddWithValue("active", enabled);
        write.Parameters.AddWithValue("reason", reason);
        if (await write.ExecuteScalarAsync() is not int savedRevision)
            throw new InvalidOperationException("The counter account and its audit could not both be saved.");
        tx.Commit();
        return current with { Revision = savedRevision, Enabled = enabled };
    }

    private async Task<PosAnonymousConfiguration?> ReadPosAnonymousConfigurationAsync(NpgsqlConnection db,
        NpgsqlTransaction tx, int branch, int actor, bool lockRow)
    {
        using var query = RegisterCommand(@"SELECT a.id,a.account_label,a.jurisdiction_country,a.revision,a.active,
            (" + ConfirmationOwnership("a", "srm_anonymous_cash_accounts") + " AND " +
            ConfirmationOwnership("c", "crm_companies") + @"),a.customer_id
            FROM public.srm_anonymous_cash_accounts a JOIN public.crm_companies c
                ON c.id=a.customer_id AND c.organization_id=@company
            WHERE a.organization_id=@company AND a.branch_id=@branch AND a.pack_context_id IS NULL
                AND a.kind='anonymous_cash'" + (lockRow ? " FOR UPDATE OF a,c" : ""), db, tx, branch, actor);
        using var rows = await query.ExecuteReaderAsync();
        if (!await rows.ReadAsync())
            return null;
        if (!rows.GetBoolean(5))
            throw new InvalidOperationException("The counter account lacks verified branch ownership.");
        return new PosAnonymousConfiguration(rows.GetInt32(0), rows.GetString(1), rows.GetString(2), rows.GetInt32(3),
            rows.GetBoolean(4), rows.GetInt32(6));
    }
}
