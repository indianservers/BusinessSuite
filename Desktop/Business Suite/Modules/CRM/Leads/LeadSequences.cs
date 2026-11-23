using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadSequenceStep(int Day,string Kind,string Title);
internal sealed record LeadSequenceTemplate(string Name,List<LeadSequenceStep> Steps);
internal sealed record LeadSequenceOptions(List<LeadSequenceTemplate> Templates,string Current,bool Active,bool CanStart);

internal static partial class LeadStore
{
    internal static async Task<LeadSequenceOptions> SequenceOptionsAsync(LeadKey key,CancellationToken cancellation)
    {
        if (key.Potential)
            throw new InvalidOperationException("Choose a Lead to manage its sequence.");
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        await CrmDirectoryWrites.RequireCrmActorAsync(settings,db,tx,cancellation,"leads","edit");
        var lead=await LockLead(db,tx,settings,key,false,cancellation,lockRecord:false);
        var details=ReadDetails(lead);
        details.TryGetValue("sequence",out var sequence);
        bool active=Nested(sequence,"active") is JsonElement state&&state.ValueKind==JsonValueKind.True;
        string current=Nested(sequence,"name")?.ToString()??"";
        string reason=Nested(sequence,"stopReason")?.ToString()??"";
        string summary=current.Length==0?"No sequence recorded.":active?$"{current} · Active":
            $"{current} · Stopped"+(reason.Length>0?$" ({reason})":"");
        return new(await ReadSequenceTemplatesAsync(db,tx,settings.OrganizationId,false,cancellation),
            summary,active,IsOpenForSequence(lead));
    }

    internal static async Task ChangeLeadSequenceAsync(LeadKey key,string? template,CancellationToken cancellation)
    {
        if (key.Potential)
            throw new InvalidOperationException("Choose a Lead to manage its sequence.");
        if (template is not null && (template.Length is <1 or >120))
            throw new ArgumentException("Choose a configured sequence.");
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"leads","edit");
        var lead=await LockLead(db,tx,settings,key,false,cancellation);
        int org=settings.OrganizationId;
        int branch=await LeadOwnerBranchAsync(db,tx,settings,key.Id,lead,cancellation);
        var scope=settings.ForScope(org,branch);
        var details=ReadDetails(lead);
        DateTime now=DateTime.UtcNow;
        DateTime? next=null;
        if (template is not null)
        {
            if (!IsOpenForSequence(lead))
                throw new InvalidOperationException("Reactivate this Lead before starting a sequence.");
            var templates=await ReadSequenceTemplatesAsync(db,tx,org,true,cancellation);
            var selected=templates.FirstOrDefault(rule=>rule.Name==template) ??
                throw new InvalidOperationException("The chosen sequence is no longer configured. Refresh and choose again.");
            await CancelActiveSequenceAsync(db,tx,scope,key.Id,details,actor.Id,now,"Replaced",cancellation);
            string sequenceId=Guid.NewGuid().ToString();
            details["sequence"]=new { id=sequenceId,name=template,active=true,startedAt=now };
            next=now.AddDays(selected.Steps.Min(step=>step.Day));
            string metadata=JsonSerializer.Serialize(new {sequenceId,sequence=template});
            foreach (var step in selected.Steps)
                await AddLeadPendingTaskAsync(db,tx,scope,key.Id,lead,actor.Id,step.Title,metadata,
                    now.AddDays(step.Day),cancellation,step.Kind);
        }
        else
        {
            details.TryGetValue("sequence",out var current);
            if (Nested(current,"active") is not JsonElement state || state.ValueKind!=JsonValueKind.True)
                throw new InvalidOperationException("This Lead has no active sequence.");
            await CancelActiveSequenceAsync(db,tx,scope,key.Id,details,actor.Id,now,"Stopped",cancellation);
        }
        await WriteState(db,tx,org,key.Id,details,key.StateRevision,cancellation);
        if (next.HasValue)
        {
            using var stamp=Cmd(db,tx,@"UPDATE public.crm_leads SET next_follow_up_at=@next,updated_by_user_id=@actor,updated_at=now()
                WHERE organization_id=@org AND id=@lead",
                ("org",NpgsqlDbType.Integer,org),("lead",NpgsqlDbType.Integer,key.Id),("actor",NpgsqlDbType.Integer,actor.Id),
                ("next",NpgsqlDbType.TimestampTz,next));
            await stamp.ExecuteNonQueryAsync(cancellation);
        }
        string title=template is null?"Sequence stopped":"Started "+template;
        await AddLeadHistoryAsync(db,tx,org,key.Id,branch,actor.Id,"sequence",title,null,"{}",cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"crm_leads",org,key.Id,actor.Id,"UPDATE",cancellation,title);
        tx.Commit();
    }

    private static bool IsOpenForSequence(DataRow lead) =>
        lead["is_converted"] is not true && lead["status"] is not ("Lost" or "Converted");

    private static async Task<List<LeadSequenceTemplate>> ReadSequenceTemplatesAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        int org,bool lockConfiguration,CancellationToken cancellation)
    {
        using var query=Cmd(db,tx,@"SELECT settings_json->'sequences' FROM public.crm_lead_management_config
            WHERE organization_id=@org"+(lockConfiguration?" FOR SHARE":""),
            ("org",NpgsqlDbType.Integer,org));
        if (await query.ExecuteScalarAsync(cancellation) is not string json)
            return [new("Standard follow-up",[
                new(0,"call","Introduce yourself and qualify the enquiry"),
                new(2,"email","Send a tailored follow-up"),
                new(5,"call","Confirm next steps")])];
        using var definitions=JsonDocument.Parse(json);
        var result=new List<LeadSequenceTemplate>();
        if (definitions.RootElement.ValueKind!=JsonValueKind.Array || definitions.RootElement.GetArrayLength()>30)
            throw new InvalidOperationException("The configured Lead sequences could not be read.");
        foreach (var template in definitions.RootElement.EnumerateArray())
        {
            if (template.ValueKind!=JsonValueKind.Object || !template.TryGetProperty("steps",out var steps) ||
                steps.ValueKind!=JsonValueKind.Array || steps.GetArrayLength() is <1 or >30 ||
                WorkflowText(template,"name").Length is <1 or >120)
                throw new InvalidOperationException("A configured Lead sequence has invalid settings.");
            var items=new List<LeadSequenceStep>();
            foreach (var step in steps.EnumerateArray())
            {
                if (step.ValueKind!=JsonValueKind.Object || !step.TryGetProperty("day",out var offset) ||
                    offset.ValueKind!=JsonValueKind.Number || !offset.TryGetInt32(out int day) || day is <0 or >365)
                    throw new InvalidOperationException("A configured Lead sequence has an invalid step delay.");
                string kind=WorkflowText(step,"type");
                string title=WorkflowText(step,"title");
                if (kind is not ("call" or "email" or "task" or "meeting") || title.Length is <1 or >180)
                    throw new InvalidOperationException("A configured Lead sequence has an invalid step type or title.");
                items.Add(new(day,kind,title));
            }
            result.Add(new(WorkflowText(template,"name"),items));
        }
        return result;
    }
}
