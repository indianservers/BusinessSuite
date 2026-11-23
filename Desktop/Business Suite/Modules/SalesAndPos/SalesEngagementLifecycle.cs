using Npgsql;

namespace Business_Suite;

internal sealed record SalesEngagementRow(int Id, string Number, string Name, string Status, string Currency, decimal Budget);
internal sealed record SalesEngagementAction(DateTime? Date, string Action, string Previous, string Current, string Reason);

internal sealed partial class SalesOrderRepository
{
    private static readonly string NativeSalesEngagementScope = OrderScope + @"
        AND o.id=@order AND o.metadata_json->>'source' IS DISTINCT FROM 'pos'
        AND coalesce(e.organization_id,1)=@company AND e.deleted_at IS NULL AND " + ConfirmationOwnership("e", "srm_engagements") + @"
        AND (@scope IN ('organization','branch','department','team') OR e.assigned_user_id=@actor OR e.project_manager_user_id=@actor)";

    internal Task<List<SalesEngagementRow>> SalesEngagementsAsync(int order) => ReadAsync(@"
        SELECT e.id,e.engagement_number,e.name,coalesce(e.status,''),coalesce(e.currency,''),coalesce(e.budget_amount,0)
        FROM public.srm_sales_orders o JOIN public.srm_engagements e ON e.sales_order_id=o.id" +
        NativeSalesEngagementScope + " ORDER BY e.id", query => query.Parameters.AddWithValue("order", order),
        row => new SalesEngagementRow(row.GetInt32(0), row.GetString(1), row.GetString(2), row.GetString(3),
            row.GetString(4), row.GetDecimal(5)));

    internal Task<List<SalesEngagementAction>> SalesEngagementActionsAsync(int order, int engagement) => ReadAsync(@"
        SELECT a.created_at,a.action,coalesce(a.before_json->>'status',''),coalesce(a.after_json->>'status',''),
            coalesce(a.after_json->>'reason','')
        FROM public.srm_sales_orders o JOIN public.srm_engagements e ON e.sales_order_id=o.id
        JOIN public.srm_audit_logs a ON a.organization_id=@company AND a.entity_type='engagement' AND a.entity_id=e.id
            AND a.action IN ('cancel','close','reopen')" + NativeSalesEngagementScope +
        " AND e.id=@engagement AND " + ConfirmationOwnership("a", "srm_audit_logs") +
        " ORDER BY a.created_at DESC NULLS LAST,a.id DESC LIMIT 100", query =>
        {
            query.Parameters.AddWithValue("order", order);
            query.Parameters.AddWithValue("engagement", engagement);
        }, row => new SalesEngagementAction(row.IsDBNull(0) ? null : row.GetDateTime(0).ToLocalTime(),
            row.GetString(1), row.GetString(2), row.GetString(3), row.GetString(4)));

    internal async Task ChangeSalesEngagementAsync(int order, int engagement, string expectedStatus, string action, string reason)
    {
        reason = reason.Trim();
        if (reason.Length is < 1 or > 1000 || action is not ("close" or "cancel" or "reopen"))
            throw new ArgumentException("Choose a lifecycle action and enter a reason of up to 1,000 characters.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose an engagement branch.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "engagement lifecycle");
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "create");
        using var read = ScopedCommand(@"
            SELECT coalesce(e.status,''), coalesce(o.status,''),e.pms_project_id
            FROM public.srm_sales_orders o JOIN public.srm_engagements e ON e.sales_order_id=o.id" +
            NativeSalesEngagementScope + " AND e.id=@engagement FOR UPDATE OF o,e", db, tx, branch, actor, scope);
        read.Parameters.AddWithValue("order", order);
        read.Parameters.AddWithValue("engagement", engagement);
        string before;
        string sourceStatus;
        int? project;
        using (var rows = await read.ExecuteReaderAsync())
        {
            if (!await rows.ReadAsync())
                throw new InvalidOperationException("This engagement is unavailable for the selected Sales order.");
            before = rows.GetString(0);
            sourceStatus = rows.GetString(1);
            project = rows.IsDBNull(2) ? null : rows.GetInt32(2);
        }
        if (before != expectedStatus)
            throw new InvalidOperationException("Engagement status changed. Reload its current state.");
        if (before == "cancelled" || (action == "reopen") != (before == "closed"))
            throw new InvalidOperationException("This lifecycle action is unavailable for the current engagement status.");
        string next = action switch
        {
            "close" => "closed",
            "cancel" => "cancelled",
            _ => project.HasValue ? "project_created" : "created"
        };
        if (action == "reopen" && sourceStatus == "cancelled")
            throw new InvalidOperationException("A cancelled source order prevents reopening.");
        if (action != "reopen")
            await VerifyLifecycleDependenciesAsync(db, tx, branch, actor.Id, engagement, project, action);

        using var write = RegisterCommand(@"
            WITH changed AS (
                UPDATE public.srm_engagements SET status=@next,updated_at=now()
                WHERE id=@engagement AND coalesce(organization_id,1)=@company AND sales_order_id=@order
                    AND status=@before AND deleted_at IS NULL RETURNING id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,before_json,after_json)
                SELECT @company,'engagement',id,@action,@actor,json_build_object('status',@before),
                    json_build_object('status',@next,'reason',@reason) FROM changed RETURNING id
            )
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit", db, tx, branch, actor.Id);
        write.Parameters.AddWithValue("order", order);
        write.Parameters.AddWithValue("engagement", engagement);
        write.Parameters.AddWithValue("before", before);
        write.Parameters.AddWithValue("next", next);
        write.Parameters.AddWithValue("action", action);
        write.Parameters.AddWithValue("reason", reason);
        if (await write.ExecuteNonQueryAsync() != 1)
            throw new InvalidOperationException("The engagement and its lifecycle audit could not both be saved.");
        tx.Commit();
    }

    private async Task VerifyLifecycleDependenciesAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor,
        int engagement, int? project, string action)
    {
        bool cancelling = action == "cancel";
        if (cancelling && project.HasValue)
            throw new InvalidOperationException("Resolve the existing delivery project before cancelling.");
        using var billing = RegisterCommand(@"SELECT EXISTS (SELECT 1 FROM public.srm_billing_plans p WHERE p.engagement_id=@engagement
            AND (@cancelling OR p.status IS NULL OR p.status NOT IN ('completed','cancelled')))
            OR EXISTS (SELECT 1 FROM public.srm_invoices i WHERE i.engagement_id=@engagement AND i.deleted_at IS NULL
                AND (@cancelling OR i.status IS NULL OR i.status NOT IN ('paid','cancelled')))", db, tx, branch, actor);
        billing.Parameters.AddWithValue("engagement", engagement);
        billing.Parameters.AddWithValue("cancelling", cancelling);
        if (await billing.ExecuteScalarAsync() is true)
            throw new InvalidOperationException(cancelling ? "Resolve existing billing dependencies before cancellation."
                : "Resolve open billing before closing the engagement.");
        if (!project.HasValue)
            return;
        using var delivery = RegisterCommand(@"SELECT coalesce(lower(p.status),'') FROM public.pms_projects p
            WHERE p.id=@project AND coalesce(p.organization_id,1)=@company AND p.deleted_at IS NULL
              AND " + ConfirmationOwnership("p", "pms_projects") + " FOR SHARE OF p", db, tx, branch, actor);
        delivery.Parameters.AddWithValue("project", project.Value);
        if (await delivery.ExecuteScalarAsync() is not ("completed" or "closed" or "cancelled"))
            throw new InvalidOperationException("Complete the verified delivery project before closing the engagement.");
    }
}
