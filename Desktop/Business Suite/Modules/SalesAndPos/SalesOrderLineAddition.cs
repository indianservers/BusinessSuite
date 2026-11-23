using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record SalesOrderItemsSnapshot(string Currency, string Revision);

internal sealed partial class SalesOrderRepository
{
    private static string SalesItemsSnapshotQuery => "SELECT coalesce(o.currency,'')," + SalesLineRevision +
        " FROM public.srm_sales_orders o" + MutableSalesItemsOrder;

    internal async Task<SalesOrderItemsSnapshot> LoadSalesOrderItemsSnapshotAsync(int order)
    {
        var rows = await ReadAsync(SalesItemsSnapshotQuery, query => query.Parameters.AddWithValue("order", order),
            row => new SalesOrderItemsSnapshot(row.GetString(0), row.GetString(1)), "create");
        return rows.SingleOrDefault() ?? throw new InvalidOperationException("Only an authorized draft or pending Sales order without an invoice can change items.");
    }

    internal Task<int> AddSalesOrderLineAsync(int order, SalesOrderItemsSnapshot snapshot, SalesOrderInputLine line, Guid request) =>
        AddSalesOrderLineCoreAsync(order, snapshot, line, request, null, null);

    internal Task<int> AddManualSalesServiceAsync(int order, SalesOrderItemsSnapshot snapshot, string description, string code,
        decimal quantity, decimal price, decimal discountRate, decimal taxRate, Guid request)
    {
        description = description.Trim();
        code = code.Trim();
        if (description.Length == 0 || description.Length > 1000 || code.Length > 80)
            throw new ArgumentException("Enter a service description of up to 1,000 characters and an optional code of up to 80 characters.");
        var line = new SalesOrderInputLine(0, "", "", quantity, price, discountRate, taxRate);
        return AddSalesOrderLineCoreAsync(order, snapshot, line, request, description, code);
    }

    private async Task<int> AddSalesOrderLineCoreAsync(int order, SalesOrderItemsSnapshot snapshot, SalesOrderInputLine line,
        Guid request, string? manualDescription, string? manualCode)
    {
        if (order < 1 || snapshot.Revision.Length != 32 || request == Guid.Empty)
            throw new ArgumentException("Reload the selected Sales order before adding its item.");
        var amount = manualDescription is null ? CalculateLine(line) : CalculateStandaloneLine(line);
        string digest = manualDescription is null ? HashSalesPayload(new { order, snapshot, line })
            : HashSalesPayload(new { order, snapshot, line, manualDescription, manualCode });
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select an order branch before adding an item.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await RequireSalesOrderCreateAsync(db, tx, branch, actor);
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "create");
        var current = await LockSalesOrderItemsAsync(db, tx, branch, actor, scope, order);
        using (var replay = RegisterCommand(@"
            SELECT a.entity_id,a.after_json->'metadata_json'->>'desktop_add_sha256'=@hash
            FROM public.srm_audit_logs a WHERE a.organization_id=@company AND a.actor_user_id=@actor
                AND a.entity_type='sales_order_line' AND a.action='created'
                AND a.after_json->>'sales_order_id'=@order::text
                AND a.after_json->'metadata_json'->>'desktop_add_request'=@request
                AND " + ConfirmationOwnership("a", "srm_audit_logs"), db, tx, branch, actor.Id))
        {
            replay.Parameters.AddWithValue("order", order);
            replay.Parameters.AddWithValue("request", request.ToString());
            replay.Parameters.AddWithValue("hash", digest);
            int? existing = null;
            using (var rows = await replay.ExecuteReaderAsync())
            {
                if (await rows.ReadAsync())
                {
                    if (rows.IsDBNull(1) || !rows.GetBoolean(1))
                        throw new InvalidOperationException("This request was already used for a different saved item.");
                    existing = rows.GetInt32(0);
                    if (await rows.ReadAsync())
                        throw new InvalidOperationException("More than one audit matches this item request.");
                }
            }
            if (existing.HasValue)
            {
                tx.Commit();
                return existing.Value;
            }
        }
        if (current != snapshot || !ValidOrderCurrency(current.Currency))
            throw new InvalidOperationException("The sales order changed. Reload its items and prices.");

        SalesCatalogItem? item = null;
        if (manualDescription is null)
        {
            using var products = new NpgsqlCommand(OrderCatalog + " AND p.id=@product FOR SHARE OF p", db, tx);
            SharedCatalogRepository.BindProductScope(products, settings.OrganizationId, branch, actor);
            products.Parameters.AddWithValue("product", line.ItemId);
            item = (await ReadSalesCatalogAsync(products)).SingleOrDefault();
            if (item is null || item.Revision != line.Revision)
                throw new InvalidOperationException("The selected catalog item changed or is unavailable. Reload it before saving.");
            if (!item.Prices.Any(price => price.Currency == current.Currency && price.Id == line.PricingId))
                throw new ArgumentException($"Choose a catalog price in {current.Currency}.");
        }

        using var write = RegisterCommand(@"
            WITH totals_before AS (
                SELECT coalesce(sum(coalesce(quantity,0)*coalesce(unit_price,0)),0) AS gross,
                    coalesce(sum(discount_amount),0) AS discount,coalesce(sum(tax_amount),0) AS tax,
                    coalesce(sum(coalesce(line_total,coalesce(quantity,0)*coalesce(unit_price,0)-coalesce(discount_amount,0)+coalesce(tax_amount,0))),0) AS total
                FROM public.srm_sales_order_lines WHERE sales_order_id=@order
            ), updated AS (
                UPDATE public.srm_sales_orders o SET subtotal=totals_before.gross+@subtotal,discount_amount=totals_before.discount+@discount,
                    tax_amount=totals_before.tax+@tax,total_amount=totals_before.total+@total,updated_at=now()
                FROM totals_before WHERE o.id=@order AND o.organization_id=@company
                    AND greatest(totals_before.gross+@subtotal,totals_before.discount+@discount,
                        totals_before.tax+@tax,totals_before.total+@total)<=@maximum
                RETURNING o.id
            ), inserted AS (
                INSERT INTO public.srm_sales_order_lines (sales_order_id,product_id,item_code,description,service_type,quantity,
                    unit_price,discount_amount,tax_amount,line_total,metadata_json)
                SELECT id,@product,@code,@description,@kind,@quantity,@price,@discount,@tax,@total,
                    json_build_object('desktop_add_request',@request,'desktop_add_sha256',@hash)
                FROM updated RETURNING *
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'sales_order_line',id,'created',@actor,row_to_json(inserted) FROM inserted RETURNING id
            ), scoped AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'srm_sales_order_lines',id::text,@company,@branch,'validated-write' FROM inserted
                UNION ALL SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit RETURNING resource_key
            )
            SELECT id FROM inserted WHERE (SELECT count(*) FROM scoped)=2", db, tx, branch, actor.Id);
        write.Parameters.AddWithValue("order", order);
        write.Parameters.Add("product", NpgsqlDbType.Integer).Value = (object?)item?.Id ?? DBNull.Value;
        write.Parameters.Add("code", NpgsqlDbType.Varchar).Value = (object?)item?.Code ?? (string.IsNullOrEmpty(manualCode) ? DBNull.Value : (object)manualCode!);
        write.Parameters.AddWithValue("description", item?.Name ?? manualDescription!);
        write.Parameters.AddWithValue("kind", item?.Kind ?? "service");
        write.Parameters.AddWithValue("quantity", line.Quantity);
        write.Parameters.AddWithValue("price", line.UnitPrice);
        write.Parameters.AddWithValue("subtotal", amount.Subtotal);
        write.Parameters.AddWithValue("discount", amount.Discount);
        write.Parameters.AddWithValue("tax", amount.Tax);
        write.Parameters.AddWithValue("total", amount.Total);
        write.Parameters.AddWithValue("maximum", MaximumOrderMoney);
        write.Parameters.AddWithValue("request", request.ToString());
        write.Parameters.AddWithValue("hash", digest);
        if (await write.ExecuteScalarAsync() is not int saved)
            throw new InvalidOperationException("The item and order totals could not be saved. Check the order's amount limits.");
        tx.Commit();
        return saved;
    }
}
