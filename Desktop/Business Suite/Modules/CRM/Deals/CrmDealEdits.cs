using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record CrmDealStage(int Id, string Name);
internal sealed record CrmDealBusinessFields(decimal? Amount,DateTime? ExpectedClose,DateTime? NextAction,string LeadSource);
internal sealed record CrmDealEdit(int Id, int Version, string Revision, string Name, string Description,
    string Priority, int Stage, List<CrmDealStage> Stages,CrmDealBusinessFields BusinessFields,bool CanEditAmount,string Currency);

internal sealed partial class CrmDealRepository
{
    internal async Task<CrmDealEdit> EditAsync(int id, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await RequireEditorAsync(db, tx, cancellation);
        DataRow row = await LockableDealAsync(db, tx, id, false, cancellation);
        bool canEditAmount=!await HasDealCatalogAsync(db,tx,row,cancellation);
        using var query = Query(db, tx, @"SELECT s.id,s.name FROM public.crm_pipeline_stages s
            JOIN public.crm_pipelines p ON p.id=s.pipeline_id AND p.organization_id=@org AND p.deleted_at IS NULL AND p.active
            WHERE s.organization_id=@org AND s.pipeline_id=@pipeline AND s.deleted_at IS NULL AND s.active
              AND NOT COALESCE(s.is_won,false) AND NOT COALESCE(s.is_lost,false)
              AND COALESCE(lower(s.stage_type),'open') NOT IN ('won','lost')
            ORDER BY s.position NULLS LAST,s.id", ("pipeline",NpgsqlDbType.Integer,row["pipeline_id"]));
        var stages = new List<CrmDealStage>();
        using var reader = await query.ExecuteReaderAsync(cancellation);
        while (await reader.ReadAsync(cancellation))
            stages.Add(new(reader.GetInt32(0),reader.GetString(1)));
        int stage = (int)row["stage_id"];
        if (!stages.Any(item => item.Id == stage))
            throw new InvalidOperationException("This deal needs an active open pipeline stage before editing.");
        return new(id,(int)row["version"],(string)row["revision"],(string)row["name"],
            Convert.ToString(row["description"])??"",Convert.ToString(row["priority"])??"",stage,stages,
            new(row["amount"] as decimal?,row["expected_close_date"] as DateTime?,row["next_follow_up_at"] as DateTime?,
                row["lead_source"] as string ?? ""),canEditAmount,row["currency"] as string ?? "");
    }

    internal async Task SaveEditAsync(CrmDealEdit original, string name,string description,string priority,int destination,
        CancellationToken cancellation, CrmDealBusinessFields? businessFields = null)
    {
        if (string.IsNullOrWhiteSpace(name) || name.Length>180 || description.Length>10000 ||
            (priority!=original.Priority && priority is not ("Low" or "Medium" or "High" or "Critical")))
            throw new ArgumentException("Enter a deal name up to 180 characters, a valid priority and a description up to 10,000 characters.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        var actor = await RequireEditorAsync(db,tx,cancellation);
        DataRow row = await LockableDealAsync(db,tx,original.Id,true,cancellation);
        if ((int)row["version"]!=original.Version || (string)row["revision"]!=original.Revision)
            throw new InvalidOperationException("This deal changed. Close the editor and refresh.");
        DateTime? nextAction=businessFields?.NextAction;
        if (nextAction is DateTime timestamp && timestamp.Kind!=DateTimeKind.Utc)
            throw new ArgumentException("The next action must be supplied as a UTC timestamp.");
        var fields=businessFields is null?original.BusinessFields:businessFields with
        {
            ExpectedClose=businessFields.ExpectedClose?.Date,
            LeadSource=businessFields.LeadSource==original.BusinessFields.LeadSource
                ?businessFields.LeadSource:businessFields.LeadSource.Trim()
        };
        decimal? amount=fields.Amount;
        bool amountChanged=!Equals(row["amount"] as decimal?,amount);
        if (amountChanged && (amount is <0 or >9999999999.99m ||
            (amount.HasValue && Math.Round(amount.Value,2)!=amount.Value)))
            throw new ArgumentException("Enter a nonnegative amount with at most two decimals.");
        if (amountChanged && await HasDealCatalogAsync(db,tx,row,cancellation))
            throw new InvalidOperationException("The product or service lines determine this deal's amount.");
        if (fields.LeadSource.Length>80 && fields.LeadSource!=original.BusinessFields.LeadSource)
            throw new ArgumentException("Enter a lead source of up to 80 characters.");
        string? sourceValue=fields.LeadSource.Length==0?null:fields.LeadSource;
        int source = (int)row["stage_id"];
        bool moving = source!=destination;
        var changes = new List<(string Field,object? Old,object? New)>();
        AddChange("name",row["name"],name);
        AddChange("description",row["description"],description.Length==0?null:description);
        AddChange("priority",row["priority"],priority.Length==0?null:priority);
        AddChange("amount",row["amount"],amount);
        AddChange("expected_close_date",row["expected_close_date"],fields.ExpectedClose);
        AddChange("next_follow_up_at",row["next_follow_up_at"],fields.NextAction);
        if (!string.Equals(row["lead_source"] as string ?? "",fields.LeadSource,StringComparison.Ordinal))
            AddChange("lead_source",row["lead_source"],sourceValue);
        if (!moving && changes.Count==0)
            return;

        await CrmDirectoryWrites.CheckRequiredFieldsAsync(db,tx,"deals",settings.OrganizationId,original.Id,cancellation);
        await GuardLocalEffectsAsync(db,tx,moving,cancellation);
        DataRow? target = moving ? await CheckStageAsync(db,tx,row,destination,cancellation,proposedFields:fields) : null;
        int? probability = target is null ? row["probability"] as int? : target["probability"] as int?;
        decimal? expected = row["expected_revenue"] as decimal?;
        if (target is not null)
        {
            if (probability is int value && (value<0 || value>100))
                throw new InvalidOperationException("The destination stage probability is invalid.");
            AddChange("stage_id",source,destination);
            AddChange("probability",row["probability"],probability);
        }
        if (moving || amountChanged)
            expected=Math.Round((amount ?? 0)*(probability ?? 0)/100m,2,MidpointRounding.ToEven);

        using var update = Query(db,tx,@"UPDATE public.crm_deals SET name=@name,description=@description,priority=@priority,
            amount=@amount,expected_close_date=@close,next_follow_up_at=@next,
            lead_source=CASE WHEN @change_source THEN @source ELSE lead_source END,
            source=CASE WHEN @change_source THEN @source ELSE source END,
            stage_id=@stage,probability=@probability,expected_revenue=@expected,version=version+1,
            updated_at=now(),updated_by_user_id=@actor WHERE organization_id=@org AND id=@id",
            ("name",NpgsqlDbType.Text,name),("description",NpgsqlDbType.Text,description.Length==0?null:description),
            ("priority",NpgsqlDbType.Text,priority.Length==0?null:priority),("stage",NpgsqlDbType.Integer,destination),
            ("amount",NpgsqlDbType.Numeric,amount),("close",NpgsqlDbType.Date,fields.ExpectedClose),
            ("next",NpgsqlDbType.TimestampTz,fields.NextAction),("source",NpgsqlDbType.Text,sourceValue),
            ("change_source",NpgsqlDbType.Boolean,changes.Any(change=>change.Field=="lead_source")),
            ("probability",NpgsqlDbType.Integer,probability),("expected",NpgsqlDbType.Numeric,expected),
            ("actor",NpgsqlDbType.Integer,actor.Id),("id",NpgsqlDbType.Integer,original.Id));
        await update.ExecuteNonQueryAsync(cancellation);
        foreach (var change in changes)
            await AddHistoryAsync(db,tx,actor.Id,row,change,cancellation);
        await WriteAuditAsync(db,tx,actor.Id,original.Id,moving,changes,cancellation);
        if (target is not null)
        {
            await LeadStore.ApplyDealStageAsync(db,tx,settings,original.Id,(int)row["pipeline_id"],(string)target["name"],actor.Id,cancellation);
            await QueueStageEventAsync(db,tx,actor.Id,row,original,target,cancellation);
        }
        await NotifyDealWatchersAsync(db,tx,actor.Id,row,name,cancellation);
        tx.Commit();

        void AddChange(string field,object? before,object? after)
        {
            if (before == DBNull.Value) before=null;
            if (!Equals(before,after))
                changes.Add((field,before,after));
        }
    }

    private async Task<bool> HasDealCatalogAsync(NpgsqlConnection db,NpgsqlTransaction tx,DataRow row,CancellationToken cancellation)
    {
        if (row["catalog_items"] is string value)
        {
            using var catalog=JsonDocument.Parse(value);
            if (catalog.RootElement.ValueKind==JsonValueKind.Array && catalog.RootElement.GetArrayLength()>0)
                return true;
            if (catalog.RootElement.ValueKind is not (JsonValueKind.Array or JsonValueKind.Null))
                return true;
        }
        using var legacy=Query(db,tx,"SELECT EXISTS (SELECT 1 FROM public.crm_deal_products WHERE deal_id=@id)",
            ("id",NpgsqlDbType.Integer,row["id"]));
        return (bool)(await legacy.ExecuteScalarAsync(cancellation))!;
    }

    private async Task<DesktopActor> RequireEditorAsync(NpgsqlConnection db,NpgsqlTransaction tx,CancellationToken cancellation)
    {
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        if (!actor.CanWriteBranch || !actor.IsSuperuser)
            throw new UnauthorizedAccessException("Desktop deal editing currently requires a Suite superuser in a writable branch.");
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"deals","edit");
        return actor;
    }

    private async Task<DataRow> LockableDealAsync(NpgsqlConnection db,NpgsqlTransaction tx,int id,bool locked,
        CancellationToken cancellation,bool requireOpen=true)
    {
        using var query=Query(db,tx,@"SELECT d.*,d.xmin::text AS revision,
            COALESCE((SELECT o.branch_id FROM public.suite_branch_ownership o WHERE o.company_id=@org
                AND o.resource_table='crm_deals' AND o.resource_key=d.id::text),d.branch_id) AS owning_branch
            FROM public.crm_deals d WHERE d.organization_id=@org AND d.id=@id AND d.deleted_at IS NULL
            AND (NOT @require_open OR d.status='Open') AND "+
            CrmDirectoryWrites.BranchScope("crm_deals","d")+(locked?" FOR UPDATE OF d":""),
            ("id",NpgsqlDbType.Integer,id),("require_open",NpgsqlDbType.Boolean,requireOpen));
        var rows=await ReadAsync(query,cancellation);
        if (rows.Rows.Count==0)
            throw new InvalidOperationException(requireOpen?"The open deal is unavailable in the current branch."
                :"The deal is unavailable in the current branch.");
        return rows.Rows[0];
    }

    private async Task GuardLocalEffectsAsync(NpgsqlConnection db,NpgsqlTransaction tx,bool moving,
        CancellationToken cancellation,string? outcome=null)
    {
        using var check=Query(db,tx,@"SELECT
            EXISTS (SELECT 1 FROM public.crm_webhooks WHERE organization_id=@org AND deleted_at IS NULL AND is_active
                AND (events::jsonb ? 'deal.updated' OR (@moving AND events::jsonb ? 'deal.stage_changed')
                    OR (@event IS NOT NULL AND events::jsonb ? @event)))",
            ("moving",NpgsqlDbType.Boolean,moving),
            ("event",NpgsqlDbType.Text,outcome is null?null:"deal."+outcome.ToLowerInvariant()));
        if (await check.ExecuteScalarAsync(cancellation) is true)
            throw new InvalidOperationException("This deal has an active edit webhook. The configured webhook delivery needs the CRM service.");
    }
}
