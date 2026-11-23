using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    private async Task<int> PersistPosReturnAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor,
        ReturnOrder order, ReturnLine line, ReturnAmount amount, PosReturnIntent intent, int? warehouse, string number, string fingerprint)
    {
        using var write = RegisterCommand(@"
            WITH returned AS (
                INSERT INTO public.srm_pos_returns (organization_id,return_number,sales_order_id,customer_id,customer_name,
                    status,refund_method,refund_status,subtotal,tax_amount,refund_amount,reason,metadata_json,created_by)
                VALUES(@company,@number,@order,@customer,@name,'completed',@method,'refunded',@subtotal,@tax,@gross,
                    @reason,json_build_object('desktop_request_id',@request,'desktop_request_sha256',@hash),@actor) RETURNING *
            ), line AS (
                INSERT INTO public.srm_pos_return_lines (return_id,sales_order_line_id,product_id,warehouse_id,item_code,
                    description,quantity,unit_price,tax_amount,line_total,condition,restock)
                SELECT id,@line,@product,@warehouse,@code,@description,@qty,@unit,@tax,@gross,@condition,@restock FROM returned RETURNING *
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'pos_return',returned.id,'created',@actor,
                    (to_jsonb(returned)||jsonb_build_object('lines',jsonb_build_array(to_jsonb(line))))::json
                FROM returned CROSS JOIN line RETURNING id
            ), stamped AS (
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'srm_pos_returns',id::text,@company,@branch,'validated-write' FROM returned
            UNION ALL SELECT 'srm_pos_return_lines',id::text,@company,@branch,'validated-write' FROM line
            UNION ALL SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit RETURNING resource_key
            )
            SELECT id FROM returned WHERE (SELECT count(*) FROM stamped)=3", db, tx, branch, actor);
        write.Parameters.AddWithValue("number", number);
        write.Parameters.AddWithValue("order", order.Id);
        write.Parameters.AddWithValue("customer", order.Buyer);
        write.Parameters.AddWithValue("name", order.Name);
        write.Parameters.AddWithValue("method", intent.Method);
        write.Parameters.AddWithValue("subtotal", amount.Gross - amount.Tax);
        write.Parameters.AddWithValue("tax", amount.Tax);
        write.Parameters.AddWithValue("gross", amount.Gross);
        write.Parameters.AddWithValue("reason", intent.Reason);
        write.Parameters.AddWithValue("request", intent.Request.ToString());
        write.Parameters.AddWithValue("hash", fingerprint);
        write.Parameters.AddWithValue("line", line.Id);
        write.Parameters.AddWithValue("product", line.Product);
        write.Parameters.AddWithValue("warehouse", NpgsqlDbType.Integer, (object?)warehouse ?? DBNull.Value);
        write.Parameters.AddWithValue("code", line.Code);
        write.Parameters.AddWithValue("description", line.Description);
        write.Parameters.AddWithValue("qty", intent.Quantity);
        write.Parameters.AddWithValue("unit", amount.NetUnit);
        write.Parameters.AddWithValue("condition", intent.Condition);
        write.Parameters.AddWithValue("restock", intent.Restock);
        return await write.ExecuteScalarAsync() is int id ? id
            : throw new InvalidOperationException("The return, its line and audit could not all be saved.");
    }
}
