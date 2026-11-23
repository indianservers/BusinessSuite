using System.Data;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

internal sealed record SalesOperationStage(string Id, string Name, string[] Required, string[] Statuses, int? Capacity)
{
    internal int AgingDays { get; init; } = 14;
    internal bool Terminal { get; init; }
    internal bool RequireInterview { get; init; }
    internal bool RequireOffer { get; init; }
}
internal sealed record SalesOperationPipeline(int Id, int Version, string Name, List<SalesOperationStage> Stages);
internal sealed record SalesOperationalPosition(int Event, int? Pipeline, string PipelineName, string Stage, string StageName);
internal sealed record SalesPositionOptions(SalesOperationalPosition? Current, List<SalesOperationPipeline> Pipelines, bool CanMove);

internal sealed partial class SalesOrderRepository
{
    private const string OperationEventFilter = @"e.organization_id=@company AND e.module_key='srm'
        AND e.entity_type='sales_order' AND e.event_type='pipeline.stage_entered'
        AND e.payload_json->>'origin'='pipeline_workspace' AND e.payload_json->'data'->>'stream'='sales_pipeline'";

    internal async Task<SalesPositionOptions> SalesPositionOptionsAsync(int order)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose the Sales order's branch.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor);
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop Sales stage");
        await ReadOperationalOrderAsync(db, tx, branch, actor, scope, order, false);
        var current = await ReadSalesPositionAsync(db, tx, branch, actor, order);
        var pipelines = await ReadOperationalPipelinesAsync(db, tx, branch, actor, null);
        bool canMove = false;
        if (actor.CanWriteBranch)
        {
            try
            {
                string edit = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "edit");
                await ReadOperationalOrderAsync(db, tx, branch, actor, edit, order, false);
                canMove = true;
            }
            catch (Exception error) when (error is UnauthorizedAccessException or InvalidOperationException) { }
        }
        tx.Commit();
        return new SalesPositionOptions(current, pipelines, canMove);
    }

    internal async Task<SalesOperationalPosition> MoveSalesPositionAsync(int order, int pipelineId, int pipelineVersion,
        string stage, int? expectedEvent, Guid request)
    {
        if (order <= 0 || pipelineId <= 0 || pipelineVersion <= 0 || stage.Length is 0 or > 100 ||
            expectedEvent is <= 0 || request == Guid.Empty)
            throw new ArgumentException("Choose a configured Sales stage and reload the order before moving it.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose the Sales order's branch.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "edit");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop Sales stage move");
        // Shared lock order with the web move: the order precedes the selected pipeline policy.
        var source = await ReadOperationalOrderAsync(db, tx, branch, actor, scope, order, true);
        string key = $"sales-position:desktop:{request:D}";
        string hash = HashSalesPayload(new { order, pipelineId, pipelineVersion, stage, expectedEvent });
        var replay = await ReadSalesPositionAsync(db, tx, branch, actor, order, key, hash);
        if (replay is not null)
        {
            tx.Commit();
            return replay;
        }
        var policy = (await ReadOperationalPipelinesAsync(db, tx, branch, actor, pipelineId)).SingleOrDefault();
        if (policy is null || policy.Version != pipelineVersion)
            throw new InvalidOperationException("The Sales pipeline changed. Reload before moving the order.");
        var current = await ReadSalesPositionAsync(db, tx, branch, actor, order);
        if (current?.Event != expectedEvent)
            throw new InvalidOperationException("This order moved in another session. Reload before moving it.");
        var destination = policy.Stages.SingleOrDefault(item => item.Id == stage);
        if (destination is null && stage != "unassigned")
            throw new ArgumentException("Choose a configured Sales stage.");
        if (destination is not null)
        {
            if (destination.Required.Any(field => field switch
                {
                    "customer_id" => !source.HasCustomer, "title" => !source.HasTitle,
                    "expected_start_date" => !source.HasStart, "expected_end_date" => !source.HasEnd, _ => true
                }))
                throw new InvalidOperationException("Complete the required order fields before entering this stage.");
            if (destination.Statuses.Length > 0 && !destination.Statuses.Contains(source.Status))
                throw new InvalidOperationException("Complete the required document approval or confirmation before entering this stage.");
            if (current?.Pipeline == policy.Id && current.Stage == destination.Id)
            {
                tx.Commit();
                return current;
            }
            if (destination.Capacity is int limit && limit > 0)
            {
                using var capacity = RegisterCommand(@"SELECT count(*) FROM public.srm_sales_orders o
                    JOIN LATERAL (SELECT e.payload_json->'data' AS data FROM public.suite_service_events e
                        WHERE e.entity_id=o.id AND " + OperationEventFilter + @"
                        ORDER BY e.id DESC LIMIT 1) entered ON true
                    WHERE o.organization_id=@company AND o.id<>@order AND o.deleted_at IS NULL
                        AND entered.data->>'pipeline_id'=@pipeline::text AND entered.data->>'stage'=@stage
                        AND " + ConfirmationOwnership("o", "srm_sales_orders"), db, tx, branch, actor.Id);
                capacity.Parameters.AddWithValue("order", order);
                capacity.Parameters.AddWithValue("pipeline", policy.Id);
                capacity.Parameters.AddWithValue("stage", destination.Id);
                if ((long)(await capacity.ExecuteScalarAsync())! >= limit)
                    throw new InvalidOperationException("The destination operational stage is at capacity.");
            }
        }
        else if (current is { Pipeline: null, Stage: "unassigned" })
        {
            tx.Commit();
            return current;
        }

        var after = new
        {
            origin = "pipeline_workspace",
            data = new
            {
                stream = "sales_pipeline", pipeline_id = destination is null ? (int?)null : policy.Id,
                pipeline_name = policy.Name, previous_stage = current?.Stage ?? "unassigned",
                previous_stage_name = current?.StageName ?? "Unassigned", stage,
                stage_name = destination?.Name ?? "Unassigned", document_status = source.Status,
                desktop_request_sha256 = hash
            },
            depth = 0
        };
        using var write = RegisterCommand(@"INSERT INTO public.suite_service_events
            (organization_id,module_key,event_type,entity_type,entity_id,actor_id,request_key,payload_json,status)
            VALUES(@company,'srm','pipeline.stage_entered','sales_order',@order,@actor,@key,@payload::json,'pending')
            RETURNING id", db, tx, branch, actor.Id);
        write.Parameters.AddWithValue("order", order);
        write.Parameters.AddWithValue("key", key);
        write.Parameters.AddWithValue("payload", JsonSerializer.Serialize(after));
        if (await write.ExecuteScalarAsync() is not int id)
            throw new InvalidOperationException("The Sales stage transition could not be recorded.");
        tx.Commit();
        return new SalesOperationalPosition(id, after.data.pipeline_id, policy.Name, stage, after.data.stage_name);
    }

    private async Task<(string Status, bool HasCustomer, bool HasTitle, bool HasStart, bool HasEnd)>
        ReadOperationalOrderAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor,
            string scope, int order, bool write)
    {
        using var query = ScopedCommand(@"SELECT coalesce(o.status,''),o.customer_id IS NOT NULL,
            length(trim(o.title))>0,o.expected_start_date IS NOT NULL,o.expected_end_date IS NOT NULL
            FROM public.srm_sales_orders o" + OrderScope + " AND o.id=@order" +
            (write ? " FOR UPDATE OF o" : ""), db, tx, branch, actor, scope);
        query.Parameters.AddWithValue("order", order);
        using var row = await query.ExecuteReaderAsync();
        if (!await row.ReadAsync())
            throw new InvalidOperationException("The Sales order is unavailable for operational stage movement.");
        return (row.GetString(0), row.GetBoolean(1), row.GetBoolean(2), row.GetBoolean(3), row.GetBoolean(4));
    }

    private async Task<SalesOperationalPosition?> ReadSalesPositionAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, DesktopActor actor, int order, string? key = null, string? hash = null)
    {
        using var query = RegisterCommand(@"SELECT e.id,e.actor_id,e.payload_json->'data'->>'pipeline_id',
            e.payload_json->'data'->>'pipeline_name',e.payload_json->'data'->>'stage',
            e.payload_json->'data'->>'stage_name',e.payload_json->'data'->>'desktop_request_sha256'
            FROM public.suite_service_events e WHERE e.entity_id=@order AND " + OperationEventFilter +
            (key is null ? "" : " AND e.request_key=@key") + " ORDER BY e.id DESC LIMIT 1", db, tx, branch, actor.Id);
        query.Parameters.AddWithValue("order", order);
        if (key is not null)
            query.Parameters.AddWithValue("key", key);
        using var row = await query.ExecuteReaderAsync();
        if (!await row.ReadAsync())
            return null;
        if (key is not null && (row.GetInt32(1) != actor.Id || row.IsDBNull(6) || row.GetString(6) != hash))
            throw new InvalidOperationException("This request already recorded a different Sales stage action.");
        int? pipeline = row.IsDBNull(2) ? null : int.TryParse(row.GetString(2), out int value) && value > 0 ? value
            : throw new InvalidOperationException("The recorded Sales position has an invalid pipeline.");
        string state = row.IsDBNull(4) ? "" : row.GetString(4);
        return new SalesOperationalPosition(row.GetInt32(0), pipeline, row.IsDBNull(3) ? "" : row.GetString(3),
            state, row.IsDBNull(5) ? state : row.GetString(5));
    }

    private async Task<List<SalesOperationPipeline>> ReadOperationalPipelinesAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, DesktopActor actor, int? pipeline)
    {
        using var query = RegisterCommand(@"SELECT id,version,values_json::text FROM public.suite_service_policies
            WHERE organization_id=@company AND module_key='srm' AND kind='sales_pipeline'" +
            (pipeline.HasValue ? " AND id=@id FOR UPDATE" : " ORDER BY id"), db, tx, branch, actor.Id);
        if (pipeline.HasValue)
            query.Parameters.AddWithValue("id", pipeline.Value);
        using var row = await query.ExecuteReaderAsync();
        var result = new List<SalesOperationPipeline>();
        while (await row.ReadAsync())
        {
            using var doc = JsonDocument.Parse(row.GetString(2));
            var definition = doc.RootElement;
            string name = ActivityText(definition, "name");
            var stages = definition.GetProperty("stages").EnumerateArray().Select(item => new SalesOperationStage(
                ActivityText(item, "id"), ActivityText(item, "name"), ReadRules(item, "required"), ReadRules(item, "required_statuses"),
                item.TryGetProperty("wip_limit", out var limit) && limit.ValueKind == JsonValueKind.Number ? limit.GetInt32() : null)
            {
                AgingDays = item.TryGetProperty("aging_days", out var age) && age.ValueKind == JsonValueKind.Number ? age.GetInt32() : 14,
                Terminal = Flag(item, "is_terminal"),
                RequireInterview = Flag(item, "require_interview"),
                RequireOffer = Flag(item, "require_offer")
            }).ToList();
            if (name.Length == 0 || stages.Count is 0 or > 30 || stages.Any(stage => stage.Id.Length == 0 ||
                stage.Name.Length == 0 || stage.Id == "unassigned") || stages.Select(stage => stage.Id).Distinct().Count() != stages.Count)
                throw new InvalidOperationException("The Sales pipeline definition is invalid.");
            result.Add(new SalesOperationPipeline(row.GetInt32(0), row.GetInt32(1), name, stages));
        }
        return result;

        static bool Flag(JsonElement item, string key) =>
            item.TryGetProperty(key, out var value) && value.ValueKind == JsonValueKind.True;

        static string[] ReadRules(JsonElement item, string key) =>
            item.TryGetProperty(key, out var value) && value.ValueKind == JsonValueKind.Array
                ? value.EnumerateArray().Select(x => x.GetString() ?? "").ToArray() : Array.Empty<string>();
    }
}
