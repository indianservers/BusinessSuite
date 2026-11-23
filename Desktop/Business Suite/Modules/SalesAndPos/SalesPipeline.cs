using System.Globalization;
using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record SalesPipelineStage(string Status, long Count)
{
    public string Display => $"{Status.Replace('_', ' ')} ({Count:N0})";
}
internal sealed record SalesPipelineOrder(int Id, string Number, string Title, string Status, string Currency,
    decimal Total, DateTime Created, DateTime? Expected, int? StageAge, decimal Unbilled, string Signals);
internal sealed record SalesPipelineFilterChoice(int Id, string Label);
internal sealed record SalesPipelineFilters(List<SalesPipelineFilterChoice> Owners, List<SalesPipelineFilterChoice> Teams,
    List<SalesPipelineFilterChoice> Customers);
internal sealed record SalesPipelinePage(DateTime? From, DateTime Until, List<SalesPipelineStage> Stages,
    List<SalesPipelineOrder> Orders);

internal sealed partial class SalesOrderRepository
{
    private const int PipelineOrderLimit = 250;
    private const string PipelineSource = @"
        SELECT o.id,o.order_number,o.title,coalesce(o.status,'unknown') AS status,coalesce(o.currency,'') AS currency,
            coalesce(o.total_amount,0) AS total,(o.created_at AT TIME ZONE @zone)::date AS created,o.expected_end_date,
            (coalesce(o.updated_at,o.created_at) AT TIME ZONE @zone)::date AS touched,o.metadata_json
        FROM public.srm_sales_orders o" + OrderScope + @"
            AND o.created_at IS NOT NULL AND (o.created_at AT TIME ZONE @zone)::date<=@until
            AND (@from IS NULL OR (o.created_at AT TIME ZONE @zone)::date>=@from)
            AND (@owner IS NULL OR o.assigned_user_id=@owner)
            AND (@team IS NULL OR EXISTS (SELECT 1 FROM public.business_sales_team_assignments assigned
                JOIN public.crm_teams t ON t.id=assigned.team_id AND t.organization_id=@company AND t.deleted_at IS NULL
                WHERE assigned.sales_order_id=o.id AND t.id=@team))
            AND (@customer IS NULL OR o.customer_id=(SELECT c.id FROM public.crm_companies c" + OrderCustomerScope +
                " AND c.id=@customer))";

    internal Task<SalesPipelinePage> SalesPipelineAsync(string period, DateTime? from, DateTime? until, string? status) =>
        FilteredSalesPipelineAsync(period, from, until, status, null, null, null);

    internal async Task<SalesPipelinePage> FilteredSalesPipelineAsync(string period, DateTime? from, DateTime? until,
        string? status, int? owner, int? team, int? customer)
    {
        if (owner is <= 0 || team is <= 0 || customer is <= 0)
            throw new ArgumentException("Choose a valid owner, team or customer.");
        if (period is not ("month" or "today" or "week" or "all" or "custom"))
            throw new ArgumentException("Choose a pipeline period.");
        if (period == "custom" && (!from.HasValue || !until.HasValue || until.Value.Date < from.Value.Date ||
            (until.Value.Date - from.Value.Date).TotalDays > 3660))
            throw new ArgumentException("Choose a valid inclusive date range of up to ten years.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to view the Sales pipeline.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor);
        await RequireNativeRegisterBranchAsync(db, tx, branch, "desktop Sales pipeline");

        DateTime today;
        string zone;
        using (var context = ScopedCommand(@"SELECT zone.name,(now() AT TIME ZONE zone.name)::date
            FROM public.companies c JOIN pg_timezone_names zone
                ON zone.name=coalesce(nullif(c.default_timezone,''),'Asia/Kolkata')
            WHERE c.id=@company", db, tx, branch, actor, scope))
        using (var reader = await context.ExecuteReaderAsync())
        {
            if (!await reader.ReadAsync())
                throw new InvalidOperationException("The company's business time zone is unavailable.");
            zone = reader.GetString(0);
            today = reader.GetDateTime(1);
        }
        DateTime end = period == "custom" ? until!.Value.Date : today;
        DateTime? start = period switch
        {
            "custom" => from!.Value.Date,
            "today" => today,
            "week" => today.AddDays(-(((int)today.DayOfWeek + 6) % 7)),
            "month" => new DateTime(today.Year, today.Month, 1),
            _ => null
        };

        using var counts = PipelineCommand("SELECT status,count(*) FROM (" + PipelineSource +
            ") orders GROUP BY status ORDER BY status");
        var stages = new List<SalesPipelineStage>();
        using (var reader = await counts.ExecuteReaderAsync())
            while (await reader.ReadAsync())
                stages.Add(new SalesPipelineStage(reader.GetString(0), reader.GetInt64(1)));

        using var list = PipelineCommand(@"SELECT orders.id,order_number,title,orders.status,currency,total,created,expected_end_date,age.days,billing.unbilled,
            concat_ws(' | ',
                CASE WHEN age.days>=14 AND orders.status NOT IN ('closed','cancelled','completed','delivered')
                    THEN 'In current stage for '||age.days||' days' END,
                CASE WHEN orders.status='pending_approval' THEN 'Pending approval' END,
                CASE WHEN orders.metadata_json::jsonb->'credit_hold'='true'::jsonb THEN 'Recorded credit hold' END,
                stock.signals,
                CASE WHEN @today-touched>=14 AND orders.status NOT IN ('closed','cancelled','completed')
                    THEN 'No update for '||(@today-touched)||' days' END,
                CASE WHEN expected_end_date<@today AND orders.status NOT IN ('closed','cancelled','completed','delivered')
                    THEN 'Delivery date passed' END,
                CASE WHEN billing.unbilled>0 THEN 'Delivered/completed value not fully invoiced' END)
            FROM (SELECT * FROM (" + PipelineSource + @") source WHERE (@status IS NULL OR status=@status)
                ORDER BY created DESC,id DESC LIMIT @limit) orders
            LEFT JOIN LATERAL (
                SELECT ev.created_at,ev.payload_json->'data'->>'stage' AS stage
                FROM public.suite_service_events ev WHERE ev.organization_id=@company AND ev.module_key='srm'
                    AND ev.event_type='pipeline.stage_entered' AND ev.entity_type='sales_order' AND ev.entity_id=orders.id
                ORDER BY ev.id DESC LIMIT 1
            ) entry ON true
            CROSS JOIN LATERAL (
                SELECT CASE WHEN entry.stage=orders.status
                    THEN greatest(0,@today-(entry.created_at AT TIME ZONE @zone)::date) END AS days
            ) age
            LEFT JOIN LATERAL (
                SELECT string_agg(CASE WHEN balances.quantity IS NULL
                    THEN 'Stock availability not verified: '||item.sku
                    WHEN sale_line.quantity>balances.quantity THEN 'Stock shortfall: '||item.sku||
                        ' (on hand '||balances.quantity||', ordered '||sale_line.quantity||')'
                    END,' | ' ORDER BY sale_line.id) AS signals
                FROM public.srm_sales_order_lines sale_line
                JOIN LATERAL (SELECT p.id,coalesce(nullif(p.sku,''),p.item_name) AS sku" +
                    SharedCatalogRepository.ProductAndDetail + SharedCatalogRepository.ProductVisibility + @"
                    AND p.organization_id=@company AND p.id=sale_line.product_id AND p.product_type='stock'
                    AND p.track_inventory LIMIT 1) item ON true
                CROSS JOIN LATERAL (
                    SELECT sum(coalesce(b.quantity,0)) AS quantity FROM public.srm_inventory_balances b
                    JOIN public.srm_warehouses w ON w.id=b.warehouse_id AND w.organization_id=@company
                    WHERE b.organization_id=@company AND b.product_id=item.id
                        AND " + ConfirmationOwnership("w", "srm_warehouses") + " AND " +
                        ConfirmationOwnership("b", "srm_inventory_balances") + @"
                ) balances
                WHERE sale_line.sales_order_id=orders.id AND " + ConfirmationOwnership("sale_line", "srm_sales_order_lines") + @"
                    AND orders.status NOT IN ('closed','cancelled','completed','delivered')
            ) stock ON true
            CROSS JOIN LATERAL (
                SELECT CASE WHEN orders.status IN ('delivered','completed','closed') AND orders.currency<>''
                    THEN greatest(0,orders.total-coalesce(sum(i.total_amount),0)) ELSE 0 END AS unbilled
                FROM public.srm_invoices i WHERE orders.status IN ('delivered','completed','closed')
                    AND i.organization_id=@company AND i.sales_order_id=orders.id AND i.deleted_at IS NULL
                    AND i.currency=orders.currency AND i.status NOT IN ('draft','cancelled','void')
                    " + HistoryInvoiceAccess + @"
            ) billing
            ORDER BY created DESC,orders.id DESC");
        list.Parameters.AddWithValue("status", NpgsqlDbType.Text, (object?)status ?? DBNull.Value);
        list.Parameters.AddWithValue("limit", PipelineOrderLimit);
        list.Parameters.AddWithValue("today", NpgsqlDbType.Date, today);
        list.Parameters.AddWithValue("branch_key", branch.ToString(CultureInfo.InvariantCulture));
        list.Parameters.AddWithValue("admin", actor.IsSuperuser || actor.IsCompanyAdmin);
        var orders = new List<SalesPipelineOrder>();
        using (var rows = await list.ExecuteReaderAsync())
            while (await rows.ReadAsync())
                orders.Add(new SalesPipelineOrder(rows.GetInt32(0), rows.GetString(1), rows.GetString(2), rows.GetString(3),
                    rows.GetString(4), rows.GetDecimal(5), rows.GetDateTime(6), rows.IsDBNull(7) ? null : rows.GetDateTime(7),
                    rows.IsDBNull(8) ? null : rows.GetInt32(8), rows.GetDecimal(9), rows.GetString(10)));
        tx.Commit();
        return new SalesPipelinePage(start, end, stages, orders);

        NpgsqlCommand PipelineCommand(string sql)
        {
            var command = ScopedCommand(sql, db, tx, branch, actor, scope);
            command.Parameters.AddWithValue("from", NpgsqlDbType.Date, (object?)start ?? DBNull.Value);
            command.Parameters.AddWithValue("until", NpgsqlDbType.Date, end);
            command.Parameters.AddWithValue("zone", NpgsqlDbType.Text, zone);
            command.Parameters.AddWithValue("owner", NpgsqlDbType.Integer, (object?)owner ?? DBNull.Value);
            command.Parameters.AddWithValue("team", NpgsqlDbType.Integer, (object?)team ?? DBNull.Value);
            command.Parameters.AddWithValue("customer", NpgsqlDbType.Integer, (object?)customer ?? DBNull.Value);
            return command;
        }
    }

    internal async Task<SalesPipelineFilters> SalesPipelineFiltersAsync()
    {
        var rows = await ReadAsync(@"WITH visible AS (SELECT o.id,o.assigned_user_id,o.customer_id
            FROM public.srm_sales_orders o" + OrderScope + @"), options AS (
                SELECT DISTINCT 'owner' AS kind,v.assigned_user_id AS id,coalesce(u.email,'Owner #'||v.assigned_user_id) AS label
                FROM visible v LEFT JOIN public.users u ON u.id=v.assigned_user_id AND (u.id=@actor OR EXISTS (
                    SELECT 1 FROM public.common_people p WHERE p.user_id=u.id AND p.organization_id=@company))
                WHERE v.assigned_user_id IS NOT NULL
                UNION ALL
                SELECT DISTINCT 'team',t.id,t.name FROM visible v
                JOIN public.business_sales_team_assignments assignment ON assignment.sales_order_id=v.id
                JOIN public.crm_teams t ON t.id=assignment.team_id AND t.organization_id=@company AND t.deleted_at IS NULL
                UNION ALL
                SELECT DISTINCT 'customer',c.id,c.name FROM public.crm_companies c" + OrderCustomerScope + @"
                    AND EXISTS (SELECT 1 FROM visible v WHERE v.customer_id=c.id)
            ) SELECT kind,id,label FROM options ORDER BY kind,lower(label),id", _ => { }, reader =>
                (Kind: reader.GetString(0), Option: new SalesPipelineFilterChoice(reader.GetInt32(1), reader.GetString(2))),
            requireNativeBranch: true);
        return new SalesPipelineFilters(Select("owner"), Select("team"), Select("customer"));

        List<SalesPipelineFilterChoice> Select(string kind) =>
            rows.Where(row => row.Kind == kind).Select(row => row.Option).ToList();
    }

}
