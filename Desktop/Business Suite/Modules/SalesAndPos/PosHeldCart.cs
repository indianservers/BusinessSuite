using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PosCartProduct(int Id, string Sku, string Name, string Barcode, decimal Price, decimal Tax);
internal sealed record PosCartEntry(int ProductId, decimal Quantity);
internal sealed record PosCartLine(int ProductId, string Sku, string Name, decimal Quantity, decimal UnitPrice, decimal TaxRate, decimal LineTotal);
internal sealed record PosHoldCart(Guid Request, int? CustomerId, string Notes, IReadOnlyList<PosCartEntry> Lines);
internal sealed record PosHeldBillRow(int Id, string Number, string Customer, string Notes, decimal Amount, int ItemCount, DateTime? Created, string Status);
internal sealed class PosHoldRejectedException(string message) : InvalidOperationException(message);
internal sealed record PosHeldCart(int Id, string Number, int? CustomerId, string Customer, string Notes, List<PosCartLine> Lines);
internal sealed record PosCartOptions(string Register, string Currency, List<PosCartProduct> Products, List<SalesCustomer> Customers, bool CanChange, bool CanCancel);

internal sealed partial class SalesOrderRepository
{
    private static readonly JsonSerializerOptions HeldJson = new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase };
    private sealed record HeldLine(string Format, string Request, string Currency, int ProductId, string Sku, string Name,
        decimal Quantity, decimal UnitPrice, decimal TaxRate, decimal LineTotal);

    private const string PosProductSource = @"
        SELECT p.id,p.sku,p.item_name,coalesce(p.barcode,''),coalesce(p.sales_rate,0),coalesce(p.gst_rate,0),
            coalesce(p.track_inventory,false),p.default_warehouse_id,p.hsn_code,p.metadata_json->'follow_up'
        " + SharedCatalogRepository.ProductAndDetail + SharedCatalogRepository.ProductVisibility + @"
        AND p.organization_id=@company AND p.active AND lower(trim(coalesce(p.product_type,'stock'))) IN ('stock','product','goods')
        AND coalesce(p.metadata_json->>'currency','INR')=@currency
        AND NOT (coalesce(p.batch_tracking,false) OR coalesce(p.serial_tracking,false) OR coalesce(p.expiry_tracking,false))
        AND NOT EXISTS (SELECT 1 FROM public.business_pharma_batch_receipts r JOIN public.business_pharma_batch_availability a
            ON a.organization_id=r.organization_id AND a.batch_id=r.batch_id WHERE r.organization_id=@company AND r.product_id=p.id)";

    internal SalesIntentJournal<PosHoldCart> HeldCartJournal(string register) => new(settings, "Held POS bills", register, ValidateHeldCart,
        "A saved hold request could not be verified. Review held bills before saving another cart.");

    internal async Task<PosCartOptions> PosCartOptionsAsync(string search)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to open the POS cart.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor);
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop POS cart");
        var register = await FindActiveRegisterAsync(db, tx, branch, actor.Id);
        if (register is null || !ValidOrderCurrency(register.Currency))
            throw new InvalidOperationException("Open a register in this branch before preparing a cart.");
        bool canChange = false;
        bool canCancel = false;
        try { await RequireHeldWriterAsync(db, tx, branch, actor, "create"); canChange = true; }
        catch (UnauthorizedAccessException) { }
        try { await RequireHeldWriterAsync(db, tx, branch, actor, "delete"); canCancel = true; }
        catch (UnauthorizedAccessException) { }

        using var catalog = new NpgsqlCommand(PosProductSource + @"
            AND (@search='' OR strpos(lower(p.item_name),lower(@search))>0 OR strpos(lower(p.sku),lower(@search))>0
                OR p.barcode=@search)
            ORDER BY (p.barcode=@search) DESC NULLS LAST,lower(p.item_name),p.id LIMIT 120", db, tx);
        SharedCatalogRepository.BindProductScope(catalog, settings.OrganizationId, branch, actor);
        catalog.Parameters.AddWithValue("currency", register.Currency);
        catalog.Parameters.AddWithValue("search", search.Trim());
        var products = await ReadPosCartProductsAsync(catalog);
        using var customers = RegisterCommand("SELECT c.id,c.name FROM public.crm_companies c" + OrderCustomerScope +
            " ORDER BY lower(c.name),c.id LIMIT 200", db, tx, branch, actor.Id);
        var parties = new List<SalesCustomer>();
        using (var reader = await customers.ExecuteReaderAsync())
            while (await reader.ReadAsync())
                parties.Add(new SalesCustomer(reader.GetInt32(0), reader.GetString(1)));
        tx.Commit();
        return new PosCartOptions(register.Number, register.Currency, products, parties, canChange, canCancel);
    }

    private static async Task<List<PosCartProduct>> ReadPosCartProductsAsync(NpgsqlCommand query)
    {
        var items = new List<PosCartProduct>();
        using var reader = await query.ExecuteReaderAsync();
        while (await reader.ReadAsync())
            items.Add(new PosCartProduct(reader.GetInt32(0), reader.GetString(1), reader.GetString(2),
                reader.GetString(3), reader.GetDecimal(4), reader.GetDecimal(5)));
        return items;
    }

    private async Task RequireHeldWriterAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor, string action)
    {
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor, "srm", action, "srm_manage", "srm_admin");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop POS held bills");
    }

    internal static PosCartLine PriceCartLine(PosCartProduct product, decimal quantity)
    {
        if (quantity <= 0 || quantity > 9999999m || decimal.Round(quantity, 3) != quantity ||
            product.Price < 0 || product.Tax < 0 || product.Tax > 100)
            throw new ArgumentException("Use a positive quantity up to three decimal places and a valid catalog price and tax rate.");
        decimal net = decimal.Round(product.Price * quantity, 2, MidpointRounding.AwayFromZero);
        decimal total = net + decimal.Round(net * product.Tax / 100m, 2, MidpointRounding.AwayFromZero);
        return new PosCartLine(product.Id, product.Sku, product.Name, quantity, product.Price, product.Tax, total);
    }

    private static void ValidateHeldCart(PosHoldCart cart)
    {
        if (cart.Request == Guid.Empty || cart.Notes is null || cart.Notes.Length > 500 || cart.Notes.IndexOf('\0') >= 0 ||
            cart.Lines.Count is < 1 or > 100 || cart.Lines.Any(l => l.ProductId <= 0 || l.Quantity <= 0 || l.Quantity > 9999999m || decimal.Round(l.Quantity,3) != l.Quantity) ||
            cart.Lines.Select(l => l.ProductId).Distinct().Count() != cart.Lines.Count)
            throw new ArgumentException("Add 1 to 100 unique products and enter a note of up to 500 characters.");

    }

    internal async Task<PosHeldCart> HoldPosCartAsync(string registerNumber, PosHoldCart cart)
    {
        ValidateHeldCart(cart);
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to hold a bill.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await RequireHeldWriterAsync(db, tx, branch, actor, "create");
        var existing = await ReadHeldCartAsync(db, tx, branch, actor.Id, null, cart.Request.ToString());
        if (existing is { } previous)
        {
            if (previous.Cart.CustomerId != cart.CustomerId || previous.Cart.Notes != cart.Notes ||
                previous.Register != registerNumber || !previous.Cart.Lines.Select(l => new PosCartEntry(l.ProductId, l.Quantity)).SequenceEqual(cart.Lines))
                throw new InvalidOperationException("The held bill request was already used with different details.");
            tx.Commit();
            return previous.Cart;
        }
        var register = await FindActiveRegisterAsync(db, tx, branch, actor.Id);
        if (register is null || register.Number != registerNumber || !ValidOrderCurrency(register.Currency))
            throw new PosHoldRejectedException("The active register changed. Reopen its POS cart.");
        string customerName = "Walk-in";
        if (cart.CustomerId is int customer)
        {
            using var lookup = RegisterCommand("SELECT c.name FROM public.crm_companies c " + OrderCustomerScope +
                " AND c.id=@customer FOR UPDATE OF c", db, tx, branch, actor.Id);
            lookup.Parameters.AddWithValue("customer", customer);
            customerName = await lookup.ExecuteScalarAsync() as string
                ?? throw new PosHoldRejectedException("The selected customer is unavailable in this branch.");
        }
        using var products = new NpgsqlCommand(PosProductSource + " AND p.id=ANY(@products) FOR UPDATE OF p", db, tx);
        SharedCatalogRepository.BindProductScope(products, settings.OrganizationId, branch, actor);
        products.Parameters.AddWithValue("currency", register.Currency);
        products.Parameters.AddWithValue("products", NpgsqlDbType.Array | NpgsqlDbType.Integer, cart.Lines.Select(l => l.ProductId).ToArray());
        var available = (await ReadPosCartProductsAsync(products)).ToDictionary(p => p.Id);
        if (available.Count != cart.Lines.Count)
            throw new PosHoldRejectedException("A product is unavailable for this register. Refresh the catalog.");
        var lines = cart.Lines.Select(input => PriceCartLine(available[input.ProductId], input.Quantity)).ToList();
        decimal total = lines.Sum(l => l.LineTotal);
        ValidateInvoiceAmount(total);
        string number = await ReserveCommercialNumberAsync(db, tx, CommercialNumberSeries.HeldBill);
        int id = await InsertHeldCartAsync(db, tx, branch, actor.Id, register, cart, customerName, lines, total, number);
        tx.Commit();
        return new PosHeldCart(id, number, cart.CustomerId, customerName, cart.Notes, lines);
    }

    private async Task<int> InsertHeldCartAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor,
        ActivePosRegister register, PosHoldCart cart, string customer, List<PosCartLine> lines, decimal total, string number)
    {
        using var write = RegisterCommand(@"
            WITH held AS (
                INSERT INTO public.srm_pos_held_bills (organization_id,session_id,hold_number,status,customer_id,customer_name,
                    notes,cart_json,amount,item_count,created_by)
                SELECT @company,p.id,@number,'held',@customer_id,@customer,@notes,@cart,@amount,@count,@actor
                FROM public.srm_pos_sessions p WHERE p.organization_id=@company AND p.session_number=@register AND p.status='open'
                    AND p.cashier_user_id=@actor AND p.deleted_at IS NULL RETURNING *
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'pos_held_bill',id,'held',@actor,
                    (to_jsonb(held)||jsonb_build_object('holdNo',hold_number,'cart',cart_json))::json FROM held RETURNING id
            ), ownership AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'srm_pos_held_bills',id::text,@company,@branch,'validated-write' FROM held
                UNION ALL SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit
            )
            SELECT id FROM held", db, tx, branch, actor);
        write.Parameters.AddWithValue("number", number);
        write.Parameters.AddWithValue("register", register.Number);
        write.Parameters.AddWithValue("customer_id", NpgsqlDbType.Integer, (object?)cart.CustomerId ?? DBNull.Value);
        write.Parameters.AddWithValue("customer", customer);
        write.Parameters.AddWithValue("notes", cart.Notes);
        write.Parameters.AddWithValue("amount", total);
        write.Parameters.AddWithValue("count", lines.Count);
        write.Parameters.AddWithValue("cart", NpgsqlDbType.Json, JsonSerializer.Serialize(lines.Select(l =>
            new HeldLine("desktop-pos-v1", cart.Request.ToString(), register.Currency, l.ProductId, l.Sku, l.Name,
                l.Quantity, l.UnitPrice, l.TaxRate, l.LineTotal)), HeldJson));
        return await write.ExecuteScalarAsync() is int id ? id
            : throw new InvalidOperationException("The register closed before the bill was held.");
    }
}
