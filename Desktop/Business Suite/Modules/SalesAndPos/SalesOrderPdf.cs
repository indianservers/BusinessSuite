using System.Globalization;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    internal async Task<byte[]> RenderSalesOrderPdfAsync(int order)
    {
        string lineScope = ConfirmationOwnership("l", "srm_sales_order_lines");
        var rows = await ReadAsync(@"
            SELECT o.order_number,o.title,coalesce(o.status,''),coalesce(o.currency,''),
                coalesce(o.subtotal,0),coalesce(o.discount_amount,0),coalesce(o.tax_amount,0),coalesce(o.total_amount,0),
                o.expected_start_date,o.expected_end_date,coalesce(o.terms,''),
                l.id,coalesce(l.item_code,''),coalesce(l.description,''),coalesce(l.quantity,0),
                coalesce(l.unit_price,0),coalesce(l.discount_amount,0),coalesce(l.tax_amount,0),coalesce(l.line_total,0)
            FROM public.srm_sales_orders o
            LEFT JOIN public.srm_sales_order_lines l ON l.sales_order_id=o.id AND " + lineScope + OrderDetailScope + @"
                AND o.id=@order AND o.metadata_json->>'source' IS DISTINCT FROM 'pos'
                AND NOT EXISTS (SELECT 1 FROM public.srm_sales_order_lines l WHERE l.sales_order_id=o.id AND NOT (" +
                lineScope + ")) ORDER BY l.id", query => query.Parameters.AddWithValue("order", order), row => (
                    Header: new SalesOrderOverview(row.GetString(0), row.GetString(1), row.GetString(2), row.GetString(3),
                        row.GetDecimal(4), row.GetDecimal(5), row.GetDecimal(6), row.GetDecimal(7), null,
                        row.IsDBNull(8) ? null : row.GetDateTime(8), row.IsDBNull(9) ? null : row.GetDateTime(9),
                        row.GetString(10), false, false),
                    Line: row.IsDBNull(11) ? null : new SalesOrderLineRow(row.GetString(12), row.GetString(13),
                        row.GetDecimal(14), row.GetDecimal(15), row.GetDecimal(16), row.GetDecimal(17), row.GetDecimal(18))));
        if (rows.Count == 0)
            throw new InvalidOperationException("The complete Sales order document is unavailable in this branch.");

        var header = rows[0].Header;
        return SalesInvoicePdf.RenderDocument($"Sales order {header.Number}", 12, 22, (row, ensureRoom, space) =>
        {
            row(header.Title, 16, true);
            row($"Status: {header.Status.Replace('_', ' ')}    Currency: {header.Currency}");
            if (header.Starts.HasValue || header.Ends.HasValue)
                row($"Expected start: {Date(header.Starts)}    Expected end: {Date(header.Ends)}");
            space(10);
            row("Order items", 15, true);
            foreach (var (_, line) in rows)
            {
                if (line is null)
                    continue;
                ensureRoom(50);
                row(line.ItemCode.Length == 0 ? line.Description : $"{line.ItemCode} - {line.Description}", 12, true);
                row($"{line.Quantity.ToString("0.###", CultureInfo.InvariantCulture)} x {Amount(line.UnitPrice)}" +
                    $"    Discount {Amount(line.Discount)}    Tax {Amount(line.Tax)}    Line total {Amount(line.LineTotal)}");
            }
            ensureRoom(62);
            space(10);
            row($"Subtotal {Amount(header.Subtotal)}    Discount {Amount(header.Discount)}    Tax {Amount(header.Tax)}");
            row($"Total {header.Currency} {Amount(header.Total)}", 16, true);
            if (!string.IsNullOrWhiteSpace(header.Terms))
            {
                ensureRoom(52);
                space(10);
                row("Terms", 15, true);
                row(header.Terms);
            }
        });

        static string Amount(decimal value) => value.ToString("N2", CultureInfo.InvariantCulture);
        static string Date(DateTime? date) => date?.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture) ?? "-";
    }
}

