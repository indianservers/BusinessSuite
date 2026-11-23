using System.Data;
using System.Text.RegularExpressions;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PipelineAdminChoice(int Id,string Name,string Description,string Revision);
internal sealed record PipelineStageDraft(string Name,int Probability,string Outcome,string Color);

internal sealed partial class CrmDealRepository
{
    internal async Task<List<PipelineAdminChoice>> PipelineListAsync(CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        await RequireStagePolicyAdminAsync(db,tx,actor,"view");
        using var query=Query(db,tx,@"SELECT p.id,p.name,p.description,p.xmin::text AS revision
            FROM public.crm_pipelines p WHERE p.organization_id=@org AND p.deleted_at IS NULL AND p.active ORDER BY p.name,p.id");
        var rows=await ReadAsync(query,cancellation);
        return rows.Rows.Cast<DataRow>().Select(row=>new PipelineAdminChoice((int)row["id"],(string)row["name"],
            row["description"] as string??"",(string)row["revision"])).ToList();
    }

    internal async Task<DataTable> PipelineAdminStagesAsync(int pipeline,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        await RequireStagePolicyAdminAsync(db,tx,actor,"view");
        using var query=Query(db,tx,@"SELECT s.id,s.xmin::text AS revision,s.name,s.position,s.probability,s.color,s.active,
            "+StageOutcome+@" AS outcome,(SELECT count(*) FROM public.crm_deals d
                WHERE d.organization_id=@org AND d.pipeline_id=p.id AND d.stage_id=s.id AND d.deleted_at IS NULL) AS deals,
            (SELECT count(*) FROM public.crm_deals d WHERE d.organization_id=@org AND d.stage_id=s.id) AS assigned
            FROM public.crm_pipeline_stages s JOIN public.crm_pipelines p ON p.id=s.pipeline_id AND p.organization_id=@org
                AND p.active AND p.deleted_at IS NULL
            WHERE s.organization_id=@org AND s.pipeline_id=@pipeline AND s.deleted_at IS NULL
            ORDER BY s.position NULLS LAST,s.id",("pipeline",NpgsqlDbType.Integer,pipeline));
        return await ReadAsync(query,cancellation);
    }

    private const string StageOutcome=@"CASE WHEN s.is_won OR lower(s.stage_type)='won' THEN 'won'
        WHEN s.is_lost OR lower(s.stage_type)='lost' THEN 'lost' ELSE 'open' END";

    internal async Task<int> SavePipelineAsync(PipelineAdminChoice? current,string name,string description,CancellationToken cancellation)
    {
        name=name.Trim();
        description=description.Trim();
        if (name.Length is <1 or >160 || description.Length>10000)
            throw new ArgumentException("Enter a pipeline name up to 160 characters and a description up to 10,000 characters.");
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await BeginPipelineWriteAsync(db,tx,current is null?"create":"edit",cancellation);
        using(var duplicate=Query(db,tx,@"SELECT 1 FROM public.crm_pipelines WHERE organization_id=@org AND deleted_at IS NULL
            AND lower(trim(name))=lower(@name) AND id IS DISTINCT FROM @id LIMIT 1",
            ("name",NpgsqlDbType.Text,name),("id",NpgsqlDbType.Integer,current?.Id)))
            if (await duplicate.ExecuteScalarAsync(cancellation) is not null)
                throw new InvalidOperationException("A pipeline with the same name already exists.");
        string? old=current is null?null:await LockPipelineStructureAsync(db,tx,current,cancellation);
        string sql=current is null?@"INSERT INTO public.crm_pipelines (organization_id,name,description,is_default,active,
                created_by_user_id,updated_by_user_id)
            VALUES (@org,@name,NULLIF(@description,''),false,true,@actor,@actor) RETURNING id,to_jsonb(crm_pipelines)::text AS snapshot":
            @"UPDATE public.crm_pipelines SET name=@name,description=NULLIF(@description,''),updated_at=now(),
                updated_by_user_id=@actor WHERE organization_id=@org AND id=@id RETURNING id,to_jsonb(crm_pipelines)::text AS snapshot";
        using var command=Query(db,tx,sql,("name",NpgsqlDbType.Text,name),("description",NpgsqlDbType.Text,description),
            ("actor",NpgsqlDbType.Integer,actor.Id),("id",NpgsqlDbType.Integer,current?.Id));
        var saved=(await ReadAsync(command,cancellation)).Rows[0];
        int id=(int)saved["id"];
        await AuditPipelineStructureAsync(db,tx,actor.Id,"pipelines",id,old,(string)saved["snapshot"],cancellation);
        tx.Commit();
        return id;
    }

    internal async Task<int> SavePipelineStageAsync(PipelineAdminChoice pipeline,int? stage,string? revision,PipelineStageDraft draft,
        CancellationToken cancellation)
    {
        draft=draft with {Name=draft.Name.Trim(),Color=draft.Color.Trim()};
        if (draft.Name.Length is <1 or >120 || draft.Probability is <0 or >100 ||
            draft.Outcome is not ("open" or "won" or "lost") || !Regex.IsMatch(draft.Color,@"\A#[0-9A-Fa-f]{6}\z"))
            throw new ArgumentException("Enter a stage name, probability from 0 to 100, outcome and a six-digit hex color.");
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await BeginPipelineWriteAsync(db,tx,stage.HasValue?"edit":"create",cancellation);
        await LockPipelineStructureAsync(db,tx,pipeline,cancellation);
        using(var duplicate=Query(db,tx,@"SELECT 1 FROM public.crm_pipeline_stages WHERE pipeline_id=@pipeline AND id IS DISTINCT FROM @stage
            AND (name=@name OR (deleted_at IS NULL AND lower(trim(name))=lower(@name))) LIMIT 1",
            ("pipeline",NpgsqlDbType.Integer,pipeline.Id),("stage",NpgsqlDbType.Integer,stage),("name",NpgsqlDbType.Text,draft.Name)))
            if (await duplicate.ExecuteScalarAsync(cancellation) is not null)
                throw new InvalidOperationException("This stage name is already used in the pipeline.");
        string? old=null;
        if (stage.HasValue)
        {
            using var lookup=Query(db,tx,@"SELECT s.xmin::text AS revision,to_jsonb(s)::text AS snapshot,"+StageOutcome+@" AS outcome
                FROM public.crm_pipeline_stages s WHERE s.organization_id=@org AND s.pipeline_id=@pipeline AND s.id=@id
                    AND s.deleted_at IS NULL FOR UPDATE OF s",
                ("id",NpgsqlDbType.Integer,stage),("pipeline",NpgsqlDbType.Integer,pipeline.Id));
            var rows=await ReadAsync(lookup,cancellation);
            if (rows.Rows.Count!=1 || (string)rows.Rows[0]["revision"]!=revision)
                throw new InvalidOperationException("The stage changed. Reload the pipeline before saving.");
            if ((string)rows.Rows[0]["outcome"]!=draft.Outcome)
            {
                using var occupied=Query(db,tx,@"SELECT EXISTS(SELECT 1 FROM public.crm_deals d
                    WHERE d.organization_id=@org AND d.pipeline_id=@pipeline AND d.stage_id=@stage)",
                    ("pipeline",NpgsqlDbType.Integer,pipeline.Id),("stage",NpgsqlDbType.Integer,stage));
                if (await occupied.ExecuteScalarAsync(cancellation) is true)
                    throw new InvalidOperationException("Move existing Deals through their workflows before changing this stage outcome.");
            }
            old=(string)rows.Rows[0]["snapshot"];
        }
        string sql=stage.HasValue?@"UPDATE public.crm_pipeline_stages SET name=@name,probability=@probability,color=@color,
            stage_type=@outcome,is_won=(@outcome='won'),is_lost=(@outcome='lost'),updated_at=now(),updated_by_user_id=@actor
            WHERE organization_id=@org AND pipeline_id=@pipeline AND id=@id RETURNING id,to_jsonb(crm_pipeline_stages)::text AS snapshot":@"
            WITH position AS (SELECT COALESCE(max(position),0)+1 AS next FROM public.crm_pipeline_stages WHERE pipeline_id=@pipeline
                AND organization_id=@org AND deleted_at IS NULL)
            INSERT INTO public.crm_pipeline_stages (organization_id,pipeline_id,name,probability,color,stage_type,is_won,is_lost,
                active,position,order_index,policy_json,created_by_user_id,updated_by_user_id)
            SELECT @org,@pipeline,@name,@probability,@color,@outcome,(@outcome='won'),(@outcome='lost'),true,next,next,'{}'::json,
                @actor,@actor FROM position RETURNING id,to_jsonb(crm_pipeline_stages)::text AS snapshot";
        using var command=Query(db,tx,sql,("name",NpgsqlDbType.Text,draft.Name),("probability",NpgsqlDbType.Integer,draft.Probability),
            ("color",NpgsqlDbType.Text,draft.Color),("outcome",NpgsqlDbType.Text,draft.Outcome),("actor",NpgsqlDbType.Integer,actor.Id),
            ("pipeline",NpgsqlDbType.Integer,pipeline.Id),("id",NpgsqlDbType.Integer,stage));
        var saved=(await ReadAsync(command,cancellation)).Rows[0];
        int id=(int)saved["id"];
        await AuditPipelineStructureAsync(db,tx,actor.Id,"pipeline-stages",id,old,(string)saved["snapshot"],cancellation);
        tx.Commit();
        return id;
    }

    private async Task<DesktopActor> BeginPipelineWriteAsync(NpgsqlConnection db,NpgsqlTransaction tx,string action,
        CancellationToken cancellation)
    {
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireStagePolicyAdminAsync(db,tx,actor,action);
        using var serialize=Query(db,tx,"SELECT pg_advisory_xact_lock(720000000::bigint+@org)");
        await serialize.ExecuteNonQueryAsync(cancellation);
        actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireStagePolicyAdminAsync(db,tx,actor,action);
        return actor;
    }

    private async Task<string> LockPipelineStructureAsync(NpgsqlConnection db,NpgsqlTransaction tx,PipelineAdminChoice pipeline,
        CancellationToken cancellation)
    {
        using var command=Query(db,tx,@"SELECT xmin::text AS revision,to_jsonb(p)::text AS snapshot FROM public.crm_pipelines p
            WHERE organization_id=@org AND id=@id AND active AND deleted_at IS NULL FOR NO KEY UPDATE",
            ("id",NpgsqlDbType.Integer,pipeline.Id));
        var rows=await ReadAsync(command,cancellation);
        if (rows.Rows.Count!=1 || (string)rows.Rows[0]["revision"]!=pipeline.Revision)
            throw new InvalidOperationException("This pipeline changed. Reload it before saving.");
        return (string)rows.Rows[0]["snapshot"];
    }

    private async Task AuditPipelineStructureAsync(NpgsqlConnection db,NpgsqlTransaction tx,int actor,string entity,int id,
        string? before,string after,CancellationToken cancellation)
    {
        using var command=Query(db,tx,@"INSERT INTO public.audit_logs (organization_id,user_id,actor_authenticated,method,entity_type,
            entity_id,action,description,module,old_values,new_values)
            VALUES (@org,@actor,true,'CRM',@entity,@id,@action,'Pipeline configuration saved','crm',@old,@new)",
            ("actor",NpgsqlDbType.Integer,actor),("entity",NpgsqlDbType.Text,entity),("id",NpgsqlDbType.Integer,id),
            ("action",NpgsqlDbType.Text,before is null?"CREATE":"UPDATE"),("old",NpgsqlDbType.Text,before),("new",NpgsqlDbType.Text,after));
        await command.ExecuteNonQueryAsync(cancellation);
    }
}
