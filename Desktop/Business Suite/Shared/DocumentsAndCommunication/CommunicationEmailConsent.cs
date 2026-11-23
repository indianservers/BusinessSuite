using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record EmailConsentRow(DateTime? Recorded, string Choice, string Source);
internal sealed record EmailConsentHistory(List<EmailConsentRow> Rows, bool Blocked, bool CanRecord, string Revision)
{
    internal bool HardBlocked { get; init; }
}

internal sealed partial class CommunicationDraftRepository
{
    private const string OwnedEmailConsents = @"FROM public.communication_consents c
        JOIN public.security_resource_ownership own ON own.resource_table='communication_consents'
          AND own.resource_id=c.id AND own.company_id=@company
        WHERE c.email=@email AND c.consent_type='email'";

    private const string HardEmailOptOut = @"EXISTS (SELECT 1 FROM public.communication_opt_outs o
        JOIN public.security_resource_ownership own ON own.resource_table='communication_opt_outs'
          AND own.resource_id=o.id AND own.company_id=@company WHERE o.email=@email AND o.channel='email')";

    private const string EffectiveEmailOptOut = HardEmailOptOut +
        " OR coalesce((SELECT c.status IN ('opted_out','unsubscribed') " + OwnedEmailConsents +
        " ORDER BY c.updated_at DESC,c.id DESC LIMIT 1),false)";

    internal async Task<EmailConsentHistory> ReadEmailConsentAsync(DraftRecipientReference reference, string email)
    {
        string address = NormalizeDraftAddress(email);
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await RequireConsentAccessAsync(db, tx, branch, actor, false);
        bool owned = await VerifyConsentRecipientAsync(db, tx, branch, actor, reference, address);
        bool mayRecord = false;
        if (owned && actor.CanWriteBranch)
        {
            try
            {
                await RequireConsentAccessAsync(db, tx, branch, actor, true);
                mayRecord = true;
            }
            catch (UnauthorizedAccessException) { }
        }
        var (blocked, hardBlocked, revision) = await ConsentStateAsync(db, tx, branch, actor.Id, address);
        var rows = new List<EmailConsentRow>();
        using var command = ConsentCommand("SELECT c.updated_at,c.status,coalesce(c.source,'') " + OwnedEmailConsents + @"
             AND c.record_type=@kind AND c.record_id=@record
             ORDER BY c.updated_at DESC,c.id DESC LIMIT 200", db, tx, branch, actor.Id, reference, address);
        using var reader = await command.ExecuteReaderAsync();
        while (await reader.ReadAsync())
            rows.Add(new(reader.IsDBNull(0) ? null : reader.GetDateTime(0).ToLocalTime(), reader.GetString(1), reader.GetString(2)));
        return new(rows, blocked, mayRecord, revision) { HardBlocked = hardBlocked };
    }

    internal Task RecordEmailConsentAsync(DraftRecipientReference reference, string email, string expectedRevision,
        string choice, string evidence) => SaveConsentAsync(reference, email, expectedRevision, choice, evidence, false);

    internal Task RecordAddressOptOutAsync(DraftRecipientReference reference, string email, string expectedRevision,
        string evidence) => SaveConsentAsync(reference, email, expectedRevision, "opted_out", evidence, true);

    private async Task SaveConsentAsync(DraftRecipientReference reference, string email, string expectedRevision,
        string choice, string evidence, bool hard)
    {
        string address = NormalizeDraftAddress(email);
        evidence = evidence.Trim();
        if (evidence.Length is < 1 or > 120 || evidence.Any(char.IsControl) ||
            choice is not ("opted_in" or "opted_out" or "unsubscribed"))
            throw new ArgumentException("Choose an email preference and enter one line of evidence, up to 120 characters.");
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        var actor = await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await RequireConsentAccessAsync(db, tx, branch, actor, true);
        using (var writeLock = Scoped("SELECT pg_advisory_xact_lock(720000000::bigint+@company)", db, tx, branch, actor.Id))
            await writeLock.ExecuteNonQueryAsync();
        actor = await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await RequireConsentAccessAsync(db, tx, branch, actor, true);
        if (!await VerifyConsentRecipientAsync(db, tx, branch, actor, reference, address))
            throw new UnauthorizedAccessException("Record the consent in the CRM record's owning branch.");
        var (_, alreadyBlocked, revision) = await ConsentStateAsync(db, tx, branch, actor.Id, address);
        if (hard && alreadyBlocked)
            return;
        if (revision != expectedRevision)
            throw new InvalidOperationException("The recorded consent changed. Refresh before saving.");
        using var command = ConsentCommand(@"
          WITH suppressed AS (
            INSERT INTO public.communication_opt_outs(email,channel,reason,source)
            SELECT @email,'email',@source,'manual' WHERE @hard
            ON CONFLICT (email,channel) DO NOTHING RETURNING id
          ), suppression_owner AS (
            INSERT INTO public.security_resource_ownership(resource_table,resource_id,company_id)
            SELECT 'communication_opt_outs',id,@company FROM suppressed
          ), recorded AS (
            INSERT INTO public.communication_consents(email,record_type,record_id,consent_type,status,source)
            SELECT @email,@kind,@record,'email',@choice,@source
            WHERE NOT @hard OR EXISTS (SELECT 1 FROM suppressed) RETURNING id
          ), owner AS (
            INSERT INTO public.security_resource_ownership(resource_table,resource_id,company_id)
            SELECT 'communication_consents',id,@company FROM recorded
          )
          INSERT INTO public.suite_branch_audit(company_id,actor_id,operation,reason,details)
          SELECT @company,@actor,'communication.email_consent',
            CASE WHEN @hard THEN 'record_address_opt_out' ELSE 'record_customer_choice' END,
            json_build_object('branch_id',@branch,'record_type',@kind,'record_id',@record,'consent_id',id,
              'status',@choice,'opt_out_id',(SELECT id FROM suppressed))
          FROM recorded", db, tx, branch, actor.Id, reference, address);
        command.Parameters.AddWithValue("choice", choice);
        command.Parameters.AddWithValue("source", evidence);
        command.Parameters.AddWithValue("hard", hard);
        if (await command.ExecuteNonQueryAsync() != 1)
            throw new InvalidOperationException("The address-wide opt-out could not be saved. No consent was changed.");
        tx.Commit();
    }

    private async Task<(bool Blocked, bool HardBlocked, string Revision)> ConsentStateAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, int actor, string email)
    {
        using var query = Scoped("SELECT " + EffectiveEmailOptOut + "," + HardEmailOptOut + "," +
            "coalesce((SELECT c.id::text || '/' || c.xmin::text " + OwnedEmailConsents + " ORDER BY c.updated_at DESC,c.id DESC LIMIT 1),'-') || ':' || " +
            "(" + HardEmailOptOut + ")::text", db, tx, branch, actor);
        query.Parameters.AddWithValue("email", email);
        using var row = await query.ExecuteReaderAsync();
        await row.ReadAsync();
        return (row.GetBoolean(0), row.GetBoolean(1), row.GetString(2));
    }

    private async Task<bool> VerifyConsentRecipientAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        DesktopActor actor, DraftRecipientReference reference, string email)
    {
        using var query = ConsentCommand(@"SELECT EXISTS (
            SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company AND b.branch_id=@branch
                AND b.resource_key=r.id::text AND b.resource_table=CASE r.kind WHEN 'company' THEN 'crm_companies'
                  WHEN 'contact' THEN 'crm_contacts' ELSE 'crm_leads' END)
            FROM (" + RecipientScope + @") r WHERE r.id=@record AND r.kind=@kind AND lower(btrim(r.email))=@email",
            db, tx, branch, actor.Id, reference, email);
        return await query.ExecuteScalarAsync() as bool?
            ?? throw new InvalidOperationException("Select an accessible CRM record with this email address.");
    }

    private async Task RequireConsentAccessAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor, bool create)
    {
        CrmDirectoryWrites.RequireCrmAccess(actor);
        var crm = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor,
            "crm", "view", "crm_view", "crm_manage", "crm_admin");
        string[] permissions = create ? ["communication_consents_manage"]
            : ["communication_view", "communication_consents_manage"];
        var communication = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor,
            "communication", create ? "create" : "view", permissions);
        if (crm.Scope != "organization" || communication.Scope != "organization")
            throw new UnauthorizedAccessException("Email consent history requires authorized CRM and Communication access.");
    }

    private NpgsqlCommand ConsentCommand(string sql, NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor,
        DraftRecipientReference reference, string email)
    {
        var command = Scoped(sql, db, tx, branch, actor);
        command.Parameters.AddWithValue("kind", NpgsqlDbType.Text, reference.Kind);
        command.Parameters.AddWithValue("record", NpgsqlDbType.Integer, reference.Id);
        command.Parameters.AddWithValue("email", NpgsqlDbType.Text, email);
        return command;
    }
}
