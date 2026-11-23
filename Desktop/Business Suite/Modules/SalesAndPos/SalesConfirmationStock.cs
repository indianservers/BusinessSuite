using System.Globalization;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    private sealed record ConfirmationLine(int ProductId, decimal Quantity, decimal UnitPrice, string? Warehouse, string? FollowUp);

    private async Task IssueConfirmationStockAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, DesktopActor actor, int order, string orderNumber)
    {
        var lines = new List<ConfirmationLine>();
        using (var read = RegisterCommand(@"
            SELECT l.product_id,coalesce(l.quantity,0),coalesce(l.unit_price,0),l.metadata_json->>'warehouse_id',
                CASE WHEN l.metadata_json::jsonb ? 'follow_up' THEN coalesce(l.metadata_json->'follow_up','null'::json)::text END
            FROM public.srm_sales_order_lines l WHERE l.sales_order_id=@order AND l.product_id IS NOT NULL ORDER BY l.id",
            db, tx, branch, actor.Id))
        {
            read.Parameters.AddWithValue("order", order);
            using var reader = await read.ExecuteReaderAsync();
            while (await reader.ReadAsync())
                lines.Add(new ConfirmationLine(reader.GetInt32(0), reader.GetDecimal(1), reader.GetDecimal(2),
                    reader.IsDBNull(3) ? null : reader.GetString(3), reader.IsDBNull(4) ? null : reader.GetString(4)));
        }

        using var priorIssue = RegisterCommand(@"SELECT nullif(o.metadata_json->>'inventory_issued_at','') IS NOT NULL
            OR EXISTS (SELECT 1 FROM public.srm_inventory_movements m WHERE m.organization_id=@company
                AND m.movement_type='sales_order_issue' AND m.reference_number=o.order_number)
            FROM public.srm_sales_orders o WHERE o.id=@order", db, tx, branch, actor.Id);
        priorIssue.Parameters.AddWithValue("order", order);
        if ((bool?)await priorIssue.ExecuteScalarAsync() == true)
            throw new InvalidOperationException("This order already has inventory issue history. Review it before confirming.");

        var movements = new List<int>();
        foreach (var line in lines)
        {
            int? warehouse;
            decimal rate;
            using (var product = new NpgsqlCommand(@"
                SELECT p.default_warehouse_id,coalesce(p.sales_rate,0),p.metadata_json->>'follow_up',
                    coalesce(p.track_inventory,false) AND lower(trim(coalesce(p.product_type,'')))
                        NOT IN ('service','services','membership','subscription','bundle'),
                    coalesce(p.batch_tracking,false) OR coalesce(p.serial_tracking,false) OR coalesce(p.expiry_tracking,false),
                    EXISTS (SELECT 1 FROM public.business_pharma_batch_receipts r
                        JOIN public.business_pharma_batch_availability a ON a.batch_id=r.batch_id AND a.organization_id=r.organization_id
                        WHERE r.organization_id=@company AND r.product_id=p.id)
                " + SharedCatalogRepository.ProductAndDetail + SharedCatalogRepository.ProductVisibility +
                " AND p.organization_id=@company AND p.id=@product FOR UPDATE OF p", db, tx))
            {
                SharedCatalogRepository.BindProductScope(product, settings.OrganizationId, branch, actor);
                product.Parameters.AddWithValue("product", line.ProductId);
                using var reader = await product.ExecuteReaderAsync();
                if (!await reader.ReadAsync())
                    throw new InvalidOperationException("An order item is unavailable in this branch.");
                RequireDeferredFollowUp(line.FollowUp ?? (reader.IsDBNull(2) ? null : reader.GetString(2)));
                bool physical = reader.GetBoolean(3);
                if (reader.GetBoolean(5) || (physical && reader.GetBoolean(4)))
                    throw new InvalidOperationException("This item requires a lot, serial, expiry, or Pharma stock operation.");
                if (!physical)
                    continue;
                warehouse = reader.IsDBNull(0) ? null : reader.GetInt32(0);
                rate = line.UnitPrice == 0 ? reader.GetDecimal(1) : line.UnitPrice;
            }

            if (!string.IsNullOrWhiteSpace(line.Warehouse) && line.Warehouse != "0")
                warehouse = int.TryParse(line.Warehouse, NumberStyles.None, CultureInfo.InvariantCulture, out int selected) ? selected : null;
            if (warehouse is not int warehouseId || warehouseId <= 0)
                throw new InvalidOperationException("A warehouse is required for each stock item.");
            if (line.Quantity <= 0)
                throw new InvalidOperationException("Quantities for stock items must be greater than zero.");
            movements.Add(await IssueSalesLineAsync(db, tx, branch, actor.Id, line, warehouseId, rate, orderNumber));
        }

        if (movements.Count == 0)
            return;
        using var stamp = RegisterCommand(@"UPDATE public.srm_sales_orders
            SET metadata_json=(coalesce(metadata_json::jsonb,'{}'::jsonb) ||
                jsonb_build_object('inventory_issued_at',@issued,'inventory_issue_movement_ids',@movements))::json
            WHERE id=@order AND organization_id=@company", db, tx, branch, actor.Id);
        stamp.Parameters.AddWithValue("order", order);
        stamp.Parameters.AddWithValue("issued", DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture));
        stamp.Parameters.AddWithValue("movements", NpgsqlDbType.Array | NpgsqlDbType.Integer, movements.ToArray());
        if (await stamp.ExecuteNonQueryAsync() != 1)
            throw new InvalidOperationException("The inventory movements could not be linked to the order.");
    }

    private static void RequireDeferredFollowUp(string? json)
    {
        if (string.IsNullOrWhiteSpace(json))
            return;
        using var config = JsonDocument.Parse(json!);
        var value = config.RootElement;
        if (value.ValueKind == JsonValueKind.Null)
            return;
        if (value.ValueKind != JsonValueKind.Object)
            throw new InvalidOperationException("Review the follow-up configuration before confirming this order.");
        if (!value.TryGetProperty("required", out var required) || required.ValueKind is JsonValueKind.Null or JsonValueKind.False)
            return;
        if (required.ValueKind == JsonValueKind.True &&
            value.TryGetProperty("reference", out var reference) && reference.ValueKind == JsonValueKind.String &&
            reference.GetString() is "delivery" or "completion" &&
            (!value.TryGetProperty("type", out var type) || type.ValueKind == JsonValueKind.String && type.GetString() != "date") &&
            (!value.TryGetProperty("reference_at", out var referenceAt) || referenceAt.ValueKind == JsonValueKind.Null ||
                referenceAt.ValueKind == JsonValueKind.String && referenceAt.GetString() == ""))
            return;
        throw new InvalidOperationException("This order requires an immediate product or service follow-up. Desktop confirmation cannot schedule it yet.");
    }

    private async Task<int> IssueSalesLineAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor,
        ConfirmationLine line, int warehouse, decimal rate, string orderNumber, bool pos = false)
    {
        using var deduct = RegisterCommand(@"
            UPDATE public.srm_inventory_balances b SET quantity=b.quantity-@quantity,updated_at=now()
            FROM public.srm_warehouses w
            WHERE w.id=@warehouse AND w.organization_id=@company AND w.active AND " + ConfirmationOwnership("w", "srm_warehouses") + @"
                AND b.organization_id=@company AND b.warehouse_id=w.id AND b.product_id=@product AND b.quantity>=@quantity
                AND " + ConfirmationOwnership("b", "srm_inventory_balances") + @"
                AND NOT EXISTS (
                    SELECT 1 FROM public.srm_inventory_balances other JOIN public.business_pack_record_ownership ownership
                      ON ownership.company_id=@company AND ownership.resource_table='srm_inventory_balances'
                      AND ownership.resource_key=other.id::text
                    WHERE other.organization_id=@company AND other.product_id=@product)", db, tx, branch, actor);
        deduct.Parameters.AddWithValue("warehouse", warehouse);
        deduct.Parameters.AddWithValue("product", line.ProductId);
        deduct.Parameters.AddWithValue("quantity", line.Quantity);
        if (await deduct.ExecuteNonQueryAsync() != 1)
            throw pos ? new PosCheckoutRejectedException("A stock balance is out of scope, unavailable, or has insufficient quantity.")
                : new InvalidOperationException("A stock balance is out of scope, unavailable, or has insufficient quantity.");

        string number = await ReserveCommercialNumberAsync(db, tx, CommercialNumberSeries.InventoryMovement);
        using var create = RegisterCommand(@"
            WITH movement AS (
                INSERT INTO public.srm_inventory_movements (organization_id,movement_number,movement_type,movement_date,
                    product_id,warehouse_id,quantity_in,quantity_out,rate,value,reference_number,notes,created_by)
                VALUES (@company,@number,@movement_type,@today,@product,@warehouse,0,@quantity,@rate,
                    @quantity*@rate,@order_number,@notes,@actor) RETURNING *
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'inventory_movement',id,upper(movement_type),@actor,row_to_json(movement)
                FROM movement RETURNING id
            ), ownership AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'srm_inventory_movements',id::text,@company,@branch,'validated-write' FROM movement
                UNION ALL SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit
            ), cache AS (
                UPDATE public.srm_products p SET current_quantity=(SELECT coalesce(sum(b.quantity),0)
                    FROM public.srm_inventory_balances b WHERE b.organization_id=@company AND b.product_id=p.id)
                WHERE p.organization_id=@company AND p.id=@product RETURNING p.id
            )
            SELECT movement.id FROM movement CROSS JOIN cache", db, tx, branch, actor);
        create.Parameters.AddWithValue("number", number);
        create.Parameters.AddWithValue("movement_type", pos ? "pos_sale" : "sales_order_issue");
        create.Parameters.AddWithValue("notes", (pos ? "POS sale " : "Sales order issue ") + orderNumber);
        create.Parameters.AddWithValue("today", NpgsqlDbType.Date, DateTime.Today);
        create.Parameters.AddWithValue("warehouse", warehouse);
        create.Parameters.AddWithValue("product", line.ProductId);
        create.Parameters.AddWithValue("quantity", line.Quantity);
        create.Parameters.AddWithValue("rate", rate);
        create.Parameters.AddWithValue("order_number", orderNumber);
        return (int)(await create.ExecuteScalarAsync())!;
    }
}
