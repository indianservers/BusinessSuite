using System.Data;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

internal sealed record WebformEdit(int Id, string Revision, string Name, string Slug, string Target,
    int Rule, bool Active, List<WebformFieldInput> Fields, List<WebformRuleOption> Rules);

internal sealed partial class CommunicationDraftRepository
{
    private const string EditableWebform = @"f.id=@id AND f.organization_id=@company
        AND f.xmin::text=@revision AND EXISTS (
            SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company AND b.branch_id=@branch
              AND b.resource_table='communication_webforms' AND b.resource_key=f.id::text)
        AND (@scope='organization' OR EXISTS (
            SELECT 1 FROM public.communication_timeline_events e WHERE e.organization_id=@company
              AND e.record_type='webform' AND e.record_id=f.id AND e.channel='webform'
              AND e.event_type='created' AND e.actor_user_id=@actor))";

    internal async Task<WebformEdit> EditWebformAsync(int id, string revision)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if (!actor.CanWriteBranch) throw new UnauthorizedAccessException("This branch is read-only.");
        string scope = await WebformEditScopeAsync(db, tx, branch, actor);
        using var command = Scoped("SELECT f.name,f.public_slug,f.target_module,coalesce(f.auto_response_rule_id,0),"
            + "f.fields_json::text,f.mapping_json::text,coalesce(f.active,false) FROM public.communication_webforms f WHERE " + EditableWebform,
            db, tx, branch, actor.Id);
        AddWebformEditParameters(command, id, revision, scope);
        string name, slug, target;
        int rule;
        bool active;
        List<WebformFieldInput> fields;
        using (var reader = await command.ExecuteReaderAsync())
        {
            if (!await reader.ReadAsync()) throw WebformChanged();
            name = reader.GetString(0);
            slug = reader.GetString(1);
            target = reader.GetString(2);
            rule = reader.GetInt32(3);
            active = reader.GetBoolean(6);
            fields = ReadEditableWebformFields(reader.IsDBNull(4) ? "null" : reader.GetString(4),
                reader.IsDBNull(5) ? "null" : reader.GetString(5));
        }
        try { ValidateWebform(name, slug, target, fields); }
        catch (ArgumentException) { throw UnsupportedWebformEdit(); }
        var rules = new List<WebformRuleOption> { new(0, "No automatic response") };
        using (var rulesCommand = WebformRulesCommand(db, tx, branch, actor.Id, scope, 0))
        using (var reader = await rulesCommand.ExecuteReaderAsync())
            while (await reader.ReadAsync()) rules.Add(new(reader.GetInt32(0), reader.GetString(1)));
        if (!rules.Any(option => option.Id == rule)) rules.Add(new(rule, $"Keep existing rule #{rule}"));
        return new(id, revision, name, slug, target, rule, active, fields, rules);
    }

    internal async Task UpdateWebformAsync(WebformEdit original, string name, string slug, string target, int rule,
        IReadOnlyList<WebformFieldInput> fields)
    {
        ValidateWebform(name, slug, target, fields);
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        string scope = await WebformEditScopeAsync(db, tx, branch, actor);
        if (rule != 0 && rule != original.Rule)
        {
            using var check = WebformRulesCommand(db, tx, branch, actor.Id, scope, rule);
            if (await check.ExecuteScalarAsync() is null)
                throw new InvalidOperationException("The selected acknowledgement rule is unavailable in this branch.");
        }
        using var command = Scoped(@"WITH changed AS (
            UPDATE public.communication_webforms f SET name=@name,public_slug=@slug,target_module=@target,
                auto_response_rule_id=NULLIF(@rule,0),fields_json=CAST(@fields AS json),mapping_json=CAST(@mapping AS json)
            WHERE " + EditableWebform + @" AND coalesce(f.auto_response_rule_id,0)=@previousRule AND coalesce(f.active,false)=@active
            RETURNING f.id
          ), timeline AS (
            INSERT INTO public.communication_timeline_events(organization_id,record_type,record_id,channel,event_type,subject,summary,actor_user_id)
            SELECT @company,'webform',id,'webform','updated',@name,'Webform updated',@actor FROM changed
          ), audit AS (
            INSERT INTO public.suite_branch_audit(company_id,actor_id,operation,reason,details)
            SELECT @company,@actor,'communication.webform','update',
                json_build_object('branch_id',@branch,'webform_id',id,'active',@active,'rule_id',NULLIF(@rule,0)) FROM changed
          ) SELECT id FROM changed", db, tx, branch, actor.Id);
        AddWebformEditParameters(command, original.Id, original.Revision, scope);
        command.Parameters.AddWithValue("previousRule", original.Rule);
        command.Parameters.AddWithValue("active", original.Active);
        command.Parameters.AddWithValue("name", name.Trim());
        command.Parameters.AddWithValue("slug", slug);
        command.Parameters.AddWithValue("target", target);
        command.Parameters.AddWithValue("rule", rule);
        command.Parameters.AddWithValue("fields", JsonSerializer.Serialize(fields.Select(f => new {
            key=f.Key,label=f.Label.Trim(),type=f.Type,required=f.Required })));
        command.Parameters.AddWithValue("mapping", JsonSerializer.Serialize(fields.ToDictionary(f => f.Target, f => f.Key)));
        try
        {
            if (await command.ExecuteScalarAsync() is null) throw WebformChanged();
            tx.Commit();
        }
        catch (PostgresException error) when (error.SqlState == PostgresErrorCodes.UniqueViolation &&
            error.ConstraintName == "uq_communication_webform_slug")
        {
            throw new InvalidOperationException("This public slug is already in use.", error);
        }
        catch (PostgresException error) when (error.SqlState == PostgresErrorCodes.SerializationFailure)
        {
            throw new InvalidOperationException(WebformChanged().Message, error);
        }
    }

    internal async Task ActivateWebformAsync(int id, string revision)
    {
        // Reuse the field validator before exposing a form to the connected public endpoint.
        var original = await EditWebformAsync(id, revision);
        if (original.Active) throw WebformChanged();
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        string scope = await WebformEditScopeAsync(db, tx, branch, actor);
        if (original.Rule != 0)
        {
            using var check = WebformRulesCommand(db, tx, branch, actor.Id, scope, original.Rule);
            if (await check.ExecuteScalarAsync() is null)
                throw new InvalidOperationException("An active acknowledgement rule is required when a rule is attached.");
        }
        using var command = Scoped(@"WITH changed AS (
            UPDATE public.communication_webforms f SET active=true
            WHERE " + EditableWebform + @" AND coalesce(f.active,false)=false
            RETURNING f.id,f.name,f.auto_response_rule_id
          ), timeline AS (
            INSERT INTO public.communication_timeline_events(organization_id,record_type,record_id,channel,event_type,subject,summary,actor_user_id)
            SELECT @company,'webform',id,'webform','activated',name,'Webform activated',@actor FROM changed
          ), audit AS (
            INSERT INTO public.suite_branch_audit(company_id,actor_id,operation,reason,details)
            SELECT @company,@actor,'communication.webform','activate',
                json_build_object('branch_id',@branch,'webform_id',id,'active',true,'rule_id',auto_response_rule_id) FROM changed
          ) SELECT id FROM changed", db, tx, branch, actor.Id);
        AddWebformEditParameters(command, original.Id, original.Revision, scope);
        try
        {
            if (await command.ExecuteScalarAsync() is null) throw WebformChanged();
            tx.Commit();
        }
        catch (PostgresException error) when (error.SqlState == PostgresErrorCodes.SerializationFailure)
        {
            throw new InvalidOperationException(WebformChanged().Message, error);
        }
    }

    private async Task<string> WebformEditScopeAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor)
    {
        var view = await AutoResponseGrantAsync(db, tx, branch, actor, "view");
        var edit = await AutoResponseGrantAsync(db, tx, branch, actor, "edit");
        return view.Scope == "own" || edit.Scope == "own" ? "own" : "organization";
    }

    private static void AddWebformEditParameters(NpgsqlCommand command, int id, string revision, string scope)
    {
        command.Parameters.AddWithValue("id", id);
        command.Parameters.AddWithValue("revision", revision);
        command.Parameters.AddWithValue("scope", scope);
    }

    private static List<WebformFieldInput> ReadEditableWebformFields(string fields, string mappings)
    {
        using var fieldsDocument = JsonDocument.Parse(fields);
        using var mappingsDocument = JsonDocument.Parse(mappings);
        if (fieldsDocument.RootElement.ValueKind != JsonValueKind.Array ||
            mappingsDocument.RootElement.ValueKind != JsonValueKind.Object) throw UnsupportedWebformEdit();
        foreach (var field in fieldsDocument.RootElement.EnumerateArray())
        {
            if (field.ValueKind != JsonValueKind.Object || field.EnumerateObject().Count() != 4 ||
                field.EnumerateObject().Select(property => property.Name).Distinct(StringComparer.Ordinal).Count() != 4 ||
                field.EnumerateObject().Any(property => property.Name switch
                {
                    "key" or "label" or "type" => property.Value.ValueKind != JsonValueKind.String,
                    "required" => property.Value.ValueKind is not (JsonValueKind.True or JsonValueKind.False),
                    _ => true
                })) throw UnsupportedWebformEdit();
        }
        var known = ReadWebformFields(fields, mappings);
        if (mappingsDocument.RootElement.EnumerateObject().Count() != known.Count)
            throw UnsupportedWebformEdit();
        return known.Select(f => new WebformFieldInput {
            Key=f.Key, Label=f.Label, Type=f.Type, Target=f.Mapping, Required=f.Required }).ToList();
    }

    private static InvalidOperationException UnsupportedWebformEdit() =>
        new("This form contains configuration that this editor cannot preserve. You can view its saved details.");

    private static InvalidOperationException WebformChanged() =>
        new("The webform is no longer available or has changed. Refresh and reopen it.");
}
