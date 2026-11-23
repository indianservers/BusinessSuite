using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class CrmDealRepository
{
    internal async Task ArchivePipelineAsync(PipelineAdminChoice pipeline,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await BeginPipelineWriteAsync(db,tx,"delete",cancellation);
        string previous=await LockPipelineStructureAsync(db,tx,pipeline,cancellation);
        using(var dependencies=Query(db,tx,@"SELECT CASE
            WHEN EXISTS (SELECT 1 FROM public.crm_deals d WHERE d.organization_id=@org AND d.pipeline_id=@id)
                THEN 'Move active and archived Deals before archiving their pipeline.'
            WHEN EXISTS (SELECT 1 FROM public.crm_lead_management_config config
                WHERE config.organization_id=@org AND config.settings_json->'salesProcess'->>'enabled'='true'
                    AND config.settings_json->'salesProcess'->>'pipelineId'=@id::text)
                THEN 'Choose a different pipeline in the active lead sales process before archiving.'
            ELSE NULL END",("id",NpgsqlDbType.Integer,pipeline.Id)))
            if (await dependencies.ExecuteScalarAsync(cancellation) is string reason)
                throw new InvalidOperationException(reason);
        using var command=Query(db,tx,@"WITH archived AS (
            UPDATE public.crm_pipelines p SET deleted_at=now(),active=false,updated_by_user_id=@actor,updated_at=now()
              WHERE p.organization_id=@org AND p.id=@id AND p.deleted_at IS NULL
              RETURNING to_jsonb(p)::text AS snapshot
        ) INSERT INTO public.audit_logs (organization_id,user_id,actor_authenticated,method,entity_type,entity_id,
            action,description,module,old_values,new_values)
        SELECT @org,@actor,true,'CRM','pipelines',@id,'DELETE','CRM pipeline archived','crm',@old,snapshot FROM archived",
            ("id",NpgsqlDbType.Integer,pipeline.Id),("actor",NpgsqlDbType.Integer,actor.Id),("old",NpgsqlDbType.Text,previous));
        if (await command.ExecuteNonQueryAsync(cancellation)!=1)
            throw new InvalidOperationException("The pipeline changed before it could be archived.");
        tx.Commit();
    }
}
