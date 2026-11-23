namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    private static readonly string NativeRegisterCheckoutEvidence = @"
        , grouped AS (
            SELECT g.id,g.pos_session_id,g.sales_order_id,g.customer_id,g.currency,
                coalesce(g.organization_id=@company AND g.branch_id=@branch AND g.pack_context_id IS NULL
                    AND g.scope_context_key=0 AND " + ConfirmationOwnership("g", "srm_pos_service_checkouts") + @"
                    AND origin.id IS NOT NULL AND origin.organization_id=@company
                    AND " + ConfirmationOwnership("origin", "srm_pos_sessions") + @"
                    AND (g.sales_order_id IS NULL OR (sale.id IS NOT NULL AND sale.organization_id=@company
                        AND sale.customer_id IS NOT DISTINCT FROM g.customer_id AND sale.currency=g.currency
                        AND " + ConfirmationOwnership("sale", "srm_sales_orders") + @")),false) AS verified
            FROM public.srm_pos_service_checkouts g
            LEFT JOIN public.srm_pos_sessions origin ON origin.id=g.pos_session_id
            LEFT JOIN public.srm_sales_orders sale ON sale.id=g.sales_order_id
            WHERE g.pos_session_id=(SELECT id FROM register) OR g.sales_order_id IN (SELECT id FROM orders)
                OR g.id IN (SELECT p.checkout_id FROM public.srm_pos_checkout_payments p
                    WHERE p.collection_session_id=(SELECT id FROM register))
        ), checkout_payments AS (
            SELECT p.collection_session_id,g.pos_session_id,r.currency,r.amount,
                lower(trim(coalesce(r.payment_method,'')))='cash'
                    AND coalesce(r.status,'') IN ('confirmed','partially_allocated','allocated') AS live_cash,
                coalesce(p.organization_id=@company AND p.branch_id=@branch AND p.scope_context_key=0
                    AND " + ConfirmationOwnership("p", "srm_pos_checkout_payments") + @"
                    AND r.id IS NOT NULL AND r.organization_id=@company
                    AND r.customer_id IS NOT DISTINCT FROM g.customer_id AND r.currency=g.currency
                    AND " + ConfirmationOwnership("r", "srm_receipts") + @",false) AS verified,
                r.id AS receipt_id
            FROM grouped g JOIN public.srm_pos_checkout_payments p ON p.checkout_id=g.id
            LEFT JOIN public.srm_receipts r ON r.id=p.receipt_id
            WHERE p.collection_session_id=(SELECT id FROM register) OR p.collection_session_id IS NULL
        )";

    private const string GroupCashAmount = @"
        coalesce((SELECT sum(amount) FROM checkout_payments
            WHERE live_cash AND collection_session_id=(SELECT id FROM register)),0)";

    private const string GroupCashRequiresReconciliation = @"
        EXISTS (SELECT 1 FROM grouped WHERE NOT verified)
        OR EXISTS (SELECT 1 FROM checkout_payments payment
            WHERE NOT verified OR (live_cash AND (amount IS NULL OR amount<=0 OR amount='NaN'::numeric
                OR (collection_session_id IS NULL AND pos_session_id=(SELECT id FROM register))
                OR (collection_session_id=(SELECT id FROM register) AND
                    (currency IS DISTINCT FROM (SELECT currency FROM register) OR currency !~ '^[A-Z]{3}$')))))
        OR EXISTS (SELECT receipt_id FROM checkout_payments GROUP BY receipt_id HAVING count(*)>1)";
}
