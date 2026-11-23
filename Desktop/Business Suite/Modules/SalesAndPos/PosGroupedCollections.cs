using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PosOutstandingInvoice(int CheckoutId, int Revision, string Invoice, string Customer, string Currency,
    decimal Total, decimal Paid, decimal Outstanding);
internal sealed record PosCollectionList(int SessionId, string Register, string Currency, List<PosOutstandingInvoice> Invoices);
internal sealed record PosLaterPaymentIntent(Guid Key, int CheckoutId, int Revision, int SessionId, string Method,
    decimal Amount, string? Reference);
internal sealed record PosCollectedPayment(string Receipt, decimal Outstanding);

internal sealed partial class SalesOrderRepository
{
    private sealed record PosInvoicePaymentState(int InvoiceId, int Buyer, int Revision, string Currency, decimal Balance, string Status);

    internal SalesIntentJournal<PosLaterPaymentIntent> PosCollectionJournal() =>
        new(settings, "POS invoice collections", "", ValidatePosLaterPayment,
            "The saved POS payment could not be verified. Reconcile the checkout before entering another payment.");

    private static void ValidatePosLaterPayment(PosLaterPaymentIntent intent)
    {
        if (intent.Key == Guid.Empty || intent.CheckoutId <= 0 || intent.Revision <= 0 || intent.SessionId <= 0 ||
            intent.Method is not ("cash" or "card" or "upi" or "bank_transfer") || intent.Amount <= 0 ||
            intent.Amount > 99999999999m || decimal.Round(intent.Amount, 2) != intent.Amount ||
            intent.Reference is { } reference && (reference.Length > 120 || reference.IndexOf('\0') >= 0))
            throw new ArgumentException("Choose an invoice and enter a positive received amount to two decimal places, a payment method, and an optional reference.");
    }

    private const string GroupedPosSalesJoins = @"
        FROM public.srm_pos_service_checkouts g
        JOIN public.srm_sales_orders o ON o.id=g.sales_order_id AND o.customer_id=g.customer_id AND o.currency=g.currency
        JOIN public.srm_invoices i ON i.id=g.invoice_id AND i.sales_order_id=o.id AND i.customer_id=g.customer_id AND i.currency=g.currency
        JOIN public.srm_pos_sessions origin ON origin.id=g.pos_session_id AND origin.organization_id=@company
        JOIN public.business_invoice_contexts ctx ON ctx.invoice_id=i.id AND ctx.seller_id=@company
            AND ctx.origin='srm' AND ctx.project_id IS NULL AND ctx.issued_at IS NOT NULL
        JOIN public.crm_companies c ON c.id=g.customer_id ";

    private static readonly string GroupedPosSalesPolicy = OrderScope + @"
        AND g.organization_id=@company AND g.branch_id=@branch AND g.pack_context_id IS NULL AND g.scope_context_key=0
        AND g.state='committed' AND g.billing_mode='invoice_at_checkout'
        AND o.metadata_json->>'source'='pos'
        AND i.organization_id=@company AND i.deleted_at IS NULL AND i.approved_at IS NOT NULL
        AND c.organization_id=@company AND c.deleted_at IS NULL
        AND (EXISTS (SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company AND b.branch_id=@branch
                AND b.resource_table='crm_companies' AND b.resource_key=c.id::text)
            OR EXISTS (SELECT 1 FROM public.suite_branch_record_shares b WHERE b.company_id=@company AND b.branch_id=@branch
                AND b.resource_table='crm_companies' AND b.resource_key=c.id::text))
        AND NOT EXISTS (SELECT 1 FROM public.business_pack_record_ownership b WHERE b.company_id=@company
            AND b.resource_table='crm_companies' AND b.resource_key=c.id::text)
        AND i.total_amount=i.paid_amount+i.balance_amount AND i.paid_amount>=0 AND i.balance_amount>=0
        AND EXISTS (SELECT 1 FROM public.srm_pos_checkout_lines m WHERE m.checkout_id=g.id)
        AND NOT EXISTS (SELECT 1 FROM public.srm_pos_checkout_lines m
            LEFT JOIN public.srm_sales_order_lines l ON l.id=m.sales_order_line_id
            LEFT JOIN public.srm_invoice_lines charge ON charge.id=m.invoice_line_id
            WHERE m.checkout_id=g.id AND NOT coalesce(m.organization_id=@company AND m.branch_id=@branch AND m.scope_context_key=0
                AND m.line_kind='product' AND coalesce(l.metadata_json->>'offering_kind','') NOT IN ('membership','subscription')
                AND l.sales_order_id=o.id AND l.product_id=m.product_id AND charge.invoice_id=i.id
                AND charge.source_type='sales_order_line' AND charge.source_id=l.id
                AND m.quantity=l.quantity AND m.quantity=charge.quantity AND m.line_total=l.line_total AND m.line_total=charge.line_total
                AND " + ConfirmationOwnership("m", "srm_pos_checkout_lines") + " AND " +
                ConfirmationOwnership("l", "srm_sales_order_lines") + " AND " + ConfirmationOwnership("charge", "srm_invoice_lines") + @",false))
        AND NOT EXISTS (SELECT 1 FROM public.srm_invoice_lines charge WHERE charge.invoice_id=i.id AND NOT EXISTS (
            SELECT 1 FROM public.srm_pos_checkout_lines m WHERE m.checkout_id=g.id AND m.invoice_line_id=charge.id))
        AND NOT EXISTS (SELECT 1 FROM public.srm_pos_checkout_payments m LEFT JOIN public.srm_receipts saved ON saved.id=m.receipt_id
            WHERE m.checkout_id=g.id AND NOT coalesce(m.organization_id=@company AND m.branch_id=@branch AND m.scope_context_key=0
                AND saved.organization_id=@company AND saved.customer_id=g.customer_id AND saved.currency=g.currency AND saved.amount>0
                AND " + ConfirmationOwnership("m", "srm_pos_checkout_payments") + " AND " + ConfirmationOwnership("saved", "srm_receipts") + @"
                AND EXISTS (SELECT 1 FROM public.srm_receipt_allocations a WHERE a.receipt_id=saved.id AND a.invoice_id=i.id
                    AND a.amount=saved.amount AND a.request_id=m.payment_key AND " + ConfirmationOwnership("a", "srm_receipt_allocations") + @"),false))
        AND " + ConfirmationOwnership("g", "srm_pos_service_checkouts") + " AND " +
        ConfirmationOwnership("i", "srm_invoices") + " AND " + ConfirmationOwnership("origin", "srm_pos_sessions");

    private const string GroupedPosNamedBuyer = @"
        AND NOT EXISTS (SELECT 1 FROM public.srm_anonymous_cash_accounts a WHERE a.customer_id=g.customer_id)";

    private static readonly string GroupedPosVerifiedSalesScope = GroupedPosSalesJoins + GroupedPosSalesPolicy;
    private static readonly string GroupedPosInvoiceScope = GroupedPosVerifiedSalesScope + GroupedPosNamedBuyer;

    internal async Task<PosCollectionList> ListGroupedPosOutstandingAsync(string search)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to collect POS invoice payments.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await RequireGroupedCollectionAsync(db, tx, branch, actor);
        var active = await FindActiveRegisterAsync(db, tx, branch, actor.Id)
            ?? throw new InvalidOperationException("Open the receiving register before collecting a payment.");
        int session;
        using (var register = RegisterQuery(@"SELECT p.id FROM public.srm_pos_sessions p" + OwnSession +
            " AND p.status='open'", db, tx, branch, actor.Id, active.Number))
            session = (int)(await register.ExecuteScalarAsync())!;

        using var query = ScopedCommand(@"SELECT g.id,g.revision,i.invoice_number,c.name,g.currency,
            i.total_amount,i.paid_amount,i.balance_amount " + GroupedPosInvoiceScope + @"
            AND i.status IN ('approved','issued','sent','overdue','partially_paid') AND i.balance_amount>0 AND g.currency=@currency
            AND (@search='' OR strpos(lower(i.invoice_number),lower(@search))>0 OR strpos(lower(c.name),lower(@search))>0)
            ORDER BY g.id DESC LIMIT 100", db, tx, branch, actor, scope);
        query.Parameters.AddWithValue("search", search.Trim());
        query.Parameters.AddWithValue("currency", active.Currency);
        var rows = new List<PosOutstandingInvoice>();
        using (var reader = await query.ExecuteReaderAsync())
            while (await reader.ReadAsync())
                rows.Add(new PosOutstandingInvoice(reader.GetInt32(0), reader.GetInt32(1), reader.GetString(2), reader.GetString(3),
                    reader.GetString(4), reader.GetDecimal(5), reader.GetDecimal(6), reader.GetDecimal(7)));
        tx.Commit();
        return new PosCollectionList(session, active.Number, active.Currency, rows);
    }

    private async Task<string> RequireGroupedCollectionAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor)
    {
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop grouped POS collections");
        await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "create", collection: true);
        return await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "approve", collection: true);
    }

    internal async Task<PosCollectedPayment> CollectGroupedPosPaymentAsync(PosLaterPaymentIntent intent)
    {
        ValidatePosLaterPayment(intent);
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to collect POS invoice payments.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await RequireGroupedCollectionAsync(db, tx, branch, actor);
        var state = await LockGroupedPosInvoiceAsync(db, tx, branch, actor, scope, intent.CheckoutId);
        string digest = PosTenderDigest(intent.Key, intent.Method, intent.Reference, intent.Amount, intent.SessionId);
        var previous = await FindGroupedPosPaymentAsync(db, tx, branch, actor.Id, intent, state, digest);
        if (previous is not null)
        {
            tx.Commit();
            return previous;
        }
        if (state.Revision != intent.Revision)
            throw new PosCheckoutRejectedException("The checkout revision changed. Refresh the amount due before recording a payment.");
        if (state.Status is not ("approved" or "issued" or "sent" or "overdue" or "partially_paid") || intent.Amount > state.Balance)
            throw new PosCheckoutRejectedException("Apply a positive payment within the issued invoice's outstanding balance.");

        string number;
        using (var register = RegisterCommand(@"SELECT p.session_number FROM public.srm_pos_sessions p
            WHERE p.id=@session AND p.organization_id=@company AND p.cashier_user_id=@actor AND p.status='open'
            AND p.deleted_at IS NULL AND p.metadata_json->>'cash_currency'=@currency
            AND " + ConfirmationOwnership("p", "srm_pos_sessions") + " FOR UPDATE OF p", db, tx, branch, actor.Id))
        {
            register.Parameters.AddWithValue("session", intent.SessionId);
            register.Parameters.AddWithValue("currency", state.Currency);
            number = await register.ExecuteScalarAsync() as string
                ?? throw new PosCheckoutRejectedException("Use an active receiving register in the checkout currency.");
        }
        if (intent.Method == "cash")
        {
            var drawer = await ReadCashSnapshotAsync(db, tx, branch, actor.Id, number);
            if (drawer.Currency != state.Currency || drawer.Expected + intent.Amount > MaximumOpeningCash)
                throw new PosCheckoutRejectedException("The receiving register needs currency or cash reconciliation.");
        }
        string receipt = await ReserveCommercialNumberAsync(db, tx, CommercialNumberSeries.Receipt);
        decimal balance = await SaveGroupedPosTenderAsync(db, tx, branch, actor.Id, intent.CheckoutId, state.InvoiceId,
            state.Buyer, intent.SessionId, state.Currency, receipt, intent.Key, intent.Method, intent.Reference, intent.Amount, digest);
        using var version = RegisterCommand(@"UPDATE public.srm_pos_service_checkouts SET revision=revision+1,updated_at=now()
            WHERE id=@checkout AND organization_id=@company AND branch_id=@branch AND pack_context_id IS NULL AND revision=@revision",
            db, tx, branch, actor.Id);
        version.Parameters.AddWithValue("checkout", intent.CheckoutId);
        version.Parameters.AddWithValue("revision", intent.Revision);
        if (await version.ExecuteNonQueryAsync() != 1)
            throw new InvalidOperationException("The checkout changed before the payment could be recorded.");
        tx.Commit();
        return new PosCollectedPayment(receipt, balance);
    }

    private async Task<PosInvoicePaymentState> LockGroupedPosInvoiceAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, DesktopActor actor, string scope, int checkout)
    {
        using var query = ScopedCommand(@"SELECT i.id,g.customer_id,g.revision,g.currency,i.balance_amount,i.status " +
            GroupedPosInvoiceScope + " AND g.id=@checkout FOR UPDATE OF g,i", db, tx, branch, actor, scope);
        query.Parameters.AddWithValue("checkout", checkout);
        using var reader = await query.ExecuteReaderAsync();
        if (!await reader.ReadAsync())
            throw new InvalidOperationException("The grouped invoice is unavailable in this branch.");
        return new PosInvoicePaymentState(reader.GetInt32(0), reader.GetInt32(1), reader.GetInt32(2), reader.GetString(3),
            reader.GetDecimal(4), reader.GetString(5));
    }

    private async Task<PosCollectedPayment?> FindGroupedPosPaymentAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        int actor, PosLaterPaymentIntent intent, PosInvoicePaymentState state, string digest)
    {
        using var query = RegisterCommand(@"SELECT r.receipt_number,coalesce(p.request_sha256=@digest AND p.collection_session_id=@session
            AND p.scope_context_key=0 AND p.organization_id=@company AND p.branch_id=@branch AND r.organization_id=@company
            AND r.created_by=@actor AND r.customer_id=@buyer AND r.currency=@currency AND r.amount=@amount AND r.payment_method=@method
            AND r.reference_number IS NOT DISTINCT FROM @reference AND
            " + ConfirmationOwnership("p", "srm_pos_checkout_payments") + " AND " + ConfirmationOwnership("r", "srm_receipts") + @"
            AND EXISTS (SELECT 1 FROM public.srm_receipt_allocations a WHERE a.receipt_id=r.id AND a.invoice_id=@invoice
                AND a.request_id=p.payment_key AND a.amount=r.amount AND " + ConfirmationOwnership("a", "srm_receipt_allocations") + @"),false)
            FROM public.srm_pos_checkout_payments p JOIN public.srm_receipts r ON r.id=p.receipt_id
            WHERE p.checkout_id=@checkout AND p.payment_key=@key", db, tx, branch, actor);
        query.Parameters.AddWithValue("checkout", intent.CheckoutId);
        query.Parameters.AddWithValue("key", intent.Key.ToString());
        query.Parameters.AddWithValue("digest", digest);
        query.Parameters.AddWithValue("session", intent.SessionId);
        query.Parameters.AddWithValue("buyer", state.Buyer);
        query.Parameters.AddWithValue("currency", state.Currency);
        query.Parameters.AddWithValue("amount", intent.Amount);
        query.Parameters.AddWithValue("method", intent.Method);
        query.Parameters.AddWithValue("reference", NpgsqlDbType.Text, (object?)intent.Reference ?? DBNull.Value);
        query.Parameters.AddWithValue("invoice", state.InvoiceId);
        using var reader = await query.ExecuteReaderAsync();
        if (!await reader.ReadAsync())
            return null;
        if (!reader.GetBoolean(1))
            throw new InvalidOperationException("The payment key was already used with different details or an inaccessible receipt.");
        return new PosCollectedPayment(reader.GetString(0), state.Balance);
    }
}
