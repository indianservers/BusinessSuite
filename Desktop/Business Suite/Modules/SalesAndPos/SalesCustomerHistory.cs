using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record SalesCustomerHistoryRow(int Id, string Number, DateTime? Date, string Currency,
    string Status, decimal Total, decimal Paid, decimal Unpaid, bool IsTest, int? OrderId);
internal sealed record SalesCustomerHistoryPage(string Customer, List<SalesCustomerHistoryRow> Rows, long Total);
internal sealed record SalesCustomerHistoryInvoice(LinkedSalesInvoiceDetails Details, int? OrderId,
    SalesMilestoneInvoiceLink? Milestone);

internal sealed partial class SalesOrderRepository
{
    internal const int CustomerHistoryPageSize = 25;

    private static string HistoryInvoiceAccess => " AND " + ConfirmationOwnership("i", "srm_invoices") + @"
                    AND NOT EXISTS (SELECT 1 FROM public.business_invoice_contexts ctx WHERE ctx.invoice_id=i.id AND ctx.seller_id<>@company)
                    AND (@scope='organization'
                        OR i.created_by=@actor
                        OR ((@scope='legacy_assigned' OR @scope='own') AND EXISTS (SELECT 1 FROM public.crm_companies owned WHERE owned.organization_id=@company AND owned.id=i.customer_id AND owned.owner_user_id=@actor))
                        OR EXISTS (SELECT 1 FROM public.srm_sales_orders o" + OrderScope + @" AND o.id=i.sales_order_id)
                        OR (@scope IN ('branch','department','team') AND EXISTS (
                            SELECT 1 FROM public.employees member
                            JOIN public.employees self ON self.user_id=@actor AND self.deleted_at IS NULL
                            WHERE member.user_id=i.created_by AND member.deleted_at IS NULL AND member.branch_id=@branch
                                AND ((@scope='branch' AND member.branch_id=self.branch_id)
                                  OR (@scope='department' AND member.department_id=self.department_id)
                                  OR (@scope='team' AND member.reporting_manager_id=self.id)))))";

    internal async Task<SalesCustomerHistoryPage> SalesCustomerHistoryAsync(int order, string currency,
        bool includeTest, int page) => (await ReadCustomerHistoryAsync(order, currency, includeTest, page, null)).Page;

    internal async Task<SalesCustomerHistoryInvoice> LoadSalesCustomerHistoryInvoiceAsync(int order, int invoice,
        string currency, bool includeTest) =>
        (await ReadCustomerHistoryAsync(order, currency, includeTest, 1, invoice)).Invoice
        ?? throw new InvalidOperationException("The selected invoice is unavailable in this purchase history.");

    internal async Task<NativeInvoicePdfData> LoadSalesCustomerHistoryPdfAsync(int order, int invoice,
        string currency, bool includeTest) =>
        (await ReadCustomerHistoryAsync(order, currency, includeTest, 1, invoice, export: true)).Pdf
        ?? throw new InvalidOperationException("The selected invoice is unavailable for export from purchase history.");

    internal async Task<SalesCustomerHistoryPage> HistoryForCustomerAsync(int customer, string currency,
        bool includeTest, int page) => (await ReadCustomerHistoryAsync(null, currency, includeTest, page, null, customer: customer)).Page;

    internal async Task<SalesCustomerHistoryInvoice> OpenInvoiceForHistoryCustomerAsync(int customer, int invoice,
        string currency, bool includeTest) =>
        (await ReadCustomerHistoryAsync(null, currency, includeTest, 1, invoice, customer: customer)).Invoice
        ?? throw new InvalidOperationException("The selected invoice is unavailable in this purchase history.");

    internal async Task<NativeInvoicePdfData> ExportInvoiceForHistoryCustomerAsync(int customer, int invoice,
        string currency, bool includeTest) =>
        (await ReadCustomerHistoryAsync(null, currency, includeTest, 1, invoice, export: true, customer: customer)).Pdf
        ?? throw new InvalidOperationException("The selected invoice is unavailable for export from purchase history.");

    internal async Task<List<SalesCustomer>> HistoryCustomersAsync(string search)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to view purchase history.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await RequireHistoryAccessAsync(db, tx, branch, actor);
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop customer purchase history");
        using var query = ScopedCommand("SELECT c.id,c.name FROM public.crm_companies c" + OrderCustomerScope + @"
            AND (@search='' OR strpos(lower(c.name),lower(@search))>0)
            AND EXISTS (SELECT 1 FROM public.srm_invoices i WHERE i.organization_id=@company
                AND i.customer_id=c.id AND i.deleted_at IS NULL" + HistoryInvoiceAccess + @")
            ORDER BY lower(c.name),c.id LIMIT 120", db, tx, branch, actor, scope);
        query.Parameters.AddWithValue("search", search.Trim());
        var rows = new List<SalesCustomer>();
        using (var reader = await query.ExecuteReaderAsync())
            while (await reader.ReadAsync())
                rows.Add(new SalesCustomer(reader.GetInt32(0), reader.GetString(1)));
        tx.Commit();
        return rows;
    }

    private Task<string> RequireHistoryAccessAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        DesktopActor actor) => SalesReadAccess.OrderScopeForPermissionsAsync(db, tx, settings.OrganizationId, branch, actor,
            "view", "srm_view", "srm_invoice_view", "srm_collection_view", "srm_profitability_view", "srm_admin");

    private async Task<(SalesCustomerHistoryPage Page, SalesCustomerHistoryInvoice? Invoice, NativeInvoicePdfData? Pdf)>
        ReadCustomerHistoryAsync(int? order, string currency, bool includeTest, int page, int? invoice, bool export = false, int? customer = null)
    {
        if ((order.HasValue == customer.HasValue) || order is <= 0 || customer is <= 0 || invoice is <= 0 || page is < 1 or > 10000 || currency.Length != 0 && !ValidOrderCurrency(currency))
            throw new ArgumentException("Choose a customer, a valid currency and a valid history page.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to view purchase history.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string historyScope = await RequireHistoryAccessAsync(db, tx, branch, actor);
        string buyerScope = order.HasValue ? await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor)
            : historyScope;
        string? invoiceScope = invoice.HasValue
            ? await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor,
                export ? "export" : "view", invoiceView: true)
            : null;
        if (invoiceScope is not (null or "organization") && historyScope != "organization" && invoiceScope != historyScope)
            throw new UnauthorizedAccessException("The invoice scope and purchase history scope do not agree.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop customer purchase history");

        string buyerFilter = order.HasValue
            ? " AND c.id=(SELECT o.customer_id FROM public.srm_sales_orders o" + OrderDetailScope + " AND o.id=@identity)"
            : " AND c.id=@identity AND EXISTS (SELECT 1 FROM public.srm_invoices i WHERE i.organization_id=@company" +
                " AND i.customer_id=c.id AND i.deleted_at IS NULL" + HistoryInvoiceAccess + ")";
        using var buyerQuery = ScopedCommand("SELECT c.id,c.name FROM public.crm_companies c" + OrderCustomerScope + buyerFilter,
            db, tx, branch, actor, buyerScope);
        buyerQuery.Parameters.AddWithValue("identity", (order ?? customer)!.Value);
        (int Id, string Name) buyer;
        using (var reader = await buyerQuery.ExecuteReaderAsync())
        {
            if (!await reader.ReadAsync())
                throw new InvalidOperationException("The linked customer is unavailable for purchase history in this branch.");
            buyer = (reader.GetInt32(0), reader.GetString(1));
        }

        using var command = ScopedCommand(@"
            WITH visible AS (
                SELECT i.id,i.invoice_number,i.issue_date,coalesce(i.currency,'') AS currency,coalesce(i.status,'') AS status,
                    coalesce(i.total_amount,0) AS total,coalesce(i.paid_amount,0) AS paid,coalesce(i.balance_amount,0) AS unpaid,
                    i.sales_order_id,i.due_date,
                    coalesce(invoice_flag.is_test,order_flag.is_test,
                        source.metadata_json::jsonb->'is_test'='true'::jsonb OR source.metadata_json::jsonb->'test_only'='true'::jsonb,false) AS is_test
                FROM public.srm_invoices i
                LEFT JOIN public.srm_sales_orders source ON source.organization_id=@company AND source.id=i.sales_order_id
                LEFT JOIN public.srm_report_flags invoice_flag ON invoice_flag.organization_id=@company
                    AND invoice_flag.entity='invoice' AND invoice_flag.resource_id=i.id
                LEFT JOIN public.srm_report_flags order_flag ON order_flag.organization_id=@company
                    AND order_flag.entity='sales_order' AND order_flag.resource_id=source.id
                WHERE i.organization_id=@company AND i.customer_id=@customer AND i.deleted_at IS NULL
                    AND (@invoice IS NULL OR i.id=@invoice)
                    AND (@currency='' OR i.currency=@currency)
                    " + HistoryInvoiceAccess + @"
            ), filtered AS (SELECT * FROM visible WHERE @include_test OR NOT is_test),
            page AS (SELECT * FROM filtered ORDER BY issue_date DESC, id DESC LIMIT @limit OFFSET @offset)
            SELECT counts.total,p.id,p.invoice_number,p.issue_date,p.currency,p.status,p.total,p.paid,p.unpaid,p.is_test,p.sales_order_id,p.due_date
            FROM (SELECT count(*) AS total FROM filtered) counts LEFT JOIN page p ON true
            ORDER BY p.issue_date DESC,p.id DESC", db, tx, branch, actor,
            invoiceScope is null || invoiceScope == "organization" ? historyScope : invoiceScope);
        command.Parameters.AddWithValue("invoice", NpgsqlDbType.Integer, (object?)invoice ?? DBNull.Value);
        command.Parameters.AddWithValue("customer", buyer.Id);
        command.Parameters.AddWithValue("currency", NpgsqlDbType.Text, currency);
        command.Parameters.AddWithValue("include_test", includeTest);
        command.Parameters.AddWithValue("limit", CustomerHistoryPageSize);
        command.Parameters.AddWithValue("offset", (page - 1) * CustomerHistoryPageSize);
        long total = 0;
        var rows = new List<SalesCustomerHistoryRow>();
        DateTime? dueDate = null;
        using (var reader = await command.ExecuteReaderAsync())
        {
            while (await reader.ReadAsync())
            {
                total = reader.GetInt64(0);
                if (!reader.IsDBNull(1))
                {
                    dueDate = reader.IsDBNull(11) ? null : reader.GetDateTime(11);
                    rows.Add(new SalesCustomerHistoryRow(reader.GetInt32(1), reader.GetString(2),
                        reader.IsDBNull(3) ? null : reader.GetDateTime(3), reader.GetString(4), reader.GetString(5),
                        reader.GetDecimal(6), reader.GetDecimal(7), reader.GetDecimal(8), reader.GetBoolean(9),
                        reader.IsDBNull(10) ? null : reader.GetInt32(10)));
                }
            }
        }
        SalesCustomerHistoryInvoice? detail = null;
        NativeInvoicePdfData? pdf = null;
        if (invoice.HasValue && rows.SingleOrDefault() is { } saved)
        {
            var lines = await ReadHistoryInvoiceLinesAsync(db, tx, branch, actor, saved.Id);
            var header = new LinkedSalesInvoice(saved.Id, saved.Number, saved.Status, saved.Currency, saved.Total,
                dueDate, saved.Date) { Paid = saved.Paid, Balance = saved.Unpaid };
            var invoiceDetail = new LinkedSalesInvoiceDetails(header, lines);
            if (export)
                pdf = await ReadInvoicePdfLayoutAsync(db, tx, branch, actor, invoiceDetail, allowProject: true);
            else
            {
                SalesMilestoneInvoiceLink? milestone = saved.OrderId is int source && invoiceScope is not null
                    ? await FindHistoryMilestoneAsync(db, tx, branch, actor, invoiceScope, source, saved.Id)
                    : null;
                detail = new SalesCustomerHistoryInvoice(invoiceDetail, saved.OrderId, milestone);
            }
        }
        tx.Commit();
        return (new SalesCustomerHistoryPage(buyer.Name, rows, total), detail, pdf);
    }

    private async Task<SalesMilestoneInvoiceLink?> FindHistoryMilestoneAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, DesktopActor actor, string scope, int order, int invoice)
    {
        using var query = ScopedCommand("SELECT e.id,b.id,m.id" + MilestoneInvoiceChain + NativeSalesEngagementScope +
            " AND b.organization_id=@company AND i.id=@invoice AND " + ConfirmationOwnership("b", "srm_billing_plans") +
            " AND " + MilestoneInvoiceOwnership + " ORDER BY m.id LIMIT 2", db, tx, branch, actor, scope);
        query.Parameters.AddWithValue("order", order);
        query.Parameters.AddWithValue("invoice", invoice);
        using var row = await query.ExecuteReaderAsync();
        if (!await row.ReadAsync())
            return null;
        var link = new SalesMilestoneInvoiceLink(row.GetInt32(0), row.GetInt32(1), row.GetInt32(2));
        return await row.ReadAsync() ? null : link;
    }

    private async Task<List<LinkedSalesInvoiceLine>> ReadHistoryInvoiceLinesAsync(NpgsqlConnection db,
        NpgsqlTransaction tx, int branch, DesktopActor actor, int invoice)
    {
        using var query = RegisterCommand(@"
            SELECT l.description,coalesce(l.quantity,0),coalesce(l.unit_price,0),coalesce(l.discount_amount,0),
                coalesce(l.tax_amount,0),coalesce(l.line_total,0)," + ConfirmationOwnership("l", "srm_invoice_lines") + @"
            FROM public.srm_invoice_lines l WHERE l.invoice_id=@invoice ORDER BY l.id LIMIT 201", db, tx, branch, actor.Id);
        query.Parameters.AddWithValue("invoice", invoice);
        var lines = new List<LinkedSalesInvoiceLine>();
        using var reader = await query.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            if (!reader.GetBoolean(6) || lines.Count >= 200)
                throw new InvalidOperationException("The complete invoice items are unavailable in this branch.");
            lines.Add(new LinkedSalesInvoiceLine(reader.GetString(0), reader.GetDecimal(1), reader.GetDecimal(2),
                reader.GetDecimal(3), reader.GetDecimal(4), reader.GetDecimal(5)));
        }
        return lines;
    }
}
