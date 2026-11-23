using System.Data;
using Npgsql;

namespace Business_Suite;

internal sealed record SalesOrderOverview(string Number, string Title, string Status, string Currency, decimal Subtotal,
    decimal Discount, decimal Tax, decimal Total, string? Customer, DateTime? Starts, DateTime? Ends, string Terms,
    bool CanCancel, bool CanClose);

internal sealed partial class SalesOrderRepository
{
    internal async Task<SalesOrderOverview> LoadSalesOrderOverviewAsync(int order)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to view sales order details.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor);
        using var query = ScopedCommand(@"
            SELECT o.order_number,o.title,coalesce(o.status,''),coalesce(o.currency,''),coalesce(o.subtotal,0),
                coalesce(o.discount_amount,0),coalesce(o.tax_amount,0),coalesce(o.total_amount,0),
                CASE WHEN EXISTS (SELECT 1 FROM public.srm_anonymous_cash_accounts a WHERE a.customer_id=o.customer_id
                    AND a.organization_id=@company AND a.branch_id=@branch AND a.pack_context_id IS NULL)
                    THEN 'Walk-in'
                    ELSE (SELECT c.name FROM public.crm_companies c " + OrderCustomerScope + @" AND c.id=o.customer_id)
                END, o.expected_start_date,o.expected_end_date,coalesce(o.terms,'')
            FROM public.srm_sales_orders o" + OrderDetailScope + " AND o.id=@order", db, tx, branch, actor, scope);
        query.Parameters.AddWithValue("order", order);
        SalesOrderOverview detail;
        using (var row = await query.ExecuteReaderAsync())
        {
            if (!await row.ReadAsync())
                throw new InvalidOperationException("The Sales order is unavailable in this branch.");
            detail = new SalesOrderOverview(row.GetString(0), row.GetString(1), row.GetString(2), row.GetString(3),
                row.GetDecimal(4), row.GetDecimal(5), row.GetDecimal(6), row.GetDecimal(7),
                row.IsDBNull(8) ? null : row.GetString(8), row.IsDBNull(9) ? null : row.GetDateTime(9),
                row.IsDBNull(10) ? null : row.GetDateTime(10), row.GetString(11), false, false);
        }
        if (CanTransitionSalesOrder(detail.Status, "cancelled"))
        {
            try
            {
                string lifecycleScope = await SalesOrderLifecycleScopeAsync(db, tx, branch, actor);
                var editable = await ReadApprovalOrderAsync(db, tx, branch, actor, lifecycleScope, order, lockRow: false);
                if (editable is not null)
                    detail = detail with { CanCancel = true, CanClose = CanTransitionSalesOrder(detail.Status, "closed") };
            }
            catch (UnauthorizedAccessException) { }
        }
        tx.Commit();
        return detail;
    }

    internal async Task ChangeSalesOrderLifecycleAsync(int order, string expectedStatus, bool close)
    {
        if (order < 1)
            throw new ArgumentException("Select a Sales order.");
        string target = close ? "closed" : "cancelled";
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to update the Sales order.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await SalesOrderLifecycleScopeAsync(db, tx, branch, actor);
        var current = await ReadApprovalOrderAsync(db, tx, branch, actor, scope, order, lockRow: true) ??
            throw new InvalidOperationException("This commercial Sales order is unavailable in the selected branch.");
        if (current.Status == target)
        {
            tx.Commit();
            return;
        }
        if (current.Status != expectedStatus || !CanTransitionSalesOrder(current.Status, target))
            throw new InvalidOperationException("The Sales order status changed or does not support this action. Reload the order.");
        using var write = RegisterCommand(@"
            WITH changed AS (
                UPDATE public.srm_sales_orders SET status=@target,updated_at=now()
                WHERE id=@order AND organization_id=@company AND status=@old AND deleted_at IS NULL RETURNING id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,before_json,after_json)
                SELECT @company,'sales_order',id,@target,@actor,json_build_object('status',@old),json_build_object('status',@target)
                FROM changed RETURNING id
            )
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit", db, tx, branch, actor.Id);
        write.Parameters.AddWithValue("order", order);
        write.Parameters.AddWithValue("old", current.Status);
        write.Parameters.AddWithValue("target", target);
        if (await write.ExecuteNonQueryAsync() != 1)
            throw new InvalidOperationException("The Sales order change and its audit could not both be saved.");
        tx.Commit();
    }

    private async Task<string> SalesOrderLifecycleScopeAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor)
    {
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "Sales order lifecycle actions");
        return await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "create");
    }

    private static bool CanTransitionSalesOrder(string from, string to) => to == "closed"
        ? from == "confirmed"
        : from is "draft" or "pending_approval" or "approved" or "confirmed";
}
