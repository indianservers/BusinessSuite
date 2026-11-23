using System.Text.Json;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadRouteRule(string Field,string EqualsValue,int OwnerId);
internal sealed record LeadRoutingSettings(string Revision,string Mode,int[] OwnerIds,List<LeadRouteRule> Rules,List<LeadSalesChoice> People,List<LeadSellerAvailability> Availability);

internal static partial class LeadStore
{
    internal static readonly string[] NativeLeadRoutingFields=["source","city","state","country","industry"];

    internal static async Task<LeadRoutingSettings> ReadLeadRoutingSettingsAsync(CancellationToken cancellation)
    {
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(System.Data.IsolationLevel.RepeatableRead);
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        await RequireLeadSettingsAdminAsync(db,tx,settings,actor);
        var candidates=await LeadOwnerCandidatesAsync(db,tx,settings.OrganizationId,settings.BranchId??0,null,false,cancellation);
        var people=new List<LeadSalesChoice>();
        foreach (var candidate in candidates)
            if (await CanReceiveRoutedLeadAsync(db,tx,settings.OrganizationId,settings.BranchId??0,candidate.Actor))
                people.Add(new(candidate.Actor.Id,candidate.Name));
        using var read=Cmd(db,tx,@"SELECT xmin::text,settings_json->>'assignment'
            FROM public.crm_lead_management_config WHERE organization_id=@org",
            ("org",NpgsqlDbType.Integer,settings.OrganizationId));
        using var row=await read.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation)) return new("","manual",[],[],people,[]);
        var assignment=row.IsDBNull(1)?new JsonObject():JsonNode.Parse(row.GetString(1))?.AsObject()??new();
        return new(row.GetString(0),assignment["mode"]?.GetValue<string>()??"manual",ReadOwnerPool(assignment),
            ReadRoutingRules(assignment),people,ReadSellerAvailability(assignment));
    }

    internal static async Task SaveLeadRoutingSettingsAsync(string revision,string mode,int[] pool,List<LeadRouteRule> rules,
        CancellationToken cancellation,IReadOnlyList<LeadSellerAvailability>? availability=null)
    {
        if (mode is not ("manual" or "round_robin" or "workload") || pool.Length>100 || rules.Count>100 ||
            pool.Any(id=>id<=0) || rules.Any(rule=>rule.OwnerId<=0 || rule.EqualsValue.Trim().Length is <1 or >180))
            throw new ArgumentException("Choose a routing mode and use up to 100 eligible owners and rules with a match value.");
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireLeadSettingsAdminAsync(db,tx,settings,actor);
        int org=settings.OrganizationId,branch=settings.BranchId??0;
        string? before=await LockLeadSettingsSectionAsync(db,tx,org,revision,"assignment",cancellation);
        var assignment=before is null?new JsonObject():JsonNode.Parse(before)?.AsObject()??new();
        var previous=ReadRoutingRules(assignment);
        if (rules.Any(rule=>!NativeLeadRoutingFields.Contains(rule.Field) && !previous.Contains(rule)))
            throw new ArgumentException("Choose a supported match field for new or changed rules.");
        var ids=pool.Concat(rules.Select(rule=>rule.OwnerId)).Distinct().ToHashSet();
        if (availability is not null)
        {
            await ValidateSellerAvailabilityAsync(db,tx,ids,availability,cancellation);
            assignment["availability"]=JsonSerializer.SerializeToNode(availability.Select(policy=>new {
                ownerId=policy.OwnerId,enabled=policy.Enabled,timezone=policy.Timezone,days=policy.Days,
                startMinute=policy.StartMinute,endMinute=policy.EndMinute,maxActiveLeads=policy.MaxActiveLeads}));
        }
        if (assignment["availability"] is JsonArray available && available.OfType<JsonObject>()
            .Any(policy=>!ids.Contains(policy["ownerId"]?.GetValue<int>()??0)))
            throw new InvalidOperationException("Keep owners with an existing availability policy in the pool or on a rule.");
        foreach (int id in ids.OrderBy(id=>id))
        {
            var candidates=await LeadOwnerCandidatesAsync(db,tx,org,branch,id,true,cancellation);
            if (candidates.Count!=1 || !await CanReceiveRoutedLeadAsync(db,tx,org,branch,candidates[0].Actor))
                throw new InvalidOperationException("A configured routing owner is unavailable in the selected company and branch.");
        }
        assignment["mode"]=mode;
        assignment["ownerIds"]=JsonSerializer.SerializeToNode(pool.Distinct().ToArray());
        assignment["rules"]=JsonSerializer.SerializeToNode(rules.Select(rule=>new {
            field=rule.Field,equals=NativeLeadRoutingFields.Contains(rule.Field)?rule.EqualsValue.Trim():rule.EqualsValue,ownerId=rule.OwnerId}));
        await WriteLeadSettingsSectionAsync(db,tx,org,actor.Id,revision,"assignment","Lead routing settings",
            before,assignment.ToJsonString(),cancellation);
        tx.Commit();
    }

    private static List<LeadRouteRule> ReadRoutingRules(JsonObject assignment) => assignment["rules"] is JsonArray rules
        ? rules.OfType<JsonObject>().Select(rule=>new LeadRouteRule(rule["field"]?.GetValue<string>()??"",
            rule["equals"]?.GetValue<string>()??"",rule["ownerId"]?.GetValue<int>()??0)).ToList() : [];

    private static async Task<bool> CanReceiveRoutedLeadAsync(NpgsqlConnection db,NpgsqlTransaction tx,int org,int branch,DesktopActor actor)
    {
        try
        {
            var grant=await DesktopModuleAccess.RequireAsync(db,tx,org,branch,actor,"crm","view",
                "crm_view","crm_manage","crm_admin","crm_leads_view","crm_leads_manage");
            return grant.Scope is "organization" or "branch" or "own" or "assigned";
        }
        catch (UnauthorizedAccessException) { return false; }
    }
}
