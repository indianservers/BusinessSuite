using Npgsql;

namespace Business_Suite;

internal sealed record SalesOrderArchivePreview(int Id, string Number, string Revision);

internal sealed partial class SalesOrderRepository
{
    private const string NativeArchiveOrder = OrderDetailScope +
        " AND o.metadata_json->>'source' IS DISTINCT FROM 'pos' AND o.id=@order";
    private const string ArchiveDependenciesClear = @"
        AND NOT EXISTS(SELECT 1 FROM public.srm_invoices i WHERE i.sales_order_id=o.id)
        AND NOT EXISTS(SELECT 1 FROM public.srm_invoice_drafts d WHERE d.sales_order_id=o.id)
        AND NOT EXISTS(SELECT 1 FROM public.srm_contracts c WHERE c.sales_order_id=o.id)
        AND NOT EXISTS(SELECT 1 FROM public.srm_engagements e WHERE e.sales_order_id=o.id)
        AND NOT EXISTS(SELECT 1 FROM public.srm_pos_service_checkouts p WHERE p.sales_order_id=o.id)
        AND NOT EXISTS(SELECT 1 FROM public.srm_anonymous_cash_accounts a WHERE a.customer_id=o.customer_id)";

    internal async Task<SalesOrderArchivePreview> LoadSalesOrderArchiveAsync(int order)
    {
        var rows = await ReadAsync("SELECT o.id,o.order_number," + SalesLineRevision +
            " FROM public.srm_sales_orders o" + NativeArchiveOrder + ArchiveDependenciesClear +
            " AND o.deleted_at IS NULL AND lower(o.status) IN ('draft','created','planned')",
            query => query.Parameters.AddWithValue("order", order),
            row => new SalesOrderArchivePreview(row.GetInt32(0), row.GetString(1), row.GetString(2)), "delete");
        return rows.SingleOrDefault() ?? throw new InvalidOperationException("Only a scoped draft order without linked commercial records can be removed.");
    }

    internal async Task ArchiveSalesOrderAsync(SalesOrderArchivePreview original, string reason, Guid request)
    {
        reason = reason.Trim();
        if (reason.Length is < 5 or > 500 || reason.IndexOf('\0') >= 0 || request == Guid.Empty)
            throw new ArgumentException("Enter a meaningful archive reason of 5 to 500 characters.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose the Sales order branch.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "Sales order archive");
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "delete");
        using (var source = ScopedCommand("SELECT o.id FROM public.srm_sales_orders o" + NativeArchiveOrder +
            " FOR UPDATE OF o", db, tx, branch, actor, scope))
        {
            source.Parameters.AddWithValue("order", original.Id);
            if (await source.ExecuteScalarAsync() is not int)
                throw new InvalidOperationException("The Sales order is unavailable in this branch.");
        }
        using (var replay = RegisterCommand(@"SELECT a.after_json->>'reason'=@reason FROM public.srm_audit_logs a
            WHERE a.organization_id=@company AND a.actor_user_id=@actor AND a.entity_type='sales_order'
                AND a.entity_id=@order AND a.action='draft_removed' AND a.after_json->>'request_id'=@request AND " +
            ConfirmationOwnership("a", "srm_audit_logs"), db, tx, branch, actor.Id))
        {
            replay.Parameters.AddWithValue("order", original.Id);
            replay.Parameters.AddWithValue("request", request.ToString());
            replay.Parameters.AddWithValue("reason", reason);
            if (await replay.ExecuteScalarAsync() is bool matched)
            {
                if (!matched)
                    throw new InvalidOperationException("The archive request used a different reason.");
                tx.Commit();
                return;
            }
        }
        using (var lines = RegisterCommand("SELECT " + ConfirmationOwnership("l", "srm_sales_order_lines") +
            " FROM public.srm_sales_order_lines l WHERE l.sales_order_id=@order ORDER BY l.id FOR UPDATE OF l NOWAIT",
            db, tx, branch, actor.Id))
        {
            lines.Parameters.AddWithValue("order", original.Id);
            using var rows = await lines.ExecuteReaderAsync();
            while (await rows.ReadAsync())
                if (!rows.GetBoolean(0))
                    throw new InvalidOperationException("The order contains saved lines outside this branch.");
        }

        using var archive = ScopedCommand(@"
            WITH retained AS (
                SELECT o.id,to_jsonb(o)||jsonb_build_object('lines',coalesce(
                    (SELECT jsonb_agg(to_jsonb(l) ORDER BY l.id) FROM public.srm_sales_order_lines l WHERE l.sales_order_id=o.id),'[]'::jsonb)) AS before
                FROM public.srm_sales_orders o" + NativeArchiveOrder + ArchiveDependenciesClear +
                " AND o.deleted_at IS NULL AND lower(o.status) IN ('draft','created','planned') AND " + SalesLineRevision + @"=@version
            ), archived AS (
                UPDATE public.srm_sales_orders o SET deleted_at=now(),status='archived',updated_at=now()
                FROM retained r WHERE o.id=r.id RETURNING o.id,r.before
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,before_json,after_json)
                SELECT @company,'sales_order',id,'draft_removed',@actor,before::json,
                    json_build_object('record',json_build_object('retained',true,'status','archived'),'reason',@reason,'request_id',@request)
                FROM archived RETURNING id
            )
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit", db, tx, branch, actor, scope);
        archive.Parameters.AddWithValue("order", original.Id);
        archive.Parameters.AddWithValue("reason", reason);
        archive.Parameters.AddWithValue("request", request.ToString());
        archive.Parameters.AddWithValue("version", original.Revision);
        if (await archive.ExecuteNonQueryAsync() != 1)
            throw new InvalidOperationException("The draft changed or gained a linked commercial record. Refresh before removing it.");
        tx.Commit();
    }
}
