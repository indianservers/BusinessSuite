using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    private static readonly string HeldCartScope = @"
        FROM public.srm_pos_held_bills h JOIN public.srm_pos_sessions p ON p.id=h.session_id
        WHERE h.organization_id=@company AND p.organization_id=@company AND h.created_by=@actor
            AND p.cashier_user_id=@actor AND p.deleted_at IS NULL
            AND h.cart_json->0->>'format'='desktop-pos-v1'
            AND " + ConfirmationOwnership("h", "srm_pos_held_bills") + " AND " + ConfirmationOwnership("p", "srm_pos_sessions");

    internal async Task<List<PosHeldBillRow>> ListHeldPosCartsAsync(bool includeRecalled)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to view held bills.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor);
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop POS held bills");
        using var query = RegisterCommand(@"
            SELECT h.id,h.hold_number,coalesce(h.customer_name,''),coalesce(h.notes,''),coalesce(h.amount,0),
                coalesce(h.item_count,0),h.created_at,h.status " + HeldCartScope +
            " AND (h.status='held' OR (@recalled AND h.status='recalled')) AND h.deleted_at IS NULL ORDER BY h.id DESC LIMIT 100", db, tx, branch, actor.Id);
        query.Parameters.AddWithValue("recalled", includeRecalled);
        var result = new List<PosHeldBillRow>();
        using (var reader = await query.ExecuteReaderAsync())
            while (await reader.ReadAsync())
                result.Add(new PosHeldBillRow(reader.GetInt32(0), reader.GetString(1), reader.GetString(2), reader.GetString(3),
                    reader.GetDecimal(4), reader.GetInt32(5), reader.IsDBNull(6) ? null : reader.GetDateTime(6), reader.GetString(7)));
        tx.Commit();
        return result;
    }

    internal async Task<PosHeldCart> ResolveHeldPosCartAsync(int id, bool cancel)
    {
        if (id <= 0)
            throw new ArgumentException("Select a held bill.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to update held bills.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await RequireHeldWriterAsync(db, tx, branch, actor, cancel ? "delete" : "create");
        var held = await ReadHeldCartAsync(db, tx, branch, actor.Id, id, null)
            ?? throw new InvalidOperationException("The selected held bill is unavailable to this cashier and branch.");
        string status = cancel ? "cancelled" : "recalled";
        if (!cancel)
        {
            var register = await FindActiveRegisterAsync(db, tx, branch, actor.Id);
            if (register is null || register.Currency != held.Currency)
                throw new InvalidOperationException("Open a register in the held bill currency before recalling it.");
            if (held.Cart.CustomerId is int customer)
            {
                using var customerQuery = RegisterCommand("SELECT c.id FROM public.crm_companies c " + OrderCustomerScope + " AND c.id=@customer",
                    db, tx, branch, actor.Id);
                customerQuery.Parameters.AddWithValue("customer", customer);
                if (await customerQuery.ExecuteScalarAsync() is null)
                    throw new InvalidOperationException("The held bill customer is unavailable in this branch.");
            }
        }

        if (held.Status == status)
        {
            tx.Commit();
            return held.Cart;
        }
        if (held.Status != "held")
            throw new InvalidOperationException("The held bill has already been resolved.");
        using var write = RegisterCommand(@"
            WITH original AS (
                SELECT h.* FROM public.srm_pos_held_bills h WHERE h.id=@id AND h.organization_id=@company
                    AND h.created_by=@actor AND h.status='held' AND h.deleted_at IS NULL
            ), resolved AS (
                UPDATE public.srm_pos_held_bills h SET status=@status,updated_at=now(),
                    recalled_by=CASE WHEN @status='recalled' THEN @actor ELSE h.recalled_by END,
                    recalled_at=CASE WHEN @status='recalled' THEN now() ELSE h.recalled_at END,
                    deleted_at=CASE WHEN @status='cancelled' THEN now() ELSE NULL END
                FROM original WHERE h.id=original.id RETURNING h.*
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,before_json,after_json)
                SELECT @company,'pos_held_bill',resolved.id,@status,@actor,
                    (to_jsonb(original)||jsonb_build_object('holdNo',original.hold_number,'cart',original.cart_json))::json,
                    (to_jsonb(resolved)||jsonb_build_object('holdNo',resolved.hold_number,'cart',resolved.cart_json))::json
                FROM resolved JOIN original ON original.id=resolved.id RETURNING id
            )
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit", db, tx, branch, actor.Id);
        write.Parameters.AddWithValue("id", id);
        write.Parameters.AddWithValue("status", status);
        if (await write.ExecuteNonQueryAsync() != 1)
            throw new InvalidOperationException("The held bill changed before the action could be saved.");
        tx.Commit();
        return held.Cart;
    }

    private sealed record HeldCartState(PosHeldCart Cart, string Status, string Register, string Currency);

    private async Task<HeldCartState?> ReadHeldCartAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        int actor, int? id, string? request)
    {
        using var read = RegisterCommand(@"
            SELECT h.id,h.hold_number,h.customer_id,coalesce(h.customer_name,''),coalesce(h.notes,''),
                h.cart_json::text,coalesce(h.status,''),p.session_number
            " + HeldCartScope + @" AND ((@id IS NOT NULL AND h.id=@id) OR
                (@request IS NOT NULL AND h.cart_json->0->>'request'=@request))
            ORDER BY h.id LIMIT 2 FOR UPDATE OF h", db, tx, branch, actor);
        read.Parameters.AddWithValue("id", NpgsqlDbType.Integer, (object?)id ?? DBNull.Value);
        read.Parameters.AddWithValue("request", NpgsqlDbType.Text, (object?)request ?? DBNull.Value);
        using var reader = await read.ExecuteReaderAsync();
        if (!await reader.ReadAsync())
            return null;
        List<HeldLine>? lines;
        try
        {
            lines = JsonSerializer.Deserialize<List<HeldLine>>(reader.GetString(5), HeldJson);
        }
        catch (JsonException error)
        {
            throw new InvalidOperationException("The saved held bill cart could not be verified.", error);
        }
        if (lines is null || lines.Count is < 1 or > 100 || lines.Any(l => l is null || l.Format != "desktop-pos-v1" ||
            l.ProductId <= 0 || l.Quantity <= 0 || l.LineTotal < 0 || l.Currency != lines[0].Currency || l.Request != lines[0].Request) ||
            lines[0].Currency is null || !ValidOrderCurrency(lines[0].Currency))
            throw new InvalidOperationException("The saved held bill cart could not be verified.");
        var cart = new PosHeldCart(reader.GetInt32(0), reader.GetString(1), reader.IsDBNull(2) ? null : reader.GetInt32(2),
            reader.GetString(3), reader.GetString(4), lines.Select(l =>
                new PosCartLine(l.ProductId, l.Sku, l.Name, l.Quantity, l.UnitPrice, l.TaxRate, l.LineTotal)).ToList());
        var state = new HeldCartState(cart, reader.GetString(6), reader.GetString(7), lines[0].Currency);
        if (await reader.ReadAsync())
            throw new InvalidOperationException("Multiple held bills match this request. Review the register history.");
        return state;
    }
}
