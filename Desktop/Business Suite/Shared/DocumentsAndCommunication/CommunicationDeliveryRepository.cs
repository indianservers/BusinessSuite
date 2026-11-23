using Npgsql;

namespace Business_Suite;

internal sealed record CommunicationDeliveryRow(string Record, string Channel, string Provider, string Status,
    DateTime? Created, string Detail, int? ReminderId = null);

internal sealed class CommunicationDeliveryRepository(DesktopDatabaseSettings settings)
{
    internal Task<List<CommunicationDeliveryRow>> ListAsync(string search, bool issuesOnly) =>
        ListFilteredAsync(search, issuesOnly, "", "");

    internal async Task<List<CommunicationDeliveryRow>> ListFilteredAsync(string search, bool issuesOnly, string channel, string status)
    {
        int branch = settings.BranchId ?? throw new InvalidOperationException("Choose a branch to view delivery history.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var transaction = db.BeginTransaction(System.Data.IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, transaction, CancellationToken.None);
        var grant = await DesktopModuleAccess.RequireAsync(db, transaction, settings.OrganizationId, branch, actor,
            "communication", "view", "communication_logs_view", "communication_view");
        if (grant.Scope is not ("organization" or "branch"))
            throw new UnauthorizedAccessException("Delivery history requires branch-wide or organization-wide access.");

        bool canReadCustomerDeliveries;
        try
        {
            var customerGrant = await DesktopModuleAccess.RequireAsync(db, transaction, settings.OrganizationId,
                branch, actor, "communication", "view", "communication_view");
            canReadCustomerDeliveries = customerGrant.Scope is "organization" or "branch";
        }
        catch (UnauthorizedAccessException)
        {
            canReadCustomerDeliveries = false;
        }

        using var command = new NpgsqlCommand(@"
            WITH visible AS (
                SELECT log.id, 'Delivery record #' || log.id AS record, log.channel, log.provider, log.status,
                       log.created_at, COALESCE(log.error_message, '') AS detail, 0 AS source
                FROM public.communication_delivery_logs log
                LEFT JOIN public.communication_email_messages email
                    ON log.channel='email' AND email.id=log.related_message_id
                    AND email.organization_id=@company
                WHERE log.organization_id=@company
                  AND EXISTS (SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company
                      AND b.branch_id=@branch AND b.resource_table='communication_delivery_logs'
                      AND b.resource_key=log.id::text)
                  AND (log.channel<>'email' OR (email.id IS NOT NULL
                      AND email.related_record_type IS DISTINCT FROM 'srm_invoice'
                      AND EXISTS (SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company
                          AND b.branch_id=@branch AND b.resource_table='communication_email_messages'
                          AND b.resource_key=email.id::text)))
                UNION ALL
                SELECT d.id, COALESCE(NULLIF(d.subject, ''), 'Customer delivery #' || d.id), d.channel,
                       'Customer delivery', d.status, d.created_at,
                       concat_ws(E'\n\n', NULLIF(d.error, ''), NULLIF(d.body, '')), 1
                FROM public.communication_customer_deliveries d
                JOIN public.communication_customer_recipients r ON r.id=d.recipient_id
                    AND r.organization_id=d.organization_id AND r.branch_id=d.branch_id
                WHERE @customer AND d.organization_id=@company AND d.branch_id=@branch
            )
            SELECT record, channel, provider, status, created_at, detail FROM visible
            WHERE (NOT @issues OR status IN ('failed','blocked','reconciliation_required'))
                AND (@channel='' OR channel=@channel)
                AND (@status='' OR status=@status)
                AND (@search='' OR strpos(lower(concat_ws(' ', record, channel, provider, status, detail)), lower(@search))>0)
            ORDER BY created_at DESC NULLS LAST, source, id DESC LIMIT 250", db, transaction);
        command.Parameters.AddWithValue("company", settings.OrganizationId);
        command.Parameters.AddWithValue("branch", branch);
        command.Parameters.AddWithValue("customer", canReadCustomerDeliveries);
        command.Parameters.AddWithValue("issues", issuesOnly);
        command.Parameters.AddWithValue("search", search.Trim());
        command.Parameters.AddWithValue("channel", channel);
        command.Parameters.AddWithValue("status", status);
        using var reader = await command.ExecuteReaderAsync();
        var result = new List<CommunicationDeliveryRow>();
        while (await reader.ReadAsync())
            result.Add(new(reader.GetString(0), reader.GetString(1), reader.GetString(2), reader.GetString(3),
                reader.IsDBNull(4) ? null : reader.GetDateTime(4).ToLocalTime(), reader.GetString(5)));
        return result;
    }
}
