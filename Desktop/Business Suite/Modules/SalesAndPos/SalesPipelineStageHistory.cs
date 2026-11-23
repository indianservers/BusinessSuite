using System.Text.Json;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    internal Task<List<SalesOrderActivityRow>> SalesOrderStageHistoryAsync(int order) => ReadAsync(@"
        SELECT e.created_at,e.actor_id,e.payload_json::text
        FROM public.srm_sales_orders o
        JOIN public.suite_service_events e ON e.entity_id=o.id AND e.organization_id=@company
          AND e.module_key='srm' AND e.entity_type='sales_order' AND e.event_type='pipeline.stage_entered'
          AND e.payload_json->>'origin'='pipeline_workspace'" + OrderScope + @"
        AND o.id=@order ORDER BY e.id DESC LIMIT 30",
        query => query.Parameters.AddWithValue("order", order), row =>
        {
            using var payload = JsonDocument.Parse(row.GetString(2));
            var root = payload.RootElement;
            var data = root.TryGetProperty("data", out var item) && item.ValueKind == JsonValueKind.Object ? item : default;
            string pipeline = StageHistoryValue(data, "pipeline_name", "pipeline_id");
            string before = StageHistoryValue(data, "previous_stage_name", "previous_stage");
            string after = StageHistoryValue(data, "stage_name", "stage");
            string document = StageHistoryValue(data, "document_status");
            if (document.Length > 0)
                after += Environment.NewLine + $"Document status  {document.Replace('_', ' ')}";
            return new SalesOrderActivityRow(row.GetDateTime(0).ToLocalTime(), pipeline.Length > 0 ? pipeline : "Sales order",
                "Stage entered", $"User #{row.GetInt32(1)}", before, after.TrimStart(), "");
        }, requireNativeBranch: true);

    private static string StageHistoryValue(JsonElement data, string primary, string? fallback = null)
    {
        if (data.ValueKind != JsonValueKind.Object)
            return "";
        string value = ActivityText(data, primary);
        return value.Length == 0 && fallback is not null ? ActivityText(data, fallback) : value;
    }
}
