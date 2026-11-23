using System.Globalization;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record ActivePosRegister(string Number, string Currency, decimal OpeningCash);
internal sealed record PosRegisterState(ActivePosRegister? Active, bool CanOpen, bool CanClose);

internal sealed partial class SalesOrderRepository
{
    private enum CommercialNumberSeries { SalesOrder, PosSession, Engagement, InventoryMovement, Invoice, Receipt, HeldBill, PosReturn, Contract }
    private const decimal MaximumOpeningCash = 999999999999.99m;
    private const string RegisterName = "Main POS Register";

    internal async Task<PosRegisterState> ActiveRegisterAsync()
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to view the active register.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(System.Data.IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor);
        await RequireNativeRegisterBranchAsync(db, tx, branch);
        var active = await FindActiveRegisterAsync(db, tx, branch, actor.Id);
        bool canManage = false;
        if (actor.CanWriteBranch)
        {
            try
            {
                await RequireRegisterWriterAsync(db, tx, branch, actor);
                canManage = true;
            }
            catch (UnauthorizedAccessException) { }
        }
        tx.Commit();
        return new PosRegisterState(active, active is null && canManage, active is not null && canManage);
    }

    internal async Task<ActivePosRegister> OpenRegisterAsync(decimal openingCash)
    {
        if (openingCash < 0 || openingCash > MaximumOpeningCash || decimal.Round(openingCash, 2) != openingCash)
            throw new ArgumentException("Enter a nonnegative opening cash amount with at most two decimal places.");

        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to open the register.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireRegisterWriterAsync(db, tx, branch, actor);
        await RequireNativeRegisterBranchAsync(db, tx, branch);
        await RequireCashIntentSchemaAsync(db, tx);
        if (await FindActiveRegisterAsync(db, tx, branch, actor.Id) is { } active)
        {
            tx.Commit();
            return active;
        }

        using var location = RegisterCommand(@"
            SELECT c.default_currency, b.name FROM public.companies c
            JOIN public.branches b ON b.company_id=c.id
            WHERE c.id=@company AND b.id=@branch", db, tx, branch, actor.Id);
        string currency;
        string branchName;
        using (var row = await location.ExecuteReaderAsync())
        {
            if (!await row.ReadAsync())
                throw new InvalidOperationException("The selected register branch is unavailable.");
            currency = row.IsDBNull(0) ? "" : row.GetString(0);
            branchName = row.GetString(1);
        }
        if (currency.Length != 3 || !currency.All(ch => ch is >= 'A' and <= 'Z'))
            throw new InvalidOperationException("Configure a valid company currency before opening a register.");

        string number = await ReserveCommercialNumberAsync(db, tx, CommercialNumberSeries.PosSession);
        using var create = RegisterCommand(@"
            WITH session AS (
                INSERT INTO public.srm_pos_sessions
                    (organization_id,session_number,status,branch,register_name,cashier_user_id,created_by,
                     opening_cash,expected_cash,counted_cash,cash_variance,metadata_json)
                VALUES (@company,@number,'open',@branch_name,@register,@actor,@actor,
                        @cash,@cash,0,0,json_build_object('cash_currency',@currency))
                RETURNING *
            ), audit AS (
                INSERT INTO public.srm_audit_logs
                    (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'pos_session',id,'opened',@actor,row_to_json(session) FROM session
                RETURNING id
            )
            INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
            SELECT 'srm_pos_sessions',id::text,@company,@branch,'validated-write' FROM session
            UNION ALL
            SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit", db, tx, branch, actor.Id);
        create.Parameters.AddWithValue("number", NpgsqlDbType.Text, number);
        create.Parameters.AddWithValue("branch_name", NpgsqlDbType.Text, branchName);
        create.Parameters.AddWithValue("register", NpgsqlDbType.Text, RegisterName);
        create.Parameters.AddWithValue("cash", NpgsqlDbType.Numeric, openingCash);
        create.Parameters.AddWithValue("currency", NpgsqlDbType.Text, currency);
        if (await create.ExecuteNonQueryAsync() != 2)
            throw new InvalidOperationException("The register and its audit entry could not both be saved.");
        tx.Commit();
        return new ActivePosRegister(number, currency, openingCash);
    }

    private async Task RequireRegisterWriterAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor)
    {
        var grant = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor,
            "srm", "create", "srm_manage", "srm_admin");
        if (grant.Scope is not ("organization" or "own" or "team"))
            throw new UnauthorizedAccessException("Your Sales record scope does not allow opening a desktop register.");
    }

    private async Task<ActivePosRegister?> FindActiveRegisterAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor)
    {
        using var find = RegisterCommand(@"
            SELECT p.session_number, coalesce(p.metadata_json->>'cash_currency',''), coalesce(p.opening_cash,0)
            FROM public.srm_pos_sessions p
            JOIN public.suite_branch_ownership b ON b.company_id=p.organization_id AND b.branch_id=@branch
                AND b.resource_table='srm_pos_sessions' AND b.resource_key=p.id::text
            WHERE p.organization_id=@company AND p.cashier_user_id=@actor AND p.deleted_at IS NULL AND p.status='open'
              AND NOT EXISTS (
                  SELECT 1 FROM public.business_pack_record_ownership o
                  WHERE o.company_id=@company AND o.resource_table='srm_pos_sessions' AND o.resource_key=p.id::text
              )
            ORDER BY p.id DESC LIMIT 2", db, tx, branch, actor);
        using var row = await find.ExecuteReaderAsync();
        if (!await row.ReadAsync())
            return null;
        var result = new ActivePosRegister(row.GetString(0), row.GetString(1), row.GetDecimal(2));
        if (await row.ReadAsync())
            throw new InvalidOperationException("More than one register is open for this cashier in the selected branch. Reconcile the sessions before continuing.");
        return result;
    }

    private async Task RequireNativeRegisterBranchAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        string operation = "desktop register operations")
    {
        using var check = RegisterCommand(@"
            SELECT EXISTS (
                SELECT 1 FROM public.business_pack_contexts c
                LEFT JOIN public.business_pack_activations a ON a.id=c.activation_id
                    AND a.company_id=c.company_id AND a.pack_key=c.pack_key AND a.pack_version=c.pack_version
                WHERE c.company_id=@company AND c.branch_id=@branch
                  AND (c.state <> 'draft' OR c.ever_activated OR a.id IS NULL OR a.state NOT IN ('draft','active'))
            )", db, tx, branch);
        if ((bool)(await check.ExecuteScalarAsync())!)
            throw new UnauthorizedAccessException($"This branch requires Business Pack authorization for {operation}.");
    }

    private static async Task RequireCashIntentSchemaAsync(NpgsqlConnection db, NpgsqlTransaction tx)
    {
        using var check = new NpgsqlCommand(@"
            SELECT (SELECT count(*)=5 FROM information_schema.columns
                     WHERE table_schema='public' AND table_name='srm_pos_cash_movements'
                       AND column_name IN ('request_key','request_sha256','request_currency','request_branch_id','request_context_id'))
               AND EXISTS (SELECT 1 FROM pg_catalog.pg_constraint c
                           WHERE c.conrelid=to_regclass('public.srm_pos_cash_movements')
                             AND c.conname='ck_srm_cash_request_source' AND c.contype='c' AND c.convalidated)
               AND EXISTS (SELECT 1 FROM pg_catalog.pg_index i JOIN pg_catalog.pg_class n ON n.oid=i.indexrelid
                           JOIN pg_catalog.pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=i.indkey[0]
                           JOIN pg_catalog.pg_attribute b ON b.attrelid=i.indrelid AND b.attnum=i.indkey[1]
                           WHERE i.indrelid=to_regclass('public.srm_pos_cash_movements')
                             AND n.relname='uq_srm_cash_company_request' AND i.indisunique AND i.indisvalid
                             AND i.indpred IS NULL AND i.indnkeyatts=2
                             AND a.attname='organization_id' AND b.attname='request_key')", db, tx);
        if (!(bool)(await check.ExecuteScalarAsync())!)
            throw new InvalidOperationException("Apply or reconcile native cash intent migration 119 before opening a register.");
    }

    private async Task<string> ReserveCommercialNumberAsync(NpgsqlConnection db, NpgsqlTransaction tx, CommercialNumberSeries series)
    {
        var (source, numberColumn, prefix) = series switch
        {
            CommercialNumberSeries.SalesOrder => ("srm_sales_orders", "order_number", "SO"),
            CommercialNumberSeries.PosSession => ("srm_pos_sessions", "session_number", "POS"),
            CommercialNumberSeries.Engagement => ("srm_engagements", "engagement_number", "ENG"),
            CommercialNumberSeries.Contract => ("srm_contracts", "contract_number", "CTR"),
            CommercialNumberSeries.PosReturn => ("srm_pos_returns", "return_number", "RET"),
            CommercialNumberSeries.HeldBill => ("srm_pos_held_bills", "hold_number", "HOLD"),
            CommercialNumberSeries.Receipt => ("srm_receipts", "receipt_number", "RCT"),
            CommercialNumberSeries.Invoice => ("srm_invoices", "invoice_number", "INV"),
            CommercialNumberSeries.InventoryMovement => ("srm_inventory_movements", "movement_number", "INV"),
            _ => throw new ArgumentOutOfRangeException(nameof(series))
        };
        // The table and column come from the fixed native numbering series above.
        using var reserve = new NpgsqlCommand($@"
            WITH used AS (
                SELECT greatest(
                    coalesce((SELECT last_number::numeric FROM public.business_number_sequences WHERE series=@series),0),
                    coalesce((SELECT max(substring({numberColumn} FROM '([0-9]+)$')::numeric)
                        FROM public.{source} WHERE coalesce(organization_id,1)=@company
                          AND {numberColumn} ~ @pattern),0)
                ) AS last
            )
            INSERT INTO public.business_number_sequences (series,last_number)
            SELECT @series,(last+1)::bigint FROM used WHERE last < 9223372036854775807
            ON CONFLICT(series) DO UPDATE SET last_number=excluded.last_number
            RETURNING last_number", db, tx);
        reserve.Parameters.AddWithValue("company", NpgsqlDbType.Integer, settings.OrganizationId);
        reserve.Parameters.AddWithValue("pattern", NpgsqlDbType.Text, $"^{prefix}-.*-[0-9]+$|^{prefix}-[0-9]+$");
        reserve.Parameters.AddWithValue("series", NpgsqlDbType.Text,
            $"srm_company:{settings.OrganizationId.ToString(CultureInfo.InvariantCulture)}:{source}:{prefix}");
        if (await reserve.ExecuteScalarAsync() is not long number)
            throw new InvalidOperationException($"The {prefix} number series is exhausted.");
        return prefix + "-" + number.ToString("D6", CultureInfo.InvariantCulture);
    }

    private NpgsqlCommand RegisterCommand(string sql, NpgsqlConnection db, NpgsqlTransaction tx, int branch, int? actor = null)
    {
        var command = new NpgsqlCommand(sql, db, tx);
        command.Parameters.AddWithValue("company", NpgsqlDbType.Integer, settings.OrganizationId);
        command.Parameters.AddWithValue("branch", NpgsqlDbType.Integer, branch);
        if (actor.HasValue)
            command.Parameters.AddWithValue("actor", NpgsqlDbType.Integer, actor.Value);
        return command;
    }
}
