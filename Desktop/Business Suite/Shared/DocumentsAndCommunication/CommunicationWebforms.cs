using System.Data;
using System.Text.Json;
using System.Text.RegularExpressions;
using Npgsql;

namespace Business_Suite;

internal sealed record WebformRow(int Id, string Name, string Slug, string Target, bool Active, int? Rule, string Revision, bool CanDeactivate, bool CanEdit);
internal sealed record WebformRuleOption(int Id, string Name);
internal sealed record WebformLibrary(List<WebformRow> Forms, List<WebformRuleOption> Rules, bool CanCreate);

internal sealed class WebformFieldInput
{
    public string Key { get; set; } = "";
    public string Label { get; set; } = "";
    public string Type { get; set; } = "text";
    public string Target { get; set; } = "message";
    public bool Required { get; set; }
}

internal sealed partial class CommunicationDraftRepository
{
    internal async Task<WebformLibrary> WebformsAsync(string search)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        var grant = await AutoResponseGrantAsync(db, tx, branch, actor, "view");
        string deleteScope = "";
        string editScope = "";
        if (actor.CanWriteBranch)
        {
            try { editScope = (await AutoResponseGrantAsync(db, tx, branch, actor, "edit")).Scope; }
            catch (UnauthorizedAccessException) { }
            try { deleteScope = (await AutoResponseGrantAsync(db, tx, branch, actor, "delete")).Scope; }
            catch (UnauthorizedAccessException) { }
        }
        var forms = new List<WebformRow>();
        using (var command = Scoped(@"SELECT f.id,f.name,f.public_slug,f.target_module,coalesce(f.active,false),f.auto_response_rule_id,f.xmin::text,
                (@deleteScope='organization' OR (@deleteScope='own' AND creator.owns_form)),
                (@editScope='organization' OR (@editScope='own' AND creator.owns_form))
            FROM public.communication_webforms f
            CROSS JOIN LATERAL (SELECT EXISTS (
                SELECT 1 FROM public.communication_timeline_events e WHERE e.organization_id=@company
                  AND e.record_type='webform' AND e.record_id=f.id AND e.channel='webform'
                  AND e.event_type='created' AND e.actor_user_id=@actor) AS owns_form) creator
            WHERE f.organization_id=@company AND EXISTS (
                SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company AND b.branch_id=@branch
                AND b.resource_table='communication_webforms' AND b.resource_key=f.id::text)
              AND (@scope='organization' OR creator.owns_form)
              AND (@search='' OR strpos(lower(f.name),lower(@search))>0 OR strpos(lower(f.public_slug),lower(@search))>0)
            ORDER BY f.id DESC LIMIT 200", db, tx, branch, actor.Id))
        {
            command.Parameters.AddWithValue("scope", grant.Scope);
            command.Parameters.AddWithValue("search", search.Trim());
            command.Parameters.AddWithValue("deleteScope", deleteScope);
            command.Parameters.AddWithValue("editScope", editScope);
            using var reader = await command.ExecuteReaderAsync();
            while (await reader.ReadAsync())
                forms.Add(new(reader.GetInt32(0),reader.GetString(1),reader.GetString(2),reader.GetString(3),
                    reader.GetBoolean(4),reader.IsDBNull(5) ? null : reader.GetInt32(5),reader.GetString(6),reader.GetBoolean(7),reader.GetBoolean(8)));
        }
        var rules = new List<WebformRuleOption> { new(0, "No automatic response") };
        bool canCreate = false;
        if (actor.CanWriteBranch)
        {
            DesktopModuleGrant? create = null;
            try { create = await AutoResponseGrantAsync(db, tx, branch, actor, "create"); }
            catch (UnauthorizedAccessException) { }
            if (create is not null)
            {
                canCreate = true;
                using var command = WebformRulesCommand(db, tx, branch, actor.Id,
                    create.Scope == "own" || grant.Scope == "own" ? "own" : "organization", 0);
                using var reader = await command.ExecuteReaderAsync();
                while (await reader.ReadAsync()) rules.Add(new(reader.GetInt32(0),reader.GetString(1)));
            }
        }
        return new(forms,rules,canCreate);
    }

    internal static void ValidateWebform(string name, string slug, string target, IReadOnlyList<WebformFieldInput> fields)
    {
        if (name.Trim().Length is < 2 or > 180 || name.Any(char.IsControl) ||
            !Regex.IsMatch(slug, @"\A[a-z0-9][a-z0-9-]{2,139}\z") || target is not ("lead" or "contact"))
            throw new ArgumentException("Enter a name, a lowercase public slug and a CRM target.");
        if (fields.Count == 0) throw new ArgumentException("Add at least one customer field.");
        var keys = new HashSet<string>(StringComparer.Ordinal);
        var mappings = new HashSet<string>(StringComparer.Ordinal);
        foreach (var field in fields)
        {
            if (!Regex.IsMatch(field.Key, @"\A[a-zA-Z][a-zA-Z0-9_]{0,119}\z") ||
                field.Label.Trim().Length is < 1 or > 160 || field.Label.Any(char.IsControl) ||
                field.Type is not ("text" or "email" or "tel" or "textarea") ||
                field.Target is not ("first_name" or "last_name" or "email" or "phone" or "company_name" or "message"))
                throw new ArgumentException("Check the label, key, input type and CRM mapping on every field.");
            if (!keys.Add(field.Key) || !mappings.Add(field.Target))
                throw new ArgumentException("Each field key and CRM mapping must be unique.");
        }
    }

    internal async Task<int> CreateWebformAsync(string name, string slug, string target, int rule,
        IReadOnlyList<WebformFieldInput> fields)
    {
        ValidateWebform(name, slug, target, fields);
        string fieldJson = JsonSerializer.Serialize(fields.Select(f => new {
            key=f.Key,label=f.Label.Trim(),type=f.Type,required=f.Required }));
        string mappingJson = JsonSerializer.Serialize(fields.ToDictionary(f => f.Target, f => f.Key));
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        var grant = await AutoResponseGrantAsync(db, tx, branch, actor, "create");
        if (rule != 0)
        {
            var view = await AutoResponseGrantAsync(db, tx, branch, actor, "view");
            using var verify = WebformRulesCommand(db, tx, branch, actor.Id,
                grant.Scope == "own" || view.Scope == "own" ? "own" : "organization", rule);
            if (await verify.ExecuteScalarAsync() is null)
                throw new InvalidOperationException("The selected acknowledgement rule is unavailable in this branch.");
        }
        using var command = Scoped(@"WITH created AS (
            INSERT INTO public.communication_webforms(organization_id,name,target_module,public_slug,fields_json,mapping_json,active,auto_response_rule_id)
            VALUES(@company,@name,@target,@slug,CAST(@fields AS json),CAST(@mapping AS json),false,NULLIF(@rule,0))
            ON CONFLICT(public_slug) DO NOTHING RETURNING id
          ), own AS (
            INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
            SELECT 'communication_webforms',id::text,@company,@branch,'desktop' FROM created
          ), timeline AS (
            INSERT INTO public.communication_timeline_events(organization_id,record_type,record_id,channel,event_type,subject,summary,actor_user_id)
            SELECT @company,'webform',id,'webform','created',@name,'Webform created',@actor FROM created
          ), audit AS (
            INSERT INTO public.suite_branch_audit(company_id,actor_id,operation,reason,details)
            SELECT @company,@actor,'communication.webform','create',
                json_build_object('branch_id',@branch,'webform_id',id,'active',false,'rule_id',NULLIF(@rule,0)) FROM created
          ) SELECT id FROM created", db, tx, branch, actor.Id);
        command.Parameters.AddWithValue("name", name.Trim());
        command.Parameters.AddWithValue("slug", slug);
        command.Parameters.AddWithValue("target", target);
        command.Parameters.AddWithValue("rule", rule);
        command.Parameters.AddWithValue("fields", fieldJson);
        command.Parameters.AddWithValue("mapping", mappingJson);
        int id;
        try
        {
            id = (int)(await command.ExecuteScalarAsync() ?? throw new InvalidOperationException("This public slug is already in use."));
        }
        catch (PostgresException error) when (error.SqlState == PostgresErrorCodes.SerializationFailure)
        {
            throw new InvalidOperationException("The configuration changed while saving. Refresh and try again.", error);
        }
        tx.Commit();
        return id;
    }

    internal async Task DeactivateWebformAsync(int id, string revision)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        var actor = await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        var grant = await AutoResponseGrantAsync(db, tx, branch, actor, "delete");
        var view = await AutoResponseGrantAsync(db, tx, branch, actor, "view");
        using var command = Scoped(@"WITH changed AS (
            UPDATE public.communication_webforms f SET active=false
            WHERE f.id=@id AND f.organization_id=@company AND f.active AND f.xmin::text=@revision
              AND EXISTS (SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company AND b.branch_id=@branch
                AND b.resource_table='communication_webforms' AND b.resource_key=f.id::text)
              AND (@scope='organization' OR EXISTS (
                SELECT 1 FROM public.communication_timeline_events e WHERE e.organization_id=@company
                  AND e.record_type='webform' AND e.record_id=f.id AND e.channel='webform'
                  AND e.event_type='created' AND e.actor_user_id=@actor))
            RETURNING f.id,f.name
          ), timeline AS (
            INSERT INTO public.communication_timeline_events(organization_id,record_type,record_id,channel,event_type,subject,summary,actor_user_id)
            SELECT @company,'webform',id,'webform','deactivated',name,'Webform deactivated',@actor FROM changed
          ), audit AS (
            INSERT INTO public.suite_branch_audit(company_id,actor_id,operation,reason,details)
            SELECT @company,@actor,'communication.webform','deactivate',
                json_build_object('branch_id',@branch,'webform_id',id,'active',false) FROM changed
          ) SELECT id FROM changed", db, tx, branch, actor.Id);
        command.Parameters.AddWithValue("id", id);
        command.Parameters.AddWithValue("revision", revision);
        command.Parameters.AddWithValue("scope", grant.Scope == "own" || view.Scope == "own" ? "own" : "organization");
        if (await command.ExecuteScalarAsync() is null)
            throw new InvalidOperationException("The webform is no longer available or has changed. Refresh and try again.");
        tx.Commit();
    }

    private NpgsqlCommand WebformRulesCommand(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        int actor, string scope, int rule)
    {
        var command = Scoped(@"SELECT r.id,r.name FROM public.communication_auto_response_rules r
            WHERE r.organization_id=@company AND r.active AND r.trigger_type='webform_submission'
              AND (@rule=0 OR r.id=@rule) AND (@scope='organization' OR r.created_by=@actor)
              AND EXISTS (SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company
                AND b.branch_id=@branch AND b.resource_table='communication_auto_response_rules' AND b.resource_key=r.id::text)
            ORDER BY r.name,r.id", db, tx, branch, actor);
        command.Parameters.AddWithValue("scope", scope);
        command.Parameters.AddWithValue("rule", rule);
        return command;
    }
}
