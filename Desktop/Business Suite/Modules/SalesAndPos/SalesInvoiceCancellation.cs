using System.Data;
using Npgsql;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    internal Task<bool> CanCancelLinkedInvoiceAsync(int order, int invoice) => CanCancelInvoiceSourceAsync(order, invoice, null);

    internal Task<bool> CanCancelSalesMilestoneInvoiceAsync(int order, int invoice, SalesMilestoneInvoiceLink milestone) =>
        CanCancelInvoiceSourceAsync(order, invoice, milestone);

    private async Task<bool> CanCancelInvoiceSourceAsync(int order, int invoice, SalesMilestoneInvoiceLink? milestone)
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
            string scope = await InvoiceCancellationScopeAsync(db, tx, branch, actor);
            var state = await ReadInvoiceCancellationStateAsync(db, tx, branch, actor, scope, order, invoice, lockRow: false, milestone);
            return state is not null && state.Status != "cancelled";
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    internal Task CancelLinkedInvoiceAsync(int order, int invoice, string reason) => CancelInvoiceSourceAsync(order, invoice, reason, null);

    internal Task CancelSalesMilestoneInvoiceAsync(int order, int invoice, string reason, SalesMilestoneInvoiceLink milestone) =>
        CancelInvoiceSourceAsync(order, invoice, reason, milestone);

    private async Task CancelInvoiceSourceAsync(int order, int invoice, string reason, SalesMilestoneInvoiceLink? milestone)
    {
        string normalized = reason.Trim();
        if (order <= 0 || invoice <= 0 || normalized.Length is < 3 or > 500 || normalized.IndexOf('\0') >= 0)
            throw new ArgumentException("Enter a cancellation reason from 3 to 500 characters.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to cancel invoice documents.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await InvoiceCancellationScopeAsync(db, tx, branch, actor);
        var state = await ReadInvoiceCancellationStateAsync(db, tx, branch, actor, scope, order, invoice, lockRow: true, milestone)
            ?? throw new InvalidOperationException("This linked invoice is unavailable in the current branch.");
        if (state.Status == "cancelled")
        {
            tx.Commit();
            return;
        }
        if (state.Paid != 0 || state.LiveAllocation)
            throw new InvalidOperationException("Reverse applied payments through Accounting before cancellation.");
        if (state.UnreversedVoucher)
            throw new InvalidOperationException("Reverse the posted invoice voucher through Accounting before cancellation.");

        using var write = RegisterCommand(@"
            WITH cancelled AS (
                UPDATE public.srm_invoices SET status='cancelled',balance_amount=0,updated_at=now()
                WHERE id=@invoice AND organization_id=@company AND status=@previous
                RETURNING id
            ), history AS (
                INSERT INTO public.srm_invoice_history (invoice_id,from_status,to_status,actor_user_id,notes)
                SELECT id,@previous,'cancelled',@actor,@reason FROM cancelled RETURNING id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,before_json,after_json)
                SELECT @company,'invoice',id,'cancelled',@actor,json_build_object('status',@previous),
                    json_build_object('reason',@reason,'source_reservations','retained_for_finance_review')
                FROM cancelled RETURNING id
            )
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'srm_invoice_history',id::text,@company,@branch,'validated-write' FROM history
            UNION ALL SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit",
            db, tx, branch, actor.Id);
        write.Parameters.AddWithValue("invoice", invoice);
        write.Parameters.AddWithValue("previous", state.Status);
        write.Parameters.AddWithValue("reason", normalized);
        if (await write.ExecuteNonQueryAsync() != 2)
            throw new InvalidOperationException("The cancellation history and audit could not both be recorded.");
        tx.Commit();
    }

    private sealed record InvoiceCancellationState(string Status, decimal Paid, bool LiveAllocation, bool UnreversedVoucher);

    private async Task<string> InvoiceCancellationScopeAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor)
    {
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop invoice cancellation");
        return await SalesReadAccess.OrderScopeForPermissionsAsync(db, tx, settings.OrganizationId, branch, actor,
            "create", "srm_invoice_approve", "srm_admin");
    }

    private async Task<InvoiceCancellationState?> ReadInvoiceCancellationStateAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, DesktopActor actor, string scope, int order, int invoice, bool lockRow, SalesMilestoneInvoiceLink? milestone)
    {
        using var read = ScopedCommand(@"
            SELECT coalesce(i.status,''),coalesce(i.paid_amount,0),
                EXISTS (SELECT 1 FROM public.srm_receipt_allocations a
                    LEFT JOIN public.business_receipt_contexts c ON c.receipt_id=a.receipt_id
                        AND c.invoice_id=i.id AND c.seller_id=@company
                    WHERE a.invoice_id=i.id AND a.amount>0 AND c.reversed_at IS NULL),
                EXISTS (SELECT 1 FROM public.fam_srm_mapping m WHERE m.company_id=@company AND m.srm_record_type='invoice'
                        AND m.srm_record_id=i.id AND m.fam_record_type='voucher')
                AND NOT EXISTS (SELECT 1 FROM public.fam_srm_mapping m WHERE m.company_id=@company AND m.srm_record_type='invoice'
                        AND m.srm_record_id=i.id AND m.fam_record_type='reversal_voucher')
            " + (milestone is null ? LinkedOrderInvoiceScope : MilestoneInvoiceReadScope) + @"
            AND i.id=@invoice
            AND NOT EXISTS (SELECT 1 FROM public.business_invoice_contexts c WHERE c.invoice_id=i.id
                AND (c.project_id IS NOT NULL OR c.origin<>'srm'))" +
            (milestone is null ? "" : MilestoneInvoiceLineProof) +
            (lockRow ? milestone is null ? " FOR UPDATE OF o,i,d" : " FOR UPDATE OF o,e,b,m,i,d" : ""),
            db, tx, branch, actor, scope);
        BindInvoicePaymentSource(read, order, milestone);
        read.Parameters.AddWithValue("invoice", invoice);
        using var reader = await read.ExecuteReaderAsync();
        return await reader.ReadAsync() ? new InvoiceCancellationState(reader.GetString(0), reader.GetDecimal(1),
            reader.GetBoolean(2), reader.GetBoolean(3)) : null;
    }
}
