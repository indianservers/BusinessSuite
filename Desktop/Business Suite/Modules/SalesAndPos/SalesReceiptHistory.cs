using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record SalesReceiptHistoryRow(int ReceiptId, string Number, decimal Amount, string Method, string Reference,
    DateTime? Date, DateTime? Applied, DateTime? Reversed, string Reason, bool CanReverse);
internal sealed record SalesReceiptHistory(string Currency, decimal Paid, decimal Outstanding, List<SalesReceiptHistoryRow> Rows);

internal sealed partial class SalesOrderRepository
{
    internal Task<SalesReceiptHistory> LoadSalesReceiptHistoryAsync(int order, int invoice) => LoadInvoiceReceiptHistoryAsync(order, invoice, null);

    internal Task<SalesReceiptHistory> LoadSalesMilestoneReceiptHistoryAsync(int order, int invoice, SalesMilestoneInvoiceLink milestone) =>
        LoadInvoiceReceiptHistoryAsync(order, invoice, milestone);

    private async Task<SalesReceiptHistory> LoadInvoiceReceiptHistoryAsync(int order, int invoice, SalesMilestoneInvoiceLink? milestone)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to view invoice payments.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop sales receipt history");
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "view", invoiceView: true);
        string currency;
        decimal paid;
        decimal balance;
        using (var header = ScopedCommand(@"SELECT i.currency,coalesce(i.paid_amount,0),coalesce(i.balance_amount,0)
            " + (milestone is null ? LinkedOrderInvoiceScope : MilestoneInvoiceReadScope + MilestoneInvoiceLineProof) +
            " AND i.id=@invoice", db, tx, branch, actor, scope))
        {
            BindInvoicePaymentSource(header, order, milestone);
            header.Parameters.AddWithValue("invoice", invoice);
            using var reader = await header.ExecuteReaderAsync();
            if (!await reader.ReadAsync())
                throw new InvalidOperationException("The invoice is unavailable in this branch.");
            currency = reader.GetString(0);
            paid = reader.GetDecimal(1);
            balance = reader.GetDecimal(2);
        }
        bool canReverse;
        try
        {
            await InvoiceApprovalScopeAsync(db, tx, branch, actor);
            canReverse = true;
        }
        catch (UnauthorizedAccessException)
        {
            canReverse = false;
        }

        using var query = RegisterCommand(@"
            SELECT r.id,r.receipt_number,coalesce(a.amount,0),coalesce(r.payment_method,''),coalesce(r.reference_number,''),
                r.receipt_date,a.allocated_at,c.reversed_at,coalesce(c.reversal_reason,''),coalesce(c.invoice_id=@invoice AND
                c.seller_id=@company AND c.reversed_at IS NULL AND c.request_id IS NOT NULL AND r.status='allocated' AND
                r.amount=a.amount AND 1=(SELECT count(*) FROM public.srm_receipt_allocations all_allocations WHERE all_allocations.receipt_id=r.id)
                AND " + NativeReceiptMappingClear + @",false)
            FROM public.srm_receipt_allocations a JOIN public.srm_receipts r ON r.id=a.receipt_id
            LEFT JOIN public.business_receipt_contexts c ON c.receipt_id=r.id AND c.seller_id=@company AND c.invoice_id=@invoice
            WHERE a.invoice_id=@invoice AND r.organization_id=@company
                AND " + ConfirmationOwnership("r", "srm_receipts") + " AND " + ConfirmationOwnership("a", "srm_receipt_allocations") + @"
            ORDER BY a.id DESC LIMIT 100", db, tx, branch, actor.Id);
        query.Parameters.AddWithValue("invoice", invoice);
        var rows = new List<SalesReceiptHistoryRow>();
        using (var reader = await query.ExecuteReaderAsync())
            while (await reader.ReadAsync())
            {
                rows.Add(new SalesReceiptHistoryRow(reader.GetInt32(0), reader.GetString(1), reader.GetDecimal(2),
                    reader.GetString(3).Replace('_', ' '), reader.GetString(4),
                    reader.IsDBNull(5) ? null : reader.GetDateTime(5), reader.IsDBNull(6) ? null : reader.GetDateTime(6),
                    reader.IsDBNull(7) ? null : reader.GetDateTime(7), reader.GetString(8), canReverse && reader.GetBoolean(9)));
            }
        tx.Commit();
        return new SalesReceiptHistory(currency, paid, balance, rows);
    }

    // The web finance path blocks any allocation posting and a voucher until its reversal voucher exists.
    // This predicate uses the receipt and allocation aliases already resolved under the selected invoice.
    private const string NativeReceiptMappingClear = @"
        NOT EXISTS (SELECT 1 FROM public.fam_srm_mapping m WHERE m.company_id=@company
            AND m.srm_record_type='allocation' AND m.srm_record_id=a.id)
        AND (NOT EXISTS (SELECT 1 FROM public.fam_srm_mapping m WHERE m.company_id=@company
            AND m.srm_record_type='receipt' AND m.srm_record_id=r.id AND m.fam_record_type='voucher')
            OR EXISTS (SELECT 1 FROM public.fam_srm_mapping m WHERE m.company_id=@company
            AND m.srm_record_type='receipt' AND m.srm_record_id=r.id AND m.fam_record_type='reversal_voucher'))";

    internal Task<SalesPaymentResult> ReverseSalesReceiptAsync(int order, int invoice, int receipt, string reason) =>
        ReverseInvoiceReceiptAsync(order, invoice, receipt, reason, null);

    internal Task<SalesPaymentResult> ReverseSalesMilestoneReceiptAsync(int order, int invoice, int receipt, string reason,
        SalesMilestoneInvoiceLink milestone) => ReverseInvoiceReceiptAsync(order, invoice, receipt, reason, milestone);

    private async Task<SalesPaymentResult> ReverseInvoiceReceiptAsync(int order, int invoice, int receipt, string reason,
        SalesMilestoneInvoiceLink? milestone)
    {
        string normalized = reason.Trim();
        if (order <= 0 || invoice <= 0 || receipt <= 0 || normalized.Length is < 3 or > 500 || normalized.IndexOf('\0') >= 0)
            throw new ArgumentException("Select a payment and enter a reversal reason from 3 to 500 characters.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to reverse invoice payments.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await InvoiceApprovalScopeAsync(db, tx, branch, actor);
        var invoiceState = await ReadSalesPaymentStateAsync(db, tx, branch, actor, scope, order, invoice, lockRows: true, milestone)
            ?? throw new InvalidOperationException("The linked invoice is unavailable in this branch.");
        using var query = RegisterCommand(@"
            SELECT r.receipt_number,c.reversed_at IS NOT NULL,
                r.amount=a.amount AND r.amount>0 AND r.unallocated_amount=0 AND r.status='allocated'
                AND i.customer_id IS NOT DISTINCT FROM r.customer_id AND i.currency=r.currency AND i.paid_amount>=r.amount,
                " + NativeReceiptMappingClear + @"
            FROM public.business_receipt_contexts c JOIN public.srm_receipts r ON r.id=c.receipt_id
            JOIN public.srm_invoices i ON i.id=c.invoice_id
            JOIN public.srm_receipt_allocations a ON a.receipt_id=r.id AND a.invoice_id=c.invoice_id
            WHERE c.invoice_id=@invoice AND c.receipt_id=@receipt AND c.seller_id=@company AND r.organization_id=@company
                AND c.request_id IS NOT NULL
                AND 1=(SELECT count(*) FROM public.srm_receipt_allocations all_allocations WHERE all_allocations.receipt_id=r.id)
                AND " + ConfirmationOwnership("r", "srm_receipts") + " AND " + ConfirmationOwnership("a", "srm_receipt_allocations") + @"
            FOR UPDATE OF c,r,a", db, tx, branch, actor.Id);
        query.Parameters.AddWithValue("invoice", invoice);
        query.Parameters.AddWithValue("receipt", receipt);
        string number;
        using (var reader = await query.ExecuteReaderAsync())
        {
            if (!await reader.ReadAsync())
                throw new InvalidOperationException("This payment is unavailable or requires legacy receipt reconciliation.");
            number = reader.GetString(0);
            if (reader.GetBoolean(1))
            {
                await reader.DisposeAsync();
                tx.Commit();
                return new SalesPaymentResult(receipt, number, invoiceState.Balance, invoiceState.Status, true);
            }
            if (!reader.GetBoolean(3))
                throw new InvalidOperationException("Reverse or reconcile the posted payment and allocation through Accounting first.");
            if (reader.IsDBNull(2) || !reader.GetBoolean(2) || !invoiceState.Issued || !invoiceState.NativeSeller ||
                invoiceState.Status is not ("paid" or "partially_paid"))
                throw new InvalidOperationException("The receipt and issued invoice balance must reconcile before reversing.");
        }

        var result = await SaveSalesReceiptReversalAsync(db, tx, branch, actor.Id, invoice, receipt, number, normalized);
        tx.Commit();
        return result;
    }

    private async Task<SalesPaymentResult> SaveSalesReceiptReversalAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, int actor, int invoice, int receipt, string number, string reason)
    {
        using var write = RegisterCommand(@"
            WITH reversal AS (
                UPDATE public.business_receipt_contexts SET reversed_at=now(),reversal_reason=@reason
                WHERE receipt_id=@receipt AND seller_id=@company AND invoice_id=@invoice AND reversed_at IS NULL
                RETURNING receipt_id,request_id
            ), cancelled AS (
                UPDATE public.srm_receipts r SET status='cancelled',unallocated_amount=0,updated_at=now()
                FROM reversal WHERE r.id=reversal.receipt_id AND r.organization_id=@company RETURNING r.id,r.amount
            ), invoice AS (
                UPDATE public.srm_invoices i SET paid_amount=i.paid_amount-cancelled.amount,
                    balance_amount=i.total_amount-i.paid_amount+cancelled.amount,
                    status=CASE WHEN i.paid_amount>cancelled.amount THEN 'partially_paid'
                        WHEN i.sent_at IS NOT NULL THEN 'sent' ELSE 'approved' END,updated_at=now()
                FROM cancelled WHERE i.id=@invoice AND i.organization_id=@company AND i.paid_amount>=cancelled.amount
                RETURNING i.id,i.status,i.currency,i.balance_amount,i.engagement_id
            ), revenue AS (
                INSERT INTO public.srm_revenue_events (organization_id,engagement_id,invoice_id,event_type,amount,currency,recognized_on)
                SELECT @company,invoice.engagement_id,invoice.id,'cash_reversed',-cancelled.amount,invoice.currency,@today
                FROM invoice CROSS JOIN cancelled RETURNING id
            ), history AS (
                INSERT INTO public.srm_invoice_history (invoice_id,to_status,actor_user_id,notes)
                SELECT id,status,@actor,'Receipt '||@receipt||' reversed: '||@reason FROM invoice RETURNING id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'receipt',receipt_id,'payment_reversed',@actor,
                    json_build_object('invoice_id',@invoice,'reason',@reason,'correlation_id',request_id)
                FROM reversal CROSS JOIN invoice RETURNING srm_audit_logs.id
            ), ownership AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT resource,id::text,@company,@branch,'validated-write' FROM (
                    SELECT 'srm_revenue_events' AS resource,id FROM revenue
                    UNION ALL SELECT 'srm_invoice_history',id FROM history UNION ALL SELECT 'srm_audit_logs',id FROM audit
                ) owned
            )
            SELECT balance_amount,status FROM invoice", db, tx, branch, actor);
        write.Parameters.AddWithValue("invoice", invoice);
        write.Parameters.AddWithValue("receipt", receipt);
        write.Parameters.AddWithValue("reason", reason);
        write.Parameters.AddWithValue("today", NpgsqlDbType.Date, DateTime.Today);
        using var reader = await write.ExecuteReaderAsync();
        if (!await reader.ReadAsync())
            throw new InvalidOperationException("The invoice or receipt changed before the reversal could be saved.");
        return new SalesPaymentResult(receipt, number, reader.GetDecimal(0), reader.GetString(1), true);
    }
}
