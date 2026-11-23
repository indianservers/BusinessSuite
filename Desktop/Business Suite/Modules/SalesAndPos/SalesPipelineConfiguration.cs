using System.Data;
using System.Globalization;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    private static readonly HashSet<string> PipelineRequiredFields =
        new(StringComparer.Ordinal) { "customer_id", "title", "expected_start_date", "expected_end_date" };
    private static readonly HashSet<string> PipelineRequiredStatuses =
        new(StringComparer.Ordinal) { "draft", "pending_approval", "approved", "confirmed", "closed", "cancelled" };

    internal async Task<List<SalesOperationPipeline>> ListSalesPipelineDefinitionsAsync()
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a Sales branch.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop Sales pipeline configuration");
        await RequireSalesPipelineConfigureAsync(db, tx, branch, actor);
        return await ReadOperationalPipelinesAsync(db, tx, branch, actor, null);
    }

    internal async Task<int> SaveSalesPipelineDefinitionAsync(int? pipeline, int expectedVersion, string name,
        SalesOperationStage[] stages, Guid request)
    {
        name = name.Trim();
        if (pipeline is <= 0 || request == Guid.Empty || expectedVersion != 0 && !pipeline.HasValue ||
            expectedVersion <= 0 && pipeline.HasValue || name.Length is 0 or > 160 || stages.Length is 0 or > 30)
            throw new ArgumentException("Enter a pipeline name and between 1 and 30 named stages.");
        var normalized = stages.Select(stage => stage with { Name = stage.Name.Trim() }).ToArray();
        if (normalized.Select(stage => stage.Name).Distinct(StringComparer.OrdinalIgnoreCase).Count() != normalized.Length ||
            normalized.Select(stage => stage.Id).Distinct(StringComparer.Ordinal).Count() != normalized.Length ||
            normalized.Any(stage => stage.Name.Length is 0 or > 30 || stage.Id.Length is 0 or > 100 ||
                stage.Capacity is < 1 or > 10000 || stage.AgingDays is < 1 or > 365 ||
                stage.Required.Length > 4 || stage.Statuses.Length > 6 ||
                stage.Required.Any(field => !PipelineRequiredFields.Contains(field)) ||
                stage.Statuses.Any(status => !PipelineRequiredStatuses.Contains(status))))
            throw new ArgumentException("Use unique stage names of up to 30 characters, recognized requirements, aging of 1-365 days and optional capacity of 1-10000.");

        string digest = HashSalesPayload(new { pipeline, expectedVersion, name, stages = normalized.Select(SerializeStage).ToArray() });
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a Sales branch.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop Sales pipeline configuration");
        await RequireSalesPipelineConfigureAsync(db, tx, branch, actor);

        string key = $"sales-pipeline:{settings.OrganizationId.ToString(CultureInfo.InvariantCulture)}:{request:N}";
        using (var prior = RegisterCommand(@"SELECT id,updated_by,values_json->>'desktop_sha256'
            FROM public.suite_service_policies WHERE organization_id=@company AND module_key='srm' AND kind='sales_pipeline'
                AND ((@pipeline IS NULL AND scope_key=@key) OR (id=@pipeline AND values_json->>'desktop_request'=@request))",
            db, tx, branch, actor.Id))
        {
            prior.Parameters.AddWithValue("pipeline", NpgsqlDbType.Integer, (object?)pipeline ?? DBNull.Value);
            prior.Parameters.AddWithValue("key", key);
            prior.Parameters.AddWithValue("request", request.ToString("D"));
            int? replayId = null;
            using (var row = await prior.ExecuteReaderAsync())
            {
                if (await row.ReadAsync())
                {
                    if (row.IsDBNull(1) || row.GetInt32(1) != actor.Id || row.IsDBNull(2) || row.GetString(2) != digest)
                        throw new InvalidOperationException("The prior request was already used with different pipeline settings.");
                    replayId = row.GetInt32(0);
                }
            }
            if (replayId is int original)
            {
                tx.Commit();
                return original;
            }
        }

        HashSet<string> priorStages = new(StringComparer.Ordinal);
        if (pipeline.HasValue)
        {
            var saved = (await ReadOperationalPipelinesAsync(db, tx, branch, actor, pipeline)).SingleOrDefault();
            if (saved is null || saved.Version != expectedVersion)
                throw new InvalidOperationException("The Sales pipeline changed. Reload before saving.");
            priorStages.UnionWith(saved.Stages.Select(stage => stage.Id));
            if (!priorStages.IsSubsetOf(normalized.Select(stage => stage.Id)))
                throw new InvalidOperationException("Retain existing Sales stages so assigned orders keep their history.");
        }
        if (normalized.Any(stage => !priorStages.Contains(stage.Id) && !stage.Id.StartsWith("new:", StringComparison.Ordinal)))
            throw new ArgumentException("The pipeline contains an invalid stage identifier.");

        var values = new
        {
            name,
            stages = normalized.Select(stage => SerializeStage(priorStages.Contains(stage.Id) ? stage :
                stage with { Id = Guid.NewGuid().ToString("N") })).ToArray(),
            desktop_request = request.ToString("D"), desktop_sha256 = digest
        };
        using var write = RegisterCommand(pipeline.HasValue ? @"
            UPDATE public.suite_service_policies SET values_json=@values::json,version=version+1,updated_by=@actor,updated_at=now()
            WHERE id=@pipeline AND version=@version AND organization_id=@company AND module_key='srm' AND kind='sales_pipeline'
            RETURNING id" : @"
            INSERT INTO public.suite_service_policies(scope_key,organization_id,module_key,kind,values_json,version,updated_by)
            VALUES(@key,@company,'srm','sales_pipeline',@values::json,1,@actor) RETURNING id",
            db, tx, branch, actor.Id);
        write.Parameters.AddWithValue("values", JsonSerializer.Serialize(values));
        write.Parameters.AddWithValue("pipeline", NpgsqlDbType.Integer, (object?)pipeline ?? DBNull.Value);
        write.Parameters.AddWithValue("version", expectedVersion);
        write.Parameters.AddWithValue("key", key);
        if (await write.ExecuteScalarAsync() is not int result)
            throw new InvalidOperationException("The Sales pipeline could not be saved. Refresh before retrying.");
        tx.Commit();
        return result;
    }

    private static object SerializeStage(SalesOperationStage stage) => new
    {
        id = stage.Id, name = stage.Name, wip_limit = stage.Capacity, aging_days = stage.AgingDays,
        required = stage.Required, required_statuses = stage.Statuses, is_terminal = stage.Terminal,
        require_interview = stage.RequireInterview, require_offer = stage.RequireOffer
    };

    private async Task RequireSalesPipelineConfigureAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor)
    {
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "edit");
        if (!actor.CanWriteBranch || scope != "organization")
            throw new UnauthorizedAccessException("Company-wide Sales edit access is required to configure pipelines.");
    }
}
