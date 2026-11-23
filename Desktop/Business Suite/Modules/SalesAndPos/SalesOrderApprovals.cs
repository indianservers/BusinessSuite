using System.Globalization;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record SalesOrderApprovalResult(string Status, int? ApprovalRequestId);

internal sealed partial class SalesOrderRepository
{
    private sealed record ApprovalOrder(string Number, string Title, string Status, string Currency,
        decimal Total, int? RequestId, int? ApprovedBy);
    private sealed record LinkedSalesApproval(int Id, string Status, int? DecidedBy);

    private const string ApprovalOrderScope = OrderScope + @"
        AND o.id=@order AND o.metadata_json->>'source' IS DISTINCT FROM 'pos'";

    private const string FindApprovalOrder = @"
        SELECT o.order_number,o.title,coalesce(o.status,''),coalesce(o.currency,''),
               coalesce(o.total_amount,0),o.approval_request_id,o.approved_by
        FROM public.srm_sales_orders o" + ApprovalOrderScope;

    internal async Task<bool> CanAdvanceApprovalAsync(int orderId, string expectedStatus)
    {
        if (settings.BranchId is not int branch)
            return false;
        try
        {
            using var db = new NpgsqlConnection(settings.ConnectionString);
            await db.OpenAsync();
            using var tx = db.BeginTransaction(System.Data.IsolationLevel.RepeatableRead);
            using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
                await readOnly.ExecuteNonQueryAsync();
            var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
            string scope = await ApprovalScopeAsync(db, tx, branch, actor, expectedStatus == "pending_approval");
            var order = await ReadApprovalOrderAsync(db, tx, branch, actor, scope, orderId, lockRow: false);
            tx.Commit();
            return order?.Status == expectedStatus;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    internal async Task<SalesOrderApprovalResult> AdvanceSalesApprovalAsync(int orderId, bool approve)
    {
        if (orderId <= 0)
            throw new ArgumentException("Select a sales order.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to work with sales approvals.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await ApprovalScopeAsync(db, tx, branch, actor, approve);
        var order = await ReadApprovalOrderAsync(db, tx, branch, actor, scope, orderId, lockRow: true) ??
            throw new InvalidOperationException("The sales order is unavailable for approval in this branch.");

        string destination;
        int? requestId = order.RequestId;
        int? decidedBy;
        if (approve)
        {
            var request = requestId is int id
                ? await ReadLinkedApprovalAsync(db, tx, branch, actor.Id, orderId, id)
                : null;
            if (order.Status == "approved" && order.ApprovedBy.HasValue && (request is null || request.Status == "Approved"))
            {
                tx.Commit();
                return new SalesOrderApprovalResult(order.Status, requestId);
            }
            if (order.Status != "pending_approval" || request is null)
                throw new InvalidOperationException("Only a sales order with a pending approval request can be approved.");
            if (request.Status == "Pending")
            {
                await ApproveRequestAsync(db, tx, branch, actor.Id, request.Id);
                decidedBy = actor.Id;
            }
            else if (request.Status == "Approved" && request.DecidedBy.HasValue)
            {
                // A decision from the shared Approval OS already exists. Preserve it when advancing Sales.
                decidedBy = request.DecidedBy;
            }
            else
            {
                throw new InvalidOperationException("The linked approval was already resolved without approval. Review its decision.");
            }
            destination = "approved";
        }
        else
        {
            if (order.Status == "pending_approval" && requestId is int existing)
            {
                var linked = await ReadLinkedApprovalAsync(db, tx, branch, actor.Id, orderId, existing);
                if (linked.Status is not ("Pending" or "Approved"))
                    throw new InvalidOperationException("The linked approval was already resolved without approval. Review its decision.");
                tx.Commit();
                return new SalesOrderApprovalResult(order.Status, requestId);
            }
            if (order.Status == "approved" && await WasSubmittedAsync(db, tx, branch, actor.Id, orderId))
            {
                tx.Commit();
                return new SalesOrderApprovalResult(order.Status, requestId);
            }
            if (order.Status != "draft" || requestId.HasValue)
                throw new InvalidOperationException("Only unsubmitted draft sales orders can be submitted.");
            bool needsApproval = order.Total >= await ApprovalThresholdAsync(db, tx);
            if (needsApproval)
                requestId = await CreateSalesApprovalAsync(db, tx, branch, actor.Id, orderId, order);
            destination = needsApproval ? "pending_approval" : "approved";
            decidedBy = needsApproval ? null : actor.Id;
        }

        using var write = ScopedCommand(@"
            UPDATE public.srm_sales_orders o SET status=@destination,approved_by=@decided,
                approval_request_id=@request,updated_at=now()" + ApprovalOrderScope + " AND o.status=@original",
            db, tx, branch, actor, scope);
        write.Parameters.AddWithValue("order", NpgsqlDbType.Integer, orderId);
        write.Parameters.AddWithValue("destination", NpgsqlDbType.Text, destination);
        write.Parameters.AddWithValue("original", NpgsqlDbType.Text, order.Status);
        write.Parameters.AddWithValue("decided", NpgsqlDbType.Integer, (object?)decidedBy ?? DBNull.Value);
        write.Parameters.AddWithValue("request", NpgsqlDbType.Integer, (object?)requestId ?? DBNull.Value);
        if (await write.ExecuteNonQueryAsync() != 1)
            throw new InvalidOperationException("The sales order state changed. Refresh before continuing.");
        await WriteSalesStageAsync(db, tx, branch, actor.Id, orderId, order.Status, destination,
            approve ? "approved" : "submitted", new { status = order.Status }, new { status = destination });
        tx.Commit();
        return new SalesOrderApprovalResult(destination, requestId);
    }

    private async Task<string> ApprovalScopeAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        DesktopActor actor, bool approve)
    {
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor,
            approve ? "approve" : "create");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop sales order approvals");
        return scope;
    }

    private async Task<ApprovalOrder?> ReadApprovalOrderAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        DesktopActor actor, string scope, int order, bool lockRow)
    {
        using var query = ScopedCommand(FindApprovalOrder + (lockRow ? " FOR UPDATE OF o" : ""),
            db, tx, branch, actor, scope);
        query.Parameters.AddWithValue("order", NpgsqlDbType.Integer, order);
        using var reader = await query.ExecuteReaderAsync();
        if (!await reader.ReadAsync())
            return null;
        return new ApprovalOrder(reader.GetString(0), reader.GetString(1), reader.GetString(2), reader.GetString(3),
            reader.GetDecimal(4), reader.IsDBNull(5) ? null : reader.GetInt32(5),
            reader.IsDBNull(6) ? null : reader.GetInt32(6));
    }

    private async Task<decimal> ApprovalThresholdAsync(NpgsqlConnection db, NpgsqlTransaction tx)
    {
        using var query = new NpgsqlCommand(@"
            SELECT value_json::text FROM public.srm_settings WHERE organization_id=@company
                AND key='sales_order_approval_threshold' FOR SHARE", db, tx);
        query.Parameters.AddWithValue("company", NpgsqlDbType.Integer, settings.OrganizationId);
        if (await query.ExecuteScalarAsync() is not string value)
            return 1_000_000m;
        using var json = JsonDocument.Parse(value);
        if (json.RootElement.ValueKind != JsonValueKind.Object)
            return 1_000_000m;
        if (!json.RootElement.TryGetProperty("amount", out JsonElement amount) || amount.ValueKind == JsonValueKind.Null)
            return 0;
        if (!decimal.TryParse(amount.ToString(), NumberStyles.Float, CultureInfo.InvariantCulture, out decimal threshold))
            throw new InvalidOperationException("The Sales order approval threshold is invalid.");
        return threshold;
    }

    private async Task<int> CreateSalesApprovalAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor,
        int orderId, ApprovalOrder order)
    {
        using var write = RegisterCommand(@"
            WITH request AS (
                INSERT INTO public.approval_requests
                    (organization_id,source_module,approval_type,entity_type,entity_id,title,description,
                     requester_user_id,assigned_role,priority,status,sla_due_at,context_json,mobile_enabled)
                VALUES (@company,'srm','sales_order','srm_sales_order',@order,@title,@description,
                    @actor,'srm_finance_manager','High','Pending',now()+interval '48 hours',
                    json_build_object('sales_order_id',@order,'total_amount',@amount),true)
                RETURNING id
            ), history AS (
                INSERT INTO public.approval_history (request_id,event_type,actor_user_id,after_status)
                SELECT id,'created',@actor,'Pending' FROM request RETURNING id
            ), stamp AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'approval_requests',id::text,@company,@branch,'validated-write' FROM request
                UNION ALL
                SELECT 'approval_history',id::text,@company,@branch,'validated-write' FROM history RETURNING resource_key
            )
            SELECT id FROM request WHERE (SELECT count(*) FROM stamp)=2", db, tx, branch, actor);
        write.Parameters.AddWithValue("order", NpgsqlDbType.Integer, orderId);
        write.Parameters.AddWithValue("title", NpgsqlDbType.Text, $"Approve sales order {order.Number}");
        write.Parameters.AddWithValue("description", NpgsqlDbType.Text,
            $"{order.Title} requires approval for {order.Currency} {order.Total.ToString("F2", CultureInfo.InvariantCulture)}");
        write.Parameters.AddWithValue("amount", NpgsqlDbType.Numeric, order.Total);
        if (await write.ExecuteScalarAsync() is not int id)
            throw new InvalidOperationException("The approval request and history could not both be saved.");
        return id;
    }

    private async Task<LinkedSalesApproval> ReadLinkedApprovalAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        int actor, int orderId, int approvalId)
    {
        using var query = RegisterCommand(@"
            SELECT a.status,a.decided_by FROM public.approval_requests a
            WHERE coalesce(a.organization_id,1)=@company AND a.id=@request AND a.entity_id=@order
              AND a.entity_type='srm_sales_order' AND a.source_module='srm' AND a.approval_type='sales_order'
              AND EXISTS (SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company
                    AND b.branch_id=@branch AND b.resource_table='approval_requests' AND b.resource_key=a.id::text)
              AND NOT EXISTS (SELECT 1 FROM public.business_pack_record_ownership b WHERE b.company_id=@company
                    AND b.resource_table='approval_requests' AND b.resource_key=a.id::text)
            FOR UPDATE OF a", db, tx, branch, actor);
        query.Parameters.AddWithValue("request", NpgsqlDbType.Integer, approvalId);
        query.Parameters.AddWithValue("order", NpgsqlDbType.Integer, orderId);
        using var reader = await query.ExecuteReaderAsync();
        if (!await reader.ReadAsync())
            throw new InvalidOperationException("The linked sales approval is unavailable in this branch.");
        return new LinkedSalesApproval(approvalId, reader.IsDBNull(0) ? "" : reader.GetString(0),
            reader.IsDBNull(1) ? null : reader.GetInt32(1));
    }

    private async Task ApproveRequestAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor, int request)
    {
        using var write = RegisterCommand(@"
            WITH decided AS (
                UPDATE public.approval_requests SET status='Approved',decided_by=@actor,decided_at=now(),updated_at=now()
                WHERE id=@request AND status='Pending' RETURNING id
            ), history AS (
                INSERT INTO public.approval_history (request_id,event_type,actor_user_id,before_status,after_status)
                SELECT id,'approved',@actor,'Pending','Approved' FROM decided RETURNING id
            )
            INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
            SELECT 'approval_history',id::text,@company,@branch,'validated-write' FROM history", db, tx, branch, actor);
        write.Parameters.AddWithValue("request", NpgsqlDbType.Integer, request);
        if (await write.ExecuteNonQueryAsync() != 1)
            throw new InvalidOperationException("The sales approval is no longer pending.");
    }

    private async Task<bool> WasSubmittedAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor, int order)
    {
        using var query = RegisterCommand(@"
            SELECT EXISTS (SELECT 1 FROM public.srm_audit_logs a
                JOIN public.suite_branch_ownership b ON b.company_id=a.organization_id AND b.branch_id=@branch
                    AND b.resource_table='srm_audit_logs' AND b.resource_key=a.id::text
                WHERE a.organization_id=@company AND a.entity_type='sales_order' AND a.entity_id=@order
                    AND a.action='submitted')", db, tx, branch, actor);
        query.Parameters.AddWithValue("order", NpgsqlDbType.Integer, order);
        return (bool)(await query.ExecuteScalarAsync())!;
    }

    private async Task WriteSalesStageAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor,
        int order, string previous, string destination, string action, object? before, object after)
    {
        using var write = RegisterCommand(@"
            WITH audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,before_json,after_json)
                VALUES (@company,'sales_order',@order,@action,@actor,
                    @before,@after) RETURNING id
            ), stage_event AS (
                INSERT INTO public.suite_service_events (organization_id,module_key,event_type,entity_type,entity_id,
                    actor_id,request_key,payload_json,status)
                VALUES (@company,'srm','pipeline.stage_entered','sales_order',@order,@actor,@key,
                    json_build_object('origin','pipeline_workspace','data',
                        json_build_object('previous_stage',@previous,'stage',@destination,'previous_stage_name',@previous,
                            'stage_name',@destination,'owner_id',NULL,'scope',NULL),'depth',0),'pending') RETURNING id
            )
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit
            UNION ALL
            SELECT 'suite_service_events',id::text,@company,@branch,'validated-write' FROM stage_event",
            db, tx, branch, actor);
        write.Parameters.AddWithValue("order", NpgsqlDbType.Integer, order);
        write.Parameters.AddWithValue("action", NpgsqlDbType.Text, action);
        write.Parameters.AddWithValue("before", NpgsqlDbType.Json, before is null ? DBNull.Value : JsonSerializer.Serialize(before));
        write.Parameters.AddWithValue("after", NpgsqlDbType.Json, JsonSerializer.Serialize(after));
        write.Parameters.AddWithValue("previous", NpgsqlDbType.Text, previous);
        write.Parameters.AddWithValue("destination", NpgsqlDbType.Text, destination);
        write.Parameters.AddWithValue("key", NpgsqlDbType.Text, $"pipeline:srm:{order}:{Guid.NewGuid():N}");
        if (await write.ExecuteNonQueryAsync() != 2)
            throw new InvalidOperationException("The sales order audit and stage event could not both be saved.");
    }
}
