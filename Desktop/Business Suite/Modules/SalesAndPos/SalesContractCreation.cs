using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record SalesContractCreated(int Id, string Number);

internal sealed partial class SalesOrderRepository
{
    internal async Task<bool> CanCreateSalesContractAsync(int order)
    {
        try
        {
            var authorized = await ReadAsync("SELECT o.id FROM public.srm_sales_orders o" + ApprovalOrderScope,
                query => query.Parameters.AddWithValue("order", order), row => row.GetInt32(0), "create");
            return authorized.Count == 1;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    internal async Task<SalesContractCreated> CreateSalesContractAsync(int order, SalesContractChanges input, string requestedNumber, Guid request)
    {
        requestedNumber = requestedNumber.Trim();
        if (order <= 0 || request == Guid.Empty || requestedNumber.Length > 80 || requestedNumber.Any(char.IsControl))
            throw new ArgumentException("Select an order and use at most 80 characters for a contract number.");
        var change = NormalizeContractChanges(input);
        string digest = HashSalesPayload(new { change, requestedNumber });
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to create a contract.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "Sales contract creation");
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "create");
        using var source = ScopedCommand("SELECT o.id,o.customer_id FROM public.srm_sales_orders o" + ApprovalOrderScope +
            " FOR UPDATE OF o", db, tx, branch, actor, scope);
        source.Parameters.AddWithValue("order", order);
        int? customer;
        using (var rows = await source.ExecuteReaderAsync())
        {
            if (!await rows.ReadAsync())
                throw new InvalidOperationException("The source Sales order is unavailable in this branch.");
            customer = rows.IsDBNull(1) ? null : rows.GetInt32(1);
        }
        using (var retry = RegisterCommand(@"SELECT c.id,c.contract_number,
                coalesce(a.after_json->>'desktop_sha256'=@hash,false)
            FROM public.srm_audit_logs a JOIN public.srm_contracts c ON c.id=a.entity_id AND c.organization_id=@company
                AND c.deleted_at IS NULL AND c.sales_order_id=@order
            WHERE a.organization_id=@company AND a.actor_user_id=@actor AND a.entity_type='contract' AND a.action='created'
                AND a.after_json->>'desktop_request'=@request AND " + ConfirmationOwnership("c", "srm_contracts") +
                " AND " + ConfirmationOwnership("a", "srm_audit_logs"), db, tx, branch, actor.Id))
        {
            retry.Parameters.AddWithValue("order", order);
            retry.Parameters.AddWithValue("hash", digest);
            retry.Parameters.AddWithValue("request", request.ToString());
            SalesContractCreated? known = null;
            using (var rows = await retry.ExecuteReaderAsync())
            {
                if (await rows.ReadAsync())
                {
                    if (!rows.GetBoolean(2))
                        throw new InvalidOperationException("This request already saved a different contract.");
                    known = new SalesContractCreated(rows.GetInt32(0), rows.GetString(1));
                    if (await rows.ReadAsync())
                        throw new InvalidOperationException("More than one contract matches this request.");
                }
            }
            if (known is not null)
            {
                tx.Commit();
                return known;
            }
        }
        if (customer.HasValue)
        {
            using var buyer = RegisterCommand("SELECT c.id FROM public.crm_companies c" + OrderCustomerScope +
                " AND c.id=@buyer FOR SHARE OF c", db, tx, branch, actor.Id);
            buyer.Parameters.AddWithValue("buyer", customer.Value);
            if (await buyer.ExecuteScalarAsync() is not int)
                throw new InvalidOperationException("The order's customer is unavailable for a contract in this branch.");
        }
        string number = requestedNumber.Length > 0 ? requestedNumber :
            await ReserveCommercialNumberAsync(db, tx, CommercialNumberSeries.Contract);
        using (var taken = RegisterCommand("SELECT 1 FROM public.srm_contracts WHERE organization_id=@company AND contract_number=@number",
            db, tx, branch, actor.Id))
        {
            taken.Parameters.AddWithValue("number", number);
            if (await taken.ExecuteScalarAsync() is int)
                throw new InvalidOperationException("The contract number is already in use.");
        }
        using var write = RegisterCommand(@"
            WITH created AS (
                INSERT INTO public.srm_contracts (organization_id,contract_number,sales_order_id,customer_id,title,status,contract_type,
                    effective_date,expiry_date,contract_value,currency,terms,created_by)
                VALUES(@company,@number,@order,@buyer,@title,'draft',@type,@effective,@expiry,@value,@currency,@terms,@actor)
                RETURNING *
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'contract',id,'created',@actor,(to_jsonb(created)||jsonb_build_object('desktop_request',@request,
                    'desktop_sha256',@hash))::json FROM created RETURNING id
            ), owned AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'srm_contracts',id::text,@company,@branch,'validated-write' FROM created
                UNION ALL SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit RETURNING resource_key
            )
            SELECT id FROM created WHERE (SELECT count(*) FROM owned)=2", db, tx, branch, actor.Id);
        write.Parameters.AddWithValue("number", number);
        write.Parameters.AddWithValue("order", order);
        write.Parameters.AddWithValue("buyer", NpgsqlDbType.Integer, (object?)customer ?? DBNull.Value);
        write.Parameters.AddWithValue("request", request.ToString());
        write.Parameters.AddWithValue("hash", digest);
        BindContractChanges(write, change);
        if (await write.ExecuteScalarAsync() is not int id)
            throw new InvalidOperationException("The contract and its audit could not both be saved.");
        tx.Commit();
        return new SalesContractCreated(id, number);
    }
}
