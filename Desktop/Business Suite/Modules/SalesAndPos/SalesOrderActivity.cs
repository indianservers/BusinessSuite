using System.Text.Json;

namespace Business_Suite;

internal sealed record SalesOrderActivityRow(DateTime? Date, string Record, string Action, string Actor, string Before,
    string After, string Reason);

internal sealed partial class SalesOrderRepository
{
    internal Task<List<SalesOrderActivityRow>> SalesOrderActivityAsync(int order) => ReadAsync(@"
        SELECT a.created_at,a.entity_type,a.entity_id,a.action,a.actor_user_id,
            a.before_json::text,a.after_json::text
        FROM public.srm_sales_orders o
        JOIN public.srm_audit_logs a ON a.organization_id=@company AND (
            (a.entity_type='sales_order' AND a.entity_id=o.id)
            OR (a.entity_type='sales_order_line' AND (
                EXISTS (SELECT 1 FROM public.srm_sales_order_lines l WHERE l.id=a.entity_id AND l.sales_order_id=o.id
                    AND " + ConfirmationOwnership("l", "srm_sales_order_lines") + @")
                OR (a.action='deleted' AND a.before_json->>'sales_order_id'=o.id::text
                    AND a.before_json->>'id'=a.entity_id::text AND NOT EXISTS (
                        SELECT 1 FROM public.srm_sales_order_lines l WHERE l.id=a.entity_id
                    ))
            ))
        )" + OrderDetailScope + " AND o.id=@order AND " + ConfirmationOwnership("a", "srm_audit_logs") +
        " ORDER BY a.created_at DESC NULLS LAST,a.id DESC LIMIT 30",
        command => command.Parameters.AddWithValue("order", order), row =>
        {
            bool line = row.GetString(1) == "sales_order_line";
            string action = row.GetString(3);
            var fields = line ? LineActivityFields : action == "document_delivery" ? DeliveryActivityFields : OrderActivityFields;
            var before = ReadActivitySnapshot(row.IsDBNull(5) ? null : row.GetString(5), fields);
            var after = ReadActivitySnapshot(row.IsDBNull(6) ? null : row.GetString(6), fields);
            return new SalesOrderActivityRow(row.IsDBNull(0) ? null : row.GetDateTime(0).ToLocalTime(),
                line ? $"Item #{row.GetInt32(2)}" : "Sales order", action.Replace('_', ' '),
                row.IsDBNull(4) ? "" : $"User #{row.GetInt32(4)}", before.Summary, after.Summary, after.Reason);
        });

    private static readonly (string Key, string Label)[] OrderActivityFields =
    {
        ("status", "Status"), ("title", "Title"), ("terms", "Terms"),
        ("expected_start_date", "Expected start"), ("expected_end_date", "Expected end"), ("subtotal", "Subtotal"),
        ("discount_amount", "Discount"), ("tax_amount", "Tax"), ("total_amount", "Total")
    };
    private static readonly (string Key, string Label)[] LineActivityFields =
    {
        ("item_code", "Code"), ("description", "Description"), ("quantity", "Quantity"),
        ("unit_price", "Unit price"), ("discount_amount", "Discount"), ("tax_amount", "Tax"), ("line_total", "Total")
    };

    private static readonly (string Key, string Label)[] DeliveryActivityFields =
    {
        ("status", "Delivery status"), ("recipient", "Recipient"), ("message_id", "Message ID"), ("error", "Provider detail")
    };

    private static (string Summary, string Reason) ReadActivitySnapshot(string? json,
        IReadOnlyList<(string Key, string Label)> fields)
    {
        if (json is null || json.Length == 0)
            return ("", "");
        using var doc = JsonDocument.Parse(json);
        if (doc.RootElement.ValueKind != JsonValueKind.Object)
            return ("", "");
        var root = doc.RootElement;
        string reason = ActivityText(root, "reason");
        var snapshot = root.TryGetProperty("record", out var record) && record.ValueKind == JsonValueKind.Object ? record : root;
        var changes = new List<string>();
        foreach (var (key, label) in fields)
        {
            string value = ActivityText(snapshot, key);
            if (value.Length > 0)
                changes.Add($"{label}  {value}");
        }
        return (string.Join(Environment.NewLine, changes), reason);
    }

    private static string ActivityText(JsonElement snapshot, string key) =>
        snapshot.TryGetProperty(key, out var property) && property.ValueKind is JsonValueKind.String or JsonValueKind.Number
            ? property.ToString() : "";
}
