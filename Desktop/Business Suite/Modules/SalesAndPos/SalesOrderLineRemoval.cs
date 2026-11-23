using Npgsql;

namespace Business_Suite;

internal sealed record RemovableSalesLine(int Id, string Code, string Description, decimal Quantity, decimal Total,
    string Revision);

internal sealed partial class SalesOrderRepository
{
    private static readonly string MutableSalesItemsOrder = OrderScope + @"
        AND o.id=@order AND o.status IN ('draft','pending_approval')
        AND o.metadata_json->>'source' IS DISTINCT FROM 'pos'
        AND NOT EXISTS (SELECT 1 FROM public.srm_anonymous_cash_accounts a WHERE a.customer_id=o.customer_id)
        AND NOT EXISTS (SELECT 1 FROM public.srm_invoices i WHERE i.sales_order_id=o.id)
        AND NOT EXISTS (SELECT 1 FROM public.srm_invoice_drafts i WHERE i.sales_order_id=o.id)
        AND NOT EXISTS (SELECT 1 FROM public.srm_pos_service_checkouts g WHERE g.sales_order_id=o.id)
        AND NOT EXISTS (SELECT 1 FROM public.srm_sales_order_lines line WHERE line.sales_order_id=o.id
            AND NOT (" + ConfirmationOwnership("line", "srm_sales_order_lines") + @"))";

    private const string SalesLineRevision = "md5((to_jsonb(o)||jsonb_build_object('lines', " +
        "(SELECT jsonb_agg(to_jsonb(current_line) ORDER BY current_line.id) FROM public.srm_sales_order_lines current_line " +
        "WHERE current_line.sales_order_id=o.id)))::text)";

    internal Task<List<RemovableSalesLine>> RemovableSalesLinesAsync(int order) => ReadAsync(@"
        SELECT l.id,coalesce(l.item_code,''),coalesce(l.description,''),coalesce(l.quantity,0),
            coalesce(l.line_total,coalesce(l.quantity,0)*coalesce(l.unit_price,0)-coalesce(l.discount_amount,0)+coalesce(l.tax_amount,0)),
            " + SalesLineRevision + @"
        FROM public.srm_sales_orders o JOIN public.srm_sales_order_lines l ON l.sales_order_id=o.id" +
        MutableSalesItemsOrder + " ORDER BY l.id", command => command.Parameters.AddWithValue("order", order),
        row => new RemovableSalesLine(row.GetInt32(0), row.GetString(1), row.GetString(2), row.GetDecimal(3), row.GetDecimal(4),
            row.GetString(5)), "delete");

    internal async Task RemoveSalesOrderLineAsync(int order, int line, string revision)
    {
        if (order < 1 || line < 1 || revision.Length != 32)
            throw new ArgumentException("Select a saved order item and refresh the list before removing it.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select the order branch before removing an item.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "delete");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "sales order item removal");
        var current = await LockSalesOrderItemsAsync(db, tx, branch, actor, scope, order);
        if (current.Revision != revision)
            throw new InvalidOperationException("The saved order or its items changed. Reload the items before removing.");

        using var write = RegisterCommand(@"
            WITH removed AS (
                DELETE FROM public.srm_sales_order_lines l WHERE l.id=@line AND l.sales_order_id=@order
                    AND " + ConfirmationOwnership("l", "srm_sales_order_lines") + @"
                    AND NOT EXISTS (SELECT 1 FROM public.srm_pos_return_lines WHERE sales_order_line_id=l.id)
                    AND NOT EXISTS (SELECT 1 FROM public.srm_pos_checkout_lines WHERE sales_order_line_id=l.id)
                    AND NOT EXISTS (SELECT 1 FROM public.service_follow_ups WHERE order_line_id=l.id)
                    AND NOT EXISTS (SELECT 1 FROM public.srm_invoice_lines lon WHERE lon.source_type='sales_order_line' AND lon.source_id=l.id)
                    AND NOT EXISTS (SELECT 1 FROM public.srm_billing_milestones m WHERE m.metadata_json->>'sales_order_line_id'=l.id::text)
                RETURNING l.*
            ), totals AS (
                SELECT coalesce(sum(coalesce(quantity,0)*coalesce(unit_price,0)),0) AS gross,
                    coalesce(sum(discount_amount),0) AS discount,coalesce(sum(tax_amount),0) AS tax,
                    coalesce(sum(coalesce(line_total,coalesce(quantity,0)*coalesce(unit_price,0)-coalesce(discount_amount,0)+coalesce(tax_amount,0))),0) AS total
                FROM public.srm_sales_order_lines WHERE sales_order_id=@order AND id<>@line
            ), updated AS (
                UPDATE public.srm_sales_orders o SET subtotal=totals.gross,discount_amount=totals.discount,
                    tax_amount=totals.tax,total_amount=totals.total,updated_at=now()
                FROM totals WHERE o.id=@order AND o.organization_id=@company AND EXISTS (SELECT 1 FROM removed)
                RETURNING o.id
            ), old_ownership AS (
                DELETE FROM public.suite_branch_ownership b USING removed
                WHERE b.company_id=@company AND b.branch_id=@branch AND b.resource_table='srm_sales_order_lines'
                    AND b.resource_key=removed.id::text
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,before_json)
                SELECT @company,'sales_order_line',removed.id,'deleted',@actor,row_to_json(removed)
                FROM removed JOIN updated ON updated.id=removed.sales_order_id RETURNING id
            )
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit", db, tx, branch, actor.Id);
        write.Parameters.AddWithValue("line", line);
        write.Parameters.AddWithValue("order", order);
        if (await write.ExecuteNonQueryAsync() != 1)
            throw new InvalidOperationException("This item is unavailable or already linked to another saved record.");
        tx.Commit();
    }

    private async Task<SalesOrderItemsSnapshot> LockSalesOrderItemsAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        DesktopActor actor, string scope, int order)
    {
        using (var source = ScopedCommand("SELECT o.id FROM public.srm_sales_orders o" + MutableSalesItemsOrder +
            " FOR UPDATE OF o", db, tx, branch, actor, scope))
        {
            source.Parameters.AddWithValue("order", order);
            if (await source.ExecuteScalarAsync() is not int)
                throw new InvalidOperationException("Only an authorized draft or pending Sales order without an invoice can change items.");
        }
        using (var lockLines = RegisterCommand("SELECT id FROM public.srm_sales_order_lines WHERE sales_order_id=@order " +
            "ORDER BY id FOR UPDATE NOWAIT", db, tx, branch, actor.Id))
        {
            lockLines.Parameters.AddWithValue("order", order);
            try { await lockLines.ExecuteNonQueryAsync(); }
            catch (PostgresException error) when (error.SqlState == PostgresErrorCodes.LockNotAvailable)
            {
                throw new InvalidOperationException("Another user is editing this order. Reload the items and retry.", error);
            }
        }
        using var prove = ScopedCommand(SalesItemsSnapshotQuery, db, tx, branch, actor, scope);
        prove.Parameters.AddWithValue("order", order);
        using var rows = await prove.ExecuteReaderAsync();
        if (!await rows.ReadAsync())
            throw new InvalidOperationException("The saved order or its items changed. Reload the items.");
        return new SalesOrderItemsSnapshot(rows.GetString(0), rows.GetString(1));
    }
}
