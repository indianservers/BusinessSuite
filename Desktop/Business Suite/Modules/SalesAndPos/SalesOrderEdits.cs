using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record SalesOrderEdit(int Id, string Number, string Title, string Terms, string Revision,
    bool HasInvoice, IReadOnlyList<SalesOrderEditLine> Lines)
{
    internal SalesOrderSchedule Schedule { get; init; } = new(null, null);
}
internal sealed record SalesOrderSchedule(DateTime? Start, DateTime? End);
internal sealed record SalesOrderEditLine(int Id, string ItemCode, string Description, decimal Quantity,
    decimal UnitPrice, decimal Discount, decimal Tax);

internal sealed partial class SalesOrderRepository
{
    private const string EditableOrder = OrderScope + @"
        AND o.id = @order AND lower(o.status) IN ('draft', 'created', 'planned')
        AND o.metadata_json->>'source' IS DISTINCT FROM 'pos'
        AND NOT EXISTS (
            SELECT 1 FROM public.srm_sales_order_lines l WHERE l.sales_order_id = o.id
            AND (
                NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership b
                    WHERE b.company_id = @company AND b.branch_id = @branch
                      AND b.resource_table = 'srm_sales_order_lines' AND b.resource_key = l.id::text)
                OR EXISTS (SELECT 1 FROM public.business_pack_record_ownership p
                    WHERE p.company_id = @company AND p.resource_table = 'srm_sales_order_lines' AND p.resource_key = l.id::text)
            )
        )";

    private const string EditSnapshot = @"
        SELECT o.id, o.order_number, o.title, coalesce(o.terms, ''),
               md5((snapshot.record - 'updated_at')::text), snapshot.record::text,
               EXISTS (SELECT 1 FROM public.srm_invoices i WHERE i.sales_order_id=o.id),
               o.expected_start_date, o.expected_end_date
        FROM public.srm_sales_orders o
        CROSS JOIN LATERAL (
            SELECT to_jsonb(o) || jsonb_build_object('lines', coalesce((
                SELECT jsonb_agg(to_jsonb(l) ORDER BY l.id)
                FROM public.srm_sales_order_lines l WHERE l.sales_order_id = o.id
            ), '[]'::jsonb)) AS record
        ) snapshot" + EditableOrder;

    internal async Task<SalesOrderEdit> LoadEditAsync(int orderId)
    {
        var rows = await ReadAsync(EditSnapshot,
            command => command.Parameters.AddWithValue("order", NpgsqlDbType.Integer, orderId),
            reader => new SalesOrderEdit(reader.GetInt32(0), reader.GetString(1), reader.GetString(2),
                reader.GetString(3), reader.GetString(4), reader.GetBoolean(6), SnapshotLines(reader.GetString(5)))
                {
                    Schedule = new SalesOrderSchedule(reader.IsDBNull(7) ? null : reader.GetDateTime(7),
                        reader.IsDBNull(8) ? null : reader.GetDateTime(8))
                }, "edit");
        return rows.SingleOrDefault() ?? throw EditUnavailable();
    }

    internal Task UpdateHeaderAsync(SalesOrderEdit original, string title, string terms, string reason, Guid request) =>
        EditSalesOrderAsync(original, title, terms, reason, request, null);

    internal Task EditSalesOrderAsync(SalesOrderEdit original, string title, string terms, string reason, Guid request,
        IReadOnlyList<SalesOrderEditLine>? lines) =>
        EditSalesOrderScheduleAsync(original, title, terms, reason, request, lines, original.Schedule);

    internal async Task EditSalesOrderScheduleAsync(SalesOrderEdit original, string title, string terms, string reason,
        Guid request, IReadOnlyList<SalesOrderEditLine>? lines, SalesOrderSchedule schedule)
    {
        title = title.Trim();
        reason = reason.Trim();
        if (title.Length is 0 or > 220)
            throw new ArgumentException("Enter a title of up to 220 characters.");
        if (terms.Length > 10000)
            throw new ArgumentException("Terms must contain at most 10,000 characters.");
        if (reason.Length is < 5 or > 500)
            throw new ArgumentException("Enter an edit reason of 5 to 500 characters.");
        if (request == Guid.Empty)
            throw new ArgumentException("The document edit request is invalid.");
        schedule = new SalesOrderSchedule(schedule.Start?.Date, schedule.End?.Date);
        bool scheduleChanged = schedule != original.Schedule;
        if (scheduleChanged && schedule.Start.HasValue && schedule.End.HasValue && schedule.End < schedule.Start)
            throw new ArgumentException("End date must be on or after start date.");
        var orderedLines = lines?.OrderBy(line => line.Id).ToArray();
        string digest = scheduleChanged ? HashSalesPayload(new { title, terms, reason, lines = orderedLines, schedule })
            : HashSalesPayload(new { title, terms, reason, lines = orderedLines });

        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to edit sales orders.");
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync();
        using var transaction = connection.BeginTransaction();
        await settings.VerifyWriteTargetAsync(connection, transaction, CancellationToken.None);
        await LockCompanyWriterAsync(connection, transaction);
        var actor = await settings.RequireActorAsync(connection, transaction, CancellationToken.None);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        string scope = await SalesReadAccess.OrderScopeAsync(connection, transaction, settings.OrganizationId, branch, actor, "edit");
        await RequireNativeRegisterBranchAsync(connection, transaction, branch, "desktop sales order editing");

        using (var lockOrder = ScopedCommand("SELECT o.id FROM public.srm_sales_orders o" + EditableOrder +
            " FOR UPDATE OF o", connection, transaction, branch, actor, scope))
        {
            lockOrder.Parameters.AddWithValue("order", NpgsqlDbType.Integer, original.Id);
            if (await lockOrder.ExecuteScalarAsync() is not int)
                throw EditUnavailable();
        }
        // Some web line routes lock a line before they recalculate the header.
        // Fail promptly if one of those writers already owns a line lock.
        try
        {
            using var lockLines = new NpgsqlCommand(@"SELECT id FROM public.srm_sales_order_lines
                WHERE sales_order_id=@order ORDER BY id FOR UPDATE NOWAIT", connection, transaction);
            lockLines.Parameters.AddWithValue("order", NpgsqlDbType.Integer, original.Id);
            await lockLines.ExecuteNonQueryAsync();
        }
        catch (PostgresException error) when (error.SqlState == PostgresErrorCodes.LockNotAvailable)
        {
            throw new InvalidOperationException("Another user is editing this order. Refresh and retry.", error);
        }
        using var read = ScopedCommand(EditSnapshot, connection, transaction, branch, actor, scope);
        read.Parameters.AddWithValue("order", NpgsqlDbType.Integer, original.Id);
        string version;
        string before;
        bool invoiced;
        using (var result = await read.ExecuteReaderAsync())
        {
            if (!await result.ReadAsync())
                throw EditUnavailable();
            version = result.GetString(4);
            before = result.GetString(5);
            invoiced = result.GetBoolean(6);
        }
        using var duplicate = ScopedCommand(@"
            SELECT coalesce(after_json->>'request_sha256'=@digest,
                @header_only AND after_json->'record'->>'title'=@title AND after_json->'record'->>'terms'=@terms
                    AND after_json->>'reason'=@reason, false)
            FROM public.srm_audit_logs a
            WHERE a.organization_id=@company AND a.actor_user_id=@actor AND a.entity_type='sales_order'
              AND a.entity_id=@order AND a.action='document_modified' AND a.after_json->>'request_id'=@request
              AND EXISTS (SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company
                AND b.branch_id=@branch AND b.resource_table='srm_audit_logs' AND b.resource_key=a.id::text)",
            connection, transaction, branch, actor, scope);
        duplicate.Parameters.AddWithValue("order", NpgsqlDbType.Integer, original.Id);
        duplicate.Parameters.AddWithValue("request", NpgsqlDbType.Text, request.ToString());
        duplicate.Parameters.AddWithValue("title", NpgsqlDbType.Text, title);
        duplicate.Parameters.AddWithValue("terms", NpgsqlDbType.Text, terms);
        duplicate.Parameters.AddWithValue("reason", NpgsqlDbType.Text, reason);
        duplicate.Parameters.AddWithValue("digest", NpgsqlDbType.Text, digest);
        duplicate.Parameters.AddWithValue("header_only", NpgsqlDbType.Boolean, lines is null && !scheduleChanged);
        object? replay = await duplicate.ExecuteScalarAsync();
        if (replay is true)
        {
            transaction.Commit();
            return;
        }
        if (replay is not null)
            throw new InvalidOperationException("An earlier save completed. Close the editor and refresh before continuing.");
        if (!StringComparer.Ordinal.Equals(version, original.Revision))
            throw new InvalidOperationException("This sales order changed. Close the editor and refresh before continuing.");

        SalesLineAmounts? amounts = null;
        if (lines is not null)
        {
            if (invoiced)
                throw new InvalidOperationException("This order has an invoice. Create a revision to change its items.");
            amounts = await EditStoredLinesAsync(connection, transaction, original.Id, SnapshotLines(before), lines);
        }
        using var write = ScopedCommand(@"
            UPDATE public.srm_sales_orders o SET title=@title,terms=@terms,updated_at=now(),
                expected_start_date=CASE WHEN @schedule_changed THEN @start ELSE o.expected_start_date END,
                expected_end_date=CASE WHEN @schedule_changed THEN @end ELSE o.expected_end_date END,
                subtotal=coalesce(@subtotal,o.subtotal),discount_amount=coalesce(@discount,o.discount_amount),
                tax_amount=coalesce(@tax,o.tax_amount),total_amount=coalesce(@total,o.total_amount)" + EditableOrder,
            connection, transaction, branch, actor, scope);
        write.Parameters.AddWithValue("order", NpgsqlDbType.Integer, original.Id);
        write.Parameters.AddWithValue("title", NpgsqlDbType.Text, title);
        write.Parameters.AddWithValue("terms", NpgsqlDbType.Text, terms);
        write.Parameters.AddWithValue("schedule_changed", NpgsqlDbType.Boolean, scheduleChanged);
        write.Parameters.AddWithValue("start", NpgsqlDbType.Date, (object?)schedule.Start ?? DBNull.Value);
        write.Parameters.AddWithValue("end", NpgsqlDbType.Date, (object?)schedule.End ?? DBNull.Value);
        write.Parameters.AddWithValue("subtotal", NpgsqlDbType.Numeric, (object?)amounts?.Subtotal ?? DBNull.Value);
        write.Parameters.AddWithValue("discount", NpgsqlDbType.Numeric, (object?)amounts?.Discount ?? DBNull.Value);
        write.Parameters.AddWithValue("tax", NpgsqlDbType.Numeric, (object?)amounts?.Tax ?? DBNull.Value);
        write.Parameters.AddWithValue("total", NpgsqlDbType.Numeric, (object?)amounts?.Total ?? DBNull.Value);
        if (await write.ExecuteNonQueryAsync() != 1)
            throw EditUnavailable();

        string after;
        using (var result = await read.ExecuteReaderAsync())
        {
            if (!await result.ReadAsync())
                throw EditUnavailable();
            after = result.GetString(5);
        }
        using var audit = ScopedCommand(@"
            WITH entry AS (
                INSERT INTO public.srm_audit_logs
                    (organization_id, entity_type, entity_id, action, actor_user_id, before_json, after_json)
                VALUES (@company, 'sales_order', @order, 'document_modified', @actor, @before,
                    json_build_object('record', CAST(@after AS json), 'reason', @reason, 'request_id', @request,
                                      'request_sha256', @digest))
                RETURNING id
            )
            INSERT INTO public.suite_branch_ownership (resource_table, resource_key, company_id, branch_id, source)
            SELECT 'srm_audit_logs', id::text, @company, @branch, 'validated-write' FROM entry",
            connection, transaction, branch, actor, scope);
        audit.Parameters.AddWithValue("order", NpgsqlDbType.Integer, original.Id);
        audit.Parameters.AddWithValue("before", NpgsqlDbType.Json, before);
        audit.Parameters.AddWithValue("after", NpgsqlDbType.Json, after);
        audit.Parameters.AddWithValue("reason", NpgsqlDbType.Text, reason);
        audit.Parameters.AddWithValue("request", NpgsqlDbType.Text, request.ToString());
        audit.Parameters.AddWithValue("digest", NpgsqlDbType.Text, digest);
        if (await audit.ExecuteNonQueryAsync() != 1)
            throw new InvalidOperationException("The edited order and its audit could not both be saved.");
        transaction.Commit();
    }

    private static async Task<SalesLineAmounts> EditStoredLinesAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int orderId, IReadOnlyList<SalesOrderEditLine> before, IReadOnlyList<SalesOrderEditLine> requested)
    {
        if (requested.Count is 0 or > 200)
            throw new ArgumentException("An edited document requires 1 to 200 saved items.");
        if (!before.Select(line => line.Id).OrderBy(id => id).SequenceEqual(requested.Select(line => line.Id).OrderBy(id => id)))
            throw new InvalidOperationException("The saved order items changed. Refresh before editing.");

        decimal subtotal = 0, discount = 0, tax = 0, total = 0;
        var changes = requested.Select(line =>
        {
            if (string.IsNullOrWhiteSpace(line.Description) || line.Description.Length > 2000)
                throw new ArgumentException("Enter a description of up to 2,000 characters for each item.");
            if (line.Quantity <= 0 || line.Quantity > 1_000_000m || decimal.Round(line.Quantity, 3) != line.Quantity)
                throw new ArgumentException("Item quantity must be positive, at most one million and fit three decimal places.");
            if (!IsEditMoney(line.UnitPrice) || !IsEditMoney(line.Discount) || !IsEditMoney(line.Tax))
                throw new ArgumentException("Item price, discount and tax must be nonnegative amounts with at most two decimal places.");
            decimal gross = line.Quantity * line.UnitPrice;
            if (line.Discount > gross)
                throw new ArgumentException("The discount exceeds the item value.");
            decimal lineTotal = decimal.Round(gross - line.Discount + line.Tax, 2, MidpointRounding.ToEven);
            subtotal += gross;
            discount += line.Discount;
            tax += lineTotal - gross + line.Discount;
            total += lineTotal;
            return new { id = line.Id, description = line.Description, quantity = line.Quantity, unit_price = line.UnitPrice,
                discount_amount = line.Discount, tax_amount = line.Tax, line_total = lineTotal };
        }).ToArray();
        if (new[] { subtotal, discount, tax, total }.Any(amount => amount < 0 || amount > MaximumLineMoney))
            throw new ArgumentException("Edited order totals are outside the supported range.");
        using var write = new NpgsqlCommand(@"
            UPDATE public.srm_sales_order_lines l SET description=change.description, quantity=change.quantity,
                unit_price=change.unit_price,discount_amount=change.discount_amount,tax_amount=change.tax_amount,
                line_total=change.line_total
            FROM jsonb_to_recordset(@changes) AS change(id integer, description text, quantity numeric, unit_price numeric,
                discount_amount numeric,tax_amount numeric,line_total numeric)
            WHERE l.sales_order_id=@order AND l.id=change.id", db, tx);
        write.Parameters.AddWithValue("changes", NpgsqlDbType.Jsonb, JsonSerializer.Serialize(changes));
        write.Parameters.AddWithValue("order", NpgsqlDbType.Integer, orderId);
        if (await write.ExecuteNonQueryAsync() != changes.Length)
            throw new InvalidOperationException("The saved order items changed. Refresh before editing.");
        return new SalesLineAmounts(subtotal, discount, tax, total);
    }

    private static bool IsEditMoney(decimal value) =>
        value >= 0 && value <= MaximumLineMoney && decimal.Round(value, 2) == value;

    private static IReadOnlyList<SalesOrderEditLine> SnapshotLines(string snapshot)
    {
        using var document = JsonDocument.Parse(snapshot);
        return document.RootElement.GetProperty("lines").EnumerateArray()
            .Select(line => new SalesOrderEditLine(line.GetProperty("id").GetInt32(),
                line.GetProperty("item_code").GetString() ?? "", line.GetProperty("description").GetString() ?? "",
                Number(line, "quantity"), Number(line, "unit_price"), Number(line, "discount_amount"), Number(line, "tax_amount"))).ToArray();

        static decimal Number(JsonElement line, string property) =>
            line.GetProperty(property).ValueKind == JsonValueKind.Number ? line.GetProperty(property).GetDecimal() : 0;
    }

    private async Task LockCompanyWriterAsync(NpgsqlConnection connection, NpgsqlTransaction transaction)
    {
        // Use the same PostgreSQL lock namespace and lock order as the web commercial writer.
        using var advisory = new NpgsqlCommand("SELECT pg_advisory_xact_lock(@key)", connection, transaction);
        advisory.Parameters.AddWithValue("key", NpgsqlDbType.Bigint, 720000000L + settings.OrganizationId);
        await advisory.ExecuteNonQueryAsync();
        using var company = new NpgsqlCommand("SELECT id FROM public.companies WHERE id = @id AND is_active FOR UPDATE",
            connection, transaction);
        company.Parameters.AddWithValue("id", NpgsqlDbType.Integer, settings.OrganizationId);
        if (await company.ExecuteScalarAsync() is null)
            throw new UnauthorizedAccessException("The selected company is unavailable for updates.");
    }

    private static InvalidOperationException EditUnavailable() =>
        new InvalidOperationException("This sales order is unavailable for draft editing.");
}
