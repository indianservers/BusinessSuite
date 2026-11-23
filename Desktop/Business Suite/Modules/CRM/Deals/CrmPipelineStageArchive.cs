using System.Data;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class CrmDealRepository
{
    internal async Task<int> ArchivePipelineStageAsync(PipelineAdminChoice pipeline,IReadOnlyList<PipelineStageRevision> snapshot,
        int source,int? replacement,CancellationToken cancellation)
    {
        if (source<=0 || replacement==source)
            throw new ArgumentException("Choose an existing stage and a different replacement when required.");
        using var db=new Npgsql.NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await BeginPipelineWriteAsync(db,tx,"delete",cancellation);
        await LockPipelineStructureAsync(db,tx,pipeline,cancellation);

        // Deal edits acquire the Deal row before stage locks.
        int[] originalDeals=await OccupantsAsync(true);
        var structure=await LockStageStructureAsync(db,tx,pipeline.Id,snapshot,cancellation);
        int[] deals=await OccupantsAsync(false);
        if (!originalDeals.SequenceEqual(deals))
            throw new InvalidOperationException("Deals entered or left this stage. Reload the pipeline before archiving.");
        if (structure.Rows.Count<=1)
            throw new InvalidOperationException("Keep at least one stage in the pipeline.");
        var origin=structure.Rows.Cast<DataRow>().SingleOrDefault(row=>(int)row["id"]==source);
        if (origin is null)
            throw new InvalidOperationException("The selected stage is unavailable in this pipeline.");
        if (deals.Length>0 && !replacement.HasValue)
            throw new InvalidOperationException("Choose a replacement stage for the assigned Deals.");
        if (replacement.HasValue)
        {
            var target=structure.Rows.Cast<DataRow>().SingleOrDefault(row=>(int)row["id"]==replacement.Value);
            if (target is null || target["active"] is not true || !Equals(origin["outcome"],target["outcome"]))
                throw new InvalidOperationException("Choose an active replacement stage with the same outcome in this pipeline.");
        }
        using(var referenced=Query(db,tx,@"SELECT EXISTS(SELECT 1 FROM public.crm_pipeline_stages s
            WHERE s.organization_id=@org AND s.pipeline_id=@pipeline AND s.id<>@source AND s.deleted_at IS NULL
              AND (COALESCE(s.policy_json::jsonb->'allowed_next_ids','[]'::jsonb) @> jsonb_build_array(@source)
                   OR COALESCE(s.policy_json::jsonb->'allowed_stage_ids','[]'::jsonb) @> jsonb_build_array(@source)))",
            ("pipeline",NpgsqlDbType.Integer,pipeline.Id),("source",NpgsqlDbType.Integer,source)))
            if (await referenced.ExecuteScalarAsync(cancellation) is true)
                throw new InvalidOperationException("Update stage transition rules that reference this stage before archiving it.");
        if (deals.Length>0)
        {
            using var move=Query(db,tx,@"WITH moved AS (
                UPDATE public.crm_deals SET stage_id=@target,version=COALESCE(version,1)+1,
                    updated_by_user_id=@actor,updated_at=now()
                WHERE organization_id=@org AND pipeline_id=@pipeline AND stage_id=@source AND id=ANY(@deals)
                RETURNING id
            ) INSERT INTO public.audit_logs (organization_id,user_id,actor_authenticated,method,entity_type,entity_id,
                action,description,module,old_values,new_values)
            SELECT @org,@actor,true,'CRM','deals',id,'UPDATE','Pipeline editor stage remap','crm',
                json_build_object('stage_id',@source)::text,json_build_object('stage_id',@target)::text FROM moved",
                ("pipeline",NpgsqlDbType.Integer,pipeline.Id),("source",NpgsqlDbType.Integer,source),("target",NpgsqlDbType.Integer,replacement),
                ("deals",NpgsqlDbType.Array|NpgsqlDbType.Integer,deals),("actor",NpgsqlDbType.Integer,actor.Id));
            if (await move.ExecuteNonQueryAsync(cancellation)!=deals.Length)
                throw new InvalidOperationException("The affected Deals changed. No assignments were moved.");
        }

        using var archive=Query(db,tx,@"WITH changed AS (
            UPDATE public.crm_pipeline_stages s SET deleted_at=now(),active=false,updated_at=now(),updated_by_user_id=@actor
              WHERE organization_id=@org AND pipeline_id=@pipeline AND id=@source RETURNING to_jsonb(s) AS state
        ) INSERT INTO public.audit_logs (organization_id,user_id,actor_authenticated,method,entity_type,entity_id,
            action,description,module,old_values,new_values)
        SELECT @org,@actor,true,'CRM','pipeline-stages',@source,'DELETE','CRM pipeline stage archived','crm',
            @before,(state||jsonb_build_object('remap_stage_id',@target,'moved_deals',@count))::text FROM changed",
            ("pipeline",NpgsqlDbType.Integer,pipeline.Id),("source",NpgsqlDbType.Integer,source),("target",NpgsqlDbType.Integer,replacement),
            ("actor",NpgsqlDbType.Integer,actor.Id),("before",NpgsqlDbType.Text,(string)origin["snapshot"]),("count",NpgsqlDbType.Integer,deals.Length));
        if (await archive.ExecuteNonQueryAsync(cancellation)!=1)
            throw new InvalidOperationException("The stage changed before it could be archived.");
        tx.Commit();
        return deals.Length;

        async Task<int[]> OccupantsAsync(bool locked)
        {
            using var command=Query(db,tx,@"SELECT d.id,(d.pipeline_id=@pipeline AND "+CrmDirectoryWrites.BranchScope("crm_deals","d")+@") AS visible
                FROM public.crm_deals d WHERE d.organization_id=@org AND d.stage_id=@source ORDER BY d.id"+
                (locked?" FOR UPDATE OF d":""),
                ("pipeline",NpgsqlDbType.Integer,pipeline.Id),("source",NpgsqlDbType.Integer,source));
            var rows=await ReadAsync(command,cancellation);
            if ((rows.Rows.Count>0 && !settings.BranchId.HasValue) ||
                rows.Rows.Cast<DataRow>().Any(row=>row["visible"] is not true))
                throw new InvalidOperationException("This stage holds Deals outside the configured writable branch or pipeline.");
            return rows.Rows.Cast<DataRow>().Select(row=>(int)row["id"]).ToArray();
        }
    }
}
