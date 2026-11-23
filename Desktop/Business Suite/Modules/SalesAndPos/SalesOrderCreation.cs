using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record SalesCustomer(int Id, string Name);
internal sealed record SalesCatalogPrice(string Id, string Name, string Currency, decimal Price)
{
    public string Display => $"{Name} · {Currency} {Price:N2}";
}
internal sealed record SalesCatalogItem(int Id, string Code, string Name, string Kind, decimal Tax, string Revision,
    IReadOnlyList<SalesCatalogPrice> Prices)
{
    public string Display => $"{Name} ({Code})";
}
internal sealed record SalesOrderInputLine(int ItemId, string Revision, string PricingId, decimal Quantity,
    decimal UnitPrice, decimal DiscountRate, decimal TaxRate);
internal sealed record SalesOrderDraft(Guid Request, string Title, int CustomerId, string Currency, DateTime? Start,
    DateTime? End, string Terms, IReadOnlyList<SalesOrderInputLine> Lines);
internal sealed record SalesOrderCreated(int Id, string Number);
internal sealed record SalesLineAmounts(decimal Subtotal, decimal Discount, decimal Tax, decimal Total);

internal sealed partial class SalesOrderRepository
{
    private const decimal MaximumLineMoney = 99_999_999_999m;
    private const decimal MaximumOrderMoney = 999_999_999_999.99m;
    private const string OrderCustomerScope = @"
        WHERE c.organization_id=@company AND c.deleted_at IS NULL AND (
            EXISTS (SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company AND b.branch_id=@branch
                AND b.resource_table='crm_companies' AND b.resource_key=c.id::text)
            OR EXISTS (SELECT 1 FROM public.suite_branch_record_shares b WHERE b.company_id=@company AND b.branch_id=@branch
                AND b.resource_table='crm_companies' AND b.resource_key=c.id::text)
        )
        AND NOT EXISTS (SELECT 1 FROM public.srm_anonymous_cash_accounts a WHERE a.customer_id=c.id)
        AND NOT EXISTS (SELECT 1 FROM public.business_pack_record_ownership b WHERE b.company_id=@company
            AND b.resource_table='crm_companies' AND b.resource_key=c.id::text)";

    private const string OrderCatalog = @"
        SELECT p.id,p.sku,p.item_name,CASE WHEN p.product_type='service' THEN 'service' ELSE 'product' END,
               coalesce(p.gst_rate,0),p.xmin::text||':'||coalesce(details.xmin::text,'-'),
               coalesce(p.metadata_json->>'currency','INR'),coalesce(p.sales_rate,0),
               coalesce(details.pricing_options::text,'[]')" +
        SharedCatalogRepository.ProductAndDetail + SharedCatalogRepository.ProductVisibility + @"
        AND p.organization_id=@company AND p.active AND coalesce(p.product_type,'stock') NOT IN ('membership','subscription','bundle')";

    internal async Task<string> SalesOrderCurrencyAsync() =>
        await ReadDraftOptionsAsync(async (db, tx, branch, actor) =>
        {
            using var query = RegisterCommand(@"SELECT default_currency FROM public.companies WHERE id=@company",
                db, tx, branch, actor.Id);
            return await query.ExecuteScalarAsync() is string code && ValidOrderCurrency(code) ? code : "INR";
        });

    internal async Task<bool> CanCreateSalesOrderAsync()
    {
        try
        {
            await SalesOrderCurrencyAsync();
            return true;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    internal Task<List<SalesCustomer>> SalesCustomersAsync(string search) =>
        ReadDraftOptionsAsync(async (db, tx, branch, actor) =>
        {
            using var query = RegisterCommand(@"SELECT c.id,c.name FROM public.crm_companies c" + OrderCustomerScope + @"
                AND (@search='' OR strpos(lower(c.name),lower(@search))>0 OR strpos(lower(coalesce(c.email,'')),lower(@search))>0)
                ORDER BY lower(c.name),c.id LIMIT 120", db, tx, branch, actor.Id);
            query.Parameters.AddWithValue("search", NpgsqlDbType.Text, search.Trim());
            var rows = new List<SalesCustomer>();
            using var reader = await query.ExecuteReaderAsync();
            while (await reader.ReadAsync())
                rows.Add(new SalesCustomer(reader.GetInt32(0), reader.GetString(1)));
            return rows;
        });

    internal Task<List<SalesCatalogItem>> SalesCatalogAsync(string search) =>
        ReadDraftOptionsAsync(async (db, tx, branch, actor) =>
        {
            using var query = new NpgsqlCommand(OrderCatalog + @"
                AND (@search='' OR strpos(lower(p.item_name),lower(@search))>0 OR strpos(lower(p.sku),lower(@search))>0)
                ORDER BY lower(p.item_name),p.id LIMIT 120", db, tx);
            SharedCatalogRepository.BindProductScope(query, settings.OrganizationId, branch, actor);
            query.Parameters.AddWithValue("search", NpgsqlDbType.Text, search.Trim());
            return await ReadSalesCatalogAsync(query);
        });

    internal async Task<SalesOrderCreated> CreateSalesOrderAsync(SalesOrderDraft draft)
    {
        string title = draft.Title.Trim();
        ValidateDraft(draft, title);
        var numbers = draft.Lines.Select(CalculateLine).ToArray();
        var subtotal = numbers.Sum(line => line.Subtotal);
        var discount = numbers.Sum(line => line.Discount);
        var tax = numbers.Sum(line => line.Tax);
        var total = numbers.Sum(line => line.Total);
        if (subtotal > MaximumOrderMoney || discount > MaximumOrderMoney || tax > MaximumOrderMoney || total > MaximumOrderMoney)
            throw new ArgumentException("This sales order exceeds the supported total.");
        string hash = HashSalesPayload(draft);
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to create a sales order.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await RequireSalesOrderCreateAsync(db, tx, branch, actor);
        if (await PreviousOrderAsync(db, tx, branch, actor.Id, draft.Request, hash) is { } retry)
        {
            tx.Commit();
            return retry;
        }

        using var customer = RegisterCommand("SELECT c.id FROM public.crm_companies c" + OrderCustomerScope +
            " AND c.id=@id FOR SHARE OF c", db, tx, branch, actor.Id);
        customer.Parameters.AddWithValue("id", NpgsqlDbType.Integer, draft.CustomerId);
        if (await customer.ExecuteScalarAsync() is not int)
            throw new InvalidOperationException("The selected customer is unavailable in this branch.");
        using var products = new NpgsqlCommand(OrderCatalog +
            " AND p.id=ANY(@ids) ORDER BY p.id FOR SHARE OF p", db, tx);
        SharedCatalogRepository.BindProductScope(products, settings.OrganizationId, branch, actor);
        products.Parameters.AddWithValue("ids", NpgsqlDbType.Array | NpgsqlDbType.Integer,
            draft.Lines.Select(line => line.ItemId).ToArray());
        var source = (await ReadSalesCatalogAsync(products)).ToDictionary(item => item.Id);
        var persisted = draft.Lines.Select((line, index) =>
        {
            if (!source.TryGetValue(line.ItemId, out var row) || row.Revision != line.Revision)
                throw new InvalidOperationException("A selected catalog item changed or is unavailable. Reload it before saving.");
            if (!row.Prices.Any(price => price.Currency == draft.Currency && price.Id == line.PricingId))
                throw new ArgumentException($"{row.Name}: choose a price in {draft.Currency}.");
            return new
            {
                product_id = row.Id,
                item_code = row.Code,
                description = row.Name,
                service_type = row.Kind,
                quantity = line.Quantity,
                unit_price = line.UnitPrice,
                discount_amount = numbers[index].Discount,
                tax_amount = numbers[index].Tax,
                line_total = numbers[index].Total
            };
        }).ToArray();

        string number = await ReserveCommercialNumberAsync(db, tx, CommercialNumberSeries.SalesOrder);
        using var insert = RegisterCommand(@"
            WITH header AS (
                INSERT INTO public.srm_sales_orders (
                    organization_id,order_number,title,status,customer_id,assigned_user_id,created_by,currency,
                    subtotal,discount_amount,tax_amount,total_amount,expected_start_date,expected_end_date,terms,metadata_json
                )
                VALUES (@company,@number,@title,'draft',@customer,@actor,@actor,@currency,@subtotal,@discount,@tax,@total,
                    @start,@end,@terms,json_build_object('desktop_create_request',@request,'desktop_create_sha256',@hash))
                RETURNING *
            ), lines AS (
                INSERT INTO public.srm_sales_order_lines (
                    sales_order_id,product_id,item_code,description,service_type,quantity,unit_price,discount_amount,tax_amount,line_total
                )
                SELECT h.id,p.product_id,p.item_code,p.description,p.service_type,p.quantity,p.unit_price,p.discount_amount,p.tax_amount,p.line_total
                FROM header h CROSS JOIN jsonb_to_recordset(@lines) AS p(product_id int,item_code text,description text,
                     service_type text,quantity numeric,unit_price numeric,discount_amount numeric,tax_amount numeric,line_total numeric)
                RETURNING id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'sales_order',id,'created',@actor,row_to_json(header) FROM header RETURNING id
            ), stamp AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'srm_sales_orders',id::text,@company,@branch,'validated-write' FROM header
                UNION ALL SELECT 'srm_sales_order_lines',id::text,@company,@branch,'validated-write' FROM lines
                UNION ALL SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit RETURNING resource_key
            )
            SELECT h.id FROM header h WHERE (SELECT count(*) FROM stamp) = @count",
            db, tx, branch, actor.Id);
        insert.Parameters.AddWithValue("number", NpgsqlDbType.Text, number);
        insert.Parameters.AddWithValue("title", NpgsqlDbType.Text, title);
        insert.Parameters.AddWithValue("customer", NpgsqlDbType.Integer, draft.CustomerId);
        insert.Parameters.AddWithValue("currency", NpgsqlDbType.Text, draft.Currency);
        insert.Parameters.AddWithValue("subtotal", NpgsqlDbType.Numeric, subtotal);
        insert.Parameters.AddWithValue("discount", NpgsqlDbType.Numeric, discount);
        insert.Parameters.AddWithValue("tax", NpgsqlDbType.Numeric, tax);
        insert.Parameters.AddWithValue("total", NpgsqlDbType.Numeric, total);
        insert.Parameters.AddWithValue("start", NpgsqlDbType.Date, (object?)draft.Start?.Date ?? DBNull.Value);
        insert.Parameters.AddWithValue("end", NpgsqlDbType.Date, (object?)draft.End?.Date ?? DBNull.Value);
        insert.Parameters.AddWithValue("terms", NpgsqlDbType.Text, draft.Terms);
        insert.Parameters.AddWithValue("request", NpgsqlDbType.Text, draft.Request.ToString());
        insert.Parameters.AddWithValue("hash", NpgsqlDbType.Text, hash);
        insert.Parameters.AddWithValue("lines", NpgsqlDbType.Jsonb, JsonSerializer.Serialize(persisted));
        insert.Parameters.AddWithValue("count", NpgsqlDbType.Integer, persisted.Length + 2);
        if (await insert.ExecuteScalarAsync() is not int id)
            throw new InvalidOperationException("The sales order, items and audit could not all be saved.");
        tx.Commit();
        return new SalesOrderCreated(id, number);
    }

    private async Task<T> ReadDraftOptionsAsync<T>(Func<NpgsqlConnection, NpgsqlTransaction, int, DesktopActor, Task<T>> read)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to create a sales order.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(System.Data.IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await RequireSalesOrderCreateAsync(db, tx, branch, actor);
        var result = await read(db, tx, branch, actor);
        tx.Commit();
        return result;
    }

    private async Task RequireSalesOrderCreateAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor)
    {
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        var grant = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor,
            "srm", "create", "srm_manage", "srm_admin");
        var customerGrant = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor,
            "srm", "view", "srm_view", "srm_admin");
        if (grant.Scope != "organization" || customerGrant.Scope != "organization")
            throw new UnauthorizedAccessException("Sales order creation requires access to the shared customer and catalog records in this branch.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop sales order creation");
    }

    private async Task<SalesOrderCreated?> PreviousOrderAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor,
        Guid request, string hash)
    {
        using var query = RegisterCommand(@"
            SELECT o.id,o.order_number,o.created_by=@actor AND o.metadata_json->>'desktop_create_sha256'=@hash
                AND EXISTS (SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company
                    AND b.branch_id=@branch AND b.resource_table='srm_sales_orders' AND b.resource_key=o.id::text)
                AND NOT EXISTS (SELECT 1 FROM public.business_pack_record_ownership b WHERE b.company_id=@company
                    AND b.resource_table='srm_sales_orders' AND b.resource_key=o.id::text)
            FROM public.srm_sales_orders o WHERE o.organization_id=@company AND o.metadata_json->>'desktop_create_request'=@request
            ORDER BY o.id LIMIT 2", db, tx, branch, actor);
        query.Parameters.AddWithValue("request", NpgsqlDbType.Text, request.ToString());
        query.Parameters.AddWithValue("hash", NpgsqlDbType.Text, hash);
        using var row = await query.ExecuteReaderAsync();
        if (!await row.ReadAsync())
            return null;
        if (row.IsDBNull(2) || !row.GetBoolean(2))
            throw new InvalidOperationException("This request already belongs to an unavailable or different order.");
        var retry = new SalesOrderCreated(row.GetInt32(0), row.GetString(1));
        if (await row.ReadAsync())
            throw new InvalidOperationException("Multiple orders match this request. Review the saved records.");
        return retry;
    }

    private static async Task<List<SalesCatalogItem>> ReadSalesCatalogAsync(NpgsqlCommand query)
    {
        var rows = new List<SalesCatalogItem>();
        using var reader = await query.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            var prices = new List<SalesCatalogPrice>
            {
                new SalesCatalogPrice("", "Base price", reader.GetString(6), reader.GetDecimal(7))
            };
            using var json = JsonDocument.Parse(reader.GetString(8));
            if (json.RootElement.ValueKind == JsonValueKind.Array)
                foreach (var option in json.RootElement.EnumerateArray())
                {
                    if (option.ValueKind != JsonValueKind.Object ||
                        !option.TryGetProperty("id", out var id) || id.ValueKind != JsonValueKind.String ||
                        !option.TryGetProperty("currency", out var currency) || currency.ValueKind != JsonValueKind.String ||
                        !option.TryGetProperty("amount", out var amount) ||
                        !decimal.TryParse(amount.ToString(), NumberStyles.Number, CultureInfo.InvariantCulture, out decimal price) ||
                        string.IsNullOrEmpty(id.GetString()) || !ValidOrderCurrency(currency.GetString()!))
                        continue;
                    string label = option.TryGetProperty("name", out var name) ? name.ToString() : "Catalog price";
                    prices.Add(new SalesCatalogPrice(id.GetString()!, label, currency.GetString()!, price));
                }
            rows.Add(new SalesCatalogItem(reader.GetInt32(0), reader.GetString(1), reader.GetString(2), reader.GetString(3),
                reader.GetDecimal(4), reader.GetString(5), prices));
        }
        return rows;
    }

    private static void ValidateDraft(SalesOrderDraft draft, string title)
    {
        if (title.Length is 0 or > 220)
            throw new ArgumentException("Enter a sales order title of up to 220 characters.");
        if (draft.CustomerId <= 0)
            throw new ArgumentException("Choose a shared customer.");
        if (draft.Start?.Date > draft.End?.Date)
            throw new ArgumentException("Start date cannot be after end date.");
        if (!ValidOrderCurrency(draft.Currency))
            throw new ArgumentException("Enter a three-letter order currency.");
        if (draft.Terms.Length > 10000 || draft.Request == Guid.Empty)
            throw new ArgumentException("The draft request or terms are invalid.");
        if (draft.Lines.Count is 0 or > 200 || draft.Lines.Select(line => line.ItemId).Distinct().Count() != draft.Lines.Count)
            throw new ArgumentException("Select between 1 and 200 distinct products or services.");
    }

    internal static SalesLineAmounts CalculateLine(SalesOrderInputLine line)
    {
        if (line.ItemId <= 0)
            throw new ArgumentException("Choose a catalog item.");
        return CalculateStandaloneLine(line);
    }

    private static SalesLineAmounts CalculateStandaloneLine(SalesOrderInputLine line)
    {
        if (line.Quantity <= 0 || line.Quantity > 1_000_000_000m ||
            decimal.Round(line.Quantity, 2) != line.Quantity)
            throw new ArgumentException("Enter a positive quantity with at most two decimal places.");
        if (line.UnitPrice < 0 || line.UnitPrice > MaximumLineMoney || decimal.Round(line.UnitPrice, 2) != line.UnitPrice)
            throw new ArgumentException("Enter a nonnegative unit price with at most two decimal places.");
        if (line.DiscountRate < 0 || line.DiscountRate > 100 || line.TaxRate < 0 || line.TaxRate > 100)
            throw new ArgumentException("Discount and tax rates must be between 0 and 100 percent.");
        decimal gross = RoundLine(line.Quantity * line.UnitPrice);
        decimal discount = RoundLine(gross * line.DiscountRate / 100);
        decimal tax = RoundLine((gross - discount) * line.TaxRate / 100);
        decimal total = gross - discount + tax;
        if (gross > MaximumLineMoney || tax > MaximumLineMoney || total > MaximumLineMoney)
            throw new ArgumentException("An item exceeds the supported line amount.");
        return new SalesLineAmounts(gross, discount, tax, total);
    }

    private static bool ValidOrderCurrency(string code) => code.Length == 3 && code.All(ch => ch is >= 'A' and <= 'Z');
    private static decimal RoundLine(decimal amount) => decimal.Round(amount, 2, MidpointRounding.AwayFromZero);

    private static string HashSalesPayload<T>(T payload)
    {
        using var sha = SHA256.Create();
        return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(JsonSerializer.Serialize(payload))))
            .Replace("-", "").ToLowerInvariant();
    }
}
