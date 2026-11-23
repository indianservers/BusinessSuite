using System.Data;
using Npgsql;

namespace Business_Suite;

internal sealed record LinkedSalesInvoice(int Id, string Number, string Status, string Currency,
    decimal Total, DateTime? DueDate, DateTime? IssueDate)
{
    internal decimal Paid { get; init; }
    internal decimal Balance { get; init; }
    internal string PaymentStatus => Status == "cancelled" ? "Not payable"
        : Balance <= 0 && Total > 0 ? "Paid" : Paid > 0 ? "Partially paid" : "Unpaid";
}
internal sealed record LinkedSalesInvoiceLine(string Description, decimal Quantity, decimal UnitPrice,
    decimal Discount, decimal Tax, decimal Total);
internal sealed record LinkedSalesInvoiceDetails(LinkedSalesInvoice Invoice, List<LinkedSalesInvoiceLine> Lines);

internal sealed partial class SalesOrderRepository
{
    private static readonly string LinkedOrderInvoiceScope = @"
            FROM public.srm_sales_orders o JOIN public.srm_invoices i ON i.sales_order_id=o.id
            JOIN public.srm_invoice_drafts d ON d.id=i.invoice_draft_id AND d.sales_order_id=o.id
            " + ApprovalOrderScope + " AND i.organization_id=@company AND i.deleted_at IS NULL AND i.engagement_id IS NULL" +
            " AND d.organization_id=@company AND d.source_type='sales_order' AND " + ConfirmationOwnership("i", "srm_invoices") +
            " AND " + ConfirmationOwnership("d", "srm_invoice_drafts") + @"
            AND NOT EXISTS (SELECT 1 FROM public.business_invoice_contexts ctx WHERE ctx.invoice_id=i.id AND ctx.seller_id<>@company)";

    internal async Task<LinkedSalesInvoice?> FindOrderInvoiceAsync(int order)
    {
        try
        {
            return (await ReadOrderInvoiceAsync(order, includeLines: false))?.Details.Invoice;
        }
        catch (UnauthorizedAccessException)
        {
            return null;
        }
    }

    internal async Task<LinkedSalesInvoiceDetails> LoadOrderInvoiceAsync(int order) =>
        (await ReadOrderInvoiceAsync(order, includeLines: true))?.Details
            ?? throw new InvalidOperationException("The linked invoice is unavailable in this branch.");

    private sealed record OrderInvoiceRead(LinkedSalesInvoiceDetails Details, NativeInvoicePdfData? Pdf);
    private const string MilestoneInvoiceChain = SalesBillingPlanChain + @"
        JOIN public.srm_billing_milestones m ON m.billing_plan_id=b.id
        JOIN public.srm_invoice_drafts d ON d.id=m.invoice_draft_id AND d.organization_id=@company
            AND d.billing_plan_id=b.id AND d.engagement_id=e.id AND d.sales_order_id=o.id AND d.source_type='billing_milestone'
        JOIN public.srm_invoices i ON i.invoice_draft_id=d.id AND i.organization_id=@company AND i.sales_order_id=o.id
            AND i.engagement_id=e.id AND i.deleted_at IS NULL";
    private static string MilestoneInvoiceOwnership => ConfirmationOwnership("m", "srm_billing_milestones") + " AND " +
        ConfirmationOwnership("d", "srm_invoice_drafts") + " AND " + ConfirmationOwnership("i", "srm_invoices");
    private static string MilestoneInvoiceReadScope => MilestoneInvoiceChain + SalesBillingPlanScope +
        " AND b.id=@plan AND m.id=@milestone AND " + MilestoneInvoiceOwnership;

    internal async Task<LinkedSalesInvoiceDetails> LoadSalesMilestoneInvoiceAsync(int order, int engagement, int plan, int milestone) =>
        (await ReadOrderInvoiceAsync(order, includeLines: true, milestone: new SalesMilestoneInvoiceLink(engagement, plan, milestone)))?.Details
            ?? throw new InvalidOperationException("The milestone invoice is unavailable in this branch.");

    internal async Task<NativeInvoicePdfData> LoadSalesMilestoneInvoicePdfAsync(int order, int engagement, int plan, int milestone, int invoice) =>
        (await ReadOrderInvoiceAsync(order, includeLines: true, exportInvoice: invoice,
            milestone: new SalesMilestoneInvoiceLink(engagement, plan, milestone)))?.Pdf
            ?? throw new InvalidOperationException("The milestone invoice is unavailable for export in this branch.");

    private async Task<OrderInvoiceRead?> ReadOrderInvoiceAsync(int order, bool includeLines, int? exportInvoice = null,
        SalesMilestoneInvoiceLink? milestone = null)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to open invoices.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor,
            exportInvoice.HasValue ? "export" : "view", invoiceView: true);
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop sales invoices");
        using var query = ScopedCommand(@"
            SELECT i.id,i.invoice_number,coalesce(i.status,''),coalesce(i.currency,''),coalesce(i.total_amount,0),i.due_date,i.issue_date,coalesce(i.paid_amount,0),coalesce(i.balance_amount,0)
            " + (milestone is null ? LinkedOrderInvoiceScope : MilestoneInvoiceReadScope) +
            (exportInvoice.HasValue ? " AND i.id=@invoice" : "") + " ORDER BY i.id LIMIT 2", db, tx, branch, actor, scope);
        if (milestone is null)
            query.Parameters.AddWithValue("order", order);
        else
        {
            BindBillingMilestoneChain(query, order, milestone.Engagement, milestone.Plan);
            query.Parameters.AddWithValue("milestone", milestone.Milestone);
        }
        if (exportInvoice is int invoiceId)
            query.Parameters.AddWithValue("invoice", invoiceId);
        LinkedSalesInvoice invoice;
        using (var reader = await query.ExecuteReaderAsync())
        {
            if (!await reader.ReadAsync())
                return null;
            invoice = new LinkedSalesInvoice(reader.GetInt32(0), reader.GetString(1), reader.GetString(2), reader.GetString(3),
                reader.GetDecimal(4), reader.IsDBNull(5) ? null : reader.GetDateTime(5), reader.IsDBNull(6) ? null : reader.GetDateTime(6))
            {
                Paid = reader.GetDecimal(7),
                Balance = reader.GetDecimal(8)
            };
            if (await reader.ReadAsync())
                throw new InvalidOperationException("This order has multiple linked invoices. Review its commercial records.");
        }
        var lines = new List<LinkedSalesInvoiceLine>();
        if (includeLines)
        {
            using var items = RegisterCommand(@"
                SELECT l.description,coalesce(l.quantity,0),coalesce(l.unit_price,0),coalesce(l.discount_amount,0),
                    coalesce(l.tax_amount,0),coalesce(l.line_total,0)," + ConfirmationOwnership("l", "srm_invoice_lines") + @",
                    l.source_type,l.source_id
                FROM public.srm_invoice_lines l WHERE l.invoice_id=@invoice ORDER BY l.id LIMIT 201", db, tx, branch, actor.Id);
            items.Parameters.AddWithValue("invoice", invoice.Id);
            using var reader = await items.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                if (!reader.GetBoolean(6) || lines.Count >= 200 || milestone is not null &&
                    (reader.IsDBNull(7) || reader.GetString(7) != "billing_milestone" ||
                        reader.IsDBNull(8) || reader.GetInt32(8) != milestone.Milestone))
                    throw new InvalidOperationException("The saved invoice items are unavailable in this branch.");
                lines.Add(new LinkedSalesInvoiceLine(reader.GetString(0), reader.GetDecimal(1), reader.GetDecimal(2),
                    reader.GetDecimal(3), reader.GetDecimal(4), reader.GetDecimal(5)));
            }
            if (milestone is not null && lines.Count != 1)
                throw new InvalidOperationException("The saved milestone invoice has an inconsistent source line.");
        }
        var detail = new LinkedSalesInvoiceDetails(invoice, lines);
        var pdf = exportInvoice.HasValue ? await ReadInvoicePdfLayoutAsync(db, tx, branch, actor, detail) : null;
        tx.Commit();
        return new OrderInvoiceRead(detail, pdf);
    }
}
