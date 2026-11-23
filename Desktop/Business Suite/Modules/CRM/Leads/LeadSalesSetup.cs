using System.Data;
using System.Text.Json;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadSalesChoice(int Id,string Name);
internal sealed record LeadSalesSetup(string Revision,int? Pipeline,int? Manager,int[] Owners,
    List<LeadSalesChoice> People,List<LeadSalesChoice> Managers);

internal static partial class LeadStore
{
    internal static async Task<LeadSalesSetup> ReadLeadSalesSetupAsync(CancellationToken cancellation)
    {
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        await RequireLeadSettingsAdminAsync(db,tx,settings,actor);
        var candidates=await SalesCandidatesAsync(db,tx,settings,null,cancellation);
        using var read=Cmd(db,tx,@"SELECT xmin::text,settings_json::text FROM public.crm_lead_management_config
            WHERE organization_id=@org",("org",NpgsqlDbType.Integer,settings.OrganizationId));
        using var row=await read.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation)) return new("",null,null,[],candidates.People,candidates.Managers);
        var doc=JsonNode.Parse(row.GetString(1)) as JsonObject ?? new();
        return new(row.GetString(0),doc["salesProcess"]?["pipelineId"]?.GetValue<int>(),
            doc["salesProcess"]?["managerId"]?.GetValue<int>(),ReadOwnerPool(doc["assignment"] as JsonObject),
            candidates.People,candidates.Managers);
    }

    internal static async Task<int> SaveLeadSalesSetupAsync(string revision,int manager,int[] pool,CancellationToken cancellation)
    {
        if (manager<=0 || pool.Length is <1 or >100 || pool.Any(id=>id<=0))
            throw new ArgumentException("Choose a sales manager and one to 100 assignment pool members.");
        var owners=pool.Distinct().ToArray();
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireLeadSettingsAdminAsync(db,tx,settings,actor);
        int org=settings.OrganizationId;
        using(var serialize=Cmd(db,tx,"SELECT pg_advisory_xact_lock(720000000::bigint+@org)",("org",NpgsqlDbType.Integer,org)))
            await serialize.ExecuteNonQueryAsync(cancellation);
        await LockLeadSettingsSectionAsync(db,tx,org,revision,"salesProcess",cancellation);
        var candidates=await SalesCandidatesAsync(db,tx,settings,owners.Append(manager).Distinct().ToArray(),cancellation);
        if (!candidates.Managers.Any(person=>person.Id==manager) || owners.Any(id=>!candidates.People.Any(person=>person.Id==id)))
            throw new InvalidOperationException("Choose active Lead owners and a manager with CRM assignment permission.");
        using var config=Cmd(db,tx,"SELECT settings_json::text FROM public.crm_lead_management_config WHERE organization_id=@org",
            ("org",NpgsqlDbType.Integer,org));
        string? before=await config.ExecuteScalarAsync(cancellation) as string;
        var existing=before is null?new JsonObject():JsonNode.Parse(before) as JsonObject ?? new();
        var assignment=existing["assignment"]?.DeepClone() as JsonObject ?? new();
        int? configured=existing["salesProcess"]?["pipelineId"]?.GetValue<int>();
        using var pipeline=Cmd(db,tx,@"SELECT id FROM public.crm_pipelines WHERE organization_id=@org
            AND id=@id AND deleted_at IS NULL AND active FOR SHARE",("org",NpgsqlDbType.Integer,org),("id",NpgsqlDbType.Integer,configured));
        int id=await pipeline.ExecuteScalarAsync(cancellation) as int? ??
            await CreateSalesConversionPipelineAsync(db,tx,org,actor.Id,cancellation);
        assignment["mode"]="round_robin";
        assignment["ownerIds"]=JsonSerializer.SerializeToNode(owners);
        string patch=JsonSerializer.Serialize(new {salesProcess=new {enabled=true,pipelineId=id,managerId=manager},
            assignment,slaHours=24,staleDays=7});
        await WriteLeadSettingsPatchAsync(db,tx,org,actor.Id,revision,"Lead sales process setup",patch,before,patch,cancellation);
        tx.Commit();
        return id;
    }

    private static async Task<int> CreateSalesConversionPipelineAsync(NpgsqlConnection db,NpgsqlTransaction tx,int org,int actor,
        CancellationToken cancellation)
    {
        using var pipeline=Cmd(db,tx,@"INSERT INTO public.crm_pipelines
            (organization_id,name,description,active,is_default,created_by_user_id,updated_by_user_id)
            VALUES (@org,'Sales Conversion','Qualified opportunity through consultation, demo, proposal and closure',true,false,@actor,@actor)
            RETURNING id",("org",NpgsqlDbType.Integer,org),("actor",NpgsqlDbType.Integer,actor));
        int id=(int)(await pipeline.ExecuteScalarAsync(cancellation))!;
        using var stages=Cmd(db,tx,@"INSERT INTO public.crm_pipeline_stages
            (organization_id,pipeline_id,name,probability,position,order_index,stage_type,is_won,is_lost,active)
            SELECT @org,@id,name,probability,position,position,kind,kind='won',kind='lost',true FROM
             (VALUES ('Consultation Scheduled',25,0,'open'),('Demo Completed',45,1,'open'),('Proposal Sent',60,2,'open'),
                 ('Negotiation',80,3,'open'),('Won',100,4,'won'),('Lost',0,5,'lost')) AS stage(name,probability,position,kind)",
            ("org",NpgsqlDbType.Integer,org),("id",NpgsqlDbType.Integer,id));
        await stages.ExecuteNonQueryAsync(cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"pipelines",org,id,actor,"CREATE",cancellation,"Sales Conversion pipeline provisioned");
        return id;
    }

    private static async Task<(List<LeadSalesChoice> People,List<LeadSalesChoice> Managers)> SalesCandidatesAsync(
        NpgsqlConnection db,NpgsqlTransaction tx,DesktopDatabaseSettings settings,int[]? ids,CancellationToken cancellation)
    {
        var people=new List<LeadSalesChoice>();
        var managers=new List<LeadSalesChoice>();
        int branch=settings.BranchId ?? 0;
        var candidates=ids is null ? await LeadOwnerCandidatesAsync(db,tx,settings.OrganizationId,branch,null,false,cancellation) : [];
        if (ids is not null)
            foreach (int id in ids.OrderBy(id=>id))
                candidates.AddRange(await LeadOwnerCandidatesAsync(db,tx,settings.OrganizationId,branch,id,true,cancellation));
        foreach (var candidate in candidates)
        {
            try
            {
                await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,branch,candidate.Actor,"crm","view",
                    "crm_view","crm_manage","crm_admin","crm_leads_view","crm_leads_manage");
                people.Add(new(candidate.Actor.Id,candidate.Name));
            }
            catch(UnauthorizedAccessException) { continue; }
            try
            {
                var grant=await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,branch,candidate.Actor,"crm","assign",
                    "crm_view","crm_manage","crm_admin","crm_leads_view","crm_leads_manage");
                if (grant.IsLegacy && grant.LegacyRole is not ("admin" or "manager" or "super_admin"))
                    await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,branch,candidate.Actor,"crm","assign","crm_admin");
                managers.Add(new(candidate.Actor.Id,candidate.Name));
            }
            catch(UnauthorizedAccessException) { }
        }
        return (people,managers);
    }

    private static int[] ReadOwnerPool(JsonObject? assignment) =>
        assignment?["ownerIds"] is JsonArray pool ? pool.Select(owner=>owner?.GetValue<int>()??0).Where(id=>id>0).Distinct().ToArray() : [];

    private static async Task<(int? Owner,bool Deferred)> AssignNewLeadAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        DesktopDatabaseSettings settings,int branch,IReadOnlyDictionary<string,string> values,CancellationToken cancellation)
    {
        int org=settings.OrganizationId;
        using var config=Cmd(db,tx,@"SELECT settings_json::text FROM public.crm_lead_management_config
            WHERE organization_id=@org AND json_typeof(settings_json->'assignment')='object' FOR UPDATE",("org",NpgsqlDbType.Integer,org));
        if (await config.ExecuteScalarAsync(cancellation) is not string json) return (null,false);
        var document=JsonNode.Parse(json)?.AsObject() ?? throw new InvalidOperationException("The sales process configuration is invalid.");
        var assignment=document["assignment"]?.AsObject() ?? throw new InvalidOperationException("The sales assignment configuration is invalid.");
        var policies=(assignment["availability"] as JsonArray ?? new()).OfType<JsonObject>()
            .GroupBy(policy=>policy["ownerId"]?.GetValue<int>()??0).ToDictionary(group=>group.Key,group=>group.Last());
        var eligible=new Dictionary<int,bool>();
        bool deferred=false;
        if (assignment["rules"] is JsonArray rules)
            foreach (var rule in rules.OfType<JsonObject>())
            {
                string field=rule["field"]?.GetValue<string>()??"";
                if (field is not ("source" or "city" or "state" or "country" or "industry") ||
                    !values.TryGetValue(field,out string? value) || !string.Equals(value,rule["equals"]?.GetValue<string>(),
                        StringComparison.OrdinalIgnoreCase))
                    continue;
                int owner=rule["ownerId"]?.GetValue<int>()??0;
                if (await IsEligibleAsync(owner)) return (owner,false);
                deferred=true;
            }
        string mode=assignment["mode"]?.GetValue<string>()??"manual";
        if (mode=="manual") return (null,deferred);
        if (mode is not ("round_robin" or "workload"))
            throw new InvalidOperationException("The configured Lead routing mode is invalid.");
        var pool=ReadOwnerPool(assignment);
        var available=new List<int>();
        foreach (int id in pool)
            if (await IsEligibleAsync(id))
                available.Add(id);
        if (available.Count==0) return (null,deferred || pool.Length>0);
        if (mode=="workload")
        {
            using var workload=Cmd(db,tx,@"SELECT candidate.id FROM unnest(@owners) candidate(id)
                LEFT JOIN public.crm_leads l ON l.organization_id=@org AND l.owner_user_id=candidate.id
                    AND l.deleted_at IS NULL AND l.status NOT IN ('Converted','Lost')
                LEFT JOIN public.crm_lead_operating_states s ON s.organization_id=l.organization_id AND s.lead_id=l.id
                GROUP BY candidate.id
                ORDER BY count(l.id) FILTER (WHERE COALESCE(s.data_json->>'archived','false')<>'true'),candidate.id LIMIT 1",
                ("org",NpgsqlDbType.Integer,org),("owners",NpgsqlDbType.Array|NpgsqlDbType.Integer,available.ToArray()));
            return ((int)(await workload.ExecuteScalarAsync(cancellation))!,false);
        }
        long cursor=document["assignmentCursor"]?.GetValue<long>() ?? 0;
        if (cursor<0 || cursor==long.MaxValue)
            throw new InvalidOperationException("The sales assignment cursor is invalid.");
        using var update=Cmd(db,tx,@"UPDATE public.crm_lead_management_config SET
            settings_json=jsonb_set(settings_json::jsonb,'{assignmentCursor}',to_jsonb(@cursor))::json,
            updated_at=now() WHERE organization_id=@org",("org",NpgsqlDbType.Integer,org),
            ("cursor",NpgsqlDbType.Bigint,cursor+1));
        await update.ExecuteNonQueryAsync(cancellation);
        return (available[(int)(cursor%available.Count)],false);

        async Task<bool> IsEligibleAsync(int id)
        {
            if (id<=0) return false;
            if (eligible.TryGetValue(id,out bool known)) return known;
            var matches=await LeadOwnerCandidatesAsync(db,tx,org,branch,id,false,cancellation);
            bool allowed=matches.Count==1 && await CanReceiveRoutedLeadAsync(db,tx,org,branch,matches[0].Actor);
            if (allowed && policies.TryGetValue(id,out var policy))
                allowed=await SellerAvailableAsync(db,tx,org,id,policy,cancellation);
            eligible[id]=allowed;
            return allowed;
        }
    }

    private static async Task<bool> SellerAvailableAsync(NpgsqlConnection db,NpgsqlTransaction tx,int org,int owner,
        JsonObject policy,CancellationToken cancellation)
    {
        if (policy["enabled"]?.GetValue<bool>() is false) return false;
        string timezone=policy["timezone"]?.GetValue<string>()??"Asia/Kolkata";
        int[] days=policy["days"] is JsonArray configured?configured.Select(day=>day?.GetValue<int>()??-1).ToArray():[0,1,2,3,4,5,6];
        int start=policy["startMinute"]?.GetValue<int>()??0;
        int end=policy["endMinute"]?.GetValue<int>()??1440;
        int? capacity=policy["maxActiveLeads"]?.GetValue<int>();
        using var availability=Cmd(db,tx,@"WITH localized AS (
          SELECT statement_timestamp() AT TIME ZONE z.name AS local_now FROM pg_catalog.pg_timezone_names z WHERE z.name=@zone
        ), clock AS (
          SELECT extract(isodow FROM local_now)::int-1 AS day,
                 extract(hour FROM local_now)::int*60+extract(minute FROM local_now)::int AS minute FROM localized
        ) SELECT EXISTS(SELECT 1 FROM clock WHERE day=ANY(@days) AND minute>=@start AND minute<@end)
          AND (@capacity IS NULL OR (SELECT count(*) FROM public.crm_leads l
            LEFT JOIN public.crm_lead_operating_states s ON s.organization_id=l.organization_id AND s.lead_id=l.id
            WHERE l.organization_id=@org AND l.owner_user_id=@owner AND l.deleted_at IS NULL
                AND l.is_converted IS NOT TRUE AND l.status NOT IN ('Converted','Lost')
                AND COALESCE(s.data_json->>'archived','false')<>'true')<@capacity)",
            ("zone",NpgsqlDbType.Text,timezone),("days",NpgsqlDbType.Array|NpgsqlDbType.Integer,days),
            ("start",NpgsqlDbType.Integer,start),("end",NpgsqlDbType.Integer,end),("capacity",NpgsqlDbType.Integer,capacity),
            ("org",NpgsqlDbType.Integer,org),("owner",NpgsqlDbType.Integer,owner));
        return await availability.ExecuteScalarAsync(cancellation) is true;
    }
}
