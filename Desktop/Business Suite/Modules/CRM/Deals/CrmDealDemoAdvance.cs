using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class CrmDealRepository
{
    internal async Task AdvanceAfterDemoAsync(NpgsqlConnection db,NpgsqlTransaction tx,int id,int pipeline,
        CancellationToken cancellation)
    {
        using var query=Query(db,tx,@"SELECT target.id AS destination,source.name AS origin
            FROM public.crm_deals d
            JOIN public.crm_pipeline_stages source ON source.id=d.stage_id AND source.pipeline_id=d.pipeline_id
                AND source.organization_id=@org
            JOIN public.crm_pipeline_stages target ON target.pipeline_id=d.pipeline_id
                AND target.organization_id=@org AND target.name='Demo Completed' AND target.deleted_at IS NULL
                AND source.position<target.position
            WHERE d.organization_id=@org AND d.id=@id AND d.pipeline_id=@pipeline AND d.status='Open' AND d.deleted_at IS NULL
            ORDER BY target.position,target.id LIMIT 1 FOR UPDATE OF d NOWAIT",
            ("id",NpgsqlDbType.Integer,id),("pipeline",NpgsqlDbType.Integer,pipeline));
        System.Data.DataTable candidates;
        try
        {
            candidates=await ReadAsync(query,cancellation);
        }
        catch (PostgresException error) when (error.SqlState==PostgresErrorCodes.LockNotAvailable)
        {
            throw new InvalidOperationException("The linked Deal is being edited. Refresh the Lead and try again.",error);
        }
        if (candidates.Rows.Count==0) return;
        var candidate=candidates.Rows[0];
        var actor=await RequireEditorAsync(db,tx,cancellation);
        var deal=await LockableDealAsync(db,tx,id,true,cancellation);
        await CrmDirectoryWrites.CheckRequiredFieldsAsync(db,tx,"deals",settings.OrganizationId,id,cancellation);
        await GuardLocalEffectsAsync(db,tx,true,cancellation);
        int destination=(int)candidate["destination"];
        int previous=(int)deal["stage_id"];
        var target=await CheckStageAsync(db,tx,deal,destination,cancellation);
        int? probability=target["probability"] as int?;
        if (probability is <0 or >100)
            throw new InvalidOperationException("The destination stage probability is invalid.");
        decimal expected=Math.Round((deal["amount"] as decimal? ?? 0)*(probability ?? 0)/100m,2,MidpointRounding.ToEven);
        using var update=Query(db,tx,@"UPDATE public.crm_deals SET stage_id=@stage,probability=@probability,expected_revenue=@expected,
            updated_by_user_id=@actor,updated_at=now(),version=version+1 WHERE organization_id=@org AND id=@id",
            ("id",NpgsqlDbType.Integer,id),("stage",NpgsqlDbType.Integer,destination),("actor",NpgsqlDbType.Integer,actor.Id),
            ("probability",NpgsqlDbType.Integer,probability),("expected",NpgsqlDbType.Numeric,expected));
        await update.ExecuteNonQueryAsync(cancellation);
        var changes=new List<(string Field,object? Old,object? New)> {("stage_id",previous,destination)};
        if (deal["probability"] as int? != probability)
            changes.Add(("probability",deal["probability"] as int?,probability));
        foreach (var change in changes)
            await AddHistoryAsync(db,tx,actor.Id,deal,change,cancellation);
        await WriteAuditAsync(db,tx,actor.Id,id,true,changes,cancellation);
        await LeadStore.ApplyDealStageAsync(db,tx,settings,id,pipeline,(string)target["name"],actor.Id,cancellation);
        await QueueStageEventAsync(db,tx,actor.Id,deal,previous,(string)candidate["origin"],target,cancellation);
        await NotifyDealWatchersAsync(db,tx,actor.Id,deal,(string)deal["name"],cancellation);
    }
}
