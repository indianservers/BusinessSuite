using System.Data;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

internal sealed record NativeInvoicePdfData(LinkedSalesInvoiceDetails Details, bool Draft, decimal Subtotal, decimal Discount,
    decimal Tax, decimal Paid, decimal Balance, JsonElement Buyer, JsonElement Seller, JsonElement Defaults, JsonElement Terms);

internal sealed partial class SalesOrderRepository
{
    internal async Task<bool> CanExportLinkedInvoiceAsync()
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
            await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop sales invoice export");
            await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "export", invoiceView: true);
            return true;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    internal async Task<NativeInvoicePdfData> LoadLinkedInvoicePdfAsync(int order, int invoice)
    {
        return (await ReadOrderInvoiceAsync(order, includeLines: true, exportInvoice: invoice))?.Pdf
            ?? throw new InvalidOperationException("The linked invoice is unavailable for export in this branch.");
    }

    private async Task<NativeInvoicePdfData> ReadInvoicePdfLayoutAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        DesktopActor actor, LinkedSalesInvoiceDetails detail, bool allowProject = false)
    {
        using var query = RegisterCommand(@"
            SELECT coalesce(ctx.issued_at IS NOT NULL AND
                ((ctx.project_id IS NULL AND ctx.origin='srm') OR (@allow_project AND ctx.project_id IS NOT NULL AND ctx.origin='pms')),
                false) AND i.approved_at IS NOT NULL,
                coalesce(i.subtotal,0),coalesce(i.discount_amount,0),coalesce(i.tax_amount,0),
                coalesce(i.paid_amount,0),coalesce(i.balance_amount,0),coalesce(defaults.values_json::text,'{}'),
                coalesce(ctx.customer_snapshot::text,'{}'),coalesce(ctx.seller_snapshot::text,'{}'),
                i.approved_at IS NOT NULL,
                coalesce(json_build_object('id',seller.id,'name',seller.name,'legal_name',seller.legal_name,
                    'address',seller.address,'gstin',seller.gstin)::text,'{}'),
                CASE WHEN c.id IS NULL THEN '{}' ELSE json_build_object('id',c.id,'name',c.name,
                    'address',CASE WHEN billing.address IS NULL THEN c.address ELSE concat_ws(', ',
                        nullif(trim(billing.address->>'line1'),''),nullif(trim(billing.address->>'line2'),''),
                        nullif(trim(billing.address->>'city'),''),nullif(trim(billing.address->>'state'),''),
                        nullif(trim(billing.address->>'postalCode'),''),nullif(trim(billing.address->>'country'),'')) END)::text END,
                ctx.project_id, coalesce(ctx.origin,'srm'),
                coalesce(ctx.seller_id=@company AND d.source_type='pms_project'
                    AND d.organization_id=@company AND d.currency=i.currency
                    AND d.sales_order_id IS NOT DISTINCT FROM i.sales_order_id
                    AND d.engagement_id IS NOT DISTINCT FROM i.engagement_id AND
                    " + ConfirmationOwnership("d", "srm_invoice_drafts") + @",false),i.customer_id
            FROM public.srm_invoices i
            LEFT JOIN public.business_invoice_contexts ctx ON ctx.invoice_id=i.id
            LEFT JOIN public.srm_invoice_drafts d ON d.id=i.invoice_draft_id
            LEFT JOIN public.companies seller ON seller.id=@company
            LEFT JOIN public.suite_service_policies defaults ON defaults.scope_key='form-snapshot:'||@company||':srm:invoice:'||i.id
                AND defaults.organization_id=@company AND defaults.kind='form_snapshot'
            LEFT JOIN public.crm_companies c ON c.id=i.customer_id AND c.organization_id=@company AND c.deleted_at IS NULL
                AND (EXISTS (SELECT 1 FROM public.suite_branch_ownership owned WHERE owned.company_id=@company AND owned.branch_id=@branch
                    AND owned.resource_table='crm_companies' AND owned.resource_key=c.id::text)
                 OR EXISTS (SELECT 1 FROM public.suite_branch_record_shares shared WHERE shared.company_id=@company AND shared.branch_id=@branch
                    AND shared.resource_table='crm_companies' AND shared.resource_key=c.id::text))
                AND NOT EXISTS (SELECT 1 FROM public.srm_anonymous_cash_accounts cash WHERE cash.customer_id=c.id)
                AND NOT EXISTS (SELECT 1 FROM public.business_pack_record_ownership pack WHERE pack.company_id=@company
                    AND pack.resource_table='crm_companies' AND pack.resource_key=c.id::text)
            LEFT JOIN public.suite_company_master_details details ON details.account_id=c.id AND details.organization_id=@company
            LEFT JOIN LATERAL (
                SELECT address FROM jsonb_array_elements(coalesce(details.addresses::jsonb,'[]'::jsonb))
                    WITH ORDINALITY saved(address,sort_order)
                WHERE lower(address->>'type')='billing' ORDER BY sort_order LIMIT 1
            ) billing ON true
            WHERE i.id=@invoice AND i.organization_id=@company", db, tx, branch, actor.Id);
        query.Parameters.AddWithValue("invoice", detail.Invoice.Id);
        query.Parameters.AddWithValue("allow_project", allowProject);
        NativeInvoicePdfData data;
        int? project = null;
        using (var reader = await query.ExecuteReaderAsync())
        {
            if (!await reader.ReadAsync())
                throw new InvalidOperationException("The invoice is unavailable for export.");
            if (!reader.IsDBNull(12) || reader.GetString(13) == "pms")
            {
                if (!allowProject || reader.IsDBNull(12) || reader.GetString(13) != "pms" || !reader.GetBoolean(14))
                    throw new InvalidOperationException("The project invoice source could not be verified for export.");
                project = reader.GetInt32(12);
            }
            bool issued = reader.GetBoolean(0);
            if (!issued && (reader.GetBoolean(9) || detail.Invoice.Status is not ("draft" or "pending_approval")))
                throw new InvalidOperationException("The issued invoice snapshot is unavailable. Review it before exporting.");
            var buyer = ParseInvoiceJson(reader.GetString(issued ? 7 : 11));
            var seller = ParseInvoiceJson(reader.GetString(issued ? 8 : 10));
            if (issued && (!buyer.TryGetProperty("id", out _) || !seller.TryGetProperty("id", out _)))
                throw new InvalidOperationException("The issued invoice legal snapshots are incomplete.");
            if (issued && project.HasValue && (reader.IsDBNull(15) ||
                !MatchesInvoiceParty(buyer, reader.GetInt32(15)) || !MatchesInvoiceParty(seller, settings.OrganizationId)))
                throw new InvalidOperationException("The project invoice legal snapshots do not match its parties.");
            data = new NativeInvoicePdfData(detail, !issued, reader.GetDecimal(1), reader.GetDecimal(2),
                reader.GetDecimal(3), reader.GetDecimal(4), reader.GetDecimal(5), buyer, seller,
                ParseInvoiceJson(reader.GetString(6)), buyer.TryGetProperty("_business_terms", out var terms) ? terms : default);
        }
        if (project is int projectId)
            await PmsProjectRepository.RequireLinkedProjectVisibleAsync(settings, db, tx, actor, projectId, CancellationToken.None);
        return data.Draft ? data with { Terms = ParseInvoiceJson(await ResolveInvoiceTerminologyAsync(db, tx, branch, actor.Id)) } : data;
    }

    private static bool MatchesInvoiceParty(JsonElement party, int id) =>
        party.TryGetProperty("id", out var value) && value.ValueKind == JsonValueKind.Number &&
        value.TryGetInt32(out int partyId) && partyId == id;

    private static JsonElement ParseInvoiceJson(string json)
    {
        using var parsed = JsonDocument.Parse(json);
        if (parsed.RootElement.ValueKind != JsonValueKind.Object)
            throw new InvalidOperationException("The invoice presentation snapshot is invalid.");
        return parsed.RootElement.Clone();
    }
}
