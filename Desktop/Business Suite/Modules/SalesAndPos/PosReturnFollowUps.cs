using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    private static readonly string RefundedFollowUpScope = @"
        FROM public.service_follow_ups f JOIN public.srm_sales_order_lines l ON l.id=f.order_line_id AND l.sales_order_id=@order
        WHERE f.order_id=@order AND f.status NOT IN ('Completed','Cancelled')
            AND coalesce(f.configuration->>'cancellation_policy','cancel')='cancel'
            AND l.quantity<=(SELECT coalesce(sum(r.quantity),0) FROM public.srm_pos_return_lines r WHERE r.sales_order_line_id=l.id)";

    private async Task CancelRefundedFollowUpsAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        int actor, ReturnOrder order, int returned)
    {
        var ids = new List<int>();
        using (var select = RegisterCommand(@"SELECT f.id,coalesce(f.organization_id=@company AND f.customer_id=@buyer
            AND f.product_id IS NOT DISTINCT FROM l.product_id AND " + ConfirmationOwnership("l", "srm_sales_order_lines") +
            " AND " + ConfirmationOwnership("f", "service_follow_ups") + ",false)" + RefundedFollowUpScope +
            " ORDER BY f.id FOR UPDATE OF f NOWAIT", db, tx, branch, actor))
        {
            select.Parameters.AddWithValue("order", order.Id);
            select.Parameters.AddWithValue("buyer", order.Buyer);
            using var reader = await select.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                if (!reader.GetBoolean(1))
                    throw new PosReturnRejectedException("A follow-up due for cancellation has no verified sale-line or branch ownership.");
                ids.Add(reader.GetInt32(0));
            }
        }
        if (ids.Count == 0)
            return;

        using var write = RegisterCommand(@"
            WITH cancelled AS (
                UPDATE public.service_follow_ups f SET status='Cancelled'
                WHERE f.id=ANY(@ids) AND f.organization_id=@company AND f.order_id=@order
                    AND f.status NOT IN ('Completed','Cancelled')
                RETURNING f.id,f.order_line_id
            ), activities AS (
                INSERT INTO public.service_follow_up_activities (follow_up_id,actor_id,action,details,created_at)
                SELECT id,@actor,'source_refunded',json_build_object('return_id',@return,'order_line_id',order_line_id),now()
                FROM cancelled RETURNING id
            )
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'service_follow_up_activities',id::text,@company,@branch,'validated-write' FROM activities", db, tx, branch, actor);
        write.Parameters.AddWithValue("ids", NpgsqlDbType.Array | NpgsqlDbType.Integer, ids.ToArray());
        write.Parameters.AddWithValue("order", order.Id);
        write.Parameters.AddWithValue("return", returned);
        if (await write.ExecuteNonQueryAsync() != ids.Count)
            throw new InvalidOperationException("The refunded stock line and its follow-up activities could not all be saved.");
    }
}
