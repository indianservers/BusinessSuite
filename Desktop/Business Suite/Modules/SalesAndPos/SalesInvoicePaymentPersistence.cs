using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    internal Task<SalesPaymentResult> SaveAppointmentInvoicePaymentAsync(NpgsqlConnection db,NpgsqlTransaction tx,int branch,
        int actor,int invoice,string number,SalesPaymentIntent intent) =>
        SaveSalesPaymentAsync(db,tx,branch,actor,invoice,number,intent,appointment:true);

    private async Task<SalesPaymentResult> SaveSalesPaymentAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        int actor, int invoice, string number, SalesPaymentIntent intent, bool appointment = false)
    {
        using var write = RegisterCommand(@"
            WITH paid AS (
                UPDATE public.srm_invoices
                SET paid_amount=paid_amount+@amount,balance_amount=total_amount-paid_amount-@amount,
                    status=CASE WHEN balance_amount=@amount THEN 'paid' ELSE 'partially_paid' END, updated_at=now()
                WHERE id=@invoice AND organization_id=@company AND balance_amount>=@amount
                RETURNING id,customer_id,currency,balance_amount,status,engagement_id
            ), receipt AS (
                INSERT INTO public.srm_receipts (organization_id,receipt_number,customer_id,status,receipt_date,payment_method,
                    reference_number,currency,amount,unallocated_amount,created_by)
                SELECT @company,@number,customer_id,'allocated',@date,@method,@reference,currency,@amount,0,@actor
                FROM paid RETURNING id,receipt_number
            ), allocation AS (
                INSERT INTO public.srm_receipt_allocations (receipt_id,invoice_id,amount,allocated_by)
                SELECT id,@invoice,@amount,@actor FROM receipt RETURNING id
            ), context AS (
                INSERT INTO public.business_receipt_contexts (receipt_id,seller_id,invoice_id,request_id)
                SELECT id,@company,@invoice,@request FROM receipt
            ), revenue AS (
                INSERT INTO public.srm_revenue_events (organization_id,engagement_id,invoice_id,event_type,amount,currency,recognized_on)
                SELECT @company,engagement_id,id,'cash_collected',@amount,currency,@today FROM paid RETURNING id
            ), history AS (
                INSERT INTO public.srm_invoice_history (invoice_id,to_status,actor_user_id,notes)
                SELECT @invoice,paid.status,@actor,'Receipt '||receipt.id||' applied; correlation '||@request
                FROM paid CROSS JOIN receipt RETURNING id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'receipt',id,CASE WHEN @appointment THEN 'allocated' ELSE 'payment_applied' END,@actor,
                    json_build_object('invoice_id',@invoice,'correlation_id',@request,'amount',round(@amount,2)::text)
                FROM receipt RETURNING id
            ), lifecycle AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,before_json,after_json)
                SELECT @company,'receipt',id,'created',@actor,NULL,json_build_object('status','draft','receipt_number',receipt_number)
                FROM receipt WHERE @appointment
                UNION ALL SELECT @company,'receipt',id,'confirmed',@actor,json_build_object('status','draft'),json_build_object('status','confirmed')
                FROM receipt WHERE @appointment RETURNING id
            ), ownership AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT resource,id::text,@company,@branch,'validated-write' FROM (
                    SELECT 'srm_receipts' AS resource,id FROM receipt UNION ALL SELECT 'srm_receipt_allocations',id FROM allocation
                    UNION ALL SELECT 'business_receipt_contexts',id FROM receipt UNION ALL SELECT 'srm_revenue_events',id FROM revenue
                    UNION ALL SELECT 'srm_invoice_history',id FROM history UNION ALL SELECT 'srm_audit_logs',id FROM audit
                    UNION ALL SELECT 'srm_audit_logs',id FROM lifecycle
                ) owned
            )
            SELECT receipt.id,receipt.receipt_number,paid.balance_amount,paid.status FROM paid CROSS JOIN receipt",
            db, tx, branch, actor);
        BindPayment(write, invoice, intent);
        write.Parameters.AddWithValue("number", number);
        write.Parameters.AddWithValue("appointment",appointment);
        write.Parameters.AddWithValue("today", NpgsqlDbType.Date, appointment ? intent.ReceiptDate : DateTime.Today);
        using var reader = await write.ExecuteReaderAsync();
        if (!await reader.ReadAsync())
            throw new InvalidOperationException("The invoice balance changed. Reopen the invoice before recording a payment.");
        return new SalesPaymentResult(reader.GetInt32(0), reader.GetString(1), reader.GetDecimal(2), reader.GetString(3), false);
    }
}
