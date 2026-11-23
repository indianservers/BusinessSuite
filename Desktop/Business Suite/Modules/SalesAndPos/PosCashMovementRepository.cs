using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PosCashMovementIntent(string Number, Guid Request, string Type, decimal Amount, string Reason);
internal sealed record PosCashMovementResult(int? Id, bool RegisterClosed);
internal sealed record PosCashMovementRow(string Direction, decimal Amount, string Reason, DateTime? Recorded);

internal sealed partial class SalesOrderRepository
{
    internal async Task<List<PosCashMovementRow>> CashMovementsAsync(string number)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to view drawer history.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(System.Data.IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor);
        await RequireNativeRegisterBranchAsync(db, tx, branch);
        using var query = RegisterQuery(@"
            SELECT m.movement_type,m.amount,coalesce(m.reason,''),m.created_at
            FROM public.srm_pos_sessions p
            JOIN public.srm_pos_cash_movements m ON m.session_id=p.id AND m.organization_id=p.organization_id" +
            OwnSession + @"
            AND EXISTS (SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company AND b.branch_id=@branch
                AND b.resource_table='srm_pos_cash_movements' AND b.resource_key=m.id::text)
            AND NOT EXISTS (SELECT 1 FROM public.business_pack_record_ownership b WHERE b.company_id=@company
                AND b.resource_table='srm_pos_cash_movements' AND b.resource_key=m.id::text)
            ORDER BY m.id DESC LIMIT 200", db, tx, branch, actor.Id, number);
        var rows = new List<PosCashMovementRow>();
        using (var reader = await query.ExecuteReaderAsync())
            while (await reader.ReadAsync())
                rows.Add(new PosCashMovementRow(reader.IsDBNull(0) ? "" : reader.GetString(0) switch
                {
                    "cash_in" => "Cash in",
                    "cash_out" => "Cash out",
                    string kind => kind
                }, reader.IsDBNull(1) ? 0 : reader.GetDecimal(1), reader.GetString(2),
                    reader.IsDBNull(3) ? null : reader.GetDateTime(3).ToLocalTime()));
        tx.Commit();
        return rows;
    }

    internal async Task<PosCashMovementResult> PostCashMovementAsync(PosCashMovementIntent intent)
    {
        ValidateCashIntent(intent);
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Select a branch to record a drawer movement.");
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

        using var session = RegisterQuery(@"
            SELECT p.id, p.status,coalesce(p.metadata_json->>'cash_currency','')
            FROM public.srm_pos_sessions p" + OwnSession + " FOR UPDATE OF p",
            db, tx, branch, actor.Id, intent.Number);
        int sessionId;
        string status;
        string currency;
        using (var reader = await session.ExecuteReaderAsync())
        {
            if (!await reader.ReadAsync())
                throw new InvalidOperationException("The cash request's register is unavailable in this branch.");
            sessionId = reader.GetInt32(0);
            status = reader.IsDBNull(1) ? "" : reader.GetString(1);
            currency = reader.GetString(2);
        }
        string key = intent.Request.ToString();
        string digest = CashIntentDigest(intent, settings.OrganizationId, sessionId, actor.Id, branch, currency);
        using var previous = RegisterCommand(@"
            SELECT m.id,m.session_id,m.created_by,m.request_branch_id,m.request_context_id,
                   m.request_currency,m.movement_type,m.amount,m.reason,m.request_sha256,
                   EXISTS (SELECT 1 FROM public.suite_branch_ownership b WHERE b.company_id=@company AND b.branch_id=@branch
                        AND b.resource_table='srm_pos_cash_movements' AND b.resource_key=m.id::text),
                   EXISTS (SELECT 1 FROM public.business_pack_record_ownership b WHERE b.company_id=@company
                        AND b.resource_table='srm_pos_cash_movements' AND b.resource_key=m.id::text)
            FROM public.srm_pos_cash_movements m WHERE m.organization_id=@company AND m.request_key=@key",
            db, tx, branch, actor.Id);
        previous.Parameters.AddWithValue("key", NpgsqlDbType.Text, key);
        int? existing = null;
        using (var reader = await previous.ExecuteReaderAsync())
        {
            if (await reader.ReadAsync())
            {
                if (!reader.GetBoolean(10) || reader.GetBoolean(11) || reader.GetInt32(1) != sessionId ||
                    reader.IsDBNull(2) || reader.GetInt32(2) != actor.Id || reader.IsDBNull(3) ||
                    reader.GetInt32(3) != branch || !reader.IsDBNull(4) || reader.GetString(5) != currency ||
                    reader.GetString(6) != intent.Type || reader.GetDecimal(7) != intent.Amount ||
                    reader.IsDBNull(8) || reader.GetString(8) != intent.Reason || reader.GetString(9) != digest)
                    throw new InvalidOperationException("This cash request is unavailable or already identifies a different movement.");
                existing = reader.GetInt32(0);
            }
        }
        if (existing.HasValue || status == "closed")
        {
            tx.Commit();
            return new PosCashMovementResult(existing, status == "closed");
        }
        if (status != "open")
            throw new InvalidOperationException("The cash request's register is unavailable for posting.");

        var snapshot = await ReadCashSnapshotAsync(db, tx, branch, actor.Id, intent.Number);
        if (snapshot.Currency != currency || currency.Length != 3 || !currency.All(ch => ch is >= 'A' and <= 'Z'))
            throw new InvalidOperationException("This register requires a verified cash currency before recording a movement.");
        decimal expected = snapshot.Expected + (intent.Type == "cash_in" ? intent.Amount : -intent.Amount);
        decimal movementTotal = (intent.Type == "cash_in" ? snapshot.CashIn : snapshot.CashOut) + intent.Amount;
        if (Math.Abs(expected) > MaximumOpeningCash || movementTotal > MaximumOpeningCash)
            throw new InvalidOperationException("This movement exceeds the register's supported cash range.");

        using var write = RegisterQuery(@"
            WITH drawer AS (
                UPDATE public.srm_pos_sessions p SET expected_cash=@expected,updated_at=now()" + OwnSession + @"
                AND p.id=@session AND p.status='open' RETURNING id
            ), movement AS (
                INSERT INTO public.srm_pos_cash_movements
                    (organization_id,session_id,movement_type,amount,reason,created_by,request_key,
                     request_sha256,request_currency,request_branch_id,request_context_id)
                SELECT @company,id,@type,@amount,@reason,@actor,@key,@digest,@currency,@branch,NULL
                FROM drawer RETURNING *
            ), audit AS (
                INSERT INTO public.srm_audit_logs
                    (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'pos_cash_movement',id,'created',@actor,row_to_json(movement) FROM movement RETURNING id
            ), stamp AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'srm_pos_cash_movements',id::text,@company,@branch,'validated-write' FROM movement
                UNION ALL
                SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit RETURNING resource_key
            )
            SELECT id FROM movement WHERE (SELECT count(*) FROM stamp)=2",
            db, tx, branch, actor.Id, intent.Number);
        write.Parameters.AddWithValue("session", NpgsqlDbType.Integer, sessionId);
        write.Parameters.AddWithValue("expected", NpgsqlDbType.Numeric, expected);
        write.Parameters.AddWithValue("type", NpgsqlDbType.Text, intent.Type);
        write.Parameters.AddWithValue("amount", NpgsqlDbType.Numeric, intent.Amount);
        write.Parameters.AddWithValue("reason", NpgsqlDbType.Text, intent.Reason);
        write.Parameters.AddWithValue("key", NpgsqlDbType.Text, key);
        write.Parameters.AddWithValue("digest", NpgsqlDbType.Text, digest);
        write.Parameters.AddWithValue("currency", NpgsqlDbType.Text, currency);
        if (await write.ExecuteScalarAsync() is not int id)
            throw new InvalidOperationException("The cash drawer movement and its audit could not both be saved.");
        tx.Commit();
        return new PosCashMovementResult(id, false);
    }

    internal static void ValidateCashIntent(PosCashMovementIntent intent)
    {
        if (string.IsNullOrWhiteSpace(intent.Number) || intent.Number.Length > 80 || intent.Number.IndexOf('\0') >= 0 ||
            intent.Request == Guid.Empty || intent.Type is not ("cash_in" or "cash_out"))
            throw new ArgumentException("A valid register and movement type are required.");
        if (intent.Amount <= 0 || intent.Amount > MaximumOpeningCash || decimal.Round(intent.Amount, 2) != intent.Amount)
            throw new ArgumentException("Enter a positive cash amount with at most two decimal places.");
        if (string.IsNullOrWhiteSpace(intent.Reason) || intent.Reason.Length > 500 || intent.Reason.IndexOf('\0') >= 0)
            throw new ArgumentException("Enter a reason of up to 500 characters.");
    }

    internal static string CashIntentDigest(PosCashMovementIntent intent, int company, int session, int actor, int branch, string currency)
    {
        // Match Python json.dumps(sort_keys=True, separators=(',', ':'), ensure_ascii=True).
        var format = CultureInfo.InvariantCulture;
        string canonical = "{\"actor_id\":" + actor.ToString(format)
            + ",\"amount\":" + Quote(intent.Amount.ToString("F2", format))
            + ",\"branch_id\":" + branch.ToString(format)
            + ",\"company_id\":" + company.ToString(format)
            + ",\"context_id\":null,\"currency\":" + Quote(currency)
            + ",\"movement_type\":" + Quote(intent.Type)
            + ",\"reason\":" + Quote(intent.Reason)
            + ",\"request_key\":" + Quote(intent.Request.ToString())
            + ",\"session_id\":" + session.ToString(format) + "}";
        using var sha = SHA256.Create();
        return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(canonical))).Replace("-", "").ToLowerInvariant();
    }

    private static string Quote(string value)
    {
        var output = new StringBuilder("\"");
        foreach (char character in value)
            output.Append(character switch
            {
                '"' => "\\\"",
                '\\' => "\\\\",
                '\b' => "\\b",
                '\f' => "\\f",
                '\n' => "\\n",
                '\r' => "\\r",
                '\t' => "\\t",
                < ' ' or > '~' => "\\u" + ((int)character).ToString("x4", CultureInfo.InvariantCulture),
                _ => character.ToString()
            });
        return output.Append('"').ToString();
    }
}
