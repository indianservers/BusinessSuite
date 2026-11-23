using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    private async Task<PosCheckoutResult?> FindPosCheckoutAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, int actor, PosCheckoutIntent intent, string digest, int customerId, PosTenderAllocation allocation)
    {
        using var query = RegisterCommand(@"
            SELECT g.id,g.request_sha256,g.created_by,g.state,
                coalesce(g.customer_id=@customer AND g.created_by=@actor AND " + ConfirmationOwnership("g", "srm_pos_service_checkouts") + @"
                    AND p.id IS NOT NULL AND p.organization_id=@company AND p.cashier_user_id=@actor
                    AND p.session_number=@register AND " + ConfirmationOwnership("p", "srm_pos_sessions") + @"
                    AND o.id IS NOT NULL AND o.organization_id=@company AND o.customer_id=g.customer_id AND o.currency=g.currency
                    AND " + ConfirmationOwnership("o", "srm_sales_orders") + @"
                    AND i.id IS NOT NULL AND i.organization_id=@company AND i.sales_order_id=o.id
                    AND i.customer_id=g.customer_id AND i.currency=g.currency AND i.approved_at IS NOT NULL
                    AND " + ConfirmationOwnership("i", "srm_invoices") + @",false),
                o.order_number,i.invoice_number,i.total_amount,g.currency,i.balance_amount,p.id,i.id
            FROM public.srm_pos_service_checkouts g
            LEFT JOIN public.srm_pos_sessions p ON p.id=g.pos_session_id
            LEFT JOIN public.srm_sales_orders o ON o.id=g.sales_order_id
            LEFT JOIN public.srm_invoices i ON i.id=g.invoice_id
            WHERE g.organization_id=@company AND g.branch_id=@branch AND g.pack_context_id IS NULL AND g.request_id=@request
            FOR UPDATE OF g", db, tx, branch, actor);
        query.Parameters.AddWithValue("request", intent.Request.ToString());
        query.Parameters.AddWithValue("register", intent.Register);
        query.Parameters.AddWithValue("customer", customerId);
        int checkout;
        int session;
        int invoice;
        PosCheckoutResult result;
        using (var reader = await query.ExecuteReaderAsync())
        {
            if (!await reader.ReadAsync())
                return null;
            if (reader.GetInt32(2) != actor || !string.Equals(reader.GetString(1), digest, StringComparison.Ordinal))
                throw new InvalidOperationException("The checkout request key was already used with different details.");
            if (reader.GetString(3) != "committed" || !reader.GetBoolean(4))
                throw new InvalidOperationException("The saved checkout does not have complete register, order, and invoice proof.");
            checkout = reader.GetInt32(0);
            session = reader.GetInt32(10);
            invoice = reader.GetInt32(11);
            result = new PosCheckoutResult(checkout, reader.GetString(5), reader.GetString(6),
                null, reader.GetDecimal(7), reader.GetString(8), reader.GetDecimal(9), allocation.Change);
        }

        if (allocation.Payments.Count == 0)
            return result;
        using var receipts = RegisterCommand(@"
            SELECT r.receipt_number
            FROM jsonb_to_recordset(@expected) AS planned(key text,method text,reference text,amount numeric)
            JOIN public.srm_pos_checkout_payments m ON m.checkout_id=@checkout AND m.payment_key=planned.key
            JOIN public.srm_receipts r ON r.id=m.receipt_id
            WHERE m.organization_id=@company AND m.branch_id=@branch AND m.scope_context_key=0 AND m.collection_session_id=@session
                AND " + ConfirmationOwnership("m", "srm_pos_checkout_payments") + @"
                AND r.organization_id=@company AND r.customer_id=@customer AND r.currency=@currency
                AND r.payment_method=planned.method AND r.reference_number IS NOT DISTINCT FROM planned.reference AND r.amount=planned.amount
                AND " + ConfirmationOwnership("r", "srm_receipts") + @"
                AND EXISTS (SELECT 1 FROM public.srm_receipt_allocations a WHERE a.receipt_id=r.id AND a.invoice_id=@invoice
                    AND a.amount=r.amount AND a.request_id=m.payment_key AND " + ConfirmationOwnership("a", "srm_receipt_allocations") + @")
            ORDER BY m.id", db, tx, branch, actor);
        receipts.Parameters.AddWithValue("checkout", checkout);
        receipts.Parameters.AddWithValue("session", session);
        receipts.Parameters.AddWithValue("invoice", invoice);
        receipts.Parameters.AddWithValue("customer", customerId);
        receipts.Parameters.AddWithValue("currency", result.Currency);
        receipts.Parameters.AddWithValue("expected", NpgsqlDbType.Jsonb, JsonSerializer.Serialize(allocation.Payments, HeldJson));
        var numbers = new List<string>();
        using (var reader = await receipts.ExecuteReaderAsync())
            while (await reader.ReadAsync())
                numbers.Add(reader.GetString(0));
        if (numbers.Count != allocation.Payments.Count)
            throw new InvalidOperationException("The saved checkout does not have complete receipt and allocation proof.");
        return result with { ReceiptNumber = string.Join(", ", numbers) };
    }
}
