using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadStageDirectory(string Revision,LeadPolicy Policy,bool CanWrite);

internal static partial class LeadStore
{
    private static readonly string[] SystemLeadStages=["New","Contacted","Qualified","Converted","Lost"];
    private static readonly HashSet<string> LeadStageFieldKeys=new(StringComparer.Ordinal)
    {
        "full_name","email","phone","phone_country_code","company_name","job_title","source","status","estimated_value",
        "next_follow_up_at","city","state","country","industry","notes","need","budget","decision_maker","purchase_timeline",
        "loss_reason","competitor","archived","archive_reason","review_at","decisionMaker","timeline","lossReason"
    };

    internal static async Task<LeadStageDirectory> StageDirectoryAsync(CancellationToken cancellation)
    {
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await CrmDirectoryWrites.RequireCrmActorAsync(settings,db,tx,cancellation,"leads");
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
        using var revision=Cmd(db,tx,"SELECT xmin::text FROM public.crm_lead_management_config WHERE organization_id=@org",
            ("org",NpgsqlDbType.Integer,settings.OrganizationId));
        string stamp=await revision.ExecuteScalarAsync(cancellation) as string??"";
        return new(stamp,await ReadPolicy(db,tx,settings.OrganizationId,cancellation),canWrite);
    }

    internal static async Task SaveLeadStageDirectoryAsync(string revision,LeadStage[] stages,bool preventDuplicates,
        CancellationToken cancellation,int? slaHours=null,int? staleDays=null)
    {
        var normalized=stages.Select(stage=>stage with {Name=stage.Name.Trim()}).ToArray();
        var names=new HashSet<string>(normalized.Select(stage=>stage.Name),StringComparer.Ordinal);
        if (normalized.Length is <5 or >25 || names.Count!=normalized.Length || !SystemLeadStages.All(names.Contains) ||
            normalized.Any(stage=>stage.Name.Length is <1 or >40))
            throw new ArgumentException("Keep the five system stages and use up to 25 unique names of 40 characters or fewer.");
        if (normalized.Any(stage=>stage.AllowedNext.Length>25||stage.AllowedNext.Any(next=>!names.Contains(next))||
            stage.Required.Length>20||stage.Required.Any(field=>!LeadStageFieldKeys.Contains(field))))
            throw new ArgumentException("Stages contain an unknown transition or required field.");
        if (slaHours is <1 or >8760 || staleDays is <1 or >365)
            throw new ArgumentException("Enter 1 to 8,760 hours for first response and 1 to 365 days for inactivity.");
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireLeadSettingsAdminAsync(db,tx,settings,actor);
        int org=settings.OrganizationId;
        await LockLeadSettingsSectionAsync(db,tx,org,revision,"stages",cancellation);
        var current=await ReadPolicy(db,tx,org,cancellation);
        if (current.Stages.Any(stage=>!names.Contains(stage.Name)))
            throw new InvalidOperationException("Keep existing Lead stages when updating their settings.");
        string before=EncodeLeadStages(current.Stages,current.PreventDuplicates,current.SlaHours,current.StaleDays);
        string after=EncodeLeadStages(normalized,preventDuplicates,slaHours??current.SlaHours,staleDays??current.StaleDays);
        using var snapshot=JsonDocument.Parse(after);
        var updates=snapshot.RootElement.EnumerateObject().Where(value=>
            (value.Name!="slaHours"||slaHours.HasValue)&&(value.Name!="staleDays"||staleDays.HasValue))
            .ToDictionary(value=>value.Name,value=>value.Value);
        await WriteLeadSettingsPatchAsync(db,tx,org,actor.Id,revision,"Lead stage settings",JsonSerializer.Serialize(updates),
            before,after,cancellation);
        tx.Commit();
    }

    private static string EncodeLeadStages(LeadStage[] stages,bool preventDuplicates,int slaHours,int staleDays) => JsonSerializer.Serialize(new {
        stages=stages.Select(stage=>new {name=stage.Name,allowedNext=stage.AllowedNext,required=stage.Required}),
        preventDuplicates,slaHours,staleDays
    });
}
