using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadResponseDraft(string Name,string Stage,string Action,string Title,int Delay,int? Owner,bool Enabled,
    string Trigger="responded");
internal sealed record LeadResponseDirectory(string Revision,List<LeadResponseDraft> Rules,List<string> Stages,List<CrmLookup> Owners,bool CanWrite);

internal static partial class LeadStore
{
    internal static async Task<LeadResponseDirectory> ResponseWorkflowDirectoryAsync(CancellationToken cancellation)
    {
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await CrmDirectoryWrites.RequireCrmActorAsync(settings,db,tx,cancellation,"leads");
        int org=settings.OrganizationId;
        bool canWrite=false;
        if (actor.CanWriteBranch)
        {
            try
            {
                await RequireLeadSettingsAdminAsync(db,tx,settings,actor);
                canWrite=true;
            }
            catch(UnauthorizedAccessException) { }
        }
        using var query=Cmd(db,tx,@"SELECT xmin::text,settings_json->>'workflows' FROM public.crm_lead_management_config
            WHERE organization_id=@org",("org",NpgsqlDbType.Integer,org));
        string revision="";
        string? workflows=null;
        using(var row=await query.ExecuteReaderAsync(cancellation))
            if (await row.ReadAsync(cancellation))
            {
                revision=row.GetString(0);
                workflows=row.IsDBNull(1)?null:row.GetString(1);
            }
        var rules=DecodeWorkflowList(workflows).Where(IsEditableWorkflowRule).Select(rule=>new LeadResponseDraft(
            WorkflowText(rule,"name"),WorkflowText(rule,"stage"),WorkflowText(rule,"action"),WorkflowText(rule,"title"),
            WorkflowInteger(rule,"delayHours")??0,WorkflowInteger(rule,"ownerId"),
            !rule.TryGetProperty("enabled",out var enabled)||enabled.ValueKind!=JsonValueKind.False,WorkflowText(rule,"trigger"))).ToList();
        var policy=await ReadPolicy(db,tx,org,cancellation);
        var owners=canWrite?await ResponseWorkflowOwnersAsync(db,tx,org,cancellation):new List<CrmLookup>();
        foreach(int ownerId in rules.Where(rule=>rule.Owner.HasValue).Select(rule=>rule.Owner!.Value).Distinct())
            if (!owners.Any(owner=>owner.Id==ownerId))
                owners.Add(new(ownerId,"User "+ownerId+" (unavailable)"));
        return new(revision,rules,policy.Stages.Select(stage=>stage.Name).ToList(),owners,canWrite);
    }

    internal static async Task SaveResponseWorkflowDirectoryAsync(string revision,List<LeadResponseDraft> rules,
        CancellationToken cancellation)
    {
        var normalized=rules.Select(rule=>rule with {Name=rule.Name.Trim(),Title=rule.Title.Trim()}).ToList();
        if (normalized.Count>100 || normalized.Any(rule=>rule.Name.Length is <1 or >120 || rule.Title.Length is <1 or >180 ||
            rule.Trigger is not ("created" or "stage_changed" or "responded") ||
            rule.Delay is <0 or >8760 || rule.Action is not ("task" or "notify" or "assign") ||
            (rule.Action=="assign" && (rule.Owner is not int owner || owner<=0))))
            throw new ArgumentException("Enter each rule's name, title, valid action, delay and assignment owner where required.");
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireLeadSettingsAdminAsync(db,tx,settings,actor);
        int org=settings.OrganizationId;
        string? prior=await LockLeadSettingsSectionAsync(db,tx,org,revision,"workflows",cancellation);
        var existing=DecodeWorkflowList(prior);
        var stages=(await ReadPolicy(db,tx,org,cancellation)).Stages.Select(stage=>stage.Name).ToHashSet(StringComparer.Ordinal);
        if (normalized.Any(rule=>rule.Stage.Length>0&&!stages.Contains(rule.Stage)))
            throw new ArgumentException("Choose a current Lead stage or leave the stage empty.");
        var assignments=normalized.Where(rule=>rule.Action=="assign").Select(rule=>rule.Owner!.Value).Distinct().ToArray();
        if (assignments.Length>0)
        {
            var owners=await ResponseWorkflowOwnersAsync(db,tx,org,cancellation);
            if (assignments.Any(owner=>!owners.Any(option=>option.Id==owner)))
                throw new InvalidOperationException("Choose active assignment owners with CRM access in this company.");
        }
        var remaining=new Queue<object>(normalized.Select(rule=>(object)new {
            name=rule.Name,enabled=rule.Enabled,trigger=rule.Trigger,stage=rule.Stage,action=rule.Action,title=rule.Title,
            delayHours=rule.Delay,ownerId=rule.Action=="assign"?rule.Owner:null
        }));
        var merged=new List<object>();
        foreach(var rule in existing)
        {
            if (!IsEditableWorkflowRule(rule))
                merged.Add(rule);
            else if (remaining.Count>0)
                merged.Add(remaining.Dequeue());
        }
        merged.AddRange(remaining);
        if (merged.Count>100)
            throw new ArgumentException("A company can configure at most 100 Lead workflow rules.");
        string after=JsonSerializer.Serialize(merged);
        await WriteLeadSettingsSectionAsync(db,tx,org,actor.Id,revision,"workflows","Lead workflows",prior,after,cancellation);
        tx.Commit();
    }

    private static List<JsonElement> DecodeWorkflowList(string? json)
    {
        using var document=JsonDocument.Parse(json??"[]");
        if (document.RootElement.ValueKind!=JsonValueKind.Array)
            throw new InvalidOperationException("The configured Lead workflows could not be read.");
        return document.RootElement.EnumerateArray().Select(rule=>rule.Clone()).ToList();
    }

    private static bool IsEditableWorkflowRule(JsonElement rule) =>
        rule.ValueKind==JsonValueKind.Object&&WorkflowText(rule,"trigger") is ("created" or "stage_changed" or "responded");

    private static int? WorkflowInteger(JsonElement rule,string field) =>
        rule.TryGetProperty(field,out var value)&&value.ValueKind==JsonValueKind.Number&&value.TryGetInt32(out int number)?number:null;

    private static async Task<List<CrmLookup>> ResponseWorkflowOwnersAsync(NpgsqlConnection db,NpgsqlTransaction tx,int org,
        CancellationToken cancellation)
    {
        var branches=new List<int>();
        using(var query=Cmd(db,tx,@"SELECT b.id FROM public.branches b WHERE b.company_id=@org AND b.is_active
            AND NOT EXISTS (SELECT 1 FROM public.suite_branch_lifecycle life WHERE life.branch_id=b.id AND life.deleted_at IS NOT NULL)
            ORDER BY b.id",("org",NpgsqlDbType.Integer,org)))
        using(var rows=await query.ExecuteReaderAsync(cancellation))
            while(await rows.ReadAsync(cancellation))
                branches.Add(rows.GetInt32(0));
        var available=new Dictionary<int,CrmLookup>();
        foreach(int branch in branches)
            foreach(var candidate in await LeadOwnerCandidatesAsync(db,tx,org,branch,null,false,cancellation))
            {
                cancellation.ThrowIfCancellationRequested();
                if (available.ContainsKey(candidate.Actor.Id))
                    continue;
                try
                {
                    await DesktopModuleAccess.RequireAsync(db,tx,org,branch,candidate.Actor,"crm","view",
                        "crm_view","crm_manage","crm_admin","crm_leads_view","crm_leads_manage");
                    available.Add(candidate.Actor.Id,new(candidate.Actor.Id,candidate.Name));
                }
                catch(UnauthorizedAccessException) { }
            }
        return available.Values.OrderBy(owner=>owner.Name,StringComparer.CurrentCultureIgnoreCase).ToList();
    }
}
