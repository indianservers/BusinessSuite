using System.Data;
using System.Net.Mail;
using System.Text.RegularExpressions;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record DraftRecipient(int Id, string Kind, string Name, string Email)
{
    public string Display => $"{Name} ({Kind})";
}

internal sealed record CommunicationDraftRow(int Id, string Record, string Recipient, string Subject,
    DateTime? Created, string Body);

internal sealed partial class CommunicationDraftRepository
{
    private readonly DesktopDatabaseSettings settings;

    internal CommunicationDraftRepository(DesktopDatabaseSettings settings) => this.settings = settings;

    internal ProtectedAppointmentJournal<CommunicationWorkingDraft> WorkingDraftJournal() =>
        new(settings, "Communication working draft", CommunicationWorkingDraft.Validate, 2 * 1024 * 1024,
            "The local working draft could not be verified.", "The local working draft could not be opened for this Windows account.");

    internal CommunicationQuickReplyStore QuickReplyStore() => new(settings);

    private const string RecipientScope = @"
        WITH candidates AS (
            SELECT l.id, 'lead' AS kind, 'crm_leads' AS resource, l.full_name AS name, l.email, l.status
            FROM public.crm_leads l WHERE l.organization_id=@company AND l.deleted_at IS NULL
            UNION ALL
            SELECT p.id, 'contact', 'crm_contacts', p.full_name, p.email, p.status
            FROM public.crm_contacts p WHERE p.organization_id=@company AND p.deleted_at IS NULL
                AND NOT EXISTS (SELECT 1 FROM public.srm_anonymous_cash_accounts a
                    WHERE a.organization_id=@company AND (a.customer_id=p.company_id OR EXISTS (
                        SELECT 1 FROM public.suite_contact_identity_links link WHERE link.organization_id=@company
                            AND link.account_id=a.customer_id AND link.contact_id=p.id)))
            UNION ALL
            SELECT c.id, 'company', 'crm_companies', c.name, c.email, c.status
            FROM public.crm_companies c WHERE c.organization_id=@company AND c.deleted_at IS NULL
                AND NOT EXISTS (SELECT 1 FROM public.srm_anonymous_cash_accounts a
                    WHERE a.organization_id=@company AND a.customer_id=c.id)
        )
        SELECT r.id, r.kind, r.name, coalesce(r.email, '') AS email, r.status
        FROM candidates r
        WHERE EXISTS (
            SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company AND b.branch_id=@branch
                AND b.resource_table=r.resource AND b.resource_key=r.id::text
        ) OR (
            r.kind IN ('contact','company') AND EXISTS (
                SELECT 1 FROM public.suite_branch_record_shares s WHERE s.company_id=@company AND s.branch_id=@branch
                    AND s.resource_table=r.resource AND s.resource_key=r.id::text
            )
        )";

    internal async Task<List<DraftRecipient>> SearchRecipientsAsync(string search)
        => await FindRecipientsAsync(search, null);

    internal async Task<DraftRecipient?> RestoreRecipientAsync(DraftRecipientReference reference)
        => (await FindRecipientsAsync("", reference)).SingleOrDefault();

    internal async Task<bool?> EmailOptOutAsync(DraftRecipientReference reference, string email)
    {
        string address = NormalizeDraftAddress(email);
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await CheckAccessAsync(db, tx, branch, actor, "create");
        using var check = Scoped(@"WITH visible AS (" + RecipientScope + @")
            SELECT CASE WHEN EXISTS (SELECT 1 FROM visible WHERE id=@id AND kind=@kind)
              AND EXISTS (SELECT 1 FROM visible WHERE lower(btrim(email))=@email)
            THEN " + EffectiveEmailOptOut + " ELSE NULL END", db, tx, branch, actor.Id);
        check.Parameters.AddWithValue("id", NpgsqlDbType.Integer, reference.Id);
        check.Parameters.AddWithValue("kind", NpgsqlDbType.Text, reference.Kind);
        check.Parameters.AddWithValue("email", NpgsqlDbType.Text, address);
        return await check.ExecuteScalarAsync() as bool?;
    }

    private async Task<List<DraftRecipient>> FindRecipientsAsync(string search, DraftRecipientReference? reference)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await CheckAccessAsync(db, tx, branch, actor, "create");
        using var searchCommand = Scoped(@"
            SELECT r.id,r.kind,r.name,r.email FROM (" + RecipientScope + @") r
            WHERE (@id IS NULL OR (r.id=@id AND r.kind=@kind))
              AND (@search='' OR strpos(lower(r.name),lower(@search))>0 OR strpos(lower(r.email),lower(@search))>0)
            ORDER BY r.name,r.kind,r.id LIMIT 30", db, tx, branch, actor.Id);
        searchCommand.Parameters.AddWithValue("search", NpgsqlDbType.Text, search);
        searchCommand.Parameters.AddWithValue("id", NpgsqlDbType.Integer, (object?)reference?.Id ?? DBNull.Value);
        searchCommand.Parameters.AddWithValue("kind", NpgsqlDbType.Text, (object?)reference?.Kind ?? DBNull.Value);
        var recipients = new List<DraftRecipient>();
        using (var rows = await searchCommand.ExecuteReaderAsync())
            while (await rows.ReadAsync())
                recipients.Add(new DraftRecipient(rows.GetInt32(0), rows.GetString(1), rows.GetString(2), rows.GetString(3)));
        tx.Commit();
        return recipients;
    }

    internal async Task<List<CommunicationDraftRow>> ListAsync(string search)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        var grant = await CheckAccessAsync(db, tx, branch, actor, "view");
        using var query = Scoped(@"
            SELECT d.id, r.name, d.to_email, d.subject, d.created_at, d.body
            FROM public.communication_email_messages d
            JOIN (" + RecipientScope + @") r ON r.id=d.related_record_id AND r.kind=d.related_record_type
            WHERE d.organization_id=@company AND d.status='draft' AND (@scope='organization' OR d.sent_by=@actor)
              AND EXISTS (
                  SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company AND b.branch_id=@branch
                    AND b.resource_table='communication_email_messages' AND b.resource_key=d.id::text
              )
              AND (@search='' OR strpos(lower(d.subject),lower(@search))>0
                   OR strpos(lower(d.to_email),lower(@search))>0 OR strpos(lower(r.name),lower(@search))>0)
            ORDER BY d.id DESC LIMIT 200", db, tx, branch, actor.Id);
        query.Parameters.AddWithValue("scope", NpgsqlDbType.Text, grant.Scope);
        query.Parameters.AddWithValue("search", NpgsqlDbType.Text, search);
        var result = new List<CommunicationDraftRow>();
        using (var reader = await query.ExecuteReaderAsync())
            while (await reader.ReadAsync())
                result.Add(new CommunicationDraftRow(reader.GetInt32(0), reader.GetString(1), reader.GetString(2), reader.GetString(3),
                    reader.IsDBNull(4) ? null : reader.GetDateTime(4).ToLocalTime(), reader.GetString(5)));
        tx.Commit();
        return result;
    }

    private static readonly Regex MergeToken = new(@"\{\{\s*([^{}]+?)\s*\}\}");

    internal Task<int> SaveAsync(DraftRecipient recipient, string email, string subject, string body) =>
        SaveAsync(recipient, email, subject, body, null);

    internal async Task<int> SaveAsync(DraftRecipient recipient, string email, string subject, string body,
        IReadOnlyDictionary<string, string>? mergeValues)
    {
        email = NormalizeDraftAddress(email);
        subject = Render(subject.Trim(), recipient, email, mergeValues);
        body = Render(body, recipient, email, mergeValues);
        if (subject.Length is 0 or > 240 || subject.Contains("\r") || subject.Contains("\n"))
            throw new ArgumentException("Enter a single-line subject of up to 240 characters.");
        if (body.Length > 50000)
            throw new ArgumentException("Keep the email body within 50,000 characters.");
        if (MergeToken.IsMatch(subject) || MergeToken.IsMatch(body))
            throw new ArgumentException("Fill in the remaining merge fields before saving the draft.");

        return await WriteDraftAsync(recipient, email, subject, body);
    }

    private static string NormalizeDraftAddress(string email)
    {
        email = email.Trim().ToLowerInvariant();
        if (email.Length > 180 || !Regex.IsMatch(email, @"^[^@\s]+@[^@\s]+\.[^@\s]+$"))
            throw new ArgumentException("Enter a valid recipient email address.");
        try
        {
            if (!string.Equals(new MailAddress(email).Address, email, StringComparison.OrdinalIgnoreCase))
                throw new FormatException();
        }
        catch (FormatException)
        {
            throw new ArgumentException("Enter a valid recipient email address.");
        }
        return email;
    }

    private async Task<int> WriteDraftAsync(DraftRecipient recipient, string email, string subject, string body)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await CheckAccessAsync(db, tx, branch, actor, "create");
        using var command = Scoped(@"
            WITH draft AS (
                INSERT INTO public.communication_email_messages
                    (organization_id,related_record_type,related_record_id,to_email,subject,body,status,sent_by)
                SELECT @company,@kind,@id,@email,@subject,@body,'draft',@actor
                WHERE EXISTS (SELECT 1 FROM (" + RecipientScope + @") r WHERE r.id=@id AND r.kind=@kind)
                RETURNING id
            ), timeline AS (
                INSERT INTO public.communication_timeline_events
                    (organization_id,record_type,record_id,channel,event_type,subject,summary,actor_user_id,metadata_json)
                SELECT @company,@kind,@id,'email','draft',@subject,@summary,@actor,json_build_object('message_id',id)
                FROM draft RETURNING id
            ), ownership AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'communication_email_messages',id::text,@company,@branch,'validated-write' FROM draft
                UNION ALL
                SELECT 'communication_timeline_events',id::text,@company,@branch,'validated-write' FROM timeline
            )
            SELECT id FROM draft", db, tx, branch, actor.Id);
        command.Parameters.AddWithValue("id", NpgsqlDbType.Integer, recipient.Id);
        command.Parameters.AddWithValue("kind", NpgsqlDbType.Text, recipient.Kind);
        command.Parameters.AddWithValue("email", NpgsqlDbType.Text, email);
        command.Parameters.AddWithValue("subject", NpgsqlDbType.Text, subject);
        command.Parameters.AddWithValue("body", NpgsqlDbType.Text, body);
        command.Parameters.AddWithValue("summary", NpgsqlDbType.Text, $"Email draft for {email}");
        int id = await command.ExecuteScalarAsync() is int saved ? saved
            : throw new InvalidOperationException("The selected CRM record is unavailable in this branch.");
        tx.Commit();
        return id;
    }

    internal static string[] CustomMergeFields(string subject, string body) =>
        MergeToken.Matches(subject).Cast<Match>().Concat(MergeToken.Matches(body).Cast<Match>())
            .Select(match => match.Groups[1].Value.Trim())
            .Where(name => name.Length != 0 && name is not ("name" or "email"))
            .Distinct(StringComparer.Ordinal).OrderBy(name => name, StringComparer.Ordinal).ToArray();

    internal static string Render(string text, DraftRecipient recipient, string email,
        IReadOnlyDictionary<string, string>? mergeValues = null) =>
        MergeToken.Replace(text, match => match.Groups[1].Value.Trim() switch
        {
            "name" when !string.IsNullOrWhiteSpace(recipient.Name) => recipient.Name,
            "email" when !string.IsNullOrWhiteSpace(email) => email,
            var name when mergeValues?.TryGetValue(name, out string value) == true && !string.IsNullOrWhiteSpace(value) => value,
            _ => match.Value
        });

    private async Task<DesktopModuleGrant> CheckAccessAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, DesktopActor actor, string action)
    {
        CrmDirectoryWrites.RequireCrmAccess(actor);
        var crm = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor, "crm",
            "view", "crm_view", "crm_manage", "crm_admin");
        string[] accepted = action == "view" ? new[] { "communication_view", "communication_email_send" }
            : new[] { "communication_email_send" };
        var communication = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor,
            "communication", action, accepted);
        if (crm.Scope != "organization" || communication.Scope is not ("organization" or "own"))
            throw new UnauthorizedAccessException("Draft composition requires access to CRM records in the selected branch.");
        return communication;
    }

    private int RequireBranch() => settings.BranchId ??
        throw new UnauthorizedAccessException("Select a branch to compose an email draft.");

    private NpgsqlCommand Scoped(string sql, NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor)
    {
        var command = new NpgsqlCommand(sql, db, tx);
        command.Parameters.AddWithValue("company", NpgsqlDbType.Integer, settings.OrganizationId);
        command.Parameters.AddWithValue("branch", NpgsqlDbType.Integer, branch);
        command.Parameters.AddWithValue("actor", NpgsqlDbType.Integer, actor);
        return command;
    }
}
