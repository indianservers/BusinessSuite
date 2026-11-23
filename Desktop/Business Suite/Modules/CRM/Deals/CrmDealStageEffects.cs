using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class CrmDealRepository
{
    private async Task<DataRow> CheckStageAsync(NpgsqlConnection db,NpgsqlTransaction tx,DataRow deal,int destination,
        CancellationToken cancellation,string outcome="Open",decimal? finalAmount=null,CrmDealBusinessFields? proposedFields=null)
    {
        using var query=Query(db,tx,@"SELECT s.id,s.name,s.probability,s.is_won,s.policy_json::text AS policy,
            CASE WHEN s.is_won OR lower(s.stage_type)='won' THEN 'Won'
                 WHEN s.is_lost OR lower(s.stage_type)='lost' THEN 'Lost' ELSE 'Open' END AS outcome
            FROM public.crm_pipeline_stages s JOIN public.crm_pipelines p ON p.id=s.pipeline_id
                AND p.organization_id=@org AND p.deleted_at IS NULL AND p.active
            WHERE s.organization_id=@org AND s.pipeline_id=@pipeline AND s.id=ANY(@stages)
                AND s.deleted_at IS NULL AND s.active ORDER BY s.id FOR UPDATE OF s",
            ("pipeline",NpgsqlDbType.Integer,deal["pipeline_id"]),
            ("stages",NpgsqlDbType.Array|NpgsqlDbType.Integer,new[] {(int)deal["stage_id"],destination}));
        var records=await ReadAsync(query,cancellation);
        if (records.Rows.Count!=2)
            throw new InvalidOperationException("The source and destination must be active stages in this deal's pipeline.");
        var source=records.Rows.Cast<DataRow>().Single(row=>(int)row["id"]==(int)deal["stage_id"]);
        var target=records.Rows.Cast<DataRow>().Single(row=>(int)row["id"]==destination);
        if ((string)source["outcome"]!="Open" || (string)target["outcome"]!=outcome)
            throw new InvalidOperationException("The current stage or destination no longer matches the requested deal outcome.");

        using var sourcePolicy=JsonDocument.Parse(source["policy"] as string??"{}");
        if (sourcePolicy.RootElement.TryGetProperty("allowed_next_ids",out JsonElement allowed)
            && allowed.GetArrayLength()>0 && !allowed.EnumerateArray().Any(value=>value.GetInt32()==destination))
            throw new InvalidOperationException("The pipeline does not allow this stage transition.");
        using var targetPolicy=JsonDocument.Parse(target["policy"] as string??"{}");
        var policy=targetPolicy.RootElement;
        if (policy.TryGetProperty("wip_limit",out JsonElement limit) && limit.ValueKind==JsonValueKind.Number)
        {
            using var count=Query(db,tx,@"SELECT count(*) FROM public.crm_deals
                WHERE organization_id=@org AND stage_id=@stage AND deleted_at IS NULL AND id<>@id",
                ("stage",NpgsqlDbType.Integer,destination),("id",NpgsqlDbType.Integer,deal["id"]));
            if ((long)(await count.ExecuteScalarAsync(cancellation))! >= limit.GetInt32())
                throw new InvalidOperationException("The destination stage is at capacity.");
        }
        if (policy.TryGetProperty("approval_required",out JsonElement approval) && approval.ValueKind==JsonValueKind.True)
        {
            using var check=Query(db,tx,@"SELECT status FROM public.crm_approval_requests
                WHERE organization_id=@org AND entity_type='deal' AND entity_id=@id 
                ORDER BY submitted_at DESC NULLS LAST,id DESC LIMIT 1 FOR SHARE",
                ("id",NpgsqlDbType.Integer,deal["id"]));
            if (await check.ExecuteScalarAsync(cancellation) as string!="approved")
                throw new InvalidOperationException("The destination stage requires an approved deal request.");
        }
        using var guidance=Query(db,tx,@"SELECT (settings_json->'dealStageGuidance'->(@stage::text))::text
            FROM public.crm_lead_management_config WHERE organization_id=@org",("stage",NpgsqlDbType.Integer,destination));
        using var configured=JsonDocument.Parse(await guidance.ExecuteScalarAsync(cancellation) as string??"{}");
        var required = Required(policy).Concat(Required(configured.RootElement)).Distinct();
        string[] missing = required.Where(field=>field is "company_id" or "contact_id" or "amount"
                or "expected_close_date" or "next_follow_up_at" or "lead_source")
            .Where(field=>Missing(Proposed(field)))
            .Select(field=>field.Replace('_',' ')).ToArray();
        if (missing.Length>0)
            throw new InvalidOperationException("Complete the stage requirements: "+string.Join(", ",missing)+".");
        return target;

        object? Proposed(string field)
        {
            if (proposedFields is null)
                return field=="amount" && finalAmount.HasValue?finalAmount.Value:deal[field];
            return field switch
            {
                "amount"=>proposedFields.Amount,
                "expected_close_date"=>proposedFields.ExpectedClose,
                "next_follow_up_at"=>proposedFields.NextAction,
                "lead_source"=>proposedFields.LeadSource,
                _=>deal[field]
            };
        }

        static bool Missing(object? value) => value is null or DBNull or "" ||
            (value is int id && id==0) || (value is decimal amount && amount==0);

        static IEnumerable<string> Required(JsonElement value) =>
            value.ValueKind==JsonValueKind.Object && value.TryGetProperty("required",out var list) && list.ValueKind==JsonValueKind.Array
                ? list.EnumerateArray().Select(item=>item.GetString()??"").ToArray() : Array.Empty<string>();
    }

    private async Task AddHistoryAsync(NpgsqlConnection db,NpgsqlTransaction tx,int actor,DataRow deal,
        (string Field,object? Old,object? New) change,CancellationToken cancellation,string? customTitle=null)
    {
        bool stage=change.Field=="stage_id";
        string title=customTitle ?? (stage?$"Stage changed to {change.New}":$"{change.Field} updated");
        string body=$"{change.Field.Replace('_',' ')} changed from {change.Old ?? "—"} to {change.New ?? "—"}";
        string metadata=JsonSerializer.Serialize(new {field=change.Field,old=change.Old,@new=change.New,
            sourceEntity="deals",sourceId=deal["id"]});
        using var command=Query(db,tx,@"WITH activity AS (
            INSERT INTO public.crm_activities (organization_id,branch_id,owner_user_id,entity_type,entity_id,deal_id,
                activity_type,title,subject,body,description,metadata_json,status,activity_date,created_by_user_id,updated_by_user_id)
            VALUES (@org,@branch,@actor,'deal',@id,@id,@type,@title,@title,@body,@body,@metadata,'Completed',now(),@actor,@actor)
            RETURNING id
        ), ownership AS (
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'crm_activities',id::text,@org,@branch,'desktop-crm' FROM activity WHERE @branch IS NOT NULL
        )
        INSERT INTO public.crm_timeline_events (organization_id,record_type,record_id,event_type,title,description,metadata_json,
            actor_user_id,occurred_at) VALUES (@org,'deal',@id,@type,@title,@body,@metadata,@actor,now())",
            ("branch",NpgsqlDbType.Integer,deal["owning_branch"] as int?),("actor",NpgsqlDbType.Integer,actor),
            ("id",NpgsqlDbType.Integer,deal["id"]),("type",NpgsqlDbType.Text,stage?"stage_change":"field_change"),
            ("title",NpgsqlDbType.Text,title),("body",NpgsqlDbType.Text,body),("metadata",NpgsqlDbType.Json,metadata));
        await command.ExecuteNonQueryAsync(cancellation);
    }

    private async Task WriteAuditAsync(NpgsqlConnection db,NpgsqlTransaction tx,int actor,int id,bool moving,
        List<(string Field,object? Old,object? New)> changes,CancellationToken cancellation)
    {
        using var command=Query(db,tx,@"INSERT INTO public.audit_logs (organization_id,user_id,actor_authenticated,method,
            entity_type,entity_id,action,description,module,old_values,new_values)
            VALUES (@org,@actor,true,'CRM','deals',@id,@action,@title,'crm',@old,@new)",
            ("actor",NpgsqlDbType.Integer,actor),("id",NpgsqlDbType.Integer,id),
            ("action",NpgsqlDbType.Text,moving?"STAGE_CHANGE":"UPDATE"),("title",NpgsqlDbType.Text,moving?"CRM stage change":"CRM update"),
            ("old",NpgsqlDbType.Text,JsonSerializer.Serialize(changes.ToDictionary(item=>item.Field,item=>item.Old))),
            ("new",NpgsqlDbType.Text,JsonSerializer.Serialize(changes.ToDictionary(item=>item.Field,item=>item.New))));
        await command.ExecuteNonQueryAsync(cancellation);
    }

    private Task QueueStageEventAsync(NpgsqlConnection db,NpgsqlTransaction tx,int actor,DataRow deal,CrmDealEdit original,
        DataRow target,CancellationToken cancellation) =>
        QueueStageEventAsync(db,tx,actor,deal,original.Stage,original.Stages.Single(item=>item.Id==original.Stage).Name,target,cancellation);

    private async Task QueueStageEventAsync(NpgsqlConnection db,NpgsqlTransaction tx,int actor,DataRow deal,int? previous,string previousName,
        DataRow target,CancellationToken cancellation)
    {
        int stage=(int)target["id"];
        int id=(int)deal["id"];
        int? owner=deal["owner_user_id"] as int?;
        var payload=new {origin="pipeline_workspace",data=new {previous_stage=previous?.ToString() ?? "None",stage=stage.ToString(),
            previous_stage_name=previousName,stage_name=(string)target["name"],
            owner_id=owner,scope=$"pipeline:{deal["pipeline_id"]}"},depth=0};
        using var insert=Query(db,tx,@"INSERT INTO public.suite_service_events
            (organization_id,module_key,event_type,entity_type,entity_id,actor_id,request_key,payload_json,status)
            VALUES (@org,'crm','pipeline.stage_entered','deal',@id,@actor,@key,@payload,'pending')",
            ("actor",NpgsqlDbType.Integer,actor),("id",NpgsqlDbType.Integer,id),
            ("key",NpgsqlDbType.Text,$"pipeline:crm:{id}:{Guid.NewGuid():N}"),
            ("payload",NpgsqlDbType.Json,JsonSerializer.Serialize(payload)));
        await insert.ExecuteNonQueryAsync(cancellation);
        using var policy=JsonDocument.Parse(target["policy"] as string??"{}");
        if (!owner.HasValue || !policy.RootElement.TryGetProperty("notify_owner",out var notify)
            || notify.ValueKind!=JsonValueKind.True)
            return;
        using var notification=Query(db,tx,@"INSERT INTO public.notifications
            (company_id,user_id,title,message,module,event_type,related_entity_type,related_entity_id,action_url,priority,channels,is_read)
            SELECT @org,u.id,'Pipeline stage changed',
                'A deal assigned to you entered a new stage. Open the deal to review its next action.',
                'crm','pipeline.stage_entered','deal',@id,@url,'normal','[""in_app""]'::json,false FROM public.users u
            WHERE u.id=@owner AND u.is_active AND EXISTS (
                SELECT 1 FROM public.common_people p WHERE p.user_id=u.id AND p.organization_id=@org)",
            ("owner",NpgsqlDbType.Integer,owner),("id",NpgsqlDbType.Integer,id),
            ("url",NpgsqlDbType.Text,$"/crm/deals/{id}"));
        await notification.ExecuteNonQueryAsync(cancellation);
    }
}
