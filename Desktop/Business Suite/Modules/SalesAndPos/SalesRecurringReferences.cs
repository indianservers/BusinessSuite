using Npgsql;

namespace Business_Suite;

internal sealed record SalesRecurringReference(string Kind, int? Id, string Name);

internal sealed partial class SalesOrderRepository
{
    private const string RecurringSalespersonScope = @" WHERE u.is_active
        AND NOT EXISTS (SELECT 1 FROM public.suite_access_memberships m
            WHERE m.company_id=@company AND m.user_id=u.id AND NOT m.active)
        AND (EXISTS (SELECT 1 FROM public.suite_access_memberships m
                WHERE m.company_id=@company AND m.user_id=u.id AND m.active)
            OR EXISTS (SELECT 1 FROM public.common_people p WHERE p.organization_id=@company AND p.user_id=u.id)
            OR EXISTS (SELECT 1 FROM public.employees e JOIN public.branches b ON b.id=e.branch_id
                WHERE b.company_id=@company AND e.user_id=u.id AND e.deleted_at IS NULL))";

    private const string RecurringPaymentModeScope = " WHERE mode.company_id=@company AND mode.active";

    internal Task<List<SalesRecurringReference>> SalesRecurringReferencesAsync(int order, int engagement, int plan) => ReadAsync(@"
        WITH authorized AS (SELECT b.id" + SalesBillingPlanChain + SalesBillingPlanScope + @"
            AND b.id=@plan AND b.status NOT IN ('completed','cancelled'))
        SELECT 'payment',mode.id,mode.name FROM public.fam_payment_modes mode" + RecurringPaymentModeScope + @"
            AND EXISTS (SELECT 1 FROM authorized)
        UNION ALL SELECT 'salesperson',u.id,u.email FROM public.users u" + RecurringSalespersonScope + @"
            AND EXISTS (SELECT 1 FROM authorized)
        ORDER BY 1,3,2", query => BindBillingMilestoneChain(query, order, engagement, plan),
        row => new SalesRecurringReference(row.GetString(0), row.GetInt32(1), row.GetString(2)), "create");

    private async Task<Dictionary<string, object>> BuildRecurringPresentationAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, int actor, SalesRecurringScheduleInput input)
    {
        var metadata = new Dictionary<string, object>
        {
            ["recurring"] = true, ["payment_terms_days"] = input.PaymentTerms,
            ["automatic_drafts"] = input.AutomaticDrafts, ["notify_on_creation"] = !input.SuppressRecurringNotice,
            ["invoice_template"] = input.Template,
            ["subject"] = input.Subject, ["customer_notes"] = input.CustomerNotes, ["terms"] = input.Terms,
            ["order_number"] = input.OrderNumber
        };
        if (input.PaymentMode is int mode)
        {
            using var command = RegisterCommand("SELECT mode.name FROM public.fam_payment_modes mode" +
                RecurringPaymentModeScope + " AND mode.id=@id FOR SHARE OF mode", db, tx, branch, actor);
            command.Parameters.AddWithValue("id", mode);
            metadata["payment_method"] = await command.ExecuteScalarAsync() is string name ? name
                : throw new InvalidOperationException("The selected expected payment mode is no longer available.");
            metadata["payment_mode_id"] = mode;
        }
        if (input.Salesperson is int salesperson)
        {
            using var command = RegisterCommand("SELECT u.email FROM public.users u" + RecurringSalespersonScope +
                " AND u.id=@id FOR SHARE OF u", db, tx, branch, actor);
            command.Parameters.AddWithValue("id", salesperson);
            metadata["salesperson_name"] = await command.ExecuteScalarAsync() is string name ? name
                : throw new InvalidOperationException("The selected salesperson is no longer available.");
            metadata["salesperson_id"] = salesperson;
        }
        return metadata;
    }
}
