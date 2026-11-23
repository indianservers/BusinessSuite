using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record CampaignInput(string Name, int Template, string Source, string SegmentStatus, int Limit);
internal sealed record EmailCampaign(int Id, string Revision, string Name, int? Template, string State, string Source,
    string SegmentStatus, int Limit);
internal sealed record CampaignList(List<EmailCampaign> Rows, bool Create, bool Edit);
internal sealed record CampaignAudienceRow(int Id, string Name, string Email, string Outcome);
internal sealed record CampaignAudience(List<CampaignAudienceRow> Rows, string Subject, string Body);

internal sealed partial class CommunicationDraftRepository
{
    private const string CampaignScope = @" FROM public.communication_campaigns c
        WHERE c.organization_id=@company AND c.type='email' AND (@scope='organization' OR c.created_by=@actor)
          AND EXISTS (SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company AND b.branch_id=@branch
            AND b.resource_table='communication_campaigns' AND b.resource_key=c.id::text)";

    private const string CampaignFields = @"SELECT c.id,c.xmin::text,c.name,c.template_id,c.status,
        coalesce(c.segment_json->>'source',c.segment_json->>'module','lead'),coalesce(c.segment_json->>'status',''),
        coalesce(c.segment_json->>'limit','50')";

    internal async Task<CampaignList> ListCampaignsAsync(string search)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        var grant = await CampaignGrantAsync(db, tx, branch, actor, "view");
        var rows = new List<EmailCampaign>();
        using (var query = CampaignCommand(CampaignFields + CampaignScope +
            " AND (@search='' OR strpos(lower(c.name),lower(@search))>0) ORDER BY c.id DESC LIMIT 200",
            db, tx, branch, actor.Id, grant.Scope))
        {
            query.Parameters.AddWithValue("search", search.Trim());
            using var reader = await query.ExecuteReaderAsync();
            while (await reader.ReadAsync())
                rows.Add(ReadCampaign(reader));
        }
        return new(rows, await AllowsCampaignWriteAsync(db, tx, branch, actor, "create"),
            await AllowsCampaignWriteAsync(db, tx, branch, actor, "edit"));
    }

    internal async Task<int> SaveCampaignAsync(EmailCampaign? original, CampaignInput input)
    {
        string name = input.Name.Trim();
        string status = input.SegmentStatus.Trim();
        if (name.Length is < 2 or > 180 || name.Any(char.IsControl) || input.Template <= 0 ||
            status.Length > 80 || status.Any(char.IsControl) || input.Limit is < 1 or > 50 ||
            input.Source is not ("lead" or "contact"))
            throw new ArgumentException("Enter a name, an active template, a CRM source and a recipient limit from 1 to 50.");
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        var grant = await CampaignGrantAsync(db, tx, branch, actor, original is null ? "create" : "edit");
        await new CommunicationTemplatesRepository(settings).VerifyCampaignTemplateAsync(db, tx, actor, branch, input.Template);
        if (original is not null)
        {
            var saved = await ReadCampaignAsync(db, tx, branch, actor.Id, grant.Scope, original.Id, true);
            if (saved.Revision != original.Revision || saved.State is not ("draft" or "cancelled"))
                throw new InvalidOperationException("This campaign changed or is no longer editable. Refresh the list.");
        }
        var segment = new Dictionary<string, object> { ["source"] = input.Source, ["limit"] = input.Limit };
        if (status.Length > 0)
            segment["status"] = status;
        const string create = @"INSERT INTO public.communication_campaigns(organization_id,name,type,template_id,segment_json,status,
            sent_count,failed_count,blocked_count,created_by)
            VALUES(@company,@name,'email',@template,@segment::json,'draft',0,0,0,@actor) RETURNING id";
        const string edit = @"UPDATE public.communication_campaigns SET name=@name,template_id=@template,
            segment_json=(coalesce(segment_json::jsonb,'{}'::jsonb)-ARRAY['source','status','limit','module']||@segment::jsonb)::json
            WHERE organization_id=@company AND id=@id RETURNING id";
        using var write = Scoped(original is null ? create : edit, db, tx, branch, actor.Id);
        write.Parameters.AddWithValue("name", name);
        write.Parameters.AddWithValue("template", input.Template);
        write.Parameters.AddWithValue("segment", JsonSerializer.Serialize(segment));
        if (original is not null)
            write.Parameters.AddWithValue("id", original.Id);
        int id = (int)(await write.ExecuteScalarAsync() ?? throw new InvalidOperationException("The campaign could not be saved."));
        if (original is null)
        {
            using var own = Scoped(@"INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
                VALUES('communication_campaigns',@id::text,@company,@branch,'desktop')", db, tx, branch, actor.Id);
            own.Parameters.AddWithValue("id", id);
            await own.ExecuteNonQueryAsync();
        }
        await AuditCampaignAsync(db, tx, branch, actor.Id, id, name, original is null ? "create" : "edit");
        tx.Commit();
        return id;
    }

    internal async Task CancelCampaignAsync(EmailCampaign selected)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        var actor = await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        var grant = await CampaignGrantAsync(db, tx, branch, actor, "edit");
        var current = await ReadCampaignAsync(db, tx, branch, actor.Id, grant.Scope, selected.Id, true);
        if (current.Revision != selected.Revision || current.State is not ("draft" or "scheduled"))
            throw new InvalidOperationException("This campaign changed or is no longer cancellable. Refresh the list.");
        using var command = Scoped("UPDATE public.communication_campaigns SET status='cancelled' WHERE organization_id=@company AND id=@id",
            db, tx, branch, actor.Id);
        command.Parameters.AddWithValue("id", current.Id);
        await command.ExecuteNonQueryAsync();
        await AuditCampaignAsync(db, tx, branch, actor.Id, current.Id, current.Name, "cancel");
        tx.Commit();
    }

    internal async Task<CampaignAudience> PreviewCampaignAsync(EmailCampaign selected)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        var grant = await CampaignGrantAsync(db, tx, branch, actor, "view");
        CrmDirectoryWrites.RequireCrmAccess(actor);
        var crm = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor,
            "crm", "view", "crm_view", "crm_manage", "crm_admin");
        if (crm.Scope != "organization")
            throw new UnauthorizedAccessException("Campaign preview requires access to the CRM audience in this branch.");
        var campaign = await ReadCampaignAsync(db, tx, branch, actor.Id, grant.Scope, selected.Id, false);
        if (campaign.Revision != selected.Revision)
            throw new InvalidOperationException("This campaign changed. Refresh before previewing.");
        if (campaign.Source is not ("lead" or "contact"))
            throw new InvalidOperationException("This campaign uses an unsupported CRM audience.");
        string suppression = EffectiveEmailOptOut.Replace("@email", "r.normalized");
        var rows = new List<CampaignAudienceRow>();
        using (var query = Scoped(@"WITH visible AS (" + RecipientScope + @"), candidates AS (
          SELECT id,name,lower(btrim(email)) AS normalized FROM visible
          WHERE kind=@source AND email<>'' AND (@status='' OR status=@status) ORDER BY id DESC LIMIT @limit
        )
        SELECT r.id,r.name,r.normalized," + suppression + " FROM candidates r ORDER BY r.id DESC", db, tx, branch, actor.Id))
        {
            query.Parameters.AddWithValue("source", campaign.Source);
            query.Parameters.AddWithValue("status", campaign.SegmentStatus);
            query.Parameters.AddWithValue("limit", campaign.Limit);
            using var reader = await query.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                string address = reader.GetString(2);
                string outcome = reader.GetBoolean(3) ? "Opted out" : "Included";
                try { NormalizeDraftAddress(address); }
                catch (ArgumentException) { outcome = "Invalid email"; }
                rows.Add(new(reader.GetInt32(0), reader.GetString(1), address, outcome));
            }
        }
        string subject = "", body = "";
        if (campaign.Template is int id && rows.FirstOrDefault(row => row.Outcome == "Included") is { } sample)
        {
            var template = await new CommunicationTemplatesRepository(settings).ReadCampaignTemplateAsync(db, tx, actor, branch, id);
            var recipient = new DraftRecipient(sample.Id, campaign.Source, sample.Name, sample.Email);
            var merge = new Dictionary<string, string>
            {
                ["record_type"] = campaign.Source, ["record_id"] = sample.Id.ToString(System.Globalization.CultureInfo.InvariantCulture)
            };
            subject = Render(template.Row.Subject, recipient, sample.Email, merge);
            body = Render(template.Body, recipient, sample.Email, merge);
        }
        return new(rows, subject, body);
    }

    private async Task<EmailCampaign> ReadCampaignAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor,
        string scope, int id, bool locked)
    {
        using var query = CampaignCommand(CampaignFields + CampaignScope + " AND c.id=@id" + (locked ? " FOR UPDATE" : ""),
            db, tx, branch, actor, scope);
        query.Parameters.AddWithValue("id", id);
        using var reader = await query.ExecuteReaderAsync();
        return await reader.ReadAsync() ? ReadCampaign(reader)
            : throw new InvalidOperationException("This campaign is unavailable in the current branch.");
    }

    private static EmailCampaign ReadCampaign(NpgsqlDataReader reader) =>
        new(reader.GetInt32(0), reader.GetString(1), reader.GetString(2), reader.IsDBNull(3) ? null : reader.GetInt32(3),
            reader.GetString(4), reader.GetString(5), reader.GetString(6),
            int.TryParse(reader.GetString(7), out int limit) ? Math.Max(1, Math.Min(50, limit)) : 50);

    private async Task<DesktopModuleGrant> CampaignGrantAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        DesktopActor actor, string action)
    {
        string[] permissions = action == "view" ? ["communication_campaigns_view", "communication_campaigns_manage"]
            : ["communication_campaigns_manage"];
        var grant = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor, "communication", action, permissions);
        if (grant.Scope is not ("organization" or "own"))
            throw new UnauthorizedAccessException("The campaign workspace requires organization or own-record access.");
        return grant;
    }

    private async Task<bool> AllowsCampaignWriteAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor, string action)
    {
        if (!actor.CanWriteBranch)
            return false;
        try { await CampaignGrantAsync(db, tx, branch, actor, action); return true; }
        catch (UnauthorizedAccessException) { return false; }
    }

    private async Task AuditCampaignAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor, int id, string name, string action)
    {
        using var command = Scoped(@"INSERT INTO public.suite_branch_audit(company_id,actor_id,operation,reason,details)
            VALUES(@company,@actor,'communication.campaign',@action,json_build_object('branch_id',@branch,'campaign_id',@id,'name',@name))",
            db, tx, branch, actor);
        command.Parameters.AddWithValue("action", action);
        command.Parameters.AddWithValue("id", id);
        command.Parameters.AddWithValue("name", name);
        await command.ExecuteNonQueryAsync();
    }

    private NpgsqlCommand CampaignCommand(string sql, NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor, string scope)
    {
        var command = Scoped(sql, db, tx, branch, actor);
        command.Parameters.AddWithValue("scope", scope);
        return command;
    }
}
