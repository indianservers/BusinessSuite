using System.Data;
using System.Text.Json;
using System.Text.Json.Serialization;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PipelinePolicyStage(int Id,int Pipeline,string Label,string Revision,bool Active,string Json);
internal sealed record DealStagePolicy
{
    [JsonPropertyName("allowed_next_ids")] public int[] AllowedNext {get;init;}=[];
    [JsonPropertyName("required")] public string[] Required {get;init;}=[];
    [JsonPropertyName("approval_required")] public bool Approval {get;init;}
    [JsonPropertyName("stagnation_days")] public int StagnationDays {get;init;}=14;
    [JsonPropertyName("wip_limit")] public int? Capacity {get;init;}
    [JsonPropertyName("notify_owner")] public bool NotifyOwner {get;init;}
}

internal sealed partial class CrmDealRepository
{
    internal static readonly (string Key,string Label)[] StageRequiredFields=[
        ("company_id","Company"),("contact_id","Primary contact"),("amount","Amount"),
        ("expected_close_date","Expected close"),("next_follow_up_at","Next action"),("lead_source","Lead source")
    ];

    internal async Task<List<PipelinePolicyStage>> PipelinePolicyStagesAsync(CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        await RequireStagePolicyAdminAsync(db,tx,actor,"view");
        using var query=Query(db,tx,@"SELECT s.id,s.pipeline_id,p.name||' · '||s.name||
            (CASE WHEN s.active THEN '' ELSE ' (inactive)' END) AS label,
            s.xmin::text AS revision,COALESCE(s.active,false),COALESCE(s.policy_json::text,'{}')
            FROM public.crm_pipeline_stages s JOIN public.crm_pipelines p ON p.organization_id=@org AND p.id=s.pipeline_id
            WHERE s.organization_id=@org AND p.active AND p.deleted_at IS NULL AND s.deleted_at IS NULL
            ORDER BY p.name,p.id,s.position NULLS LAST,s.id");
        using var reader=await query.ExecuteReaderAsync(cancellation);
        var result=new List<PipelinePolicyStage>();
        while (await reader.ReadAsync(cancellation))
            result.Add(new(reader.GetInt32(0),reader.GetInt32(1),reader.GetString(2),reader.GetString(3),
                reader.GetBoolean(4),reader.GetString(5)));
        return result;
    }

    internal async Task SaveStagePolicyAsync(PipelinePolicyStage original,DealStagePolicy draft,CancellationToken cancellation)
    {
        if (draft.StagnationDays is <1 or >365 || draft.Capacity is <1 or >10000 || draft.AllowedNext.Length>100
            || draft.AllowedNext.Distinct().Count()!=draft.AllowedNext.Length || draft.AllowedNext.Contains(original.Id)
            || draft.Required.Distinct().Count()!=draft.Required.Length
            || draft.Required.Any(field=>!StageRequiredFields.Any(item=>item.Key==field)))
            throw new ArgumentException("Use supported required fields and destinations. Aging must be 1–365 days and capacity 1–10,000.");
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireStagePolicyAdminAsync(db,tx,actor,"edit");
        using(var serialize=Query(db,tx,"SELECT pg_advisory_xact_lock(720000000::bigint+@org)"))
            await serialize.ExecuteNonQueryAsync(cancellation);
        await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireStagePolicyAdminAsync(db,tx,actor,"edit");
        using var stages=Query(db,tx,@"SELECT s.id,s.xmin::text AS revision FROM public.crm_pipeline_stages s
            JOIN public.crm_pipelines p ON p.organization_id=@org AND p.id=s.pipeline_id AND p.active AND p.deleted_at IS NULL
            WHERE s.organization_id=@org AND s.pipeline_id=@pipeline AND s.deleted_at IS NULL
            ORDER BY s.id FOR UPDATE OF s",("pipeline",NpgsqlDbType.Integer,original.Pipeline));
        var existing=await ReadAsync(stages,cancellation);
        var source=existing.Rows.Cast<DataRow>().SingleOrDefault(row=>(int)row["id"]==original.Id);
        if (source is null || (string)source["revision"]!=original.Revision)
            throw new InvalidOperationException("The pipeline changed. Reload the stage before saving its policy.");
        var ids=existing.Rows.Cast<DataRow>().Select(row=>(int)row["id"]).ToHashSet();
        if (draft.AllowedNext.Any(id=>!ids.Contains(id)))
            throw new InvalidOperationException("Allowed next stages must belong to the same pipeline.");
        using var command=Query(db,tx,@"WITH original AS (
            SELECT policy_json FROM public.crm_pipeline_stages WHERE organization_id=@org AND id=@id
        ), changed AS (
            UPDATE public.crm_pipeline_stages SET policy_json=(
                CASE WHEN jsonb_typeof(policy_json::jsonb)='object' THEN policy_json::jsonb ELSE '{}'::jsonb END
                || @policy::jsonb)::json,updated_at=now(),updated_by_user_id=@actor
            WHERE organization_id=@org AND id=@id RETURNING policy_json
        ) INSERT INTO public.audit_logs (organization_id,user_id,actor_authenticated,method,entity_type,entity_id,action,
            description,module,old_values,new_values)
        SELECT @org,@actor,true,'CRM','pipeline-stages',@id,'UPDATE','Pipeline stage policy updated','crm',
            json_build_object('policy',original.policy_json)::text,json_build_object('policy',changed.policy_json)::text
        FROM original CROSS JOIN changed",
            ("id",NpgsqlDbType.Integer,original.Id),("actor",NpgsqlDbType.Integer,actor.Id),
            ("policy",NpgsqlDbType.Json,JsonSerializer.Serialize(draft)));
        await command.ExecuteNonQueryAsync(cancellation);
        tx.Commit();
    }

    private async Task RequireStagePolicyAdminAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,string action)
    {
        var grant=await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,settings.BranchId ?? 0,
            actor,"crm",action,["crm_pipeline_manage","crm_manage","crm_admin"]);
        if (grant.Scope!="organization" || (grant.IsLegacy && !actor.IsCompanyAdmin && !actor.IsSuperuser))
            throw new UnauthorizedAccessException("Pipeline settings require organization-wide CRM pipeline management access.");
    }
}
