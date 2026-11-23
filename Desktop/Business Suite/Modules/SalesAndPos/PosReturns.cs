using System.Data;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PosReturnSale(int OrderId, string Order, string Invoice, string Customer, string Currency);
internal sealed record PosReturnSourceLine(int Id, string Product, decimal Sold, decimal Returned, decimal Remaining, decimal UnitPrice);
internal sealed record PosReturnIntent(Guid Request, int OrderId, int LineId, decimal Quantity, string Condition,
    bool Restock, string Method, string Reason);
internal sealed record PosReturnResult(string Number, string Currency, decimal Amount, decimal Tax);
internal sealed class PosReturnRejectedException(string message) : InvalidOperationException(message);

internal sealed partial class SalesOrderRepository
{
    private sealed record ReturnOrder(int Id, string Number, int Buyer, string Name, string Currency, decimal Paid);
    private sealed record ReturnLine(int Id, int Product, string Code, string Description, decimal Sold, decimal Price,
        decimal Tax, decimal Total, decimal Returned, decimal Refunded, decimal ReturnedTax);
    private sealed record ReturnAmount(decimal Gross, decimal Tax, decimal NetUnit);

    internal SalesIntentJournal<PosReturnIntent> PosReturnJournal() =>
        new(settings, "POS returns", "", ValidateReturnIntent,
            "The saved POS return recovery record could not be verified. Review the sale before entering a new return.");

    private static void ValidateReturnIntent(PosReturnIntent intent)
    {
        if (intent.Request == Guid.Empty || intent.OrderId <= 0 || intent.LineId <= 0 || intent.Quantity <= 0 ||
            intent.Quantity > 9999999m || decimal.Round(intent.Quantity, 3) != intent.Quantity ||
            intent.Condition is not ("sellable" or "damaged" or "not_returned") || (intent.Restock && intent.Condition != "sellable") ||
            string.IsNullOrWhiteSpace(intent.Method) || intent.Method.Length > 60 || intent.Method.IndexOf('\0') >= 0 ||
            intent.Reason is null || intent.Reason.Length > 500 || intent.Reason.IndexOf('\0') >= 0)
            throw new ArgumentException("Choose an original sale line, a valid quantity and disposition, and a refund method.");
    }

    internal async Task<bool> CanRecordPosReturnAsync()
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
            await PosReturnScopeAsync(db, tx, branch, actor, write: true);
            return true;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    internal async Task<List<PosReturnSale>> ListPosReturnSalesAsync(string search)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to view POS returns.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await PosReturnScopeAsync(db, tx, branch, actor, write: false);
        using var query = ScopedCommand(@"SELECT o.id,o.order_number,i.invoice_number,c.name,o.currency " +
            GroupedPosInvoiceScope + @" AND i.status IN ('paid','partially_paid') AND i.paid_amount>0
            AND (@search='' OR strpos(lower(o.order_number),lower(@search))>0 OR strpos(lower(o.title),lower(@search))>0
                OR strpos(lower(i.invoice_number),lower(@search))>0)
            ORDER BY o.id DESC LIMIT 100", db, tx, branch, actor, scope);
        query.Parameters.AddWithValue("search", search.Trim());
        var rows = new List<PosReturnSale>();
        using (var reader = await query.ExecuteReaderAsync())
            while (await reader.ReadAsync())
                rows.Add(new PosReturnSale(reader.GetInt32(0), reader.GetString(1), reader.GetString(2), reader.GetString(3), reader.GetString(4)));
        tx.Commit();
        return rows;
    }

    internal async Task<List<PosReturnSourceLine>> PosReturnLinesAsync(int order)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to view return lines.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await PosReturnScopeAsync(db, tx, branch, actor, write: false);
        await ReadReturnOrderAsync(db, tx, branch, actor, scope, order, false);
        var lines = await ReadReturnSourceLinesAsync(db, tx, branch, actor.Id, order, null, false);
        tx.Commit();
        return lines.Select(line => new PosReturnSourceLine(line.Id, line.Description, line.Sold, line.Returned,
            Math.Max(0, line.Sold - line.Returned), line.Price)).ToList();
    }

    internal async Task<PosReturnResult> RecordPosReturnAsync(PosReturnIntent intent)
    {
        ValidateReturnIntent(intent);
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to record a POS return.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await PosReturnScopeAsync(db, tx, branch, actor, write: true);
        var order = await ReadReturnOrderAsync(db, tx, branch, actor, scope, intent.OrderId, true);
        using var sha = SHA256.Create();
        string fingerprint = BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(JsonSerializer.Serialize(intent, HeldJson))))
            .Replace("-", "").ToLowerInvariant();
        var existing = await FindReturnIntentAsync(db, tx, branch, actor.Id, order, intent.Request, fingerprint);
        if (existing is not null)
        {
            tx.Commit();
            return existing;
        }
        var lines = await ReadReturnSourceLinesAsync(db, tx, branch, actor.Id, order.Id, intent.LineId, true);
        if (lines.Count != 1)
            throw new PosReturnRejectedException("Choose a line from the original sale.");
        var line = lines[0];
        var amounts = CalculateReturnAmount(line, intent.Quantity);
        await VerifyReturnScopeAndAmountAsync(db, tx, branch, actor.Id, order, line, amounts.Gross);
        string number = await ReserveCommercialNumberAsync(db, tx, CommercialNumberSeries.PosReturn);
        int? warehouse = intent.Restock ? await RestockPosReturnAsync(db, tx, branch, actor, order, line, amounts.NetUnit, intent.Quantity, number) : null;
        int returned = await PersistPosReturnAsync(db, tx, branch, actor.Id, order, line, amounts, intent, warehouse, number, fingerprint);
        await CancelRefundedFollowUpsAsync(db, tx, branch, actor.Id, order, returned);
        tx.Commit();
        return new PosReturnResult(number, order.Currency, amounts.Gross, amounts.Tax);
    }

    private async Task<string> PosReturnScopeAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor, bool write)
    {
        if (write && !actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop POS returns");
        return await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, write ? "create" : "view");
    }

    private async Task<ReturnOrder> ReadReturnOrderAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor,
        string scope, int order, bool lockRow)
    {
        using var query = ScopedCommand(@"SELECT o.id,o.order_number,i.customer_id,c.name,o.currency,i.paid_amount " +
            GroupedPosInvoiceScope + @" AND o.id=@order AND i.status IN ('paid','partially_paid') AND i.paid_amount>0" +
            (lockRow ? " FOR UPDATE OF g,o,i" : ""), db, tx, branch, actor, scope);
        query.Parameters.AddWithValue("order", order);
        using var reader = await query.ExecuteReaderAsync();
        if (!await reader.ReadAsync())
            throw new InvalidOperationException("The paid original POS sale is unavailable in this branch.");
        return new ReturnOrder(reader.GetInt32(0), reader.GetString(1), reader.GetInt32(2), reader.GetString(3),
            reader.GetString(4), reader.GetDecimal(5));
    }

    private async Task<List<ReturnLine>> ReadReturnSourceLinesAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        int actor, int order, int? line, bool lockRow)
    {
        using var query = RegisterCommand(@"
            SELECT l.id,l.product_id,coalesce(l.item_code,''),coalesce(l.description,''),coalesce(l.quantity,0),
                coalesce(l.unit_price,0),coalesce(l.tax_amount,0),coalesce(l.line_total,0),
                prior.quantity,prior.value,prior.tax,prior.verified
            FROM public.srm_sales_order_lines l
            CROSS JOIN LATERAL (
                SELECT coalesce(sum(d.quantity),0) AS quantity,coalesce(sum(d.line_total),0) AS value,
                    coalesce(sum(d.tax_amount),0) AS tax,coalesce(bool_and(coalesce(r.organization_id=@company
                        AND r.sales_order_id=@order AND d.product_id=l.product_id AND " + ConfirmationOwnership("r", "srm_pos_returns") +
                        " AND " + ConfirmationOwnership("d", "srm_pos_return_lines") + @",false)),true) AS verified
                FROM public.srm_pos_return_lines d JOIN public.srm_pos_returns r ON r.id=d.return_id WHERE d.sales_order_line_id=l.id
            ) prior
            WHERE l.sales_order_id=@order AND l.product_id IS NOT NULL AND " + ConfirmationOwnership("l", "srm_sales_order_lines") +
            " AND (@line IS NULL OR l.id=@line) ORDER BY l.id" + (lockRow ? " FOR UPDATE OF l NOWAIT" : ""), db, tx, branch, actor);
        query.Parameters.AddWithValue("order", order);
        query.Parameters.AddWithValue("line", NpgsqlDbType.Integer, (object?)line ?? DBNull.Value);
        var result = new List<ReturnLine>();
        using var reader = await query.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            if (!reader.GetBoolean(11))
                throw new InvalidOperationException("Previous return records require branch reconciliation.");
            result.Add(new ReturnLine(reader.GetInt32(0), reader.GetInt32(1), reader.GetString(2), reader.GetString(3),
                reader.GetDecimal(4), reader.GetDecimal(5), reader.GetDecimal(6), reader.GetDecimal(7),
                reader.GetDecimal(8), reader.GetDecimal(9), reader.GetDecimal(10)));
        }
        return result;
    }

    private static ReturnAmount CalculateReturnAmount(ReturnLine line, decimal quantity)
    {
        if (line.Sold <= 0 || line.Returned < 0 || line.Returned + quantity > line.Sold)
            throw new PosReturnRejectedException("Return quantity exceeds the original line's remaining sold quantity.");
        decimal remainingGross = line.Total - line.Refunded;
        decimal remainingTax = line.Tax - line.ReturnedTax;
        bool finalReturn = quantity + line.Returned == line.Sold;
        decimal ratio = quantity / line.Sold;
        decimal gross = finalReturn ? remainingGross : Math.Min(remainingGross, decimal.Round(line.Total * ratio, 2, MidpointRounding.AwayFromZero));
        decimal tax = finalReturn ? remainingTax : Math.Min(remainingTax, decimal.Round(line.Tax * ratio, 2, MidpointRounding.AwayFromZero));
        if (gross < 0 || tax < 0 || tax > gross || line.Tax > line.Total)
            throw new PosReturnRejectedException("The return value or tax exceeds the original source.");
        return new ReturnAmount(gross, tax, decimal.Round((line.Total - line.Tax) / line.Sold, 2, MidpointRounding.AwayFromZero));
    }
}
