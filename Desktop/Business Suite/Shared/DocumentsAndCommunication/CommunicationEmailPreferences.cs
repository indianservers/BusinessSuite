using System.Data;
using System.Net.Mail;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

internal sealed record CustomerEmailConsent(bool Transactional, bool Marketing, bool Greeting);
internal sealed record CustomerEmailPreferences(string Name, string Email, CustomerEmailConsent Consent,
    string Revision, bool CanEdit, bool CanOptIn, string Source, DateTime? Recorded);

internal sealed partial class CommunicationCustomerRepository
{
    internal async Task<CustomerEmailPreferences> EmailPreferencesAsync(int recipient, CancellationToken cancellation)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, cancellation);
        await RequirePermissionAsync(db, tx, actor, branch, false);
        bool edit = actor.CanWriteBranch && await AllowsEmailPreferenceAsync(db, tx, actor, branch, "communication_email_send");
        bool optIn = edit && await AllowsEmailPreferenceAsync(db, tx, actor, branch, "communication_consents_manage");
        return await ReadEmailPreferencesAsync(db, tx, branch, recipient, false, edit, optIn, cancellation);
    }

    internal async Task SaveEmailPreferencesAsync(int recipient, string revision, CustomerEmailConsent values,
        string source, CancellationToken cancellation)
    {
        source = source.Trim();
        if (source.Length is < 1 or > 240 || source.Any(char.IsControl))
            throw new ArgumentException("Enter one line of consent evidence, up to 240 characters.");
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await settings.VerifyWriteTargetAsync(db, tx, cancellation);
        await RequireEmailPreferenceAsync(db, tx, actor, branch, "communication_email_send");
        var current = await ReadEmailPreferencesAsync(db, tx, branch, recipient, true, true, false, cancellation);
        if (current.Revision != revision)
            throw new InvalidOperationException("The customer's preferences changed. Refresh before saving.");
        if (values == current.Consent)
            return;
        if ((values.Transactional && !current.Consent.Transactional) || (values.Marketing && !current.Consent.Marketing) ||
            (values.Greeting && !current.Consent.Greeting))
        {
            await RequireEmailPreferenceAsync(db, tx, actor, branch, "communication_consents_manage");
            try
            {
                if (string.IsNullOrWhiteSpace(current.Email) ||
                    !string.Equals(new MailAddress(current.Email).Address, current.Email, StringComparison.OrdinalIgnoreCase))
                    throw new FormatException();
            }
            catch (FormatException)
            {
                throw new InvalidOperationException("A valid email address is required before recording an email opt-in.");
            }
        }
        string preferences = JsonSerializer.Serialize(new Dictionary<string, bool>
        {
            ["email.transactional"] = values.Transactional, ["email.marketing"] = values.Marketing,
            ["email.greeting"] = values.Greeting
        });
        using var command = ScopedCommand(db, tx, branch, @"
            WITH patched AS (
                SELECT r.id,coalesce(r.preferences::jsonb,'{}'::jsonb)||@preferences::jsonb AS data,
                    coalesce(r.consent_history::jsonb,'[]'::jsonb) AS history
                FROM public.communication_customer_recipients r
                WHERE r.id=@id AND r.organization_id=@company AND r.branch_id=@branch
            ), changed AS (
                UPDATE public.communication_customer_recipients r SET preferences=p.data::json,consent_source=@source,
                    consent_at=now(),
                    consent_history=(coalesce((SELECT jsonb_agg(h.value ORDER BY h.ordinality)
                        FROM jsonb_array_elements(p.history) WITH ORDINALITY h(value,ordinality)
                        WHERE h.ordinality > jsonb_array_length(p.history)-99),'[]'::jsonb) ||
                        jsonb_build_array(jsonb_build_object('at',now(),'actor',@actor,'source',@source,
                            'preferences',p.data)))::json
                FROM patched p WHERE r.id=p.id RETURNING r.id,p.data
            )
            INSERT INTO public.suite_branch_audit (company_id,actor_id,operation,reason,details)
            SELECT @company,@actor,'customer_communication.recipient_preferences','recipient_preferences',
                json_build_object('recipient_id',id,'branch_id',@branch,'preferences',data) FROM changed");
        command.Parameters.AddWithValue("id", recipient);
        command.Parameters.AddWithValue("actor", actor.Id);
        command.Parameters.AddWithValue("source", source);
        command.Parameters.AddWithValue("preferences", preferences);
        await command.ExecuteNonQueryAsync(cancellation);
        tx.Commit();
    }

    private async Task<CustomerEmailPreferences> ReadEmailPreferencesAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, int recipient, bool locked, bool canEdit, bool canOptIn, CancellationToken cancellation)
    {
        const string sql = @"SELECT name,coalesce(email,''),xmin::text,coalesce(consent_source,''),consent_at,
            preferences::jsonb->'email.transactional' = 'true'::jsonb,
            preferences::jsonb->'email.marketing' = 'true'::jsonb,
            preferences::jsonb->'email.greeting' = 'true'::jsonb
            FROM public.communication_customer_recipients WHERE id=@id AND organization_id=@company AND branch_id=@branch";
        using var query = ScopedCommand(db, tx, branch, sql + (locked ? " FOR UPDATE" : ""));
        query.Parameters.AddWithValue("id", recipient);
        using var row = await query.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            throw new InvalidOperationException("This customer is unavailable in the current branch.");
        return new(row.GetString(0),row.GetString(1),
            new(!row.IsDBNull(5) && row.GetBoolean(5),!row.IsDBNull(6) && row.GetBoolean(6),!row.IsDBNull(7) && row.GetBoolean(7)),
            row.GetString(2),canEdit,canOptIn,row.GetString(3),row.IsDBNull(4) ? null : row.GetDateTime(4).ToLocalTime());
    }

    private async Task<bool> AllowsEmailPreferenceAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        DesktopActor actor, int branch, string permission)
    {
        try
        {
            await RequireEmailPreferenceAsync(db, tx, actor, branch, permission);
            return true;
        }
        catch (UnauthorizedAccessException) { return false; }
    }

    private async Task RequireEmailPreferenceAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        DesktopActor actor, int branch, string permission)
    {
        var grant = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch,
            actor, "communication", "edit", permission);
        if (grant.Scope is not ("organization" or "branch"))
            throw new UnauthorizedAccessException("Customer preferences require branch-wide or organization-wide access.");
    }
}
