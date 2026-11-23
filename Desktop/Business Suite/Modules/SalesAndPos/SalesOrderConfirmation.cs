using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record SalesOrderConfirmationResult(int EngagementId, int BillingPlanId);

internal sealed partial class SalesOrderRepository
{
    internal async Task<SalesOrderConfirmationResult> ConfirmSalesOrderAsync(int orderId)
    {
        if (orderId <= 0)
            throw new ArgumentException("Select a sales order.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to confirm sales orders.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await ApprovalScopeAsync(db, tx, branch, actor, approve: false);
        var order = await ReadApprovalOrderAsync(db, tx, branch, actor, scope, orderId, lockRow: true);
        if (order?.Status is not ("approved" or "confirmed"))
            throw new InvalidOperationException("Only an approved sales order in this branch can be confirmed.");

        int? engagement = await FindConfirmationDocumentAsync(db, tx, branch, actor.Id, orderId, "srm_engagements", "sales_order_id", true);
        int? plan = engagement is int existingEngagement
            ? await FindConfirmationDocumentAsync(db, tx, branch, actor.Id, existingEngagement, "srm_billing_plans", "engagement_id", false)
            : null;
        if (order.Status == "confirmed")
        {
            if (engagement is not int confirmedEngagement || plan is not int confirmedPlan)
                throw new InvalidOperationException("The existing confirmation has incomplete commercial records. Review those records before continuing.");
            tx.Commit();
            return new SalesOrderConfirmationResult(confirmedEngagement, confirmedPlan);
        }

        await ValidateConfirmationSourcesAsync(db, tx, branch, actor, orderId);
        await IssueConfirmationStockAsync(db, tx, branch, actor, orderId, order.Number);
        int engagementId = engagement ?? await CreateConfirmationEngagementAsync(db, tx, branch, actor.Id, orderId);
        int? contract = await FindConfirmationDocumentAsync(db, tx, branch, actor.Id, orderId, "srm_contracts", "sales_order_id", true);
        int planId = plan ?? await CreateConfirmationPlanAsync(db, tx, branch, actor.Id, orderId, engagementId, contract);

        using var update = ScopedCommand(@"UPDATE public.srm_sales_orders o SET status='confirmed',updated_at=now()" +
            ApprovalOrderScope + " AND o.status='approved'", db, tx, branch, actor, scope);
        update.Parameters.AddWithValue("order", orderId);
        if (await update.ExecuteNonQueryAsync() != 1)
            throw new InvalidOperationException("The sales order state changed. Refresh before continuing.");
        await WriteSalesStageAsync(db, tx, branch, actor.Id, orderId, order.Status, "confirmed", "confirmed", null,
            new { engagement_id = engagementId, billing_plan_id = planId });
        tx.Commit();
        return new SalesOrderConfirmationResult(engagementId, planId);
    }

    private async Task<int?> FindConfirmationDocumentAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        int actor, int parent, string table, string parentColumn, bool softDeleted)
    {
        // All SQL identifiers are private constants supplied by the three call sites.
        using var query = RegisterCommand("SELECT document.id, coalesce(document.organization_id=@company,false) AND " +
            ConfirmationOwnership("document", table) + " FROM public." + table + " document WHERE document." +
            parentColumn + "=@parent" + (softDeleted ? " AND document.deleted_at IS NULL" : "") +
            " ORDER BY document.id LIMIT 2 FOR UPDATE OF document", db, tx, branch, actor);
        query.Parameters.AddWithValue("parent", parent);
        using var reader = await query.ExecuteReaderAsync();
        if (!await reader.ReadAsync())
            return null;
        int id = reader.GetInt32(0);
        if (!reader.GetBoolean(1) || await reader.ReadAsync())
            throw new InvalidOperationException("A linked commercial record is outside this branch or has multiple matches.");
        return id;
    }

    private static string ConfirmationOwnership(string alias, string table) => $@"
            EXISTS (SELECT 1 FROM public.suite_branch_ownership branch_owner WHERE branch_owner.company_id=@company AND branch_owner.branch_id=@branch
                AND branch_owner.resource_table='{table}' AND branch_owner.resource_key={alias}.id::text)
            AND NOT EXISTS (SELECT 1 FROM public.business_pack_record_ownership pack_owner WHERE pack_owner.company_id=@company
                AND pack_owner.resource_table='{table}' AND pack_owner.resource_key={alias}.id::text)";

    private async Task ValidateConfirmationSourcesAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        DesktopActor actor, int order)
    {
        using (var lines = RegisterCommand(@"SELECT " + ConfirmationOwnership("l", "srm_sales_order_lines") +
            " FROM public.srm_sales_order_lines l WHERE l.sales_order_id=@order ORDER BY l.id FOR UPDATE OF l NOWAIT",
            db, tx, branch, actor.Id))
        {
            lines.Parameters.AddWithValue("order", order);
            using var reader = await lines.ExecuteReaderAsync();
            while (await reader.ReadAsync())
                if (!reader.GetBoolean(0))
                    throw new InvalidOperationException("The order includes saved lines outside this branch.");
        }
        using var relationships = RegisterCommand(@"
            SELECT (o.customer_id IS NULL OR EXISTS (SELECT 1 FROM public.crm_companies c " + OrderCustomerScope + @"
                AND c.id=o.customer_id))
                AND (o.crm_deal_id IS NULL OR EXISTS (SELECT 1 FROM public.crm_deals d WHERE d.id=o.crm_deal_id
                    AND d.organization_id=@company AND d.deleted_at IS NULL AND " + ConfirmationOwnership("d", "crm_deals") + @"))
                AND (o.crm_quote_id IS NULL OR EXISTS (SELECT 1 FROM public.crm_quotations q WHERE q.id=o.crm_quote_id
                    AND q.organization_id=@company AND q.deleted_at IS NULL AND " + ConfirmationOwnership("q", "crm_quotations") + @"))
            FROM public.srm_sales_orders o WHERE o.id=@order", db, tx, branch, actor.Id);
        relationships.Parameters.AddWithValue("order", order);
        if ((bool?)await relationships.ExecuteScalarAsync() != true)
            throw new InvalidOperationException("A related customer, CRM deal, or quotation is unavailable in this branch.");
    }

    private async Task<int> CreateConfirmationEngagementAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, int actor, int order)
    {
        string number = await ReserveCommercialNumberAsync(db, tx, CommercialNumberSeries.Engagement);
        using var create = RegisterCommand(@"
            WITH engagement AS (
                INSERT INTO public.srm_engagements (organization_id,engagement_number,sales_order_id,customer_id,
                    crm_deal_id,crm_quote_id,assigned_user_id,name,status,billing_type,budget_amount,currency,created_by)
                SELECT @company,@number,id,customer_id,crm_deal_id,crm_quote_id,assigned_user_id,title,'project_pending',
                    'fixed_fee',total_amount,currency,@actor FROM public.srm_sales_orders WHERE id=@order
                RETURNING id,sales_order_id,crm_deal_id,crm_quote_id
            ), links AS (
                INSERT INTO public.srm_engagement_links (engagement_id,linked_module,linked_entity_type,linked_entity_id,label)
                SELECT e.id,link.module,link.kind,link.identifier,link.module||':'||link.kind
                FROM engagement e CROSS JOIN LATERAL (VALUES ('crm','deal',e.crm_deal_id),('crm','quote',e.crm_quote_id),
                    ('srm','sales_order',e.sales_order_id)) link(module,kind,identifier)
                WHERE link.identifier IS NOT NULL RETURNING id
            ), ownership AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'srm_engagements',id::text,@company,@branch,'validated-write' FROM engagement
                UNION ALL SELECT 'srm_engagement_links',id::text,@company,@branch,'validated-write' FROM links
            )
            SELECT id FROM engagement", db, tx, branch, actor);
        create.Parameters.AddWithValue("number", number);
        create.Parameters.AddWithValue("order", order);
        return (int)(await create.ExecuteScalarAsync())!;
    }

    private async Task<int> CreateConfirmationPlanAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        int actor, int order, int engagement, int? contract)
    {
        using var create = RegisterCommand(@"
            WITH order_lines AS (
                SELECT l.*, row_number() OVER(ORDER BY l.id) AS ordinal
                FROM public.srm_sales_order_lines l WHERE l.sales_order_id=@order
            ), plan AS (
                INSERT INTO public.srm_billing_plans
                    (organization_id,engagement_id,name,billing_type,status,currency,total_amount,created_by)
                SELECT @company,@engagement,'Billing plan for '||order_number,
                    CASE WHEN EXISTS (SELECT 1 FROM order_lines) THEN 'milestone' ELSE 'fixed_fee' END,
                    'draft',currency,total_amount,@actor FROM public.srm_sales_orders WHERE id=@order
                RETURNING id,billing_type,total_amount
            ), milestones AS (
                INSERT INTO public.srm_billing_milestones (billing_plan_id,name,status,amount,metadata_json)
                SELECT plan.id,coalesce(nullif(l.description,''),'Milestone '||l.ordinal),'pending',coalesce(l.line_total,0),
                    json_build_object('sales_order_line_id',l.id,'source_quote_line_id',l.source_quote_line_id,
                        'pms_template_key',l.metadata_json->'pms_template_key')
                FROM plan CROSS JOIN order_lines l
                UNION ALL SELECT plan.id,o.title,'pending',plan.total_amount,NULL
                FROM plan JOIN public.srm_sales_orders o ON o.id=@order WHERE plan.billing_type='fixed_fee'
                RETURNING id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'billing_plan',id,'created_from_sales_order',@actor,
                    json_build_object('sales_order_id',@order,'contract_id',@contract) FROM plan RETURNING id
            ), ownership AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'srm_billing_plans',id::text,@company,@branch,'validated-write' FROM plan
                UNION ALL SELECT 'srm_billing_milestones',id::text,@company,@branch,'validated-write' FROM milestones
                UNION ALL SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit
            )
            SELECT id FROM plan", db, tx, branch, actor);
        create.Parameters.AddWithValue("order", order);
        create.Parameters.AddWithValue("engagement", engagement);
        create.Parameters.AddWithValue("contract", NpgsqlDbType.Integer, (object?)contract ?? DBNull.Value);
        return (int)(await create.ExecuteScalarAsync())!;
    }
}
