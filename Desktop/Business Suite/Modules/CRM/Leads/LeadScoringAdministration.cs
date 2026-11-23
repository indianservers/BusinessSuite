using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadScoringRuleKey(int Id,string Revision);
internal sealed record LeadScoringDraft(string Name,string Field,string Operator,string Value,int Points,bool Active);
internal sealed record LeadScoringDirectory(DataTable Rows,bool CanCreate,bool CanEdit,bool CanArchive);

internal static partial class LeadStore
{
    internal static async Task<LeadScoringDirectory> ScoringDirectoryAsync(CancellationToken cancellation)
    {
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        await RequireScoringRuleAccessAsync(db,tx,settings,actor,"view");
        bool create=await Allowed("create");
        bool edit=await Allowed("edit");
        bool archive=await Allowed("delete");
        int org=settings.OrganizationId;
        if (create&&actor.CanWriteBranch)
        {
            using var existing=Cmd(db,tx,@"SELECT EXISTS (
                SELECT 1 FROM public.crm_lead_scoring_rules WHERE organization_id=@org)",("org",NpgsqlDbType.Integer,org));
            if (await existing.ExecuteScalarAsync(cancellation) is false)
            {
                var writer=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
                await RequireScoringRuleAccessAsync(db,tx,settings,writer,"create");
                await ReadLeadScoringRulesAsync(db,tx,org,writer.Id,cancellation);
            }
        }
        using var query=Cmd(db,tx,@"SELECT id,xmin::text AS revision,name,field,operator,COALESCE(value,'') AS value,
            points,COALESCE(is_active,false) AS active FROM public.crm_lead_scoring_rules
            WHERE organization_id=@org AND deleted_at IS NULL ORDER BY id",("org",NpgsqlDbType.Integer,org));
        DataTable rows;
        using (var reader=await query.ExecuteReaderAsync(cancellation))
            rows=await Table(reader,cancellation);
        tx.Commit();
        return new(rows,create,edit,archive);

        async Task<bool> Allowed(string action)
        {
            if (!actor.CanWriteBranch)
                return false;
            try
            {
                await RequireScoringRuleAccessAsync(db,tx,settings,actor,action);
                return true;
            }
            catch(UnauthorizedAccessException) { return false; }
        }
    }

    internal static async Task<int> SaveLeadScoringRuleAsync(LeadScoringRuleKey? key,LeadScoringDraft draft,
        CancellationToken cancellation)
    {
        draft=draft with { Name=draft.Name.Trim(),Field=draft.Field.Trim(),Operator=draft.Operator.Trim().ToLowerInvariant() };
        if (draft.Name.Length is <1 or >160 || draft.Field.Length is <1 or >100 || draft.Value.Length>240 ||
            draft.Operator is not ("exists" or "has_value" or "not_exists" or "empty" or "equals" or "eq" or "is" or
                "not_equals" or "neq" or "contains" or "gt" or "gte" or "lt" or "lte" or "older_than_days"))
            throw new ArgumentException("Enter a rule name, field and supported operator within the field limits.");
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireScoringRuleAccessAsync(db,tx,settings,actor,key is null?"create":"edit");
        int org=settings.OrganizationId;
        string? before=key is null?null:await LockScoringRuleAsync(db,tx,org,key,cancellation);
        string sql=key is null?@"INSERT INTO public.crm_lead_scoring_rules
                (organization_id,name,field,operator,value,points,is_active,created_by_user_id,updated_by_user_id)
            VALUES (@org,@name,@field,@operator,@value,@points,@active,@actor,@actor)
            RETURNING id,to_jsonb(crm_lead_scoring_rules)::text AS snapshot":
            @"UPDATE public.crm_lead_scoring_rules SET name=@name,field=@field,operator=@operator,value=@value,
                points=@points,is_active=@active,updated_by_user_id=@actor,updated_at=now()
            WHERE organization_id=@org AND id=@id RETURNING id,to_jsonb(crm_lead_scoring_rules)::text AS snapshot";
        using var save=Cmd(db,tx,sql,("org",NpgsqlDbType.Integer,org),("id",NpgsqlDbType.Integer,key?.Id),
            ("name",NpgsqlDbType.Text,draft.Name),("field",NpgsqlDbType.Text,draft.Field),("operator",NpgsqlDbType.Text,draft.Operator),
            ("value",NpgsqlDbType.Text,draft.Value),("points",NpgsqlDbType.Integer,draft.Points),("active",NpgsqlDbType.Boolean,draft.Active),
            ("actor",NpgsqlDbType.Integer,actor.Id));
        int id;
        string after;
        try
        {
            using var rows=await save.ExecuteReaderAsync(cancellation);
            if (!await rows.ReadAsync(cancellation))
                throw new InvalidOperationException("This scoring rule changed. Refresh and try again.");
            id=rows.GetInt32(0);
            after=rows.GetString(1);
        }
        catch(PostgresException error) when(error.SqlState==PostgresErrorCodes.UniqueViolation)
        {
            throw new InvalidOperationException("This scoring rule name is already used in the company.");
        }
        await AuditScoringRuleAsync(db,tx,org,id,actor.Id,key is null?"CREATE":"UPDATE",before,after,cancellation);
        tx.Commit();
        return id;
    }

    internal static async Task ArchiveLeadScoringRuleAsync(LeadScoringRuleKey key,CancellationToken cancellation)
    {
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireScoringRuleAccessAsync(db,tx,settings,actor,"delete");
        int org=settings.OrganizationId;
        string before=await LockScoringRuleAsync(db,tx,org,key,cancellation);
        using var archive=Cmd(db,tx,@"UPDATE public.crm_lead_scoring_rules SET is_active=false,deleted_at=now(),
            updated_at=now(),updated_by_user_id=@actor WHERE organization_id=@org AND id=@id
            RETURNING to_jsonb(crm_lead_scoring_rules)::text",
            ("org",NpgsqlDbType.Integer,org),("id",NpgsqlDbType.Integer,key.Id),("actor",NpgsqlDbType.Integer,actor.Id));
        if (await archive.ExecuteScalarAsync(cancellation) is not string after)
            throw new InvalidOperationException("This scoring rule changed. Refresh and try again.");
        await AuditScoringRuleAsync(db,tx,org,key.Id,actor.Id,"DELETE",before,after,cancellation);
        tx.Commit();
    }

    private static async Task<string> LockScoringRuleAsync(NpgsqlConnection db,NpgsqlTransaction tx,int org,
        LeadScoringRuleKey key,CancellationToken cancellation)
    {
        using var query=Cmd(db,tx,@"SELECT to_jsonb(r)::text FROM public.crm_lead_scoring_rules r
            WHERE r.organization_id=@org AND r.id=@id AND r.deleted_at IS NULL AND r.xmin::text=@revision FOR UPDATE OF r",
            ("org",NpgsqlDbType.Integer,org),("id",NpgsqlDbType.Integer,key.Id),("revision",NpgsqlDbType.Text,key.Revision));
        return await query.ExecuteScalarAsync(cancellation) as string ??
            throw new InvalidOperationException("This scoring rule changed. Refresh and try again.");
    }

    private static async Task RequireScoringRuleAccessAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        DesktopDatabaseSettings settings,DesktopActor actor,string action)
    {
        string[] permissions=action=="view"?["crm_view","crm_manage","crm_admin"]:["crm_manage","crm_admin"];
        var grant=await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,settings.BranchId??0,actor,
            "crm",action,permissions);
        if (action=="view")
            return;
        CrmDirectoryWrites.RequireCrmAccess(actor);
        if (grant.Scope!="organization")
            throw new UnauthorizedAccessException("Changing scoring rules requires company-wide CRM management access.");
    }

    private static async Task AuditScoringRuleAsync(NpgsqlConnection db,NpgsqlTransaction tx,int org,int id,int actor,
        string action,string? before,string after,CancellationToken cancellation)
    {
        using var query=Cmd(db,tx,@"INSERT INTO public.audit_logs
            (organization_id,user_id,actor_authenticated,method,entity_type,entity_id,action,old_values,new_values,description,module)
            VALUES (@org,@actor,true,'CRM','crm_lead_scoring_rules',@id,@action,@before,@after,'Business Suite Desktop','crm')",
            ("org",NpgsqlDbType.Integer,org),("id",NpgsqlDbType.Integer,id),("actor",NpgsqlDbType.Integer,actor),
            ("action",NpgsqlDbType.Text,action),("before",NpgsqlDbType.Text,before),("after",NpgsqlDbType.Text,after));
        await query.ExecuteNonQueryAsync(cancellation);
    }
}
