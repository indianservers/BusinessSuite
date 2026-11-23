using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    private const string BillingMilestoneProjection = "SELECT m.id,m.name,coalesce(m.status,''),m.due_date,coalesce(m.amount,0)," +
        " (m.invoice_draft_id IS NOT NULL OR coalesce(m.status='invoiced',false))";
    private static string BillingMilestoneSource => SalesBillingPlanChain +
        " JOIN public.srm_billing_milestones m ON m.billing_plan_id=b.id " + SalesBillingPlanScope +
        " AND b.id=@plan AND " + ConfirmationOwnership("m", "srm_billing_milestones");

    internal Task<List<SalesBillingMilestoneRow>> SalesBillingEligibilityAsync(int order, int engagement, int plan,
        DateTime from, DateTime until)
    {
        if (until.Date < from.Date)
            throw new ArgumentException("End date must not precede start date.");
        return ReadSalesBillingMilestonesAsync(order, engagement, plan, from.Date, until.Date);
    }

    private Task<List<SalesBillingMilestoneRow>> ReadSalesBillingMilestonesAsync(int order, int engagement, int plan,
        DateTime? from, DateTime? until) => ReadAsync(BillingMilestoneProjection + BillingMilestoneSource + @"
        AND (@from IS NULL OR (e.status NOT IN ('closed','cancelled') AND b.status='active'
            AND m.invoice_draft_id IS NULL AND m.status IN ('approved','ready','completed') AND m.due_date BETWEEN @from AND @until))
        ORDER BY m.due_date NULLS LAST,m.id", query =>
        {
            BindBillingMilestoneChain(query, order, engagement, plan);
            query.Parameters.AddWithValue("from", NpgsqlDbType.Date, (object?)from ?? DBNull.Value);
            query.Parameters.AddWithValue("until", NpgsqlDbType.Date, (object?)until ?? DBNull.Value);
        }, ReadBillingMilestone);

    internal Task AmendSalesBillingMilestoneAsync(int order, int engagement, int plan, SalesBillingMilestoneRow original,
        decimal amount, DateTime? due, string reason)
    {
        reason = reason.Trim();
        if (amount < 0 || amount > MaximumOrderMoney || decimal.Round(amount, 2) != amount || reason.Length is < 1 or > 1000)
            throw new ArgumentException("Enter a nonnegative amount with at most two decimals and an amendment reason.");
        return ChangeSalesBillingMilestoneAsync(order, engagement, plan, original, amount, due?.Date, reason, false);
    }

    internal Task ApproveSalesBillingMilestoneAsync(int order, int engagement, int plan, SalesBillingMilestoneRow original) =>
        ChangeSalesBillingMilestoneAsync(order, engagement, plan, original, original.Amount, original.DueDate, "", true);

    private async Task ChangeSalesBillingMilestoneAsync(int order, int engagement, int plan, SalesBillingMilestoneRow original,
        decimal amount, DateTime? due, string reason, bool approve)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose the billing milestone branch.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "billing milestones");
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor,
            approve ? "approve" : "edit");
        using var read = ScopedCommand(BillingMilestoneProjection + ",to_jsonb(m)::text " + BillingMilestoneSource +
            " AND m.id=@milestone AND e.status NOT IN ('closed','cancelled') FOR UPDATE OF o,e,b,m", db, tx, branch, actor, scope);
        BindBillingMilestoneChain(read, order, engagement, plan);
        read.Parameters.AddWithValue("milestone", original.Id);
        SalesBillingMilestoneRow current;
        string before;
        using (var rows = await read.ExecuteReaderAsync())
        {
            if (!await rows.ReadAsync())
                throw new InvalidOperationException("The milestone is unavailable, or its engagement is closed or cancelled.");
            current = ReadBillingMilestone(rows);
            before = rows.GetString(6);
        }
        if (current.Invoiced)
            throw new InvalidOperationException("An invoiced milestone cannot be amended or approved.");
        if (current.Amount != original.Amount || current.DueDate != original.DueDate)
            throw new InvalidOperationException("Milestone amount or due date changed. Reload before saving.");
        if (approve && current.Status == "approved")
        {
            tx.Commit();
            return;
        }
        using var write = RegisterCommand(@"
            WITH plan AS (
                UPDATE public.srm_billing_plans b SET total_amount=coalesce(b.total_amount,0)+@difference,updated_at=now()
                WHERE b.id=@plan AND b.organization_id=@company AND NOT @approve
                    AND abs(coalesce(b.total_amount,0)+@difference)<=@maximum RETURNING b.id
            ), changed AS (
                UPDATE public.srm_billing_milestones SET status=CASE WHEN @approve THEN 'approved' ELSE 'pending' END,
                    amount=CASE WHEN @approve THEN amount ELSE @amount END,
                    due_date=CASE WHEN @approve THEN due_date ELSE @due END
                WHERE id=@milestone AND billing_plan_id=@plan AND (@approve OR EXISTS (SELECT 1 FROM plan))
                RETURNING id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,before_json,after_json)
                SELECT @company,'billing_milestone',id,CASE WHEN @approve THEN 'approved' ELSE 'amended' END,@actor,
                    CASE WHEN @approve THEN json_build_object('status',@oldstatus) ELSE @before END,
                    CASE WHEN @approve THEN json_build_object('status','approved')
                        ELSE json_build_object('status','pending','amount',@amount::text,'due_date',@due,'reason',@reason) END
                FROM changed RETURNING id
            )
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit", db, tx, branch, actor.Id);
        write.Parameters.AddWithValue("plan", plan);
        write.Parameters.AddWithValue("milestone", original.Id);
        write.Parameters.AddWithValue("approve", approve);
        write.Parameters.AddWithValue("difference", amount - current.Amount);
        write.Parameters.AddWithValue("maximum", MaximumOrderMoney);
        write.Parameters.AddWithValue("amount", amount);
        write.Parameters.AddWithValue("due", NpgsqlDbType.Date, (object?)due ?? DBNull.Value);
        write.Parameters.AddWithValue("oldstatus", current.Status);
        write.Parameters.AddWithValue("before", NpgsqlDbType.Json, before);
        write.Parameters.AddWithValue("reason", reason);
        if (await write.ExecuteNonQueryAsync() != 1)
            throw new InvalidOperationException("The milestone change, plan total and audit could not all be saved.");
        tx.Commit();
    }

    private static void BindBillingMilestoneChain(NpgsqlCommand query, int order, int engagement, int plan)
    {
        query.Parameters.AddWithValue("order", order);
        query.Parameters.AddWithValue("engagement", engagement);
        query.Parameters.AddWithValue("plan", plan);
    }

    private static SalesBillingMilestoneRow ReadBillingMilestone(NpgsqlDataReader row) =>
        new(row.GetInt32(0), row.GetString(1), row.GetString(2), row.IsDBNull(3) ? null : row.GetDateTime(3),
            row.GetDecimal(4), row.GetBoolean(5));
}
