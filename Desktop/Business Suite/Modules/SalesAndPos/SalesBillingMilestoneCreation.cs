using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    internal async Task<int> CreateSalesBillingMilestoneAsync(int order, int engagement, int plan, string name,
        decimal amount, DateTime? due, Guid request)
    {
        name = name.Trim();
        due = due?.Date;
        if (plan < 1 || request == Guid.Empty || name.Length is < 1 or > 180 || name.Any(char.IsControl))
            throw new ArgumentException("Enter a milestone name from 1 to 180 characters.");
        if (amount < 0 || amount > MaximumOrderMoney || decimal.Round(amount, 2) != amount)
            throw new ArgumentException("Enter a nonnegative milestone amount with at most two decimal places.");

        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose the billing plan branch.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "billing milestone creation");
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "create");
        using (var read = ScopedCommand("SELECT b.id" + SalesBillingPlanChain + SalesBillingPlanScope +
            " AND b.id=@plan FOR UPDATE OF o,e,b", db, tx, branch, actor, scope))
        {
            BindBillingMilestoneChain(read, order, engagement, plan);
            if (await read.ExecuteScalarAsync() is not int)
                throw new InvalidOperationException("The billing plan is unavailable for this engagement and branch.");
        }

        string digest = HashSalesPayload(new { plan, name, amount, due });
        using (var previous = RegisterCommand(@"
            SELECT a.entity_id,coalesce(a.after_json->'metadata_json'->>'desktop_create_sha256'=@hash,false)
                AND EXISTS(SELECT 1 FROM public.srm_billing_milestones m WHERE m.id=a.entity_id AND m.billing_plan_id=@plan AND " +
                ConfirmationOwnership("m", "srm_billing_milestones") + @")
            FROM public.srm_audit_logs a WHERE a.organization_id=@company AND a.actor_user_id=@actor
                AND a.entity_type='billing_milestone' AND a.action='created'
                AND a.after_json->>'billing_plan_id'=@plan::text
                AND a.after_json->'metadata_json'->>'desktop_create_request'=@request
                AND " + ConfirmationOwnership("a", "srm_audit_logs"), db, tx, branch, actor.Id))
        {
            previous.Parameters.AddWithValue("plan", plan);
            previous.Parameters.AddWithValue("request", request.ToString());
            previous.Parameters.AddWithValue("hash", digest);
            int? found = null;
            using (var rows = await previous.ExecuteReaderAsync())
            {
                if (await rows.ReadAsync())
                {
                    if (!rows.GetBoolean(1))
                        throw new InvalidOperationException("This request was already used for another milestone or its scope changed.");
                    found = rows.GetInt32(0);
                    if (await rows.ReadAsync())
                        throw new InvalidOperationException("More than one milestone matches this request.");
                }
            }
            if (found.HasValue)
            {
                tx.Commit();
                return found.Value;
            }
        }

        using var write = RegisterCommand(@"
            WITH updated AS (
                UPDATE public.srm_billing_plans SET total_amount=coalesce(total_amount,0)+@amount,updated_at=now()
                WHERE id=@plan AND organization_id=@company AND abs(coalesce(total_amount,0)+@amount)<=@max RETURNING id
            ), milestone AS (
                INSERT INTO public.srm_billing_milestones (billing_plan_id,name,status,due_date,amount,metadata_json)
                SELECT id,@name,'pending',@due,@amount,json_build_object('desktop_create_request',@request,'desktop_create_sha256',@hash)
                FROM updated RETURNING *
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'billing_milestone',id,'created',@actor,row_to_json(milestone) FROM milestone RETURNING id
            ), owned AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'srm_billing_milestones',id::text,@company,@branch,'validated-write' FROM milestone
                UNION ALL SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit RETURNING resource_key
            )
            SELECT id FROM milestone WHERE (SELECT count(*) FROM owned)=2", db, tx, branch, actor.Id);
        write.Parameters.AddWithValue("plan", plan);
        write.Parameters.AddWithValue("name", name);
        write.Parameters.AddWithValue("amount", amount);
        write.Parameters.AddWithValue("max", MaximumOrderMoney);
        write.Parameters.AddWithValue("due", NpgsqlDbType.Date, (object?)due ?? DBNull.Value);
        write.Parameters.AddWithValue("request", request.ToString());
        write.Parameters.AddWithValue("hash", digest);
        if (await write.ExecuteScalarAsync() is not int saved)
            throw new InvalidOperationException("The milestone and plan total could not be saved. Review the plan's amount limit.");
        tx.Commit();
        return saved;
    }
}
