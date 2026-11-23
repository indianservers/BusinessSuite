using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record SalesOperationalLane(string Id, string Name, long Count, int? Capacity, int AgingDays);
internal sealed record SalesOperationalBoardRow(int Id, string Number, string Title, string Stage, string DocumentStatus,
    string Currency, decimal Total, int? DaysInStage, bool Aging, bool Commercial);
internal sealed record SalesOperationalBoard(List<SalesOperationPipeline> Definitions, int? Selected,
    List<SalesOperationalLane> Lanes, List<SalesOperationalBoardRow> Rows);

internal sealed partial class SalesOrderRepository
{
    internal async Task<SalesOperationalBoard> SalesOperationalBoardAsync(int? pipeline, string search, string? stage)
    {
        if (pipeline is <= 0 || stage?.Length > 100 || search.Length > 200)
            throw new ArgumentException("Choose a valid Sales pipeline and search.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a Sales branch.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor);
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop Sales operational board");
        var definitions = await ReadOperationalPipelinesAsync(db, tx, branch, actor, null);
        var selected = pipeline.HasValue ? definitions.SingleOrDefault(item => item.Id == pipeline) : null;
        if (pipeline.HasValue && selected is null)
            throw new InvalidOperationException("The selected Sales pipeline is no longer available.");
        var names = selected?.Stages.ToDictionary(item => item.Id, StringComparer.Ordinal)
            ?? new Dictionary<string, SalesOperationStage>(StringComparer.Ordinal);
        if (selected is not null && stage is not (null or "unassigned") && !names.ContainsKey(stage))
            throw new InvalidOperationException("The selected Sales stage is no longer available.");
        string orderFields = @"WITH visible AS (
            SELECT o.id,o.order_number,o.title,coalesce(o.status,'unknown') AS document_status,
                coalesce(o.currency,'') AS currency,coalesce(o.total_amount,0) AS total,o.created_at,
                o.metadata_json->>'source' IS DISTINCT FROM 'pos' AS commercial,";
        string position = selected is null
            ? @"coalesce(o.status,'unknown') AS operation_stage,NULL::int AS age
                FROM public.srm_sales_orders o" + OrderScope
            : @"coalesce(entered.stage,'unassigned') AS operation_stage,
                CASE WHEN entered.stage IS NOT NULL THEN greatest(0,floor(extract(epoch FROM (now()-entered.entered_at))/86400))::int END AS age
            FROM public.srm_sales_orders o
            LEFT JOIN LATERAL (
                SELECT e.created_at AS entered_at,e.payload_json->'data'->>'pipeline_id' AS pipeline,
                    e.payload_json->'data'->>'stage' AS stage
                FROM public.suite_service_events e WHERE e.entity_id=o.id AND " + OperationEventFilter + @"
                ORDER BY e.id DESC LIMIT 1
            ) latest ON true
            LEFT JOIN LATERAL (
                SELECT latest.entered_at,latest.stage WHERE latest.pipeline=@pipeline::text
            ) entered ON true" + OrderScope + @"
            AND (latest.pipeline IS NULL OR latest.pipeline=@pipeline::text)
            AND (entered.stage IS NULL OR entered.stage=ANY(@stages))";
        string source = orderFields + position + @"
            AND (@search='' OR strpos(lower(o.title),lower(@search))>0 OR strpos(lower(o.order_number),lower(@search))>0
                OR EXISTS (SELECT 1 FROM public.crm_companies c" + OrderCustomerScope + @"
                    AND c.id=o.customer_id AND strpos(lower(c.name),lower(@search))>0)))";
        var counts = new Dictionary<string, long>(StringComparer.Ordinal);
        using (var count = Query(source + " SELECT operation_stage,count(*) FROM visible GROUP BY operation_stage"))
        using (var row = await count.ExecuteReaderAsync())
            while (await row.ReadAsync())
                counts.Add(row.GetString(0), row.GetInt64(1));
        var lanes = selected is null
            ? new[] { "draft", "pending_approval", "approved", "confirmed", "closed", "cancelled" }
                .Concat(counts.Keys.OrderBy(item => item)).Distinct(StringComparer.Ordinal)
                .Select(id => new SalesOperationalLane(id, DocumentStageName(id), Count(id), null, 14)).ToList()
            : new[] { new SalesOperationalLane("unassigned", "Unassigned", Count("unassigned"), null, 14) }
                .Concat(selected.Stages.Select(item => new SalesOperationalLane(item.Id, item.Name, Count(item.Id),
                    item.Capacity, item.AgingDays))).ToList();
        using var list = Query(source + @" SELECT id,order_number,title,document_status,currency,total,operation_stage,age,commercial
            FROM visible WHERE (@stage IS NULL OR operation_stage=@stage) ORDER BY created_at DESC NULLS LAST,id DESC LIMIT 250");
        list.Parameters.AddWithValue("stage", NpgsqlDbType.Text, (object?)stage ?? DBNull.Value);
        var rows = new List<SalesOperationalBoardRow>();
        using (var row = await list.ExecuteReaderAsync())
        {
            while (await row.ReadAsync())
            {
                string id = row.GetString(6);
                int? age = row.IsDBNull(7) ? null : row.GetInt32(7);
                names.TryGetValue(id, out var definition);
                rows.Add(new SalesOperationalBoardRow(row.GetInt32(0), row.GetString(1), row.GetString(2),
                    definition?.Name ?? (selected is null ? DocumentStageName(id) : "Unassigned"), row.GetString(3), row.GetString(4), row.GetDecimal(5), age,
                    definition is { Terminal: false } && age >= definition.AgingDays &&
                    row.GetString(3) is not ("closed" or "cancelled"), row.GetBoolean(8)));
            }
        }
        tx.Commit();
        return new SalesOperationalBoard(definitions, selected?.Id, lanes, rows);

        static string DocumentStageName(string id) =>
            System.Globalization.CultureInfo.CurrentCulture.TextInfo.ToTitleCase(id.Replace('_', ' '));
        long Count(string id) => counts.TryGetValue(id, out long count) ? count : 0;
        NpgsqlCommand Query(string sql)
        {
            var command = ScopedCommand(sql, db, tx, branch, actor, scope);
            command.Parameters.AddWithValue("search", search.Trim());
            if (selected is not null)
            {
                command.Parameters.AddWithValue("pipeline", selected.Id);
                command.Parameters.AddWithValue("stages", NpgsqlDbType.Array | NpgsqlDbType.Text, names.Keys.ToArray());
            }
            return command;
        }
    }
}
