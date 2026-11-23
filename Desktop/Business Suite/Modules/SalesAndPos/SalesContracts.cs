using Npgsql;

namespace Business_Suite;

internal sealed record SalesContractRow(int Id, string Number, string Title, string Status, string Kind,
    string Currency, decimal Value, DateTime? Effective, DateTime? Expiry, string Terms, string Revision);

internal sealed partial class SalesOrderRepository
{
    private const string ContractOrderChain = @" FROM public.srm_sales_orders o
        JOIN public.srm_contracts c ON c.sales_order_id=o.id ";
    private static string LinkedContractScope => OrderScope + @" AND o.id=@order
        AND o.metadata_json->>'source' IS DISTINCT FROM 'pos'
        AND c.organization_id=@company AND c.deleted_at IS NULL AND " + ConfirmationOwnership("c", "srm_contracts");

    internal Task<List<SalesContractRow>> SalesContractsAsync(int order) => ReadAsync(@"
        SELECT c.id,c.contract_number,c.title,coalesce(c.status,''),coalesce(c.contract_type,''),
            coalesce(c.currency,''),coalesce(c.contract_value,0),c.effective_date,c.expiry_date,coalesce(c.terms,''),c.xmin::text" +
        ContractOrderChain + LinkedContractScope + " ORDER BY c.id", query => query.Parameters.AddWithValue("order", order),
        row => new SalesContractRow(row.GetInt32(0), row.GetString(1), row.GetString(2), row.GetString(3),
            row.GetString(4), row.GetString(5), row.GetDecimal(6), row.IsDBNull(7) ? null : row.GetDateTime(7),
            row.IsDBNull(8) ? null : row.GetDateTime(8), row.GetString(9), row.GetString(10)));

    internal async Task<string> ChangeSalesContractAsync(int order, int contract, string expected, string target)
    {
        if (order <= 0 || contract <= 0 || target is not ("active" or "expired" or "renewed" or "terminated"))
            throw new ArgumentException("Select a saved contract and a valid action.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to manage the contract.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "Sales contract status");
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "create");
        using var read = ScopedCommand("SELECT coalesce(c.status,'')" + ContractOrderChain + LinkedContractScope +
            " AND c.id=@id FOR UPDATE OF o,c", db, tx, branch, actor, scope);
        read.Parameters.AddWithValue("order", order);
        read.Parameters.AddWithValue("id", contract);
        if (await read.ExecuteScalarAsync() is not string current)
            throw new InvalidOperationException("The linked contract is unavailable in this branch.");
        if (current == target)
        {
            tx.Commit();
            return current;
        }
        if (current != expected || !IsContractTransition(current, target))
            throw new InvalidOperationException("The contract status changed or cannot take this action. Reload the contract.");

        using var write = RegisterCommand(@"
            WITH changed AS (
                UPDATE public.srm_contracts SET status=@target,updated_at=now(),
                    approved_by=CASE WHEN @target='active' THEN @actor ELSE approved_by END
                WHERE organization_id=@company AND id=@id AND sales_order_id=@order AND status=@before AND deleted_at IS NULL
                RETURNING id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,before_json,after_json)
                SELECT @company,'contract',id,@action,@actor,json_build_object('status',@before),
                    json_build_object('status',@target) FROM changed RETURNING id
            )
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit", db, tx, branch, actor.Id);
        write.Parameters.AddWithValue("id", contract);
        write.Parameters.AddWithValue("order", order);
        write.Parameters.AddWithValue("before", current);
        write.Parameters.AddWithValue("target", target);
        write.Parameters.AddWithValue("action", target == "active" ? "activated" : target);
        if (await write.ExecuteNonQueryAsync() != 1)
            throw new InvalidOperationException("The contract and its lifecycle audit could not both be saved.");
        tx.Commit();
        return target;
    }

    internal static bool IsContractTransition(string from, string target) => (from, target) switch
    {
        ("draft" or "under_review" or "renewed", "active" or "terminated") => true,
        ("active", "expired" or "terminated" or "renewed") => true,
        ("expired", "renewed") => true,
        _ => false
    };
}
