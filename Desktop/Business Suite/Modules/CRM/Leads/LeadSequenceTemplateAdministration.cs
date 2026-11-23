using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadSequenceDirectory(string Revision,List<LeadSequenceTemplate> Templates,bool CanWrite);

internal static partial class LeadStore
{
    internal static async Task<LeadSequenceDirectory> SequenceDirectoryAsync(CancellationToken cancellation)
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
        using var query=Cmd(db,tx,"SELECT xmin::text FROM public.crm_lead_management_config WHERE organization_id=@org",
            ("org",NpgsqlDbType.Integer,settings.OrganizationId));
        string revision=await query.ExecuteScalarAsync(cancellation) as string??"";
        var templates=await ReadSequenceTemplatesAsync(db,tx,settings.OrganizationId,false,cancellation);
        return new(revision,templates,canWrite);
    }

    internal static async Task SaveSequenceDirectoryAsync(string revision,List<LeadSequenceTemplate> templates,
        CancellationToken cancellation)
    {
        var normalized=templates.Select(template=>new LeadSequenceTemplate(template.Name.Trim(),
            template.Steps.Select(step=>step with {Title=step.Title.Trim()}).ToList())).ToList();
        if (normalized.Count>30 || normalized.Any(t=>t.Name.Length is <1 or >120 || t.Steps.Count is <1 or >30 ||
            t.Steps.Any(s=>s.Day is <0 or >365 || s.Kind is not ("call" or "email" or "meeting" or "task") ||
                s.Title.Length is <1 or >180)))
            throw new ArgumentException("Use up to 30 named sequences with 1 to 30 valid steps each. Step delays must be between 0 and 365 days.");
        if (normalized.Select(template=>template.Name).Distinct(StringComparer.Ordinal).Count()!=normalized.Count)
            throw new ArgumentException("Sequence names must be unique.");
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireLeadSettingsAdminAsync(db,tx,settings,actor);
        int org=settings.OrganizationId;
        string? before=await LockLeadSettingsSectionAsync(db,tx,org,revision,"sequences",cancellation);
        string after=JsonSerializer.Serialize(normalized.Select(template=>new {
            name=template.Name,steps=template.Steps.Select(step=>new { day=step.Day,type=step.Kind,title=step.Title })
        }));
        await WriteLeadSettingsSectionAsync(db,tx,org,actor.Id,revision,"sequences","Lead sequence templates",before,after,cancellation);
        tx.Commit();
    }

    private static async Task<string?> LockLeadSettingsSectionAsync(NpgsqlConnection db,NpgsqlTransaction tx,int org,
        string revision,string section,CancellationToken cancellation)
    {
        using var read=Cmd(db,tx,@"SELECT xmin::text,settings_json->>@section
            FROM public.crm_lead_management_config WHERE organization_id=@org FOR UPDATE",
            ("org",NpgsqlDbType.Integer,org),("section",NpgsqlDbType.Text,section));
        string storedRevision="";
        string? before=null;
        using(var row=await read.ExecuteReaderAsync(cancellation))
            if (await row.ReadAsync(cancellation))
            {
                storedRevision=row.GetString(0);
                before=row.IsDBNull(1)?null:row.GetString(1);
            }
        if (storedRevision!=revision)
            throw new InvalidOperationException("The Lead settings changed. Refresh before saving.");
        return before;
    }

    private static async Task WriteLeadSettingsSectionAsync(NpgsqlConnection db,NpgsqlTransaction tx,int org,int actor,
        string revision,string section,string description,string? before,string after,CancellationToken cancellation)
    {
        using var value=JsonDocument.Parse(after);
        string patch=JsonSerializer.Serialize(new Dictionary<string,JsonElement> { [section]=value.RootElement });
        await WriteLeadSettingsPatchAsync(db,tx,org,actor,revision,description,patch,before,after,cancellation);
    }

    private static async Task WriteLeadSettingsPatchAsync(NpgsqlConnection db,NpgsqlTransaction tx,int org,int actor,
        string revision,string description,string patch,string? before,string after,CancellationToken cancellation)
    {
        string sql=revision.Length==0?@"INSERT INTO public.crm_lead_management_config (organization_id,settings_json,updated_by)
                VALUES (@org,@patch,@actor)
                ON CONFLICT (organization_id) DO NOTHING":
            @"UPDATE public.crm_lead_management_config SET
                settings_json=(COALESCE(settings_json::jsonb,'{}'::jsonb)||@patch::jsonb)::json,
                updated_by=@actor,updated_at=now() WHERE organization_id=@org AND xmin::text=@revision";
        using var save=Cmd(db,tx,sql,("org",NpgsqlDbType.Integer,org),("actor",NpgsqlDbType.Integer,actor),
            ("patch",NpgsqlDbType.Json,patch),("revision",NpgsqlDbType.Text,revision));
        if (await save.ExecuteNonQueryAsync(cancellation)!=1)
            throw new InvalidOperationException("The Lead settings changed. Refresh before saving.");
        using var audit=Cmd(db,tx,@"INSERT INTO public.audit_logs
            (organization_id,user_id,actor_authenticated,method,entity_type,entity_id,action,old_values,new_values,description,module)
            VALUES (@org,@actor,true,'CRM','crm_lead_management_config',@org,'UPDATE',@before,@after,@description,'crm')",
            ("org",NpgsqlDbType.Integer,org),("actor",NpgsqlDbType.Integer,actor),("before",NpgsqlDbType.Text,before),
            ("after",NpgsqlDbType.Text,after),("description",NpgsqlDbType.Text,description));
        await audit.ExecuteNonQueryAsync(cancellation);
    }

    private static async Task RequireLeadSettingsAdminAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopDatabaseSettings settings,
        DesktopActor actor)
    {
        CrmDirectoryWrites.RequireCrmAccess(actor);
        var grant=await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,settings.BranchId??0,actor,
            "crm","edit","crm_admin");
        if (grant.Scope!="organization")
            throw new UnauthorizedAccessException("Changing these settings requires company-wide CRM administration.");
    }
}
