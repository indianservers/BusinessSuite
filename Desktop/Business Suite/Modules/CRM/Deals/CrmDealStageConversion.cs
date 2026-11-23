using System.Data;
using Npgsql;

namespace Business_Suite;

internal sealed partial class CrmDealRepository
{
    internal async Task<DataTable> StageConversionAsync(string search,string status,CrmDealFilters filters,
        CancellationToken cancellation)
    {
        filters.Validate();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        await RequireDealsAsync(db,tx,actor,false);
        var (from,parameters)=await FilteredDealDataAsync(db,tx,actor,search,status,false,filters,[]);
        using var query=Query(db,tx,@"WITH scoped AS (
            SELECT d.id,NULLIF(d.currency,'') AS currency_key"+from+@"
        ), history AS (
            SELECT deal.id,deal.currency_key,e.metadata_json->>'old' AS old_stage,e.metadata_json->>'new' AS new_stage
            FROM scoped deal
            JOIN public.crm_timeline_events e ON e.organization_id=@org AND e.record_id=deal.id
                AND e.record_type='deal' AND e.event_type='stage_change'
        ), stages AS (
            SELECT id,name,pipeline_id,position,is_won,is_lost,stage_type
            FROM public.crm_pipeline_stages WHERE organization_id=@org
        ), entries AS (
            SELECT DISTINCT id,currency_key,new_stage AS stage_key FROM history WHERE new_stage IS NOT NULL
        ), progression AS (
            SELECT DISTINCT h.id,source.id AS stage_id FROM history h
            JOIN stages source ON source.id::text=h.old_stage
            JOIN stages destination ON destination.id::text=h.new_stage AND destination.pipeline_id=source.pipeline_id
            WHERE destination.is_won IS TRUE OR destination.stage_type='won'
                OR (destination.position>source.position AND destination.is_lost IS FALSE AND destination.stage_type<>'lost')
        )
        SELECT stage.id AS stage_id,stage.name AS stage,pipeline.name AS pipeline,entries.currency_key,
            COALESCE(entries.currency_key,'Unknown') AS currency,count(*) AS entries,count(progression.id) AS progressed,
            CASE WHEN NOT (stage.is_won IS TRUE OR stage.is_lost IS TRUE OR COALESCE(stage.stage_type,'open') IN ('won','lost'))
                THEN round(100.0*count(progression.id)/count(*),2) END AS conversion_rate
        FROM entries JOIN stages stage ON stage.id::text=entries.stage_key
        JOIN public.crm_pipelines pipeline ON pipeline.id=stage.pipeline_id AND pipeline.organization_id=@org
        LEFT JOIN progression ON progression.id=entries.id AND progression.stage_id=stage.id
        GROUP BY pipeline.name,stage.id,stage.name,stage.position,stage.is_won,stage.is_lost,stage.stage_type,entries.currency_key
        ORDER BY pipeline.name,stage.position,stage.id,currency",parameters);
        return await ReadAsync(query,cancellation);
    }
}
