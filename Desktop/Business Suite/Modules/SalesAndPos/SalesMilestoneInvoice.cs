using System.Globalization;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

internal sealed record SalesMilestoneInvoiceLink(int Engagement, int Plan, int Milestone);

internal sealed partial class SalesOrderRepository
{
    private sealed record RecurringInvoicePresentation(DateTime IssueDate, int PaymentTerms, string Snapshot);
    private sealed record MilestoneInvoiceSource(int Id, int Engagement, int Plan, int? Buyer,
        RecurringInvoicePresentation? Recurring, bool Batch, bool NotifyRecurring);

    internal async Task<SalesInvoiceDraftResult> DraftSalesMilestoneInvoiceAsync(int order, int engagement, int plan, int milestone)
    {
        if (order < 1 || engagement < 1 || plan < 1 || milestone < 1)
            throw new ArgumentException("Select a saved billing milestone.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose the billing milestone branch.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await SalesInvoiceScopeAsync(db, tx, branch, actor);
        var invoice = await DraftMilestoneSourceAsync(db, tx, branch, actor, scope, order, engagement, plan,
            milestone, DateTime.Today, batch: false);
        tx.Commit();
        return invoice;
    }

    private async Task<SalesInvoiceDraftResult> DraftMilestoneSourceAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        DesktopActor actor, string scope, int order, int engagement, int plan, int milestone, DateTime billingDate, bool batch)
    {
        using var query = ScopedCommand(@"
            SELECT m.name,coalesce(m.status,''),m.due_date,m.invoice_draft_id,coalesce(m.amount,0),coalesce(b.currency,''),
                coalesce(e.customer_id,o.customer_id),coalesce(m.metadata_json->>'recurring','false') NOT IN ('false','0',''),
                m.metadata_json->>'sales_order_line_id',m.metadata_json::text,
                coalesce(m.metadata_json->>'notify_on_creation','true')='true',e.customer_id IS NOT NULL
            " + BillingMilestoneSource + " AND m.id=@milestone AND e.status NOT IN ('closed','cancelled') FOR UPDATE OF o,e,b,m",
            db, tx, branch, actor, scope);
        BindBillingMilestoneChain(query, order, engagement, plan);
        query.Parameters.AddWithValue("milestone", milestone);
        string name;
        string currency;
        decimal amount;
        int? buyer;
        string? sourceLine;
        RecurringInvoicePresentation? recurring;
        bool notify;
        using (var row = await query.ExecuteReaderAsync())
        {
            if (!await row.ReadAsync())
                throw new InvalidOperationException("The billing milestone is unavailable or its engagement is closed.");
            if (!row.IsDBNull(3))
                throw new InvalidOperationException("Billing milestone is already invoiced.");
            if (!row.IsDBNull(2) && row.GetDateTime(2).Date > billingDate)
                throw new InvalidOperationException("Milestone is not yet due for billing.");
            if (row.GetString(1) is not ("approved" or "ready" or "completed"))
                throw new InvalidOperationException("Billing milestone must be approved or completed before invoicing.");
            recurring = row.GetBoolean(7)
                ? ReadRecurringInvoicePresentation(row.IsDBNull(2) ? null : row.GetDateTime(2), row.GetString(9))
                : null;
            if (batch && (recurring is null || !row.GetBoolean(11)))
                throw new InvalidOperationException("A recurring draft needs its saved occurrence and linked engagement customer.");
            notify = batch && row.GetBoolean(10);
            name = row.GetString(0);
            amount = row.GetDecimal(4);
            currency = row.GetString(5);
            buyer = row.IsDBNull(6) ? null : row.GetInt32(6);
            sourceLine = row.IsDBNull(8) ? null : row.GetString(8);
        }
        if (!ValidInvoiceCurrency(currency))
            throw new InvalidOperationException("The billing plan currency is unsupported by the invoice ledger.");
        if (buyer.HasValue)
        {
            using var customer = RegisterCommand("SELECT c.id FROM public.crm_companies c" + OrderCustomerScope +
                " AND c.id=@buyer FOR SHARE OF c", db, tx, branch, actor.Id);
            customer.Parameters.AddWithValue("buyer", buyer.Value);
            if (await customer.ExecuteScalarAsync() is not int)
                throw new InvalidOperationException("The milestone invoice customer is unavailable in this branch.");
        }
        await ValidateConfirmationSourcesAsync(db, tx, branch, actor, order);
        await RequireUnbilledSalesOrderAsync(db, tx, branch, actor.Id, order, milestone);
        decimal discount = 0;
        decimal tax = 0;
        if (!string.IsNullOrEmpty(sourceLine) && sourceLine != "0")
        {
            using var source = RegisterCommand(@"SELECT coalesce(l.line_total,0),coalesce(l.discount_amount,0),coalesce(l.tax_amount,0)
                FROM public.srm_sales_order_lines l WHERE l.id::text=@line AND l.sales_order_id=@order AND " +
                ConfirmationOwnership("l", "srm_sales_order_lines"), db, tx, branch, actor.Id);
            source.Parameters.AddWithValue("line", sourceLine);
            source.Parameters.AddWithValue("order", order);
            using var row = await source.ExecuteReaderAsync();
            if (!await row.ReadAsync())
                throw new InvalidOperationException("Billing milestone has an invalid commercial source mapping.");
            decimal gross = row.GetDecimal(0);
            if (gross > 0)
            {
                discount = RoundLine(amount * row.GetDecimal(1) / gross);
                tax = RoundLine(amount * row.GetDecimal(2) / gross);
            }
        }
        var line = NormalizeInvoiceLine(null, name, 1, amount - tax + discount, discount, tax);
        string number = await ReserveCommercialNumberAsync(db, tx, CommercialNumberSeries.Invoice);
        return await SaveSalesInvoiceDraftAsync(db, tx, branch, actor.Id, order, currency, number,
            new List<SalesInvoiceDraftLine> { line }, new MilestoneInvoiceSource(milestone, engagement, plan, buyer, recurring, batch, notify));
    }

    private static RecurringInvoicePresentation ReadRecurringInvoicePresentation(DateTime? scheduled, string metadata)
    {
        if (!scheduled.HasValue)
            throw new InvalidOperationException("A recurring milestone must have its saved billing date before drafting.");
        using var json = JsonDocument.Parse(metadata);
        var root = json.RootElement;
        int paymentTerms = 30;
        if (root.TryGetProperty("payment_terms_days", out var terms) &&
            (!int.TryParse(terms.ToString(), NumberStyles.None, CultureInfo.InvariantCulture, out paymentTerms) ||
                paymentTerms is < 0 or > 365 || scheduled.Value.Date > DateTime.MaxValue.Date.AddDays(-paymentTerms)))
            throw new InvalidOperationException("The recurring milestone payment terms are invalid.");
        var snapshot = new Dictionary<string, object>(StringComparer.Ordinal) { ["payment_terms_days"] = paymentTerms };
        foreach (string key in new[] { "subject", "customer_notes", "terms", "invoice_template", "payment_method", "salesperson_name", "order_number" })
        {
            if (!root.TryGetProperty(key, out var value))
                continue;
            if (value.ValueKind != JsonValueKind.String)
                throw new InvalidOperationException("The recurring milestone presentation is invalid.");
            string text = value.GetString()!;
            if (key == "invoice_template" && text is not ("standard" or "compact" or "detailed"))
                throw new InvalidOperationException("The recurring milestone invoice template is invalid.");
            snapshot[key] = text;
        }
        if (root.TryGetProperty("payment_mode_id", out var mode))
        {
            if (mode.ValueKind != JsonValueKind.Number || !mode.TryGetInt32(out int modeId) || modeId <= 0)
                throw new InvalidOperationException("The recurring milestone saved payment mode is invalid.");
            snapshot["payment_mode_id"] = modeId;
        }
        return new RecurringInvoicePresentation(scheduled.Value.Date, paymentTerms, JsonSerializer.Serialize(snapshot));
    }
}
