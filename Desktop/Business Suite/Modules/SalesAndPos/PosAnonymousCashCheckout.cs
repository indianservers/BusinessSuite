using System.Data;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    private static readonly Lazy<Dictionary<string, string>> AnonymousJurisdictions = new(() =>
    {
        using var stream = typeof(SalesOrderRepository).Assembly.GetManifestResourceStream("BusinessSuite.ValidationContract.json")
            ?? throw new InvalidOperationException("The native counter jurisdiction contract is unavailable.");
        using var document = JsonDocument.Parse(stream);
        return document.RootElement.GetProperty("countries").EnumerateArray()
            .ToDictionary(country => country.GetProperty("iso").GetString()!,
                country => country.GetProperty("country").GetString()!, StringComparer.Ordinal);
    });

    private sealed record AnonymousCheckoutBuyer(int Id);

    // This alternate projection is reachable only with the buyer resolved inside the locked full-cash checkout.
    private const string AnonymousInvoiceIssueScope = @"
        WHERE c.id=@cash_customer AND c.organization_id=@company AND c.deleted_at IS NULL
            AND existing.invoice_id IS NULL
            AND EXISTS (SELECT 1 FROM public.srm_anonymous_cash_accounts a WHERE a.customer_id=c.id
                AND a.organization_id=@company AND a.branch_id=@branch AND a.pack_context_id IS NULL
                AND a.active AND a.kind='anonymous_cash')";

    private async Task<AnonymousCheckoutBuyer?> ResolveAnonymousCheckoutBuyerAsync(NpgsqlConnection db,
        NpgsqlTransaction tx, int branch, int actor, bool lockRows, bool requireActive = true)
    {
        using var query = RegisterCommand(@"
            SELECT c.id,a.jurisdiction_country,c.country,
                (a.active OR NOT @require_active) AND a.revision>0 AND a.kind='anonymous_cash'
                AND c.name=a.account_label AND c.status='Active' AND c.account_type='Customer' AND c.deleted_at IS NULL
                AND coalesce(c.email,'')='' AND coalesce(c.phone,'')='' AND coalesce(c.phone_country_code,'')=''
                AND coalesce(c.address,'')='' AND coalesce(c.city,'')='' AND coalesce(c.state,'')='' AND coalesce(c.website,'')=''
                AND " + ConfirmationOwnership("a", "srm_anonymous_cash_accounts") + " AND " +
                ConfirmationOwnership("c", "crm_companies") + @"
                AND NOT EXISTS (SELECT 1 FROM public.suite_company_master_details d WHERE d.account_id=c.id AND
                    (d.organization_id<>@company OR coalesce(d.addresses::jsonb,'null'::jsonb) NOT IN ('[]'::jsonb,'null'::jsonb)
                    OR coalesce(d.tax_registrations::jsonb,'null'::jsonb) NOT IN ('[]'::jsonb,'null'::jsonb)
                    OR coalesce(d.legal_name,'')<>'' OR coalesce(d.trade_name,'')<>'' OR d.business_type='Individual'))
                AND NOT EXISTS (SELECT 1 FROM public.crm_contacts t WHERE t.company_id=c.id AND
                    (t.organization_id IS DISTINCT FROM @company OR t.full_name IS DISTINCT FROM c.name OR
                    coalesce(t.email,'')<>'' OR coalesce(t.phone,'')<>'' OR coalesce(t.phone_country_code,'')<>'' OR
                    NOT EXISTS(SELECT 1 FROM public.suite_contact_identity_links l WHERE l.contact_id=t.id) OR
                    EXISTS(SELECT 1 FROM public.suite_contact_identity_links l WHERE l.contact_id=t.id AND
                        (l.organization_id<>@company OR l.account_id IS DISTINCT FROM c.id OR l.person_id IS NOT NULL
                        OR l.employee_id IS NOT NULL OR l.lead_id IS NOT NULL))))
            FROM public.srm_anonymous_cash_accounts a JOIN public.crm_companies c ON c.id=a.customer_id AND c.organization_id=@company
            WHERE a.organization_id=@company AND a.branch_id=@branch AND a.pack_context_id IS NULL
            ORDER BY a.id LIMIT 2" + (lockRows ? " FOR UPDATE OF a,c" : ""), db, tx, branch, actor);
        query.Parameters.AddWithValue("require_active", requireActive);
        using var reader = await query.ExecuteReaderAsync();
        if (!await reader.ReadAsync() || reader.IsDBNull(2) || reader.IsDBNull(3) || !reader.GetBoolean(3))
            return null;
        int id = reader.GetInt32(0);
        string code = reader.GetString(1);
        string country = reader.GetString(2);
        if (!AnonymousJurisdictions.Value.TryGetValue(code, out string? name) || (country != code && country != name) ||
            await reader.ReadAsync())
            return null;
        return new AnonymousCheckoutBuyer(id);
    }

    internal async Task<bool> CanCheckoutAnonymousPosCashAsync()
    {
        if (settings.BranchId is not int branch)
            return false;
        try
        {
            using var db = new NpgsqlConnection(settings.ConnectionString);
            await db.OpenAsync();
            using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
            using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
                await readOnly.ExecuteNonQueryAsync();
            var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
            await RequirePosCheckoutAsync(db, tx, branch, actor);
            return await ResolveAnonymousCheckoutBuyerAsync(db, tx, branch, actor.Id, lockRows: false) is not null;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }
}
