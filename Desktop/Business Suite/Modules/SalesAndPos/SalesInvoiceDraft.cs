using System.Globalization;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record SalesInvoiceDraftResult(int Id, string Number, string Currency, decimal Total, DateTime Due);
internal sealed record SalesInvoiceDraftLine(int? SourceLineId, string Description, decimal Quantity, decimal Price, decimal Discount, decimal Tax, decimal Subtotal, decimal Total);

internal sealed partial class SalesOrderRepository
{
    internal async Task<bool> CanDraftSalesInvoiceAsync(int orderId)
    {
        if (settings.BranchId is not int branch)
            return false;
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(System.Data.IsolationLevel.RepeatableRead);
        try
        {
            var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
            string scope = await SalesInvoiceScopeAsync(db, tx, branch, actor);
            return await ReadApprovalOrderAsync(db, tx, branch, actor, scope, orderId, lockRow: false) is not null;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    private async Task<string> SalesInvoiceScopeAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor)
    {
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "create", invoiceDraft: true);
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop sales invoice drafts");
        return scope;
    }

    internal async Task<SalesInvoiceDraftResult> DraftSalesInvoiceAsync(int orderId)
    {
        if (orderId <= 0)
            throw new ArgumentException("Select a sales order.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to create an invoice draft.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await SalesInvoiceScopeAsync(db, tx, branch, actor);
        var order = await ReadApprovalOrderAsync(db, tx, branch, actor, scope, orderId, lockRow: true)
            ?? throw new InvalidOperationException("The sales order is unavailable for native invoicing in this branch.");
        await ValidateConfirmationSourcesAsync(db, tx, branch, actor, orderId);
        await RequireUnbilledSalesOrderAsync(db, tx, branch, actor.Id, orderId);
        if (!ValidInvoiceCurrency(order.Currency))
            throw new InvalidOperationException("The order currency is unsupported by the commercial invoice ledger.");
        var lines = await ReadInvoiceSourceLinesAsync(db, tx, branch, actor.Id, orderId, order);
        string number = await ReserveCommercialNumberAsync(db, tx, CommercialNumberSeries.Invoice);
        var result = await SaveSalesInvoiceDraftAsync(db, tx, branch, actor.Id, orderId, order.Currency, number, lines);
        tx.Commit();
        return result;
    }

    private async Task RequireUnbilledSalesOrderAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor, int order,
        int? milestone = null)
    {
        using var query = RegisterCommand(@"
            WITH engagements AS (SELECT id FROM public.srm_engagements WHERE sales_order_id=@order),
                 milestones AS (
                    SELECT m.id FROM public.srm_billing_milestones m JOIN public.srm_billing_plans p ON p.id=m.billing_plan_id
                    WHERE p.engagement_id IN (SELECT id FROM engagements)
                 )
            SELECT EXISTS (
                SELECT 1 FROM public.srm_invoice_lines il
                WHERE (il.source_type='sales_order' AND il.source_id=@order)
                   OR (il.source_type='sales_order_line' AND il.source_id IN
                        (SELECT id FROM public.srm_sales_order_lines WHERE sales_order_id=@order))
                   OR (il.source_type='engagement' AND il.source_id IN (SELECT id FROM engagements))
                   OR (il.source_type='billing_milestone'
                        AND ((@milestone IS NULL AND il.source_id IN (SELECT id FROM milestones)) OR il.source_id=@milestone))
            ) OR EXISTS (SELECT 1 FROM public.srm_invoices i WHERE i.sales_order_id=@order AND i.engagement_id IS NULL),
            EXISTS (
                SELECT 1 FROM public.business_project_commercial p JOIN public.srm_industry_records r ON r.project_id=p.project_id
                WHERE p.sales_order_id=@order AND r.organization_id=@company AND r.kind IN ('boq','variation') AND r.status='approved'
            )", db, tx, branch, actor);
        query.Parameters.AddWithValue("order", order);
        query.Parameters.AddWithValue("milestone", NpgsqlDbType.Integer, (object?)milestone ?? DBNull.Value);
        using var reader = await query.ExecuteReaderAsync();
        await reader.ReadAsync();
        if (reader.GetBoolean(1))
            throw new InvalidOperationException("This project uses approved measurement billing. Bill the certified measurements in Construction operations.");
        if (reader.GetBoolean(0))
            throw new InvalidOperationException("This commercial source is already reserved by an order, engagement, or milestone invoice.");
    }

    private async Task<List<SalesInvoiceDraftLine>> ReadInvoiceSourceLinesAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, int actor, int orderId, ApprovalOrder order)
    {
        using var query = RegisterCommand(@"SELECT id,coalesce(nullif(description,''),@title),coalesce(quantity,0),
            coalesce(unit_price,0),coalesce(discount_amount,0),coalesce(tax_amount,0)
            FROM public.srm_sales_order_lines WHERE sales_order_id=@order ORDER BY id LIMIT 201", db, tx, branch, actor);
        query.Parameters.AddWithValue("order", orderId);
        query.Parameters.AddWithValue("title", order.Title);
        var rows = new List<SalesInvoiceDraftLine>();
        using var reader = await query.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            if (rows.Count == 200)
                throw new InvalidOperationException("An invoice supports up to 200 lines.");
            rows.Add(NormalizeInvoiceLine(reader.GetInt32(0), reader.GetString(1), reader.GetDecimal(2), reader.GetDecimal(3),
                reader.GetDecimal(4), reader.GetDecimal(5)));
        }
        if (rows.Count == 0)
            rows.Add(NormalizeInvoiceLine(null, order.Title, 1, order.Total, 0, 0));
        foreach (decimal amount in new[] { rows.Sum(row => row.Subtotal), rows.Sum(row => row.Discount), rows.Sum(row => row.Tax), rows.Sum(row => row.Total) })
            ValidateInvoiceAmount(amount);
        return rows;
    }

    private static SalesInvoiceDraftLine NormalizeInvoiceLine(int? line, string description, decimal quantity,
        decimal price, decimal discount, decimal tax)
    {
        foreach (decimal value in new[] { quantity, price, discount, tax })
            ValidateInvoiceAmount(value);
        price = decimal.Round(price, 2, MidpointRounding.AwayFromZero);
        discount = decimal.Round(discount, 2, MidpointRounding.AwayFromZero);
        tax = decimal.Round(tax, 2, MidpointRounding.AwayFromZero);
        decimal raw = quantity * price;
        if (quantity <= 0 || string.IsNullOrWhiteSpace(description) || description.Length > 2000 || discount > raw)
            throw new InvalidOperationException("Invoice lines need a description, positive quantity and a discount within the line subtotal.");
        decimal subtotal = decimal.Round(raw, 2, MidpointRounding.AwayFromZero);
        decimal total = subtotal - discount + tax;
        ValidateInvoiceAmount(total);
        return new SalesInvoiceDraftLine(line, description, quantity, price, discount, tax, subtotal, total);
    }

    private static bool ValidInvoiceCurrency(string currency) => currency is
        "INR" or "USD" or "AED" or "EUR" or "GBP" or "SAR" or "CAD" or "AUD" or "SGD" or "JPY" or
        "CHF" or "CNY" or "NZD" or "ZAR" or "QAR";

    private static void ValidateInvoiceAmount(decimal value)
    {
        if (value < 0 || value > 99999999999m)
            throw new InvalidOperationException("Invoice quantities and amounts must be nonnegative and within supported limits.");
    }
}
