using System.Data;
using System.Globalization;
using System.Text;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PosReceiptIndexRow(int CheckoutId, string Invoice, string Customer, DateTime? Committed,
    string Currency, decimal Total, decimal Paid, decimal Outstanding);
internal sealed record PosReceiptPrintLine(string Name, decimal Quantity, decimal Rate);
internal sealed record PosReceiptPrintPayment(string Number, string Method, string Status, decimal Amount);
internal sealed record PosReceiptPrintData(PosReceiptIndexRow Sale, List<PosReceiptPrintLine> Items, List<PosReceiptPrintPayment> Payments)
{
    internal string FormatText()
    {
        var text = new StringBuilder();
        text.AppendLine($"Invoice {Sale.Invoice}");
        if (Sale.Committed is DateTime created)
            text.AppendLine(created.ToLocalTime().ToString("g", CultureInfo.CurrentCulture));
        text.AppendLine($"Customer: {Sale.Customer}");
        text.AppendLine();
        foreach (var line in Items)
            text.AppendLine($"{line.Name} × {line.Quantity:0.##########} @ {Money(line.Rate)}");
        text.AppendLine();
        text.AppendLine($"Total: {Money(Sale.Total)}");
        text.AppendLine($"Paid: {Money(Sale.Paid)}");
        text.AppendLine($"Balance: {Money(Sale.Outstanding)}");
        foreach (var payment in Payments)
        {
            string status = payment.Status == "cancelled" ? " · Cancelled" : "";
            text.AppendLine($"Receipt: {payment.Number} · {payment.Method} · {Money(payment.Amount)}{status}");
        }
        return text.ToString();
    }

    private string Money(decimal value) => $"{Sale.Currency} {value.ToString("N2", CultureInfo.GetCultureInfo("en-IN"))}";
}

internal sealed partial class SalesOrderRepository
{
    private const string PosReceiptHeader = @"
        SELECT g.id,i.invoice_number,CASE WHEN EXISTS (SELECT 1 FROM public.srm_anonymous_cash_accounts a WHERE a.customer_id=g.customer_id)
            THEN 'Walk-in' ELSE coalesce(nullif(ctx.customer_snapshot->>'name',''),c.name) END,
            g.committed_at,g.currency,i.total_amount,i.paid_amount,i.balance_amount ";

    internal async Task<bool> CanExportPosReceiptsAsync()
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
            await PosReceiptScopeAsync(db, tx, branch, actor, "export");
            return true;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    internal Task<List<PosReceiptIndexRow>> ListPosReceiptsAsync(string search) =>
        ReadPosReceiptIndexAsync(search, null);

    internal async Task<PosReceiptIndexRow?> FindPosReceiptForInvoiceAsync(int invoice)
    {
        if (invoice <= 0)
            return null;
        try
        {
            var rows = await ReadPosReceiptIndexAsync("", invoice);
            return rows.Count == 1 ? rows[0] : null;
        }
        catch (UnauthorizedAccessException)
        {
            return null;
        }
    }

    private async Task<List<PosReceiptIndexRow>> ReadPosReceiptIndexAsync(string search, int? invoice)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to view POS receipts.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await PosReceiptScopeAsync(db, tx, branch, actor, "view");
        using var query = ScopedCommand(PosReceiptHeader + GroupedPosVerifiedSalesScope + @"
            AND (@invoice IS NULL OR i.id=@invoice)
            AND (@query='' OR strpos(lower(i.invoice_number),lower(@query))>0 OR EXISTS (
                SELECT 1 FROM public.srm_pos_checkout_payments p JOIN public.srm_receipts receipt ON receipt.id=p.receipt_id
                WHERE p.checkout_id=g.id AND strpos(lower(receipt.receipt_number),lower(@query))>0))
            ORDER BY g.committed_at DESC NULLS LAST,g.id DESC LIMIT 100", db, tx, branch, actor, scope);
        query.Parameters.AddWithValue("query", search.Trim());
        query.Parameters.AddWithValue("invoice", NpgsqlDbType.Integer, (object?)invoice ?? DBNull.Value);
        var rows = new List<PosReceiptIndexRow>();
        using (var reader = await query.ExecuteReaderAsync())
            while (await reader.ReadAsync())
                rows.Add(ReadPosReceiptHeader(reader));
        tx.Commit();
        return rows;
    }

    internal async Task<PosReceiptPrintData> LoadPosReceiptAsync(int checkout, bool export)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to open this POS receipt.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await PosReceiptScopeAsync(db, tx, branch, actor, export ? "export" : "view");
        PosReceiptIndexRow sale;
        using (var header = ScopedCommand(PosReceiptHeader + GroupedPosVerifiedSalesScope + " AND g.id=@checkout",
            db, tx, branch, actor, scope))
        {
            header.Parameters.AddWithValue("checkout", checkout);
            using var reader = await header.ExecuteReaderAsync();
            if (!await reader.ReadAsync())
                throw new InvalidOperationException("This POS receipt is unavailable in the selected branch.");
            sale = ReadPosReceiptHeader(reader);
        }
        var lines = new List<PosReceiptPrintLine>();
        using (var query = RegisterCommand(@"SELECT i.description,m.quantity,m.unit_price
            FROM public.srm_pos_checkout_lines m JOIN public.srm_invoice_lines i ON i.id=m.invoice_line_id
            WHERE m.checkout_id=@checkout ORDER BY m.id", db, tx, branch, actor.Id))
        {
            query.Parameters.AddWithValue("checkout", checkout);
            using var reader = await query.ExecuteReaderAsync();
            while (await reader.ReadAsync())
                lines.Add(new PosReceiptPrintLine(reader.GetString(0), reader.GetDecimal(1), reader.GetDecimal(2)));
        }
        var payments = new List<PosReceiptPrintPayment>();
        using (var query = RegisterCommand(@"SELECT r.receipt_number,coalesce(r.payment_method,''),coalesce(r.status,''),r.amount
            FROM public.srm_pos_checkout_payments p JOIN public.srm_receipts r ON r.id=p.receipt_id
            WHERE p.checkout_id=@checkout ORDER BY p.id", db, tx, branch, actor.Id))
        {
            query.Parameters.AddWithValue("checkout", checkout);
            using var reader = await query.ExecuteReaderAsync();
            while (await reader.ReadAsync())
                payments.Add(new PosReceiptPrintPayment(reader.GetString(0), reader.GetString(1).Replace('_', ' '),
                    reader.GetString(2), reader.GetDecimal(3)));
        }
        tx.Commit();
        return new PosReceiptPrintData(sale, lines, payments);
    }

    private async Task<string> PosReceiptScopeAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        DesktopActor actor, string action)
    {
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop POS receipt history");
        return await SalesReadAccess.OrderScopeForPermissionsAsync(db, tx, settings.OrganizationId, branch, actor,
            action, "srm_invoice_view", "srm_invoice_create", "srm_collection_view", "srm_collection_create", "srm_admin");
    }

    private static PosReceiptIndexRow ReadPosReceiptHeader(NpgsqlDataReader reader) =>
        new(reader.GetInt32(0), reader.GetString(1), reader.GetString(2), reader.IsDBNull(3) ? null : reader.GetDateTime(3),
            reader.GetString(4), reader.GetDecimal(5), reader.GetDecimal(6), reader.GetDecimal(7));
}
