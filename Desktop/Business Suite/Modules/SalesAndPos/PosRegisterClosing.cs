using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PosCashSnapshot(string Number, string Currency, decimal Opening, decimal Sales, decimal CashIn,
    decimal CashOut)
{
    internal decimal Expected => Opening + Sales + CashIn - CashOut;
}

internal sealed partial class SalesOrderRepository
{
    internal async Task<PosCashSnapshot> ReadRegisterCashAsync(string number)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to reconcile a register.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(System.Data.IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor);
        await RequireNativeRegisterBranchAsync(db, tx, branch);
        await RequireCashIntentSchemaAsync(db, tx);
        var snapshot = await ReadCashSnapshotAsync(db, tx, branch, actor.Id, number);
        tx.Commit();
        return snapshot;
    }

    internal async Task<decimal> CloseRegisterAsync(PosCashSnapshot original, decimal counted, string notes)
    {
        if (counted < 0 || counted > MaximumOpeningCash || decimal.Round(counted, 2) != counted)
            throw new ArgumentException("Enter nonnegative counted cash with at most two decimal places.");
        if (notes.Length > 500)
            throw new ArgumentException("Closing notes must contain at most 500 characters.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to close a register.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireRegisterWriterAsync(db, tx, branch, actor);
        await RequireNativeRegisterBranchAsync(db, tx, branch);
        await RequireCashIntentSchemaAsync(db, tx);

        using var closed = RegisterQuery(@"
            SELECT p.cash_variance FROM public.srm_pos_sessions p" + OwnSession + " AND p.status='closed'",
            db, tx, branch, actor.Id, original.Number);
        if (await closed.ExecuteScalarAsync() is decimal recorded)
        {
            tx.Commit();
            return recorded;
        }
        var current = await ReadCashSnapshotAsync(db, tx, branch, actor.Id, original.Number);
        if (current != original)
            throw new InvalidOperationException("The register cash changed. Refresh the cash summary before closing.");
        if (current.Currency.Length == 0 && counted != 0)
            throw new InvalidOperationException("This empty register has no cash currency. Close with zero counted cash.");
        decimal variance = counted - current.Expected;
        if (Math.Abs(variance) > MaximumOpeningCash)
            throw new InvalidOperationException("The cash variance exceeds the register's supported range.");

        using var write = RegisterQuery(@"
            WITH closed AS (
                UPDATE public.srm_pos_sessions p SET status='closed', expected_cash=@expected,
                    counted_cash=@counted,cash_variance=@variance,closed_at=now(),updated_at=now()" +
                OwnSession + @" AND p.status='open' RETURNING *
            ), closing AS (
                INSERT INTO public.srm_pos_cashier_closings
                    (organization_id,session_id,opening_cash,cash_sales,cash_in,cash_out,expected_cash,
                     counted_cash,variance,notes,closed_by)
                SELECT @company,id,opening_cash,@sales,@cash_in,@cash_out,@expected,@counted,@variance,@notes,@actor
                FROM closed RETURNING id
            ), audit AS (
                INSERT INTO public.srm_audit_logs
                    (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'pos_session',id,'closed',@actor,row_to_json(closed) FROM closed RETURNING id
            )
            INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
            SELECT 'srm_pos_cashier_closings',id::text,@company,@branch,'validated-write' FROM closing
            UNION ALL
            SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit",
            db, tx, branch, actor.Id, original.Number);
        write.Parameters.AddWithValue("notes", NpgsqlDbType.Text, notes);
        write.Parameters.AddWithValue("expected", NpgsqlDbType.Numeric, current.Expected);
        write.Parameters.AddWithValue("counted", NpgsqlDbType.Numeric, counted);
        write.Parameters.AddWithValue("variance", NpgsqlDbType.Numeric, variance);
        write.Parameters.AddWithValue("sales", NpgsqlDbType.Numeric, current.Sales);
        write.Parameters.AddWithValue("cash_in", NpgsqlDbType.Numeric, current.CashIn);
        write.Parameters.AddWithValue("cash_out", NpgsqlDbType.Numeric, current.CashOut);
        if (await write.ExecuteNonQueryAsync() != 2)
            throw new InvalidOperationException("The register closing and its audit could not both be saved.");
        tx.Commit();
        return variance;
    }

    private const string OwnSession = @"
        WHERE p.organization_id=@company AND p.cashier_user_id=@actor AND p.session_number=@number
            AND p.deleted_at IS NULL
            AND EXISTS (SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company
                AND b.branch_id=@branch AND b.resource_table='srm_pos_sessions' AND b.resource_key=p.id::text)
            AND NOT EXISTS (SELECT 1 FROM public.business_pack_record_ownership b WHERE b.company_id=@company
                AND b.resource_table='srm_pos_sessions' AND b.resource_key=p.id::text)";

    private async Task<PosCashSnapshot> ReadCashSnapshotAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, int actor, string number)
    {
        using var query = RegisterQuery(@"
            WITH register AS (
                SELECT p.id,coalesce(p.opening_cash,0) opening,p.metadata_json->>'cash_currency' currency,
                       p.metadata_json::text IS DISTINCT FROM 'null' AND json_typeof(p.metadata_json::json) <> 'object'
                           AS malformed,
                       p.metadata_json::jsonb ? 'cash_currency' AS has_currency
                FROM public.srm_pos_sessions p" + OwnSession + @" AND p.status='open'
            ), orders AS (
                SELECT o.* FROM register r JOIN public.srm_sales_orders o
                    ON o.metadata_json->>'source'='pos' AND CASE
                        WHEN trim(o.metadata_json->>'pos_session_id') ~ '^[+]?[0-9]+$'
                        THEN trim(o.metadata_json->>'pos_session_id')::numeric=r.id ELSE false END
                WHERE o.deleted_at IS NULL
            ), movement AS (
                SELECT m.* FROM register r JOIN public.srm_pos_cash_movements m ON m.session_id=r.id
            )" + NativeRegisterCheckoutEvidence + @"
            SELECT r.opening,coalesce(r.currency,''),
               coalesce((SELECT sum(total_amount) FROM orders o WHERE o.metadata_json->>'payment_mode'='Cash'
                   AND NOT EXISTS (SELECT 1 FROM grouped g WHERE g.sales_order_id=o.id)),0) + " + GroupCashAmount + @",
               coalesce((SELECT sum(amount) FROM movement WHERE movement_type='cash_in'),0),
               coalesce((SELECT sum(amount) FROM movement WHERE movement_type='cash_out'),0),
               coalesce(r.malformed,false) OR
               (coalesce(r.has_currency,false) AND (r.currency IS NULL OR r.currency !~ '^[A-Z]{3}$')) OR
               (r.currency IS NULL AND (r.opening<>0 OR EXISTS(SELECT 1 FROM movement) OR EXISTS(SELECT 1 FROM orders))) OR
               EXISTS (SELECT 1 FROM orders o WHERE o.organization_id IS DISTINCT FROM @company OR
                   NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company
                     AND b.branch_id=@branch AND b.resource_table='srm_sales_orders' AND b.resource_key=o.id::text)
                   OR EXISTS (SELECT 1 FROM public.business_pack_record_ownership b WHERE b.company_id=@company
                     AND b.resource_table='srm_sales_orders' AND b.resource_key=o.id::text)
                   OR (NOT EXISTS (SELECT 1 FROM grouped g WHERE g.sales_order_id=o.id)
                       AND (coalesce(o.metadata_json->>'payment_mode','') NOT IN ('Cash','Card','UPI','Wallet','Bank Transfer','Credit')
                   OR (o.metadata_json->>'payment_mode'='Cash' AND (o.currency IS DISTINCT FROM r.currency
                        OR o.total_amount IS NULL OR o.total_amount<0))))) OR
               EXISTS (SELECT 1 FROM movement m WHERE m.organization_id IS DISTINCT FROM @company OR
                   coalesce(m.movement_type,'') NOT IN ('cash_in','cash_out') OR m.amount IS NULL OR m.amount<=0
                   OR (m.request_key IS NOT NULL AND (m.request_currency IS DISTINCT FROM r.currency
                        OR m.request_branch_id IS DISTINCT FROM @branch OR m.request_context_id IS NOT NULL))
                   OR NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company
                     AND b.branch_id=@branch AND b.resource_table='srm_pos_cash_movements' AND b.resource_key=m.id::text)
                   OR EXISTS (SELECT 1 FROM public.business_pack_record_ownership b WHERE b.company_id=@company
                     AND b.resource_table='srm_pos_cash_movements' AND b.resource_key=m.id::text)) OR
               (" + GroupCashRequiresReconciliation + @") OR
               EXISTS (SELECT 1 FROM public.business_restaurant_bill_receipts p WHERE p.collection_session_id=r.id) OR
               EXISTS (SELECT 1 FROM public.srm_pos_cashier_closings c WHERE c.session_id=r.id)
            FROM register r", db, tx, branch, actor, number);
        using var row = await query.ExecuteReaderAsync();
        if (!await row.ReadAsync())
            throw new InvalidOperationException("This cashier's open register is unavailable in the selected branch.");
        if (row.GetBoolean(5))
            throw new InvalidOperationException("This register has cash sources that require reconciliation before desktop closing.");
        var result = new PosCashSnapshot(number, row.GetString(1), row.GetDecimal(0), row.GetDecimal(2),
            row.GetDecimal(3), row.GetDecimal(4));
        if (Math.Abs(result.Expected) > MaximumOpeningCash || result.CashIn > MaximumOpeningCash ||
            result.CashOut > MaximumOpeningCash || result.Sales > MaximumOpeningCash)
            throw new InvalidOperationException("This register's cash totals exceed the supported range.");
        return result;
    }

    private NpgsqlCommand RegisterQuery(string sql, NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, int actor, string number)
    {
        var command = RegisterCommand(sql, db, tx, branch, actor);
        command.Parameters.AddWithValue("number", NpgsqlDbType.Text, number);
        return command;
    }
}
