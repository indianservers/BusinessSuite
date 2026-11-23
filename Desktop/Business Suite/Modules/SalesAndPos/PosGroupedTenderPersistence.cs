using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    private static string PosTenderDigest(Guid key, string method, string? reference, decimal amount, int? session = null)
    {
        string payment = "{\"amount\": " + Quote(amount.ToString("F2", CultureInfo.InvariantCulture)) +
            ", \"method\": " + Quote(method) + ", \"payment_key\": " + Quote(key.ToString()) +
            ", \"reference\": " + (reference is null ? "null" : Quote(reference)) + "}";
        if (session is int id)
            payment = "{\"payment\": " + payment + ", \"pos_session_id\": " + id.ToString(CultureInfo.InvariantCulture) + "}";
        using var sha = SHA256.Create();
        return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(payment))).Replace("-", "").ToLowerInvariant();
    }

    private async Task<decimal> SaveGroupedPosTenderAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor,
        int checkout, int invoice, int buyer, int session, string currency, string number, Guid key, string method,
        string? reference, decimal amount, string digest)
    {
        using var command = RegisterCommand(@"
            WITH paid AS (
                UPDATE public.srm_invoices i SET paid_amount=i.paid_amount+@amount,balance_amount=i.balance_amount-@amount,
                    status=CASE WHEN i.balance_amount=@amount THEN 'paid' ELSE 'partially_paid' END,updated_at=now()
                WHERE i.id=@invoice AND i.organization_id=@company AND i.approved_at IS NOT NULL
                    AND i.status IN ('approved','issued','sent','overdue','partially_paid') AND i.balance_amount>=@amount
                    AND i.total_amount=i.paid_amount+i.balance_amount
                RETURNING id,balance_amount
            ), receipt AS (
                INSERT INTO public.srm_receipts (organization_id,receipt_number,customer_id,status,receipt_date,payment_method,
                    reference_number,currency,amount,unallocated_amount,created_by)
                SELECT @company,@number,@customer,'allocated',@date,@method,@reference,@currency,@amount,0,@actor FROM paid RETURNING *
            ), allocation AS (
                INSERT INTO public.srm_receipt_allocations (receipt_id,invoice_id,amount,request_id,allocated_by)
                SELECT id,@invoice,@amount,@payment_key,@actor FROM receipt RETURNING id
            ), payment AS (
                INSERT INTO public.srm_pos_checkout_payments (organization_id,branch_id,scope_context_key,checkout_id,payment_key,
                    receipt_id,collection_session_id,request_sha256)
                SELECT @company,@branch,0,@checkout,@payment_key,receipt.id,@session,@payment_digest FROM receipt RETURNING id
            ), revenue AS (
                INSERT INTO public.srm_revenue_events (organization_id,invoice_id,event_type,amount,currency,recognized_on)
                SELECT @company,id,'cash_collected',@amount,@currency,@date FROM paid RETURNING id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,before_json,after_json)
                SELECT @company,'receipt',id,'created',@actor,NULL,
                    (to_jsonb(receipt)||jsonb_build_object('status','draft','unallocated_amount',@amount))::json FROM receipt
                UNION ALL SELECT @company,'receipt',id,'confirmed',@actor,json_build_object('status','draft'),
                    json_build_object('status','confirmed') FROM receipt
                UNION ALL SELECT @company,'receipt',id,'allocated',@actor,NULL,
                    json_build_object('invoice_id',@invoice,'amount',@amount) FROM receipt RETURNING id
            ), stamps AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT kind,id::text,@company,@branch,'validated-write' FROM (
                    SELECT 'srm_receipts' AS kind,id FROM receipt
                    UNION ALL SELECT 'srm_receipt_allocations',id FROM allocation
                    UNION ALL SELECT 'srm_pos_checkout_payments',id FROM payment
                    UNION ALL SELECT 'srm_revenue_events',id FROM revenue
                    UNION ALL SELECT 'srm_audit_logs',id FROM audit
                ) owned
            )
            SELECT balance_amount FROM paid", db, tx, branch, actor);
        command.Parameters.AddWithValue("checkout", checkout);
        command.Parameters.AddWithValue("invoice", invoice);
        command.Parameters.AddWithValue("customer", buyer);
        command.Parameters.AddWithValue("session", session);
        command.Parameters.AddWithValue("currency", currency);
        command.Parameters.AddWithValue("number", number);
        command.Parameters.AddWithValue("date", NpgsqlDbType.Date, DateTime.Today);
        command.Parameters.AddWithValue("amount", amount);
        command.Parameters.AddWithValue("method", method);
        command.Parameters.AddWithValue("reference", NpgsqlDbType.Text, (object?)reference ?? DBNull.Value);
        command.Parameters.AddWithValue("payment_key", key.ToString());
        command.Parameters.AddWithValue("payment_digest", digest);
        return await command.ExecuteScalarAsync() is decimal balance ? balance
            : throw new InvalidOperationException("The issued invoice balance changed before recording the payment.");
    }
}
