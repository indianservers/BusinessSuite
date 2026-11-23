using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    private async Task<PosReturnResult?> FindReturnIntentAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        int actor, ReturnOrder order, Guid request, string fingerprint)
    {
        using var query = RegisterCommand(@"
            SELECT r.return_number,r.refund_amount,r.tax_amount,coalesce(r.created_by=@actor
                AND r.sales_order_id=@order AND r.metadata_json->>'desktop_request_sha256'=@hash
                AND " + ConfirmationOwnership("r", "srm_pos_returns") + @",false)
            FROM public.srm_pos_returns r
            WHERE r.organization_id=@company AND r.metadata_json->>'desktop_request_id'=@request
            ORDER BY r.id LIMIT 2 FOR UPDATE OF r", db, tx, branch, actor);
        query.Parameters.AddWithValue("request", request.ToString());
        query.Parameters.AddWithValue("order", order.Id);
        query.Parameters.AddWithValue("hash", fingerprint);
        using var reader = await query.ExecuteReaderAsync();
        if (!await reader.ReadAsync())
            return null;
        if (!reader.GetBoolean(3))
            throw new InvalidOperationException("A different or inaccessible return used this request key.");
        var result = new PosReturnResult(reader.GetString(0), order.Currency, reader.GetDecimal(1), reader.GetDecimal(2));
        if (await reader.ReadAsync())
            throw new InvalidOperationException("Multiple returns match this request. Review the sale before continuing.");
        return result;
    }

    private async Task VerifyReturnScopeAndAmountAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor,
        ReturnOrder order, ReturnLine line, decimal amount)
    {
        using var query = RegisterCommand(@"
            SELECT coalesce((SELECT sum(r.refund_amount) FROM public.srm_pos_returns r WHERE r.sales_order_id=@order),0),
                EXISTS (SELECT 1 FROM public.srm_pos_returns r WHERE r.sales_order_id=@order AND
                    (r.organization_id IS DISTINCT FROM @company OR NOT (" + ConfirmationOwnership("r", "srm_pos_returns") + @"))),
                EXISTS (SELECT 1 FROM public.srm_products p WHERE p.id=@product AND p.organization_id=@company
                    AND p.deleted_at IS NULL AND lower(coalesce(p.product_type,'stock')) IN ('stock','product','goods')
                    AND NOT (coalesce(p.batch_tracking,false) OR coalesce(p.serial_tracking,false) OR coalesce(p.expiry_tracking,false))
                    AND NOT EXISTS(SELECT 1 FROM public.business_pack_record_ownership b WHERE b.company_id=@company
                        AND b.resource_table='srm_products' AND b.resource_key=p.id::text)
                    AND NOT EXISTS(SELECT 1 FROM public.business_pharma_batch_receipts r
                        JOIN public.business_pharma_batch_availability a ON a.organization_id=r.organization_id AND a.batch_id=r.batch_id
                        WHERE r.organization_id=@company AND r.product_id=p.id))",
            db, tx, branch, actor);
        query.Parameters.AddWithValue("order", order.Id);
        query.Parameters.AddWithValue("product", line.Product);
        using var reader = await query.ExecuteReaderAsync();
        await reader.ReadAsync();
        if (reader.GetBoolean(1))
            throw new InvalidOperationException("Previous refunds require branch reconciliation.");
        if (reader.GetDecimal(0) + amount > order.Paid)
            throw new PosReturnRejectedException("The refund exceeds the original sale's remaining collected value.");
        if (!reader.GetBoolean(2))
            throw new PosReturnRejectedException("This item requires its specialized product or inventory return workflow.");
    }

    private async Task<int?> RestockPosReturnAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor,
        ReturnOrder order, ReturnLine line, decimal rate, decimal quantity, string number)
    {
        int warehouse;
        using (var issue = RegisterCommand(@"
            SELECT m.warehouse_id,coalesce(nullif(@rate,0),p.sales_rate,0)
            FROM public.srm_sales_orders o JOIN public.srm_inventory_movements m
                ON m.organization_id=o.organization_id AND m.product_id=@product AND m.reference_number=o.order_number
            JOIN public.srm_products p ON p.id=m.product_id AND p.organization_id=@company AND p.deleted_at IS NULL
            JOIN public.srm_warehouses w ON w.id=m.warehouse_id AND w.organization_id=@company AND w.active
            WHERE o.id=@order AND o.organization_id=@company AND m.movement_type='pos_sale' AND m.quantity_out=@sold
                AND o.metadata_json::jsonb->'inventory_issue_movement_ids' @> jsonb_build_array(m.id)
                AND " + ConfirmationOwnership("m", "srm_inventory_movements") + " AND " +
                ConfirmationOwnership("w", "srm_warehouses") + @"
            ORDER BY m.id LIMIT 2 FOR UPDATE OF p,w", db, tx, branch, actor.Id))
        {
            issue.Parameters.AddWithValue("order", order.Id);
            issue.Parameters.AddWithValue("product", line.Product);
            issue.Parameters.AddWithValue("rate", rate);
            issue.Parameters.AddWithValue("sold", line.Sold);
            using var reader = await issue.ExecuteReaderAsync();
            if (!await reader.ReadAsync())
                throw new PosReturnRejectedException("The original stock issue and branch warehouse could not be verified. Review the sale before restocking.");
            warehouse = reader.GetInt32(0);
            rate = reader.GetDecimal(1);
            if (await reader.ReadAsync())
                throw new PosReturnRejectedException("The original sale has multiple stock sources for this line.");
        }

        using var balance = RegisterCommand(@"
            UPDATE public.srm_inventory_balances b SET quantity=b.quantity+@quantity,updated_at=now()
            WHERE b.organization_id=@company AND b.product_id=@product AND b.warehouse_id=@warehouse
                AND b.quantity>=0 AND " + ConfirmationOwnership("b", "srm_inventory_balances") + @"
                AND NOT EXISTS (SELECT 1 FROM public.srm_inventory_balances other JOIN public.business_pack_record_ownership a
                    ON a.company_id=@company AND a.resource_table='srm_inventory_balances' AND a.resource_key=other.id::text
                    WHERE other.organization_id=@company AND other.product_id=@product)", db, tx, branch, actor.Id);
        balance.Parameters.AddWithValue("product", line.Product);
        balance.Parameters.AddWithValue("warehouse", warehouse);
        balance.Parameters.AddWithValue("quantity", quantity);
        if (await balance.ExecuteNonQueryAsync() != 1)
            throw new PosReturnRejectedException("The original warehouse balance requires reconciliation before accepting restock.");

        string movement = await ReserveCommercialNumberAsync(db, tx, CommercialNumberSeries.InventoryMovement);
        using var post = RegisterCommand(@"
            WITH adjustment AS (
                INSERT INTO public.srm_inventory_movements (organization_id,movement_number,movement_type,movement_date,
                    product_id,warehouse_id,quantity_in,quantity_out,rate,value,reference_number,notes,created_by)
                VALUES (@company,@movement,'pos_return',@today,@product,@warehouse,@quantity,0,@rate,@quantity*@rate,
                    @number,'POS return '||@number||' for '||@original,@actor) RETURNING *
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'inventory_movement',id,'POS_RETURN',@actor,row_to_json(adjustment) FROM adjustment RETURNING id
            ), cache AS (
                UPDATE public.srm_products p SET current_quantity=(SELECT coalesce(sum(b.quantity),0)
                    FROM public.srm_inventory_balances b WHERE b.organization_id=@company AND b.product_id=p.id)
                WHERE p.organization_id=@company AND p.id=@product
            )
            INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
            SELECT 'srm_inventory_movements',id::text,@company,@branch,'validated-write' FROM adjustment
            UNION ALL SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit", db, tx, branch, actor.Id);
        post.Parameters.AddWithValue("movement", movement);
        post.Parameters.AddWithValue("number", number);
        post.Parameters.AddWithValue("original", order.Number);
        post.Parameters.AddWithValue("product", line.Product);
        post.Parameters.AddWithValue("warehouse", warehouse);
        post.Parameters.AddWithValue("quantity", quantity);
        post.Parameters.AddWithValue("rate", rate);
        post.Parameters.AddWithValue("today", NpgsqlDbType.Date, DateTime.Today);
        if (await post.ExecuteNonQueryAsync() != 2)
            throw new InvalidOperationException("The restock movement and its audit could not both be saved.");
        return warehouse;
    }
}
