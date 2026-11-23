using Npgsql;

namespace Business_Suite;

internal sealed record SalesBillingPlanRow(int Id, string Name, string Type, string Status, string Currency, decimal Total, string Rule);
internal sealed record SalesBillingMilestoneRow(int Id, string Name, string Status, DateTime? DueDate, decimal Amount, bool Invoiced);

internal sealed partial class SalesOrderRepository
{
    private const string SalesBillingPlanChain = @" FROM public.srm_sales_orders o
        JOIN public.srm_engagements e ON e.sales_order_id=o.id JOIN public.srm_billing_plans b ON b.engagement_id=e.id ";
    private static string SalesBillingPlanScope => NativeSalesEngagementScope + " AND e.id=@engagement AND b.organization_id=@company AND " +
        ConfirmationOwnership("b", "srm_billing_plans");

    internal Task<List<SalesBillingPlanRow>> SalesBillingPlansAsync(int order, int engagement) => ReadAsync(@"
        SELECT b.id,b.name,coalesce(b.billing_type,''),coalesce(b.status,''),coalesce(b.currency,''),coalesce(b.total_amount,0),
            coalesce(b.recurrence_rule,'')" +
        SalesBillingPlanChain + SalesBillingPlanScope + " ORDER BY b.id", query =>
        {
            query.Parameters.AddWithValue("order", order);
            query.Parameters.AddWithValue("engagement", engagement);
        }, row => new SalesBillingPlanRow(row.GetInt32(0), row.GetString(1), row.GetString(2), row.GetString(3),
            row.GetString(4), row.GetDecimal(5), row.GetString(6)));

    internal Task<List<SalesBillingMilestoneRow>> SalesBillingMilestonesAsync(int order, int engagement, int plan) =>
        ReadSalesBillingMilestonesAsync(order, engagement, plan, null, null);

    internal async Task<string> AdvanceSalesBillingPlanAsync(int order, int engagement, int plan, string expected, string target)
    {
        if (order <= 0 || engagement <= 0 || plan <= 0 || target is not ("active" or "paused" or "completed" or "cancelled"))
            throw new ArgumentException("Select a linked billing plan and a valid action.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose the billing plan branch.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "billing plan lifecycle");
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "create");
        using var read = ScopedCommand("SELECT coalesce(b.status,'')" + SalesBillingPlanChain + SalesBillingPlanScope +
            " AND b.id=@plan FOR UPDATE OF o,e,b", db, tx, branch, actor, scope);
        read.Parameters.AddWithValue("order", order);
        read.Parameters.AddWithValue("engagement", engagement);
        read.Parameters.AddWithValue("plan", plan);
        if (await read.ExecuteScalarAsync() is not string current)
            throw new InvalidOperationException("The billing plan is unavailable for this engagement and branch.");
        if (current == target)
        {
            tx.Commit();
            return current;
        }
        if (current != expected || !IsBillingPlanTransition(current, target))
            throw new InvalidOperationException("Billing plan status changed or does not support that action. Reload the plan.");
        using var write = RegisterCommand(@"
            WITH changed AS (
                UPDATE public.srm_billing_plans SET status=@target,updated_at=now()
                WHERE id=@plan AND engagement_id=@engagement AND organization_id=@company AND status=@before
                RETURNING id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,before_json,after_json)
                SELECT @company,'billing_plan',id,@action,@actor,json_build_object('status',@before),
                    json_build_object('status',@target) FROM changed RETURNING id
            )
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit", db, tx, branch, actor.Id);
        write.Parameters.AddWithValue("engagement", engagement);
        write.Parameters.AddWithValue("plan", plan);
        write.Parameters.AddWithValue("before", current);
        write.Parameters.AddWithValue("target", target);
        write.Parameters.AddWithValue("action", target == "active" ? "activated" : target);
        if (await write.ExecuteNonQueryAsync() != 1)
            throw new InvalidOperationException("The plan status and audit could not both be saved.");
        tx.Commit();
        return target;
    }

    internal static bool IsBillingPlanTransition(string from, string to) => (from, to) switch
    {
        ("draft", "active" or "cancelled") => true,
        ("active", "paused" or "completed" or "cancelled") => true,
        ("paused", "active" or "cancelled") => true,
        _ => false
    };
}
