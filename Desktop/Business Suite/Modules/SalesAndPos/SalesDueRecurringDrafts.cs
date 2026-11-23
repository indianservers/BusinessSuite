using System.Globalization;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    internal async Task<List<SalesInvoiceDraftResult>> DraftDueSalesRecurringInvoicesAsync(int order, int engagement, int plan)
    {
        if (order < 1 || engagement < 1 || plan < 1)
            throw new ArgumentException("Select a saved billing plan.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose the recurring billing branch.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await SalesInvoiceScopeAsync(db, tx, branch, actor);
        DateTime billingDate = await RecurringBillingDateAsync(db, tx, branch, actor.Id);
        using var select = ScopedCommand("SELECT m.id" + BillingMilestoneSource + @"
            AND b.status='active' AND e.status NOT IN ('closed','cancelled')
            AND m.metadata_json::jsonb->'recurring'='true'::jsonb AND m.due_date<=@today AND m.invoice_draft_id IS NULL
            AND m.status IN ('approved','ready','completed') ORDER BY m.due_date,m.id LIMIT 100 FOR UPDATE OF o,e,b,m",
            db, tx, branch, actor, scope);
        BindBillingMilestoneChain(select, order, engagement, plan);
        select.Parameters.AddWithValue("today", NpgsqlDbType.Date, billingDate);
        var milestones = new List<int>();
        using (var reader = await select.ExecuteReaderAsync())
            while (await reader.ReadAsync())
                milestones.Add(reader.GetInt32(0));
        var invoices = new List<SalesInvoiceDraftResult>(milestones.Count);
        foreach (int milestone in milestones)
            invoices.Add(await DraftMilestoneSourceAsync(db, tx, branch, actor, scope, order, engagement, plan,
                milestone, billingDate, batch: true));
        tx.Commit();
        return invoices;
    }

    private async Task<DateTime> RecurringBillingDateAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor)
    {
        string companyKey = "form-defaults:company:" + settings.OrganizationId.ToString(CultureInfo.InvariantCulture);
        string branchKey = companyKey + ":branch:" + branch.ToString(CultureInfo.InvariantCulture);
        using var query = RegisterCommand(@"
            SELECT (now() AT TIME ZONE coalesce(
                (SELECT nullif(p.values_json->>'timezone','') FROM unnest(@keys::text[]) WITH ORDINALITY wanted(scope_key,priority)
                    JOIN public.suite_service_policies p ON p.scope_key=wanted.scope_key AND p.organization_id=@company
                        AND p.kind='form_defaults' WHERE nullif(p.values_json->>'timezone','') IS NOT NULL
                    ORDER BY wanted.priority DESC LIMIT 1),nullif(c.default_timezone,''),'Asia/Kolkata'))::date
            FROM public.companies c WHERE c.id=@company", db, tx, branch, actor);
        query.Parameters.AddWithValue("keys", NpgsqlDbType.Array | NpgsqlDbType.Text,
            new[] { companyKey, companyKey + ":module:srm", branchKey, branchKey + ":module:srm" });
        if (await query.ExecuteScalarAsync() is not DateTime day)
            throw new InvalidOperationException("The business billing date is unavailable.");
        return day;
    }
}
