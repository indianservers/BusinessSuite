using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    internal Task<bool> CanApproveLinkedInvoiceAsync(int order, int invoice) => CanApproveInvoiceSourceAsync(order, invoice, null);

    internal Task<bool> CanApproveSalesMilestoneInvoiceAsync(int order, int invoice, SalesMilestoneInvoiceLink milestone) =>
        CanApproveInvoiceSourceAsync(order, invoice, milestone);

    private async Task<bool> CanApproveInvoiceSourceAsync(int order, int invoice, SalesMilestoneInvoiceLink? milestone)
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
            string scope = await InvoiceApprovalScopeAsync(db, tx, branch, actor);
            var state = await ReadInvoiceApprovalStateAsync(db, tx, branch, actor, scope, order, invoice, lockRow: false, milestone);
            return state is { Status: "draft" or "pending_approval", Issued: false };
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    internal Task ApproveLinkedInvoiceAsync(int order, int invoice) => ApproveInvoiceSourceAsync(order, invoice, null);

    internal Task ApproveSalesMilestoneInvoiceAsync(int order, int invoice, SalesMilestoneInvoiceLink milestone) =>
        ApproveInvoiceSourceAsync(order, invoice, milestone);

    private async Task ApproveInvoiceSourceAsync(int order, int invoice, SalesMilestoneInvoiceLink? milestone)
    {
        if (order <= 0 || invoice <= 0)
            throw new ArgumentException("Select a linked invoice.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to approve this invoice.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await InvoiceApprovalScopeAsync(db, tx, branch, actor);
        var state = await ReadInvoiceApprovalStateAsync(db, tx, branch, actor, scope, order, invoice, lockRow: true, milestone)
            ?? throw new InvalidOperationException("This invoice is unavailable for approval in the active branch.");
        if (state.Status is not ("draft" or "pending_approval" or "approved"))
            throw new InvalidOperationException("Only a draft or pending invoice can be approved.");
        bool issued = state is { Status: "approved", Issued: true, HasSnapshot: true };
        if (issued && milestone is null)
        {
            tx.Commit();
            return;
        }
        if (!issued && (state.Issued || state.HasSnapshot))
            throw new InvalidOperationException("Existing invoice issue evidence is inconsistent. Review it before approving.");
        if (!state.HasCustomer)
            throw new InvalidOperationException("Link a shared customer before issuing the invoice.");

        string lineScope = milestone is not null ? "(l.source_type='billing_milestone' AND l.source_id=@milestone)" : @"
            ((l.source_type='sales_order' AND l.source_id=@order) OR
                (l.source_type='sales_order_line' AND EXISTS
                    (SELECT 1 FROM public.srm_sales_order_lines s WHERE s.id=l.source_id AND s.sales_order_id=@order AND " +
                        ConfirmationOwnership("s", "srm_sales_order_lines") + ")))";
        using (var items = RegisterCommand(@"SELECT " + ConfirmationOwnership("l", "srm_invoice_lines") + " AND " + lineScope +
            " FROM public.srm_invoice_lines l WHERE l.invoice_id=@invoice ORDER BY l.id FOR UPDATE OF l NOWAIT",
            db, tx, branch, actor.Id))
        {
            items.Parameters.AddWithValue("invoice", invoice);
            items.Parameters.AddWithValue("order", order);
            if (milestone is not null)
                items.Parameters.AddWithValue("milestone", milestone.Milestone);
            using var reader = await items.ExecuteReaderAsync();
            if (!await reader.ReadAsync())
                throw new InvalidOperationException("The invoice requires at least one saved line.");
            int count = 0;
            do
            {
                if (reader.IsDBNull(0) || !reader.GetBoolean(0))
                    throw new InvalidOperationException("This invoice includes a revision, specialized billing source, or inaccessible line.");
                count++;
            } while (await reader.ReadAsync());
            if (milestone is not null && count != 1)
                throw new InvalidOperationException("The milestone invoice must contain its one reserved source line.");
        }

        if (issued)
        {
            tx.Commit();
            return;
        }
        string terms = await ResolveInvoiceTerminologyAsync(db, tx, branch, actor.Id);
        await SaveInvoiceIssueAsync(db, tx, branch, actor.Id, invoice, state.Status, terms);
        tx.Commit();
    }

    private sealed record InvoiceApprovalState(string Status, bool Issued, bool HasSnapshot, bool HasCustomer);

    internal async Task ApproveAppointmentInvoiceInTransactionAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        int branch,int actor,int appointment,int invoice,CancellationToken cancellation)
    {
        InvoiceApprovalState state;
        using (var query = RegisterCommand(@"SELECT coalesce(i.status,''),i.approved_at IS NOT NULL,
                c.issued_at IS NOT NULL,i.customer_id IS NOT NULL
            FROM public.srm_industry_records a JOIN public.srm_invoices i ON i.id=a.invoice_id
            JOIN public.srm_invoice_drafts d ON d.id=i.invoice_draft_id
            JOIN public.business_invoice_contexts c ON c.invoice_id=i.id
            WHERE a.id=@appointment AND a.organization_id=@company AND a.branch_id=@branch AND a.kind='appointment'
                AND a.status='completed' AND i.id=@invoice AND i.organization_id=@company AND i.deleted_at IS NULL
                AND i.customer_id=a.customer_id AND (d.customer_id IS NULL OR i.customer_id=d.customer_id) AND i.currency=d.currency
                AND (a.data->>'currency')=i.currency AND d.organization_id=@company AND d.source_type='industry_appointment'
                AND i.sales_order_id IS NULL AND i.engagement_id IS NULL AND d.sales_order_id IS NULL AND d.engagement_id IS NULL
                AND c.seller_id=@company AND c.origin='srm' AND c.request_id='industry:'||a.id::text
                AND c.project_id IS NOT DISTINCT FROM a.project_id
                AND NOT EXISTS (SELECT 1 FROM public.srm_pos_service_occurrences p WHERE p.appointment_id=a.id)
                AND NOT EXISTS (SELECT 1 FROM public.business_pack_record_ownership b
                    WHERE b.resource_table='srm_industry_records' AND b.resource_key=a.id::text)
                AND " + AppointmentApprovalOwnership("i","srm_invoices") + " AND " + AppointmentApprovalOwnership("d","srm_invoice_drafts") +
                " FOR UPDATE OF a,i,d,c",db,tx,branch,actor))
        {
            query.Parameters.AddWithValue("invoice",invoice);
            query.Parameters.AddWithValue("appointment",appointment);
            using var row=await query.ExecuteReaderAsync(cancellation);
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("The appointment invoice is unavailable for approval in this branch.");
            state = new InvoiceApprovalState(row.GetString(0),row.GetBoolean(1),row.GetBoolean(2),row.GetBoolean(3));
        }
        if (state is { Status: "approved", Issued: true, HasSnapshot: true })
            return;
        if (state.Status is not ("draft" or "pending_approval") || state.Issued || state.HasSnapshot || !state.HasCustomer)
            throw new InvalidOperationException("Only a draft or pending appointment invoice with consistent issue evidence can be approved.");
        using (var line = RegisterCommand(@"SELECT " + AppointmentApprovalOwnership("l","srm_invoice_lines") + @"
            AND l.source_type='industry_appointment' AND l.source_id=@appointment
            FROM public.srm_invoice_lines l WHERE l.invoice_id=@invoice FOR UPDATE OF l NOWAIT",db,tx,branch,actor))
        {
            line.Parameters.AddWithValue("invoice",invoice);
            line.Parameters.AddWithValue("appointment",appointment);
            using var row = await line.ExecuteReaderAsync(cancellation);
            if (!await row.ReadAsync(cancellation) || row.IsDBNull(0) || !row.GetBoolean(0) || await row.ReadAsync(cancellation))
                throw new InvalidOperationException("The appointment invoice must contain its one scoped service line.");
        }
        string terms = await ResolveInvoiceTerminologyAsync(db,tx,branch,actor);
        await SaveInvoiceIssueAsync(db,tx,branch,actor,invoice,state.Status,terms,appointment:appointment);
    }

    private static string AppointmentApprovalOwnership(string alias,string table) => $@"
        NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='{table}'
            AND o.resource_key={alias}.id::text AND (o.company_id<>@company OR o.branch_id<>@branch))
        AND NOT EXISTS (SELECT 1 FROM public.business_pack_record_ownership o
            WHERE o.resource_table='{table}' AND o.resource_key={alias}.id::text)";

    private async Task<string> InvoiceApprovalScopeAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor)
    {
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop sales invoice approval");
        return await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "approve");
    }

    private async Task<InvoiceApprovalState?> ReadInvoiceApprovalStateAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, DesktopActor actor, string scope, int order, int invoice, bool lockRow, SalesMilestoneInvoiceLink? milestone = null)
    {
        using var query = ScopedCommand(@"SELECT coalesce(i.status,''),i.approved_at IS NOT NULL,
            EXISTS (SELECT 1 FROM public.business_invoice_contexts ctx WHERE ctx.invoice_id=i.id AND ctx.seller_id=@company
                AND ctx.origin='srm' AND ctx.project_id IS NULL AND ctx.issued_at IS NOT NULL),
            i.customer_id IS NOT NULL " + (milestone is null ? LinkedOrderInvoiceScope : MilestoneInvoiceReadScope) +
            " AND i.id=@invoice AND i.customer_id IS NOT DISTINCT FROM d.customer_id AND i.currency=d.currency" +
            (milestone is null ? "" : " AND m.status='invoiced'") +
            (lockRow ? milestone is null ? " FOR UPDATE OF o,i,d" : " FOR UPDATE OF o,e,b,m,i,d" : ""), db, tx, branch, actor, scope);
        if (milestone is null)
            query.Parameters.AddWithValue("order", order);
        else
        {
            BindBillingMilestoneChain(query, order, milestone.Engagement, milestone.Plan);
            query.Parameters.AddWithValue("milestone", milestone.Milestone);
        }
        query.Parameters.AddWithValue("invoice", invoice);
        using var reader = await query.ExecuteReaderAsync();
        return await reader.ReadAsync()
            ? new InvoiceApprovalState(reader.GetString(0), reader.GetBoolean(1), reader.GetBoolean(2), reader.GetBoolean(3))
            : null;
    }

    private async Task SaveInvoiceIssueAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor,
        int invoice, string previous, string terms, AnonymousCheckoutBuyer? anonymous = null, int? appointment = null)
    {
        using var write = RegisterCommand(@"
            WITH parties AS (
                SELECT i.id,existing.contact_id,
                    jsonb_build_object('id',c.id,'name',c.name,'address',CASE WHEN billing.address IS NULL THEN c.address
                        ELSE concat_ws(', ',nullif(trim(billing.address->>'line1'),''),
                            nullif(trim(billing.address->>'line2'),''),nullif(trim(billing.address->>'city'),''),
                            nullif(trim(billing.address->>'state'),''),nullif(trim(billing.address->>'postalCode'),''),
                            nullif(trim(billing.address->>'country'),'')) END,
                        'city',coalesce(nullif(billing.address->>'city',''),c.city),
                        'state',coalesce(nullif(billing.address->>'state',''),c.state),
                        'country',coalesce(nullif(billing.address->>'country',''),c.country),'email',c.email,'phone',c.phone,
                        '_business_terms',@terms::jsonb) AS buyer,
                    jsonb_build_object('id',seller.id,'name',seller.name,'legal_name',seller.legal_name,'address',seller.address,
                        'gstin',seller.gstin,'email',seller.email,'phone',seller.phone) AS issuer,
                    CASE WHEN contact.id IS NULL THEN '{}'::jsonb ELSE
                        jsonb_build_object('id',contact.id,'name',contact.full_name,'email',contact.email) END AS contact
                FROM public.srm_invoices i
                JOIN public.crm_companies c ON c.id=i.customer_id
                JOIN public.companies seller ON seller.id=@company AND seller.is_active
                LEFT JOIN public.business_invoice_contexts existing ON existing.invoice_id=i.id
                LEFT JOIN public.crm_contacts contact ON contact.id=existing.contact_id AND contact.company_id=c.id
                    AND contact.organization_id=@company AND contact.deleted_at IS NULL AND " + ConfirmationOwnership("contact", "crm_contacts") + @"
                LEFT JOIN public.suite_company_master_details details ON details.account_id=c.id AND details.organization_id=@company
                LEFT JOIN LATERAL (
                    SELECT address FROM jsonb_array_elements(coalesce(details.addresses::jsonb,'[]'::jsonb))
                        WITH ORDINALITY saved(address,sort_order)
                    WHERE lower(address->>'type')='billing' ORDER BY sort_order LIMIT 1
                ) billing ON true
                " + (anonymous is null ? OrderCustomerScope : AnonymousInvoiceIssueScope) + @"
                AND i.id=@invoice AND i.organization_id=@company
                AND (existing.invoice_id IS NULL OR (existing.seller_id=@company AND existing.origin='srm'
                    AND ((@appointment IS NULL AND existing.project_id IS NULL)
                        OR (@appointment IS NOT NULL AND existing.request_id='industry:'||@appointment::text))
                    AND existing.issued_at IS NULL))
                AND (existing.contact_id IS NULL OR contact.id IS NOT NULL)
            ), snapshot AS (
                INSERT INTO public.business_invoice_contexts (invoice_id,seller_id,request_id,origin,contact_id,
                    customer_snapshot,seller_snapshot,contact_snapshot,issued_at)
                SELECT id,@company,@request,'srm',contact_id,buyer::json,issuer::json,contact::json,now() FROM parties
                ON CONFLICT (invoice_id) DO UPDATE SET customer_snapshot=excluded.customer_snapshot,
                    seller_snapshot=excluded.seller_snapshot,contact_snapshot=excluded.contact_snapshot,issued_at=excluded.issued_at
                WHERE business_invoice_contexts.seller_id=@company AND business_invoice_contexts.origin='srm'
                    AND ((@appointment IS NULL AND business_invoice_contexts.project_id IS NULL)
                        OR (@appointment IS NOT NULL AND business_invoice_contexts.request_id='industry:'||@appointment::text))
                    AND business_invoice_contexts.issued_at IS NULL
                    AND business_invoice_contexts.contact_id IS NOT DISTINCT FROM excluded.contact_id
                RETURNING invoice_id,issued_at
            ), approved AS (
                UPDATE public.srm_invoices i SET status='approved',approved_by=@actor,approved_at=snapshot.issued_at,updated_at=now()
                FROM snapshot WHERE i.id=snapshot.invoice_id AND i.organization_id=@company AND i.status=@previous
                    AND i.approved_at IS NULL RETURNING i.id
            ), history AS (
                INSERT INTO public.srm_invoice_history (invoice_id,from_status,to_status,actor_user_id)
                SELECT id,@previous,'approved',@actor FROM approved RETURNING id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,before_json,after_json)
                SELECT @company,'invoice',id,'approved',@actor,json_build_object('status',@previous),
                    json_build_object('status','approved') FROM approved RETURNING id
            ), ownership AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'srm_invoice_history',id::text,@company,@branch,'validated-write' FROM history
                UNION ALL SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit
            )
            SELECT id FROM approved", db, tx, branch, actor);
        write.Parameters.AddWithValue("invoice", invoice);
        write.Parameters.AddWithValue("appointment",NpgsqlDbType.Integer,(object?)appointment ?? DBNull.Value);
        if (anonymous is not null)
            write.Parameters.AddWithValue("cash_customer", anonymous.Id);
        write.Parameters.AddWithValue("previous", previous);
        write.Parameters.AddWithValue("request", Guid.NewGuid().ToString());
        write.Parameters.AddWithValue("terms", NpgsqlDbType.Jsonb, terms);
        if (await write.ExecuteScalarAsync() is not int)
            throw new InvalidOperationException("Review the invoice's customer, seller and billing contact before approving.");
    }
}
