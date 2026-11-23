using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PipelineStageRevision(int Id,string Revision);

internal sealed partial class CrmDealRepository
{
    internal async Task ReorderPipelineStagesAsync(PipelineAdminChoice pipeline,IReadOnlyList<PipelineStageRevision> snapshot,
        int[] ordered,CancellationToken cancellation)
    {
        int[] expected=snapshot.Select(stage=>stage.Id).ToArray();
        if (expected.Length<2 || ordered.Length!=expected.Length || ordered.Distinct().Count()!=ordered.Length ||
            !new HashSet<int>(expected).SetEquals(ordered))
            throw new ArgumentException("The reorder must include each current stage exactly once.");
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await BeginPipelineWriteAsync(db,tx,"edit",cancellation);
        await LockPipelineStructureAsync(db,tx,pipeline,cancellation);
        await LockStageStructureAsync(db,tx,pipeline.Id,snapshot,cancellation);
        if (expected.SequenceEqual(ordered))
            return;
        using var update=Query(db,tx,@"UPDATE public.crm_pipeline_stages s SET position=stage.next::int,
            order_index=stage.next::int,updated_at=now(),updated_by_user_id=@actor
            FROM unnest(@order) WITH ORDINALITY AS stage(id,next)
            WHERE s.organization_id=@org AND s.pipeline_id=@pipeline AND s.id=stage.id AND s.deleted_at IS NULL
                AND (s.position IS DISTINCT FROM stage.next::int OR s.order_index IS DISTINCT FROM stage.next::int)",
            ("order",NpgsqlDbType.Array|NpgsqlDbType.Integer,ordered),("actor",NpgsqlDbType.Integer,actor.Id),
            ("pipeline",NpgsqlDbType.Integer,pipeline.Id));
        await update.ExecuteNonQueryAsync(cancellation);
        using var audit=Query(db,tx,@"INSERT INTO public.audit_logs (organization_id,user_id,actor_authenticated,method,
            entity_type,entity_id,action,description,module,old_values,new_values)
            VALUES (@org,@actor,true,'CRM','pipelines',@pipeline,'UPDATE','CRM pipeline stages reordered','crm',@old,@new)",
            ("actor",NpgsqlDbType.Integer,actor.Id),("pipeline",NpgsqlDbType.Integer,pipeline.Id),
            ("old",NpgsqlDbType.Text,JsonSerializer.Serialize(new {stage_order=expected})),
            ("new",NpgsqlDbType.Text,JsonSerializer.Serialize(new {stage_order=ordered})));
        await audit.ExecuteNonQueryAsync(cancellation);
        tx.Commit();
    }

    private async Task<DataTable> LockStageStructureAsync(NpgsqlConnection db,NpgsqlTransaction tx,int pipeline,
        IReadOnlyList<PipelineStageRevision> snapshot,CancellationToken cancellation)
    {
        using var stages=Query(db,tx,@"SELECT s.id,s.organization_id,s.xmin::text AS revision,s.position,s.active,
            to_jsonb(s)::text AS snapshot,"+StageOutcome+@" AS outcome
            FROM public.crm_pipeline_stages s WHERE s.pipeline_id=@pipeline AND s.deleted_at IS NULL
            ORDER BY s.id FOR UPDATE OF s",("pipeline",NpgsqlDbType.Integer,pipeline));
        var rows=await ReadAsync(stages,cancellation);
        if (rows.Rows.Cast<DataRow>().Any(row=>row["organization_id"] is not int org || org!=settings.OrganizationId))
            throw new InvalidOperationException("An existing stage has unverified company ownership. Review its pipeline configuration.");
        var current=rows.Rows.Cast<DataRow>().OrderBy(row=>row["position"] as int? ?? int.MaxValue)
            .ThenBy(row=>(int)row["id"]).Select(row=>new PipelineStageRevision((int)row["id"],(string)row["revision"]));
        if (!current.SequenceEqual(snapshot))
            throw new InvalidOperationException("The pipeline stages changed. Reload the pipeline before saving.");
        return rows;
    }
}
