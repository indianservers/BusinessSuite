using System.Data;
using System.Text.Json;

namespace Business_Suite;

internal static class LeadWorkbook
{
    private static readonly string[] Fields=[
        "full_name","email","phone","phone_country_code","company_name","job_title","source","status",
        "estimated_value","next_follow_up_at","city","state","country","industry","notes",
        "need","budget","decision_maker","purchase_timeline","loss_reason","competitor","archived","archive_reason","review_at"
    ];
    internal static void Write(Stream output, DataTable records, CancellationToken cancellation)
    {
        TabularWorkbook.WriteAsync(output, "Leads", Fields, append =>
        {
            foreach (DataRow record in records.Rows)
            {
                cancellation.ThrowIfCancellationRequested();
                using var parsed=JsonDocument.Parse((string)record["operating_state"]);
                var detail=parsed.RootElement;
                detail.TryGetProperty("qualification",out var qualification);
                var values=Fields.Select(field=>field switch
                {
                    "need" or "budget"=>Read(qualification,field),
                    "decision_maker"=>Read(qualification,"decisionMaker"),
                    "purchase_timeline"=>Read(qualification,"timeline"),
                    "loss_reason"=>Read(detail,"lossReason"),
                    "competitor"=>Read(detail,"competitor"),
                    "archived"=>record["deleted_at"] is not DBNull || Read(detail,"archived") is true,
                    "archive_reason"=>Read(detail,"archiveReason"),
                    "review_at"=>Read(detail,"reviewAt"),
                    _=>record[field] is DBNull?null:record[field]
                });
                append(values);
            }
            return Task.CompletedTask;
        }, cancellation).GetAwaiter().GetResult();
    }

    private static object? Read(JsonElement element,string key)
    {
        if (element.ValueKind!=JsonValueKind.Object || !element.TryGetProperty(key,out var value))
            return null;
        return value.ValueKind switch
        {
            JsonValueKind.String=>value.GetString(),
            JsonValueKind.True=>true,
            JsonValueKind.False=>false,
            JsonValueKind.Number when value.TryGetDecimal(out var number)=>number,
            _=>null
        };
    }

}
