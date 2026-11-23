using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record CrmDealFilters(int? Pipeline=null,int? Stage=null,int? Owner=null,int? Team=null,string? Currency=null,
    string? Priority=null,string? Type=null,string? Industry=null,string? Source=null,string? LostReason=null,
    int? EnteredStage=null,DateTime? From=null,DateTime? Until=null,bool NoNextAction=false)
{
    internal void Validate()
    {
        if (From.HasValue && Until.HasValue && From.Value.Date>Until.Value.Date)
            throw new ArgumentException("The expected close start date must be on or before the end date.");
    }
}

internal sealed record CrmDealFilterChoice(string? Value,string Name,int? Pipeline=null);

internal sealed partial class CrmDealRepository
{
    internal async Task<ILookup<string,CrmDealFilterChoice>> FilterOptionsAsync(bool archived,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        await RequireDealsAsync(db,tx,actor,archived);
        using var query=Query(db,tx,@"WITH visible AS (
            SELECT d.id,d.pipeline_id,d.stage_id,d.owner_user_id,d.assigned_team_id,d.currency,d.priority,d.deal_type,
                d.industry,d.source,d.lead_source,d.lost_reason,d.loss_reason,d.status
            FROM public.crm_deals d WHERE d.organization_id=@org AND (d.deleted_at IS NOT NULL)=@archived
                AND "+CrmDirectoryWrites.BranchScope("crm_deals","d")+@"
        ), options(kind,value,label,pipeline) AS (
            SELECT 'pipeline',d.pipeline_id::text,p.name,NULL::int
            FROM visible d JOIN public.crm_pipelines p ON p.id=d.pipeline_id AND p.organization_id=@org
            UNION
            SELECT 'stage',d.stage_id::text,p.name||' · '||s.name,d.pipeline_id FROM visible d
            JOIN public.crm_pipelines p ON p.id=d.pipeline_id AND p.organization_id=@org
            JOIN public.crm_pipeline_stages s ON s.id=d.stage_id AND s.pipeline_id=p.id
                AND (s.organization_id=@org OR s.organization_id IS NULL)
            UNION
            SELECT 'entered',s.id::text,p.name||' · '||s.name,s.pipeline_id FROM visible d
            JOIN public.crm_timeline_events e ON e.organization_id=@org AND e.record_type='deal'
                AND e.event_type='stage_change' AND e.record_id=d.id
            JOIN public.crm_pipeline_stages s ON e.metadata_json->>'new'=s.id::text
                AND (s.organization_id=@org OR s.organization_id IS NULL)
            JOIN public.crm_pipelines p ON p.id=s.pipeline_id AND p.organization_id=@org
            UNION
            SELECT 'owner',d.owner_user_id::text,COALESCE(u.email,'Owner #'||d.owner_user_id::text),NULL::int FROM visible d
            LEFT JOIN public.users u ON u.id=d.owner_user_id AND EXISTS (
                SELECT 1 FROM public.common_people person WHERE person.user_id=u.id AND person.organization_id=@org)
            WHERE d.owner_user_id IS NOT NULL
            UNION
            SELECT 'team',d.assigned_team_id::text,t.name,NULL::int FROM visible d
            JOIN public.crm_teams t ON t.id=d.assigned_team_id AND t.organization_id=@org
            UNION
            SELECT x.kind,x.value,x.value,NULL::int FROM visible d CROSS JOIN LATERAL (
                VALUES ('currency',d.currency),('priority',d.priority),('type',d.deal_type),('industry',d.industry),
                    ('source',d.source),('source',d.lead_source),('loss',CASE WHEN d.status='Lost'
                    THEN COALESCE(NULLIF(d.lost_reason,''),NULLIF(d.loss_reason,''),'No reason recorded') END)
            ) x(kind,value) WHERE NULLIF(trim(x.value),'') IS NOT NULL
        ) SELECT kind,value,label,pipeline FROM options ORDER BY kind,lower(label),value",
            ("archived",NpgsqlDbType.Boolean,archived));
        using var rows=await query.ExecuteReaderAsync(cancellation);
        var options=new List<(string Kind,CrmDealFilterChoice Choice)>();
        while (await rows.ReadAsync(cancellation))
            options.Add((rows.GetString(0),new(rows.GetString(1),rows.GetString(2),rows.IsDBNull(3)?null:rows.GetInt32(3))));
        return options.ToLookup(option=>option.Kind,option=>option.Choice);
    }
}
