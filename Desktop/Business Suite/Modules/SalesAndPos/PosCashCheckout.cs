using System.Data;
using System.Globalization;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PosCheckoutItem(Guid LineKey, int ProductId, decimal Quantity, decimal Price, decimal Tax);
internal sealed record PosCheckoutIntent(Guid Request, Guid PaymentKey, string Register, string Currency, int CustomerId,
    string Notes, decimal Total, IReadOnlyList<PosCheckoutItem> Items)
{
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Tender { get; init; }

    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Reference { get; init; }

    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public IReadOnlyList<PosTenderPart>? Parts { get; init; }

    [JsonIgnore]
    internal string PaymentMethod => Tender ?? "cash";
}
internal sealed record PosCheckoutResult(int CheckoutId, string OrderNumber, string InvoiceNumber, string? ReceiptNumber,
    decimal Total, string Currency, decimal Outstanding, decimal Change = 0);
internal sealed class PosCheckoutRejectedException(string message) : InvalidOperationException(message);

internal sealed partial class SalesOrderRepository
{
    private sealed record CheckoutProduct(PosCartLine Line, Guid Key, bool Track, int? Warehouse, string? Hsn);

    internal SalesIntentJournal<PosCheckoutIntent> PosCheckoutJournal() =>
        new(settings, "POS cash checkout", "", ValidateCheckoutIntent,
            "A saved checkout could not be verified. Reconcile the register before taking another payment.");

    private static void ValidateCheckoutIntent(PosCheckoutIntent intent)
    {
        if (intent.Request == Guid.Empty || intent.PaymentKey == Guid.Empty || intent.CustomerId < 0 ||
            intent.PaymentMethod is not ("cash" or "card" or "upi" or "bank_transfer" or "credit" or "split") ||
            ((intent.PaymentMethod is "credit" or "split") && intent.Reference is not null) ||
            (intent.PaymentMethod != "split" && intent.Parts is not null) ||
            intent.Reference is { } reference && (reference.Length > 120 || reference.IndexOf('\0') >= 0) ||
            string.IsNullOrWhiteSpace(intent.Register) || intent.Register.Length > 80 ||
            intent.Currency is null || !ValidInvoiceCurrency(intent.Currency) || intent.Notes is null ||
            intent.Notes.Length > 500 || intent.Notes.IndexOf('\0') >= 0 ||
            intent.Total <= 0 || intent.Total > 99999999999m || decimal.Round(intent.Total, 2) != intent.Total ||
            intent.Items is null || intent.Items.Count is < 1 or > 100 ||
            intent.Items.Any(line => line is null || line.LineKey == Guid.Empty || line.ProductId <= 0 || line.Quantity <= 0 ||
                line.Quantity > 9999999m || decimal.Round(line.Quantity, 3) != line.Quantity || line.Price < 0 ||
                line.Price > 99999999999m || decimal.Round(line.Price, 2) != line.Price || line.Tax < 0 || line.Tax > 100) ||
            intent.Items.Select(line => line.LineKey).Distinct().Count() != intent.Items.Count ||
            intent.Items.Select(line => line.ProductId).Distinct().Count() != intent.Items.Count)
            throw new ArgumentException("Use a valid buyer mode and register and 1 to 100 stock lines with a supported payment and a positive total.");
        if (intent.CustomerId == 0 && intent.PaymentMethod == "credit")
            throw new ArgumentException("Walk-in sales require full payment at checkout. Select a named customer for credit.");
        if (intent.PaymentMethod == "split")
            GetPosTenderAllocation(intent);
    }

    internal Task<bool> CanCheckoutPosCashAsync() => CanCheckoutPosAsync(collect: true);
    internal Task<bool> CanCheckoutPosCreditAsync() => CanCheckoutPosAsync(collect: false);

    private async Task<bool> CanCheckoutPosAsync(bool collect)
    {
        if (settings.BranchId is not int branch)
            return false;
        try
        {
            using var db = new NpgsqlConnection(settings.ConnectionString);
            await db.OpenAsync();
            using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
            using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
                await readOnly.ExecuteNonQueryAsync();
            var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
            await RequirePosCheckoutAsync(db, tx, branch, actor, collect);
            return true;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    private async Task RequirePosCheckoutAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor, bool collect = true)
    {
        await RequireHeldWriterAsync(db, tx, branch, actor, "create");
        await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "create", invoiceDraft: true);
        await InvoiceApprovalScopeAsync(db, tx, branch, actor);
        if (collect)
            await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "approve", collection: true);
    }

    internal async Task<PosCheckoutResult> CheckoutPosCashAsync(PosCheckoutIntent intent)
    {
        ValidateCheckoutIntent(intent);
        var allocation = GetPosTenderAllocation(intent);
        bool collect = allocation.Payments.Count > 0;
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch before checking out.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await RequirePosCheckoutAsync(db, tx, branch, actor, collect);
        AnonymousCheckoutBuyer? anonymous = intent.CustomerId == 0
            ? await ResolveAnonymousCheckoutBuyerAsync(db, tx, branch, actor.Id, lockRows: true) ??
                throw new PosCheckoutRejectedException("An administrator must enable a valid walk-in counter account for this branch.")
            : null;
        int customerId = anonymous?.Id ?? intent.CustomerId;
        string digest = CheckoutDigest(intent);
        var previous = await FindPosCheckoutAsync(db, tx, branch, actor.Id, intent, digest, customerId, allocation);
        if (previous is not null)
        {
            tx.Commit();
            return previous;
        }

        var register = await FindActiveRegisterAsync(db, tx, branch, actor.Id);
        if (register is null || register.Number != intent.Register || register.Currency != intent.Currency)
            throw new PosCheckoutRejectedException("Select an open register in the cart currency.");
        int sessionId;
        using (var session = RegisterQuery("SELECT p.id FROM public.srm_pos_sessions p" + OwnSession +
            " AND p.status='open' FOR UPDATE OF p", db, tx, branch, actor.Id, intent.Register))
        {
            sessionId = await session.ExecuteScalarAsync() is int id ? id
                : throw new PosCheckoutRejectedException("The cashier register is unavailable.");
        }
        decimal cashToDrawer = allocation.Payments.Where(part => part.Method == "cash").Sum(part => part.Amount);
        if (cashToDrawer > 0)
        {
            var snapshot = await ReadCashSnapshotAsync(db, tx, branch, actor.Id, intent.Register);
            if (snapshot.Currency != intent.Currency || snapshot.Expected + cashToDrawer > MaximumOpeningCash)
                throw new PosCheckoutRejectedException("The register denomination or drawer total requires reconciliation.");
        }

        if (anonymous is null)
        {
            using var customer = RegisterCommand("SELECT c.id FROM public.crm_companies c " + OrderCustomerScope +
            " AND c.id=@customer FOR UPDATE OF c", db, tx, branch, actor.Id);
            customer.Parameters.AddWithValue("customer", customerId);
            if (await customer.ExecuteScalarAsync() is null)
                throw new PosCheckoutRejectedException("Select a named customer available in this branch.");
        }
        var lines = await LoadCheckoutProductsAsync(db, tx, branch, actor, intent);
        if (lines.Sum(line => line.Line.LineTotal) != intent.Total)
            throw new PosCheckoutRejectedException("The checkout total changed. Review the current prices and tax.");
        string orderNumber = await ReserveCommercialNumberAsync(db, tx, CommercialNumberSeries.SalesOrder);
        var order = await CreatePosCheckoutOrderAsync(db, tx, branch, actor.Id, sessionId, orderNumber, customerId, intent, lines);
        string invoiceNumber = await ReserveCommercialNumberAsync(db, tx, CommercialNumberSeries.Invoice);
        var invoice = await SaveSalesInvoiceDraftAsync(db, tx, branch, actor.Id, order.Id, intent.Currency, invoiceNumber, order.Lines);
        string terms = await ResolveInvoiceTerminologyAsync(db, tx, branch, actor.Id);
        await SaveInvoiceIssueAsync(db, tx, branch, actor.Id, invoice.Id, "draft", terms, anonymous);
        int checkout = await CommitPosCheckoutGraphAsync(db, tx, branch, actor.Id, sessionId, order.Id, invoice.Id,
            digest, customerId, intent);
        var receipts = new List<string>();
        foreach (var tender in allocation.Payments)
        {
            string receiptNumber = await ReserveCommercialNumberAsync(db, tx, CommercialNumberSeries.Receipt);
            await SaveGroupedPosTenderAsync(db, tx, branch, actor.Id, checkout, invoice.Id, customerId, sessionId,
                intent.Currency, receiptNumber, tender.Key, tender.Method, tender.Reference, tender.Amount,
                PosTenderDigest(tender.Key, tender.Method, tender.Reference, tender.Amount));
            receipts.Add(receiptNumber);
        }
        tx.Commit();
        return new PosCheckoutResult(checkout, orderNumber, invoiceNumber, receipts.Count == 0 ? null : string.Join(", ", receipts),
            intent.Total, intent.Currency, intent.Total - allocation.Paid, allocation.Change);
    }

    private static string CheckoutDigest(PosCheckoutIntent intent)
    {
        using var sha = SHA256.Create();
        return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(JsonSerializer.Serialize(intent, HeldJson))))
            .Replace("-", "").ToLowerInvariant();
    }

    private async Task<List<CheckoutProduct>> LoadCheckoutProductsAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, DesktopActor actor, PosCheckoutIntent intent)
    {
        using var query = new NpgsqlCommand(PosProductSource + " AND p.id=ANY(@products) FOR UPDATE OF p", db, tx);
        SharedCatalogRepository.BindProductScope(query, settings.OrganizationId, branch, actor);
        query.Parameters.AddWithValue("currency", intent.Currency);
        query.Parameters.AddWithValue("products", NpgsqlDbType.Array | NpgsqlDbType.Integer, intent.Items.Select(i => i.ProductId).ToArray());
        var input = intent.Items.ToDictionary(i => i.ProductId);
        var result = new Dictionary<int, CheckoutProduct>();
        using var reader = await query.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            var source = new PosCartProduct(reader.GetInt32(0), reader.GetString(1), reader.GetString(2), reader.GetString(3),
                reader.GetDecimal(4), reader.GetDecimal(5));
            var line = input[source.Id];
            if (source.Price != line.Price || source.Tax != line.Tax)
                throw new PosCheckoutRejectedException("POS price or tax changed. Reload the catalog and review the bill.");
            if (!reader.IsDBNull(9))
            {
                using var config = JsonDocument.Parse(reader.GetString(9));
                if (config.RootElement.ValueKind != JsonValueKind.Null &&
                    (config.RootElement.ValueKind != JsonValueKind.Object ||
                    (config.RootElement.TryGetProperty("required", out var required) &&
                        required.ValueKind is not (JsonValueKind.False or JsonValueKind.Null))))
                    throw new PosCheckoutRejectedException("A catalog item requires follow-up scheduling before checkout.");
            }
            bool stock = reader.GetBoolean(6);
            int? warehouse = reader.IsDBNull(7) ? null : reader.GetInt32(7);
            if (stock && warehouse is null)
                throw new PosCheckoutRejectedException("A default branch warehouse is required for tracked stock.");
            result.Add(source.Id, new CheckoutProduct(PriceCartLine(source, line.Quantity), line.LineKey, stock, warehouse,
                reader.IsDBNull(8) ? null : reader.GetString(8)));
        }
        if (result.Count != intent.Items.Count)
            throw new PosCheckoutRejectedException("A stock item is unavailable for this register.");
        return intent.Items.Select(i => result[i.ProductId]).ToList();
    }
}
