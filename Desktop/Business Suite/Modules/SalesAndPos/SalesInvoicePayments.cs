using System.Data;
using System.Globalization;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record SalesPaymentIntent(Guid RequestId, decimal Amount, string Reference, string Method, DateTime ReceiptDate);
internal sealed class SalesPaymentRejectedException(string message) : InvalidOperationException(message);
internal sealed record SalesPaymentResult(int ReceiptId, string Number, decimal Outstanding, string Status, bool Reversed);

internal sealed partial class SalesOrderRepository
{
    private sealed record SalesPaymentState(string Status, decimal Balance, bool Issued, bool HasCustomer, bool NativeSeller);
    internal SalesIntentJournal<SalesPaymentIntent> PaymentJournal(int invoice) => new(settings, "Invoice payments",
        invoice.ToString(CultureInfo.InvariantCulture), ValidateSalesPayment,
        "A saved payment request could not be verified. Reconcile the invoice before entering another payment.");

    internal static void ValidateSalesPayment(SalesPaymentIntent intent)
    {
        if (intent.RequestId == Guid.Empty || intent.Amount <= 0 || intent.Amount > 99999999999m ||
            decimal.Round(intent.Amount, 2) != intent.Amount || intent.Reference is null || intent.Reference.Length > 120 ||
            intent.Method is not ("bank_transfer" or "upi" or "cash" or "card" or "cheque") ||
            intent.ReceiptDate == default || intent.ReceiptDate.TimeOfDay != TimeSpan.Zero)
            throw new ArgumentException("Enter a positive received amount to two decimal places, a payment method, a receipt date and a reference of up to 120 characters.");
    }

    internal Task<decimal?> CanRecordSalesPaymentAsync(int order, int invoice) => CanRecordInvoicePaymentAsync(order, invoice, null);

    internal Task<decimal?> CanRecordSalesMilestonePaymentAsync(int order, int invoice, SalesMilestoneInvoiceLink milestone) =>
        CanRecordInvoicePaymentAsync(order, invoice, milestone);

    private async Task<decimal?> CanRecordInvoicePaymentAsync(int order, int invoice, SalesMilestoneInvoiceLink? milestone)
    {
        if (settings.BranchId is not int branch)
            return null;
        try
        {
            using var db = new NpgsqlConnection(settings.ConnectionString);
            await db.OpenAsync();
            using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
            using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
                await readOnly.ExecuteNonQueryAsync();
            var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
            string scope = await SalesPaymentScopeAsync(db, tx, branch, actor);
            var state = await ReadSalesPaymentStateAsync(db, tx, branch, actor, scope, order, invoice, false, milestone);
            if (state is not { Issued: true, HasCustomer: true, NativeSeller: true })
                return null;
            return state.Status == "cancelled" ? 0m : state.Balance;
        }
        catch (UnauthorizedAccessException)
        {
            return null;
        }
    }

    internal Task<SalesPaymentResult> RecordSalesPaymentAsync(int order, int invoice, SalesPaymentIntent intent) =>
        RecordInvoicePaymentAsync(order, invoice, intent, null);

    internal Task<SalesPaymentResult> RecordSalesMilestonePaymentAsync(int order, int invoice, SalesPaymentIntent intent,
        SalesMilestoneInvoiceLink milestone) => RecordInvoicePaymentAsync(order, invoice, intent, milestone);

    private async Task<SalesPaymentResult> RecordInvoicePaymentAsync(int order, int invoice, SalesPaymentIntent intent,
        SalesMilestoneInvoiceLink? milestone)
    {
        ValidateSalesPayment(intent);
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to record a payment.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await SalesPaymentScopeAsync(db, tx, branch, actor);
        var state = await ReadSalesPaymentStateAsync(db, tx, branch, actor, scope, order, invoice, true, milestone)
            ?? throw new InvalidOperationException("The linked invoice is unavailable in this branch.");
        var previous = await FindRecordedPaymentAsync(db, tx, branch, actor.Id, invoice, state, intent);
        if (previous is not null)
        {
            tx.Commit();
            return previous;
        }
        if (!state.Issued || !state.HasCustomer || !state.NativeSeller ||
            state.Status is not ("approved" or "issued" or "sent" or "overdue" or "partially_paid") || intent.Amount > state.Balance)
            throw new SalesPaymentRejectedException("Apply a positive payment within the issued invoice's outstanding balance.");
        string number = await ReserveCommercialNumberAsync(db, tx, CommercialNumberSeries.Receipt);
        var saved = await SaveSalesPaymentAsync(db, tx, branch, actor.Id, invoice, number, intent);
        tx.Commit();
        return saved;
    }

    private async Task<string> SalesPaymentScopeAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor)
    {
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "create", collection: true);
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "approve", collection: true);
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop invoice payments");
        return scope;
    }

    private async Task<SalesPaymentState?> ReadSalesPaymentStateAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        DesktopActor actor, string scope, int order, int invoice, bool lockRows, SalesMilestoneInvoiceLink? milestone = null)
    {
        using var query = ScopedCommand(@"
            SELECT coalesce(i.status,''),coalesce(i.balance_amount,0),
                i.approved_at IS NOT NULL AND EXISTS (
                    SELECT 1 FROM public.business_invoice_contexts c WHERE c.invoice_id=i.id AND c.issued_at IS NOT NULL
                        AND c.origin='srm' AND c.project_id IS NULL AND c.seller_id=@company),
                i.customer_id IS NOT NULL AND EXISTS (
                    SELECT 1 FROM public.crm_companies c " + OrderCustomerScope + @" AND c.id=i.customer_id),
                EXISTS (SELECT 1 FROM public.companies c WHERE c.id=@company AND c.is_active)
            " + (milestone is null ? LinkedOrderInvoiceScope : MilestoneInvoiceReadScope + MilestoneInvoiceLineProof) +
            @" AND i.id=@invoice AND i.customer_id IS NOT DISTINCT FROM d.customer_id
              AND i.currency=d.currency AND i.paid_amount>=0 AND i.balance_amount>=0
              AND (i.total_amount=i.paid_amount+i.balance_amount OR (i.status='cancelled' AND i.paid_amount=0 AND i.balance_amount=0))" +
            (lockRows ? milestone is null ? " FOR UPDATE OF o,i,d" : " FOR UPDATE OF o,e,b,m,i,d" : ""), db, tx, branch, actor, scope);
        BindInvoicePaymentSource(query, order, milestone);
        query.Parameters.AddWithValue("invoice", invoice);
        using var reader = await query.ExecuteReaderAsync();
        return await reader.ReadAsync() ? new SalesPaymentState(reader.GetString(0), reader.GetDecimal(1),
            reader.GetBoolean(2), reader.GetBoolean(3), reader.GetBoolean(4)) : null;
    }

    private static string MilestoneInvoiceLineProof => @" AND m.status='invoiced'
        AND (SELECT count(*)=1 AND bool_and(coalesce(l.source_type='billing_milestone'
            AND l.source_id=m.id AND " + ConfirmationOwnership("l", "srm_invoice_lines") + @",false))
            FROM public.srm_invoice_lines l WHERE l.invoice_id=i.id)";

    private static void BindInvoicePaymentSource(NpgsqlCommand query, int order, SalesMilestoneInvoiceLink? milestone)
    {
        if (milestone is null)
            query.Parameters.AddWithValue("order", order);
        else
        {
            BindBillingMilestoneChain(query, order, milestone.Engagement, milestone.Plan);
            query.Parameters.AddWithValue("milestone", milestone.Milestone);
        }
    }

    private async Task<SalesPaymentResult?> FindRecordedPaymentAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        int actor, int invoice, SalesPaymentState state, SalesPaymentIntent intent)
    {
        using var query = RegisterCommand(@"
            SELECT r.id,r.receipt_number,c.reversed_at IS NOT NULL,
                   r.organization_id=@company AND c.seller_id=@company AND " + ConfirmationOwnership("r", "srm_receipts") + @",
                   r.amount=@amount AND coalesce(r.reference_number,'')=@reference AND r.payment_method=@method AND r.receipt_date=@date
            FROM public.business_receipt_contexts c JOIN public.srm_receipts r ON r.id=c.receipt_id
            WHERE c.invoice_id=@invoice AND c.request_id=@request", db, tx, branch, actor);
        BindPayment(query, invoice, intent);
        using var reader = await query.ExecuteReaderAsync();
        if (!await reader.ReadAsync())
            return null;
        if (reader.IsDBNull(3) || !reader.GetBoolean(3))
            throw new UnauthorizedAccessException("The saved receipt is outside this branch.");
        if (reader.IsDBNull(4) || !reader.GetBoolean(4))
            throw new InvalidOperationException("This payment request was already used with different details.");
        return new SalesPaymentResult(reader.GetInt32(0), reader.GetString(1), state.Balance, state.Status, reader.GetBoolean(2));
    }

    private static void BindPayment(NpgsqlCommand command, int invoice, SalesPaymentIntent intent)
    {
        command.Parameters.AddWithValue("invoice", invoice);
        command.Parameters.AddWithValue("request", intent.RequestId.ToString());
        command.Parameters.AddWithValue("amount", intent.Amount);
        command.Parameters.AddWithValue("reference", intent.Reference);
        command.Parameters.AddWithValue("method", intent.Method);
        command.Parameters.AddWithValue("date", NpgsqlDbType.Date, intent.ReceiptDate);
    }
}
