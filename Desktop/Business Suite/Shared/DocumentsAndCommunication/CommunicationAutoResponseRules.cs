using System.Data;
using Npgsql;

namespace Business_Suite;

internal sealed record AutoResponseRuleRow(int Id, string Name, string Trigger, string Template, bool Active);
internal sealed record AutoResponseRuleList(List<AutoResponseRuleRow> Rows, bool CanCreate);
internal sealed record AutoResponseRuleInput(string Name, int Template, bool Active);

internal sealed partial class CommunicationDraftRepository
{
    internal async Task<AutoResponseRuleList> AutoResponseRulesAsync(string search)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        var grant = await AutoResponseGrantAsync(db, tx, branch, actor, "view");
        var rows = new List<AutoResponseRuleRow>();
        using (var command = Scoped(@"SELECT r.id,r.name,coalesce(r.trigger_type,''),
              r.template_id,coalesce(r.active,false)
            FROM public.communication_auto_response_rules r
            WHERE r.organization_id=@company AND (@scope='organization' OR r.created_by=@actor)
              AND (@search='' OR strpos(lower(r.name),lower(@search))>0)
              AND EXISTS (SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company AND b.branch_id=@branch
                    AND b.resource_table='communication_auto_response_rules' AND b.resource_key=r.id::text)
            ORDER BY r.id DESC LIMIT 200", db, tx, branch, actor.Id))
        {
            command.Parameters.AddWithValue("scope", grant.Scope);
            command.Parameters.AddWithValue("search", search.Trim());
            using var reader = await command.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                string trigger = reader.GetString(2);
                rows.Add(new(reader.GetInt32(0), reader.GetString(1),
                    trigger == "webform_submission" ? "Webform submission" : trigger,
                    reader.IsDBNull(3) ? "" : $"#{reader.GetInt32(3)}", reader.GetBoolean(4)));
            }
        }
        bool canCreate = false;
        if (actor.CanWriteBranch)
        {
            try { await AutoResponseGrantAsync(db, tx, branch, actor, "create"); canCreate = true; }
            catch (UnauthorizedAccessException) { }
        }
        return new(rows, canCreate);
    }

    internal async Task<int> CreateAutoResponseRuleAsync(AutoResponseRuleInput input)
    {
        string name = input.Name.Trim();
        if (name.Length is < 2 or > 180 || name.Any(char.IsControl) || input.Template <= 0)
            throw new ArgumentException("Enter a rule name of 2 to 180 characters and choose an active email template.");
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await AutoResponseGrantAsync(db, tx, branch, actor, "create");
        await new CommunicationTemplatesRepository(settings).VerifyCampaignTemplateAsync(db, tx, actor, branch, input.Template);
        using var command = Scoped(@"WITH created AS (
            INSERT INTO public.communication_auto_response_rules(organization_id,name,trigger_type,template_id,active,condition_json,created_by)
            VALUES(@company,@name,'webform_submission',@template,@active,'{}'::json,@actor) RETURNING id
          ), own AS (
            INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
            SELECT 'communication_auto_response_rules',id::text,@company,@branch,'desktop' FROM created
          ), audit AS (
            INSERT INTO public.suite_branch_audit(company_id,actor_id,operation,reason,details)
            SELECT @company,@actor,'communication.auto_response_rule','create',
                json_build_object('branch_id',@branch,'rule_id',id,'template_id',@template,'active',@active) FROM created
          ) SELECT id FROM created", db, tx, branch, actor.Id);
        command.Parameters.AddWithValue("name", name);
        command.Parameters.AddWithValue("template", input.Template);
        command.Parameters.AddWithValue("active", input.Active);
        int id = (int)(await command.ExecuteScalarAsync() ?? throw new InvalidOperationException("The rule could not be saved."));
        tx.Commit();
        return id;
    }

    private async Task<DesktopModuleGrant> AutoResponseGrantAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, DesktopActor actor, string action)
    {
        string[] permissions = action == "view" ? ["communication_view", "communication_webforms_manage"] : ["communication_webforms_manage"];
        var grant = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor, "communication", action, permissions);
        if (grant.Scope is not ("organization" or "own"))
            throw new UnauthorizedAccessException("The rule library requires organization or own-record access.");
        return grant;
    }
}
