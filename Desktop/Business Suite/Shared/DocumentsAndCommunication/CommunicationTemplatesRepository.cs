using System.Data;
using System.Net;
using System.Text.RegularExpressions;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record EmailTemplateRow(int Id, string Name, string Subject, string Module, bool Active, DateTime? Updated)
{
    public bool Favorite { get; init; }
}
internal sealed record EmailTemplateEdit(EmailTemplateRow Row, string Body, string Revision);
internal sealed record EmailTemplateList(List<EmailTemplateRow> Rows, bool Create, bool Edit, bool Disable);
internal sealed record EmailTemplateEvent(DateTime? Recorded, string Action, string Subject, string Summary);

internal sealed class CommunicationTemplatesRepository
{
    private readonly DesktopDatabaseSettings settings;

    internal CommunicationTemplatesRepository(DesktopDatabaseSettings settings) => this.settings = settings;

    private const string VisibleTemplate = @"
        WHERE coalesce(t.organization_id, 1) = @company AND coalesce(t.template_type, 'email') = 'email'
          AND EXISTS (
              SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id = @company AND b.branch_id = @branch
                  AND b.resource_table = 'communication_email_templates' AND b.resource_key = t.id::text
          )
          AND (
              @scope = 'organization'
              OR (@scope IN ('own','team') AND t.created_by = @actor)
              OR (@scope IN ('branch','department','team') AND EXISTS (
                  SELECT 1 FROM public.employees member
                  JOIN public.employees actor ON actor.user_id = @actor AND actor.deleted_at IS NULL
                  WHERE member.user_id = t.created_by AND member.deleted_at IS NULL AND member.branch_id = @branch
                    AND ((@scope='branch' AND member.branch_id=actor.branch_id)
                      OR (@scope='department' AND member.department_id=actor.department_id)
                      OR (@scope='team' AND member.reporting_manager_id=actor.id))
              ))
          )";
    private const string ListFields = @"SELECT t.id, t.name, t.subject, t.module_name, coalesce(t.active, false),
                                      coalesce(t.updated_at, t.created_at)";

    internal async Task<EmailTemplateList> ListAsync(string search, bool includeDisabled) =>
        await ListAsync(search, includeDisabled, null, false);

    internal async Task<EmailTemplateList> ListAsync(string search, bool includeDisabled, HashSet<int>? favorites, bool favoritesOnly)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await SetReadOnlyAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        var grant = await GrantAsync(db, tx, branch, actor, "view");
        using var query = ScopedCommand(ListFields + " FROM public.communication_email_templates t" + VisibleTemplate + @"
            AND (@disabled OR coalesce(t.active, false))
            AND (NOT @favoritesOnly OR t.id = ANY(@favorites))
            AND (@search = '' OR strpos(lower(t.name), lower(@search)) > 0
                              OR strpos(lower(t.subject), lower(@search)) > 0)
            ORDER BY t.id DESC LIMIT 200", db, tx, branch, actor, grant);
        query.Parameters.AddWithValue("search", NpgsqlDbType.Text, search);
        query.Parameters.AddWithValue("disabled", NpgsqlDbType.Boolean, includeDisabled);
        query.Parameters.AddWithValue("favoritesOnly", NpgsqlDbType.Boolean, favoritesOnly);
        query.Parameters.AddWithValue("favorites", NpgsqlDbType.Array | NpgsqlDbType.Integer,
            favoritesOnly && favorites is not null ? favorites.ToArray() : Array.Empty<int>());
        var rows = new List<EmailTemplateRow>();
        using (var reader = await query.ExecuteReaderAsync())
            while (await reader.ReadAsync())
            {
                var row = ReadRow(reader);
                rows.Add(row with { Favorite = favorites?.Contains(row.Id) == true });
            }
        bool create = actor.CanWriteBranch && await CanAsync(db, tx, branch, actor, "create");
        bool edit = actor.CanWriteBranch && await CanAsync(db, tx, branch, actor, "edit");
        bool disable = actor.CanWriteBranch && await CanAsync(db, tx, branch, actor, "delete");
        tx.Commit();
        return new EmailTemplateList(rows, create, edit, disable);
    }

    internal async Task<EmailTemplateEdit> OpenAsync(int templateId)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await SetReadOnlyAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        var grant = await GrantAsync(db, tx, branch, actor, "view");
        var result = await ReadTemplateAsync(db, tx, branch, actor, grant, templateId);
        tx.Commit();
        return result;
    }

    internal async Task<EmailTemplateEdit> ReadCampaignTemplateAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        DesktopActor actor, int branch, int templateId)
    {
        var grant = await GrantAsync(db, tx, branch, actor, "view");
        return await ReadTemplateAsync(db, tx, branch, actor, grant, templateId);
    }

    internal async Task VerifyCampaignTemplateAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        DesktopActor actor, int branch, int templateId)
    {
        var template = await ReadCampaignTemplateAsync(db, tx, actor, branch, templateId);
        if (!template.Row.Active)
            throw new InvalidOperationException("Choose an active email template.");
    }

    internal async Task<List<EmailTemplateEvent>> TimelineAsync(int templateId)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await SetReadOnlyAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        var grant = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor,
            "communication", "view", "communication_view", "communication_email_send");
        await ReadTemplateAsync(db, tx, branch, actor, grant, templateId);
        using var query = ScopedCommand(@"
            SELECT a.created_at, a.event_type, coalesce(a.subject, ''), coalesce(a.summary, '')
            FROM public.communication_timeline_events a
            WHERE coalesce(a.organization_id, 1) = @company AND a.record_type='template' AND a.record_id=@id
              AND a.channel='email' AND (@scope='organization' OR a.actor_user_id=@actor)
              AND EXISTS (
                  SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company AND b.branch_id=@branch
                    AND b.resource_table='communication_timeline_events' AND b.resource_key=a.id::text
              )
            ORDER BY a.created_at DESC NULLS LAST, a.id DESC LIMIT 200", db, tx, branch, actor, grant);
        query.Parameters.AddWithValue("id", NpgsqlDbType.Integer, templateId);
        var rows = new List<EmailTemplateEvent>();
        using (var reader = await query.ExecuteReaderAsync())
            while (await reader.ReadAsync())
                rows.Add(new EmailTemplateEvent(reader.IsDBNull(0) ? null : reader.GetDateTime(0).ToLocalTime(),
                    reader.GetString(1), reader.GetString(2), reader.GetString(3)));
        tx.Commit();
        return rows;
    }

    internal Task<int> SaveAsync(EmailTemplateEdit? original, string name, string subject, string body)
    {
        name = name.Trim();
        subject = subject.Trim();
        if (name.Length is < 2 or > 180)
            throw new ArgumentException("Enter a template name of 2 to 180 characters.");
        if (subject.Length is 0 or > 240)
            throw new ArgumentException("Enter a subject of up to 240 characters.");
        if (body.Length > 20000)
            throw new ArgumentException("Keep the template content within 20,000 characters.");
        return WriteAsync(original, name, subject, body, disable: false);
    }

    internal Task<int> DisableAsync(EmailTemplateEdit original) =>
        WriteAsync(original, original.Row.Name, original.Row.Subject, original.Body, disable: true);

    private async Task<int> WriteAsync(EmailTemplateEdit? original, string name, string subject, string body, bool disable)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        var actor = await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        string action = original is null ? "create" : disable ? "delete" : "edit";
        var grant = await GrantAsync(db, tx, branch, actor, action);
        int id;
        string timeline;
        if (original is null)
        {
            if (grant.Scope == "assigned")
                throw Unavailable();
            using var create = ScopedCommand(@"
                INSERT INTO public.communication_email_templates
                    (organization_id,name,subject,body_text,body_html,module_name,template_type,active,created_by)
                SELECT @company,@name,@subject,@body,@html,'lead','email',true,@actor
                WHERE @scope IN ('organization','own','team') OR EXISTS (
                    SELECT 1 FROM public.employees e WHERE e.user_id=@actor AND e.deleted_at IS NULL
                      AND e.branch_id=@branch AND (@scope='branch' OR (@scope='department' AND e.department_id IS NOT NULL))
                )
                RETURNING id", db, tx, branch, actor, grant);
            BindDraft(create, name, subject, body);
            id = await create.ExecuteScalarAsync() is int createdId ? createdId : throw Unavailable();
            await OwnAsync(db, tx, branch, "communication_email_templates", id);
            timeline = "created";
        }
        else
        {
            var current = await ReadTemplateAsync(db, tx, branch, actor, grant, original.Row.Id, forUpdate: true);
            if (current.Revision != original.Revision)
                throw new InvalidOperationException("This email template changed. Refresh before continuing.");
            if (disable && !current.Row.Active)
                throw new InvalidOperationException("This email template is already disabled.");
            bool bodyChanged = !StringComparer.Ordinal.Equals(NormalizeLines(original.Body), NormalizeLines(body));
            using var update = ScopedCommand(@"
                UPDATE public.communication_email_templates t SET name=@name, subject=@subject,
                       body_text=CASE WHEN @replace_body THEN @body ELSE t.body_text END,
                       body_html=CASE WHEN @replace_body THEN @html ELSE t.body_html END,
                       active=NOT @disable, updated_at=now()" + VisibleTemplate + " AND t.id=@id",
                db, tx, branch, actor, grant);
            BindDraft(update, name, subject, body);
            update.Parameters.AddWithValue("replace_body", NpgsqlDbType.Boolean, bodyChanged);
            update.Parameters.AddWithValue("disable", NpgsqlDbType.Boolean, disable);
            update.Parameters.AddWithValue("id", NpgsqlDbType.Integer, current.Row.Id);
            if (await update.ExecuteNonQueryAsync() != 1)
                throw Unavailable();
            id = current.Row.Id;
            timeline = disable ? "disabled" : "updated";
        }

        using var audit = ScopedCommand(@"
            INSERT INTO public.communication_timeline_events
                (organization_id,record_type,record_id,channel,event_type,subject,summary,actor_user_id)
            VALUES (@company,'template',@id,'email',@event,@subject,@summary,@actor)
            RETURNING id", db, tx, branch, actor, grant);
        audit.Parameters.AddWithValue("id", NpgsqlDbType.Integer, id);
        audit.Parameters.AddWithValue("event", NpgsqlDbType.Text, timeline);
        audit.Parameters.AddWithValue("subject", NpgsqlDbType.Text, subject);
        audit.Parameters.AddWithValue("summary", NpgsqlDbType.Text, $"Template {name} {timeline}");
        await OwnAsync(db, tx, branch, "communication_timeline_events", (int)(await audit.ExecuteScalarAsync())!);
        tx.Commit();
        return id;
    }

    private async Task<EmailTemplateEdit> ReadTemplateAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        DesktopActor actor, DesktopModuleGrant grant, int id, bool forUpdate = false)
    {
        string sql = ListFields + ", coalesce(t.body_text, ''), t.body_html, t.xmin::text" +
                     " FROM public.communication_email_templates t" + VisibleTemplate + " AND t.id=@id";
        using var query = ScopedCommand(forUpdate ? sql + " FOR UPDATE OF t" : sql, db, tx, branch, actor, grant);
        query.Parameters.AddWithValue("id", NpgsqlDbType.Integer, id);
        using var reader = await query.ExecuteReaderAsync();
        if (!await reader.ReadAsync())
            throw Unavailable();
        string body = reader.GetString(6);
        if (body.Length == 0 && !reader.IsDBNull(7))
        {
            string breaks = Regex.Replace(reader.GetString(7), @"(?i)<br\s*/?>|</(?:p|div|li|tr)>", "\n");
            body = WebUtility.HtmlDecode(Regex.Replace(breaks, "<[^>]*>", "")).Trim();
        }
        return new EmailTemplateEdit(ReadRow(reader), body, reader.GetString(8));
    }

    private static void BindDraft(NpgsqlCommand command, string name, string subject, string body)
    {
        command.Parameters.AddWithValue("name", NpgsqlDbType.Text, name);
        command.Parameters.AddWithValue("subject", NpgsqlDbType.Text, subject);
        command.Parameters.AddWithValue("body", NpgsqlDbType.Text, body);
        string html = "<!--suite-richtext:v1--><p>" +
            WebUtility.HtmlEncode(NormalizeLines(body)).Replace("\n", "<br>") + "</p>";
        command.Parameters.AddWithValue("html", NpgsqlDbType.Text, html);
    }

    private static string NormalizeLines(string body) => body.Replace("\r\n", "\n").Replace("\r", "\n");

    private NpgsqlCommand ScopedCommand(string sql, NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        DesktopActor actor, DesktopModuleGrant grant)
    {
        var command = new NpgsqlCommand(sql, db, tx);
        command.Parameters.AddWithValue("company", NpgsqlDbType.Integer, settings.OrganizationId);
        command.Parameters.AddWithValue("branch", NpgsqlDbType.Integer, branch);
        command.Parameters.AddWithValue("actor", NpgsqlDbType.Integer, actor.Id);
        command.Parameters.AddWithValue("scope", NpgsqlDbType.Text, grant.Scope);
        return command;
    }

    private async Task OwnAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, string table, int id)
    {
        using var command = new NpgsqlCommand(@"
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            VALUES (@table,@key,@company,@branch,'validated-write')", db, tx);
        command.Parameters.AddWithValue("table", NpgsqlDbType.Text, table);
        command.Parameters.AddWithValue("key", NpgsqlDbType.Text, id.ToString(System.Globalization.CultureInfo.InvariantCulture));
        command.Parameters.AddWithValue("company", NpgsqlDbType.Integer, settings.OrganizationId);
        command.Parameters.AddWithValue("branch", NpgsqlDbType.Integer, branch);
        await command.ExecuteNonQueryAsync();
    }

    private static async Task SetReadOnlyAsync(NpgsqlConnection db, NpgsqlTransaction tx)
    {
        using var command = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx);
        await command.ExecuteNonQueryAsync();
    }

    private Task<DesktopModuleGrant> GrantAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor, string action)
    {
        string[] permissions = action == "view" ? new[] { "communication_view", "communication_templates_manage" }
            : new[] { "communication_templates_manage" };
        return DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor, "communication", action, permissions);
    }

    private async Task<bool> CanAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor, string action)
    {
        try
        {
            return (await GrantAsync(db, tx, branch, actor, action)).Scope != "assigned";
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    private int RequireBranch() => settings.BranchId ??
        throw new UnauthorizedAccessException("Select a branch to work with communication templates.");

    private static EmailTemplateRow ReadRow(NpgsqlDataReader reader) =>
        new EmailTemplateRow(reader.GetInt32(0), reader.GetString(1), reader.GetString(2), reader.GetString(3),
            reader.GetBoolean(4), reader.IsDBNull(5) ? null : reader.GetDateTime(5).ToLocalTime());

    private static InvalidOperationException Unavailable() =>
        new InvalidOperationException("This email template is unavailable in the selected branch.");
}
