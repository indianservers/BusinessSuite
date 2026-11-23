using System.Data;
using Npgsql;

namespace Business_Suite;

internal sealed record PosReturnHistoryRow(int Id, string Number, string Order, string State, string RefundMethod,
    string RefundStatus, string Currency, decimal Amount, DateTime? Created, string Reason, decimal Tax);
internal sealed record PosReturnDetailLine(string Product, decimal Quantity, decimal Tax, decimal Amount, string Condition, bool Restock);
internal sealed record PosReturnHistoryDetail(PosReturnHistoryRow Return, List<PosReturnDetailLine> Lines);

internal sealed partial class SalesOrderRepository
{
    private static readonly string ReturnHistoryProjection = @"SELECT r.id,r.return_number,o.order_number,coalesce(r.status,''),
        coalesce(r.refund_method,''),coalesce(r.refund_status,''),o.currency,coalesce(r.refund_amount,0),
        r.created_at,coalesce(r.reason,''),coalesce(r.tax_amount,0) " +
        GroupedPosSalesJoins + " JOIN public.srm_pos_returns r ON r.sales_order_id=o.id " +
        GroupedPosSalesPolicy + GroupedPosNamedBuyer + @"
        AND r.organization_id=@company AND r.customer_id=g.customer_id AND " + ConfirmationOwnership("r", "srm_pos_returns") + @"
        AND EXISTS (SELECT 1 FROM public.srm_pos_return_lines d WHERE d.return_id=r.id)
        AND NOT EXISTS (SELECT 1 FROM public.srm_pos_return_lines d LEFT JOIN public.srm_sales_order_lines l ON l.id=d.sales_order_line_id
            WHERE d.return_id=r.id AND NOT coalesce(l.sales_order_id=o.id AND l.product_id IS NOT DISTINCT FROM d.product_id
                AND " + ConfirmationOwnership("d", "srm_pos_return_lines") + " AND " +
                ConfirmationOwnership("l", "srm_sales_order_lines") + @",false))";

    internal async Task<List<PosReturnHistoryRow>> ListPosReturnHistoryAsync(string search)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to view the return register.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await PosReturnScopeAsync(db, tx, branch, actor, write: false);
        using var query = ScopedCommand(ReturnHistoryProjection + @"
            AND (@search='' OR strpos(lower(r.return_number),lower(@search))>0 OR strpos(lower(o.order_number),lower(@search))>0)
            ORDER BY r.id DESC LIMIT 100", db, tx, branch, actor, scope);
        query.Parameters.AddWithValue("search", search.Trim());
        var rows = new List<PosReturnHistoryRow>();
        using (var reader = await query.ExecuteReaderAsync())
            while (await reader.ReadAsync())
                rows.Add(ReadReturnHistoryRow(reader));
        tx.Commit();
        return rows;
    }

    internal async Task<PosReturnHistoryDetail> LoadPosReturnHistoryAsync(int id)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to view this return.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await PosReturnScopeAsync(db, tx, branch, actor, write: false);
        PosReturnHistoryRow header;
        using (var query = ScopedCommand(ReturnHistoryProjection + " AND r.id=@id", db, tx, branch, actor, scope))
        {
            query.Parameters.AddWithValue("id", id);
            using var reader = await query.ExecuteReaderAsync();
            if (!await reader.ReadAsync())
                throw new InvalidOperationException("This POS return is unavailable in the selected branch.");
            header = ReadReturnHistoryRow(reader);
        }
        using var lines = RegisterCommand(@"SELECT coalesce(d.description,''),coalesce(d.quantity,0),coalesce(d.tax_amount,0),
            coalesce(d.line_total,0),coalesce(d.condition,''),coalesce(d.restock,false)
            FROM public.srm_pos_return_lines d WHERE d.return_id=@id ORDER BY d.id", db, tx, branch, actor.Id);
        lines.Parameters.AddWithValue("id", id);
        var detail = new List<PosReturnDetailLine>();
        using (var reader = await lines.ExecuteReaderAsync())
            while (await reader.ReadAsync())
                detail.Add(new PosReturnDetailLine(reader.GetString(0), reader.GetDecimal(1), reader.GetDecimal(2),
                    reader.GetDecimal(3), reader.GetString(4).Replace('_', ' '), reader.GetBoolean(5)));
        tx.Commit();
        return new PosReturnHistoryDetail(header, detail);
    }

    private static PosReturnHistoryRow ReadReturnHistoryRow(NpgsqlDataReader reader) =>
        new(reader.GetInt32(0), reader.GetString(1), reader.GetString(2), reader.GetString(3), reader.GetString(4),
            reader.GetString(5), reader.GetString(6), reader.GetDecimal(7), reader.IsDBNull(8) ? null : reader.GetDateTime(8),
            reader.GetString(9), reader.GetDecimal(10));
}
