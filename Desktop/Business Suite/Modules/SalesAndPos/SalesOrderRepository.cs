using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record SalesOrderRow(int Id, string OrderNumber, string Title, string Status,
    string Currency, decimal Total, DateTime? StartDate, DateTime? EndDate)
{
    public string Customer { get; init; } = "";
}

internal sealed record SalesOrderLineRow(string ItemCode, string Description, decimal Quantity, decimal UnitPrice,
    decimal Discount, decimal Tax, decimal LineTotal);

internal sealed record PosSessionRow(string Number, string Status, string Register, DateTime Opened,
    DateTime? Closed, decimal OpeningCash, decimal? ExpectedCash, decimal? CountedCash, decimal? Variance);

internal sealed partial class SalesOrderRepository
{
    internal const int ResultLimit = 200;
    private readonly DesktopDatabaseSettings settings;

    internal SalesOrderRepository(DesktopDatabaseSettings settings) => this.settings = settings;

    private const string OrderScope = OrderAccess + " AND o.deleted_at IS NULL";
    private const string OrderDetailScope = OrderAccess + " AND (o.deleted_at IS NULL OR o.status='archived')";
    private const string OrderAccess = @"
        WHERE coalesce(o.organization_id, 1) = @company
          AND (
              @scope = 'organization'
              OR (@scope = 'legacy_assigned' AND o.assigned_user_id = @actor)
              OR (@scope = 'own' AND o.assigned_user_id = @actor AND o.created_by = @actor)
              OR (@scope = 'team' AND o.created_by = @actor)
              OR (@scope IN ('branch', 'department', 'team') AND EXISTS (
                  SELECT 1 FROM public.employees member
                  JOIN public.employees actor ON actor.user_id = @actor AND actor.deleted_at IS NULL
                  WHERE member.user_id = o.created_by AND member.deleted_at IS NULL AND member.branch_id = @branch
                    AND ((@scope = 'branch' AND member.branch_id = actor.branch_id)
                      OR (@scope = 'department' AND member.department_id = actor.department_id)
                      OR (@scope = 'team' AND member.reporting_manager_id = actor.id))
              ))
          )
          AND EXISTS (
              SELECT 1 FROM public.suite_branch_ownership b
              WHERE b.company_id = @company AND b.branch_id = @branch
                AND b.resource_table = 'srm_sales_orders' AND b.resource_key = o.id::text
          )
          AND NOT EXISTS (
              SELECT 1 FROM public.business_pack_record_ownership p
              WHERE p.company_id = @company AND p.resource_table = 'srm_sales_orders' AND p.resource_key = o.id::text
          )";

    internal Task<List<SalesOrderRow>> ListAsync(string search, string status) => ListFilteredAsync(search, status, null, null);

    internal Task<List<SalesOrderRow>> ListFilteredAsync(string search, string status, DateTime? from, DateTime? until)
    {
        if (from.HasValue && until.HasValue && from.Value.Date > until.Value.Date)
            throw new ArgumentException("The latest end date must be on or after the earliest start date.");
        const string sql = @"
            SELECT o.id, o.order_number, o.title, coalesce(o.status, ''), coalesce(o.currency, ''),
                   coalesce(o.total_amount, 0), o.expected_start_date, o.expected_end_date, coalesce(buyer.name, '')
            FROM public.srm_sales_orders o
            LEFT JOIN LATERAL (
                SELECT CASE WHEN EXISTS (SELECT 1 FROM public.srm_anonymous_cash_accounts a
                    WHERE a.organization_id=@company AND a.branch_id=@branch AND a.pack_context_id IS NULL AND a.customer_id=o.customer_id)
                    THEN 'Walk-in' ELSE (SELECT c.name FROM public.crm_companies c " + OrderCustomerScope +
                        @" AND c.id=o.customer_id) END AS name
            ) buyer ON true" + OrderAccess + @"
              AND ((@status='archived' AND o.status='archived') OR (o.deleted_at IS NULL AND o.status IS DISTINCT FROM 'archived'
                  AND (@status = '' OR o.status = @status)))
              AND (@from IS NULL OR o.expected_start_date>=@from)
              AND (@until IS NULL OR o.expected_end_date<=@until)
              AND (@search = '' OR strpos(lower(o.order_number), lower(@search)) > 0
                               OR strpos(lower(o.title), lower(@search)) > 0
                               OR strpos(lower(coalesce(buyer.name,'')), lower(@search)) > 0)
            ORDER BY o.id DESC LIMIT @limit";
        return ReadAsync(sql, command =>
        {
            command.Parameters.AddWithValue("search", NpgsqlDbType.Text, search);
            command.Parameters.AddWithValue("status", NpgsqlDbType.Text, status);
            command.Parameters.AddWithValue("from", NpgsqlDbType.Date, (object?)from?.Date ?? DBNull.Value);
            command.Parameters.AddWithValue("until", NpgsqlDbType.Date, (object?)until?.Date ?? DBNull.Value);
            command.Parameters.AddWithValue("limit", NpgsqlDbType.Integer, ResultLimit);
        }, reader => new SalesOrderRow(reader.GetInt32(0), reader.GetString(1), reader.GetString(2),
            reader.GetString(3), reader.GetString(4), reader.GetDecimal(5),
            reader.IsDBNull(6) ? null : reader.GetDateTime(6),
            reader.IsDBNull(7) ? null : reader.GetDateTime(7)) { Customer = reader.GetString(8) });
    }

    internal Task<List<SalesOrderLineRow>> LinesAsync(int orderId)
    {
        const string sql = @"
            SELECT coalesce(l.item_code, ''), coalesce(l.description, ''), coalesce(l.quantity, 0),
                   coalesce(l.unit_price, 0), coalesce(l.discount_amount, 0), coalesce(l.tax_amount, 0),
                   coalesce(l.line_total, 0)
            FROM public.srm_sales_orders o
            JOIN public.srm_sales_order_lines l ON l.sales_order_id = o.id" + OrderDetailScope + @"
              AND o.id = @order
              AND EXISTS (
                  SELECT 1 FROM public.suite_branch_ownership b
                  WHERE b.company_id = @company AND b.branch_id = @branch
                    AND b.resource_table = 'srm_sales_order_lines' AND b.resource_key = l.id::text
              )
              AND NOT EXISTS (
                  SELECT 1 FROM public.business_pack_record_ownership p
                  WHERE p.company_id = @company AND p.resource_table = 'srm_sales_order_lines' AND p.resource_key = l.id::text
              )
            ORDER BY l.id";
        return ReadAsync(sql, command => command.Parameters.AddWithValue("order", NpgsqlDbType.Integer, orderId),
            reader => new SalesOrderLineRow(reader.GetString(0), reader.GetString(1), reader.GetDecimal(2),
                reader.GetDecimal(3), reader.GetDecimal(4), reader.GetDecimal(5), reader.GetDecimal(6)));
    }

    internal Task<List<PosSessionRow>> PosSessionsAsync()
    {
        const string sql = @"
            SELECT p.session_number, p.status, coalesce(p.register_name, ''), p.opened_at,
                   p.closed_at, coalesce(p.opening_cash, 0),
                   CASE WHEN p.status='closed' THEN p.expected_cash END,
                   CASE WHEN p.status='closed' THEN p.counted_cash END,
                   CASE WHEN p.status='closed' THEN p.cash_variance END
            FROM public.srm_pos_sessions p
            WHERE p.organization_id = @company AND p.deleted_at IS NULL AND p.opened_at IS NOT NULL
              AND (@scope = 'organization' OR (@scope IN ('legacy_assigned','own','team')
                    AND p.cashier_user_id = @actor AND p.created_by = @actor))
              AND EXISTS (
                  SELECT 1 FROM public.suite_branch_ownership b
                  WHERE b.company_id = @company AND b.branch_id = @branch
                    AND b.resource_table = 'srm_pos_sessions' AND b.resource_key = p.id::text
              )
              AND NOT EXISTS (
                  SELECT 1 FROM public.business_pack_record_ownership x
                  WHERE x.company_id = @company AND x.resource_table = 'srm_pos_sessions' AND x.resource_key = p.id::text
              )
            ORDER BY p.id DESC LIMIT 100";
        return ReadAsync(sql, _ => { }, reader => new PosSessionRow(reader.GetString(0),
            reader.IsDBNull(1) ? "" : reader.GetString(1), reader.GetString(2), reader.GetDateTime(3).ToLocalTime(),
            reader.IsDBNull(4) ? null : reader.GetDateTime(4).ToLocalTime(), reader.GetDecimal(5),
            reader.IsDBNull(6) ? null : reader.GetDecimal(6), reader.IsDBNull(7) ? null : reader.GetDecimal(7),
            reader.IsDBNull(8) ? null : reader.GetDecimal(8)));
    }

    private async Task<List<T>> ReadAsync<T>(string sql, Action<NpgsqlCommand> bind, Func<NpgsqlDataReader, T> map,
        string action = "view", bool requireNativeBranch = false)
    {
        int branchId = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to view sales orders.");
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync();
        using var transaction = connection.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", connection, transaction))
            await readOnly.ExecuteNonQueryAsync();
        DesktopActor actor = await settings.RequireActorAsync(connection, transaction, CancellationToken.None);
        if (action != "view" && !actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        string scope = await SalesReadAccess.OrderScopeAsync(connection, transaction,
            settings.OrganizationId, branchId, actor, action);
        if (requireNativeBranch)
            await RequireNativeRegisterBranchAsync(connection, transaction, branchId, "desktop Sales pipeline filters");
        using var command = ScopedCommand(sql, connection, transaction, branchId, actor, scope);
        bind(command);
        var rows = new List<T>();
        using (var reader = await command.ExecuteReaderAsync())
            while (await reader.ReadAsync())
                rows.Add(map(reader));
        transaction.Commit();
        return rows;
    }

    private NpgsqlCommand ScopedCommand(string sql, NpgsqlConnection connection, NpgsqlTransaction transaction,
        int branchId, DesktopActor actor, string scope)
    {
        var command = new NpgsqlCommand(sql, connection, transaction);
        command.Parameters.AddWithValue("company", NpgsqlDbType.Integer, settings.OrganizationId);
        command.Parameters.AddWithValue("branch", NpgsqlDbType.Integer, branchId);
        command.Parameters.AddWithValue("actor", NpgsqlDbType.Integer, actor.Id);
        command.Parameters.AddWithValue("scope", NpgsqlDbType.Text, scope);
        return command;
    }
}
