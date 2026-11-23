using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    private sealed record PosCheckoutOrder(int Id, List<SalesInvoiceDraftLine> Lines);

    private async Task<PosCheckoutOrder> CreatePosCheckoutOrderAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor,
        int session, string number, int customerId, PosCheckoutIntent intent, List<CheckoutProduct> products)
    {
        var snapshots = products.Select(p => NormalizeInvoiceLine(null, p.Line.Name, p.Line.Quantity,
            p.Line.UnitPrice, 0, p.Line.LineTotal - decimal.Round(p.Line.UnitPrice * p.Line.Quantity, 2, MidpointRounding.AwayFromZero))).ToList();
        using var create = RegisterCommand(@"
            WITH order_row AS (
                INSERT INTO public.srm_sales_orders (organization_id,order_number,title,status,customer_id,assigned_user_id,
                    created_by,currency,subtotal,discount_amount,tax_amount,total_amount,terms,metadata_json)
                VALUES (@company,@number,'Service checkout','draft',@customer,@actor,@actor,@currency,@subtotal,0,@tax,@total,@notes,
                    json_build_object('source','pos','pos_sale_id',@request,'pos_session_id',@session)) RETURNING id
            ), items AS (
                INSERT INTO public.srm_sales_order_lines (sales_order_id,product_id,item_code,description,service_type,
                    quantity,unit_price,discount_amount,tax_amount,line_total,metadata_json)
                SELECT o.id,p.product_id,p.sku,p.description,'product',p.quantity,p.price,0,p.tax,p.total,
                    json_build_object('checkout_line_key',p.line_key,'note','',
                        'tax_snapshot',json_build_object('gst_rate',p.tax_rate,'hsn_code',p.hsn,'tax_inclusive',false))
                FROM order_row o CROSS JOIN jsonb_to_recordset(@lines) AS p(product_id int,sku text,description text,
                    quantity numeric,price numeric,tax numeric,total numeric,line_key text,tax_rate text,hsn text)
                RETURNING id,sales_order_id,product_id
            ), stamps AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'srm_sales_orders',id::text,@company,@branch,'validated-write' FROM order_row
                UNION ALL SELECT 'srm_sales_order_lines',id::text,@company,@branch,'validated-write' FROM items
            )
            SELECT sales_order_id,id,product_id FROM items", db, tx, branch, actor);
        create.Parameters.AddWithValue("number", number);
        create.Parameters.AddWithValue("request", intent.Request.ToString());
        create.Parameters.AddWithValue("session", session);
        create.Parameters.AddWithValue("customer", customerId);
        create.Parameters.AddWithValue("currency", intent.Currency);
        create.Parameters.AddWithValue("subtotal", snapshots.Sum(l => l.Subtotal));
        create.Parameters.AddWithValue("tax", snapshots.Sum(l => l.Tax));
        create.Parameters.AddWithValue("total", intent.Total);
        create.Parameters.AddWithValue("notes", intent.Notes);
        create.Parameters.AddWithValue("lines", NpgsqlDbType.Jsonb, JsonSerializer.Serialize(products.Select((p, index) => new
        {
            product_id = p.Line.ProductId, sku = p.Line.Sku, description = p.Line.Name, quantity = p.Line.Quantity,
            price = p.Line.UnitPrice, tax = snapshots[index].Tax, total = snapshots[index].Total,
            line_key = p.Key.ToString(), tax_rate = p.Line.TaxRate.ToString(CultureInfo.InvariantCulture), hsn = p.Hsn
        })));
        int order = 0;
        var savedLines = new Dictionary<int, int>();
        using (var reader = await create.ExecuteReaderAsync())
            while (await reader.ReadAsync())
            {
                order = reader.GetInt32(0);
                savedLines.Add(reader.GetInt32(2), reader.GetInt32(1));
            }
        if (order == 0 || savedLines.Count != products.Count)
            throw new InvalidOperationException("The checkout order lines could not all be saved.");

        var movements = new List<int>();
        foreach (var p in products)
        {
            if (p.Track && p.Warehouse is int warehouse)
            {
                var request = new ConfirmationLine(p.Line.ProductId, p.Line.Quantity, p.Line.UnitPrice, null, null);
                movements.Add(await IssueSalesLineAsync(db, tx, branch, actor, request, warehouse, p.Line.UnitPrice, number, pos: true));
            }
        }
        if (movements.Count > 0)
        {
            using var stamp = RegisterCommand(@"UPDATE public.srm_sales_orders SET metadata_json=(metadata_json::jsonb||
                jsonb_build_object('inventory_issued_at',@time,'inventory_issue_movement_ids',@movements))::json
                WHERE id=@order AND organization_id=@company", db, tx, branch, actor);
            stamp.Parameters.AddWithValue("order", order);
            stamp.Parameters.AddWithValue("time", DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture));
            stamp.Parameters.AddWithValue("movements", NpgsqlDbType.Array | NpgsqlDbType.Integer, movements.ToArray());
            if (await stamp.ExecuteNonQueryAsync() != 1)
                throw new InvalidOperationException("The checkout inventory references could not be saved.");
        }
        using var audit = RegisterCommand(@"
            WITH created AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'sales_order',o.id,'created',@actor,row_to_json(o) FROM public.srm_sales_orders o
                WHERE o.id=@order AND o.organization_id=@company RETURNING id
            )
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM created", db, tx, branch, actor);
        audit.Parameters.AddWithValue("order", order);
        if (await audit.ExecuteNonQueryAsync() != 1)
            throw new InvalidOperationException("The checkout order audit could not be saved.");
        return new PosCheckoutOrder(order, products.Select((p, index) =>
            snapshots[index] with { SourceLineId = savedLines[p.Line.ProductId] }).ToList());
    }

    private async Task<int> CommitPosCheckoutGraphAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor,
        int session, int order, int invoice, string requestDigest, int customerId, PosCheckoutIntent intent)
    {
        using var command = RegisterCommand(@"
            WITH root AS (
                INSERT INTO public.srm_pos_service_checkouts (organization_id,branch_id,request_id,request_sha256,created_by,
                    customer_id,currency,pos_session_id,sales_order_id,invoice_id,state,billing_mode,committed_at)
                VALUES (@company,@branch,@request,@digest,@actor,@customer,@currency,@session,@order,@invoice,
                    'committed','invoice_at_checkout',now()) RETURNING id
            ), line_map AS (
                INSERT INTO public.srm_pos_checkout_lines (organization_id,branch_id,scope_context_key,checkout_id,client_line_key,
                    line_kind,product_id,sales_order_line_id,invoice_line_id,quantity,unit_price,discount_amount,tax_amount,line_total,
                    catalog_tax_snapshot)
                SELECT @company,@branch,0,root.id,l.metadata_json->>'checkout_line_key','product',l.product_id,l.id,i.id,
                    l.quantity,l.unit_price,l.discount_amount,l.tax_amount,l.line_total,l.metadata_json->'tax_snapshot'
                FROM root CROSS JOIN public.srm_sales_order_lines l
                JOIN public.srm_invoice_lines i ON i.source_type='sales_order_line' AND i.source_id=l.id AND i.invoice_id=@invoice
                WHERE l.sales_order_id=@order RETURNING id
            ), stamps AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT kind,id::text,@company,@branch,'validated-write' FROM (
                    SELECT 'srm_pos_service_checkouts' AS kind,id FROM root
                    UNION ALL SELECT 'srm_pos_checkout_lines',id FROM line_map
                ) owned
            )
            SELECT root.id FROM root WHERE (SELECT count(*) FROM line_map)=@count", db, tx, branch, actor);
        command.Parameters.AddWithValue("request", intent.Request.ToString());
        command.Parameters.AddWithValue("digest", requestDigest);
        command.Parameters.AddWithValue("customer", customerId);
        command.Parameters.AddWithValue("currency", intent.Currency);
        command.Parameters.AddWithValue("session", session);
        command.Parameters.AddWithValue("order", order);
        command.Parameters.AddWithValue("invoice", invoice);
        command.Parameters.AddWithValue("count", intent.Items.Count);
        return await command.ExecuteScalarAsync() is int id ? id
            : throw new InvalidOperationException("The checkout order, invoice and receipt could not be linked.");
    }
}
