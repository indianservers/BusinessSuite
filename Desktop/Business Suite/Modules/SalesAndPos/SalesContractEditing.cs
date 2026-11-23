using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record SalesContractChanges(string Title, string Kind, string Currency, decimal Value,
    DateTime? Effective, DateTime? Expiry, string Terms);

internal sealed partial class SalesOrderRepository
{
    internal async Task EditSalesContractAsync(int order, SalesContractRow original, SalesContractChanges input, Guid request)
    {
        if (order <= 0 || original.Id <= 0 || request == Guid.Empty)
            throw new ArgumentException("Select a saved contract before editing.");
        var change = NormalizeContractChanges(input);

        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose the contract branch.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "Sales contract editing");
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "edit");
        using var read = ScopedCommand("SELECT c.xmin::text,to_jsonb(c)::text" + ContractOrderChain + LinkedContractScope +
            " AND c.id=@id FOR UPDATE OF o,c", db, tx, branch, actor, scope);
        read.Parameters.AddWithValue("order", order);
        read.Parameters.AddWithValue("id", original.Id);
        string revision;
        string before;
        using (var rows = await read.ExecuteReaderAsync())
        {
            if (!await rows.ReadAsync())
                throw new InvalidOperationException("The linked contract is unavailable in this branch.");
            revision = rows.GetString(0);
            before = rows.GetString(1);
        }
        string digest = HashSalesPayload(change);
        using (var retry = RegisterCommand(@"SELECT coalesce(a.after_json->>'desktop_sha256'=@hash,false)
            FROM public.srm_audit_logs a WHERE a.organization_id=@company AND a.actor_user_id=@actor
                AND a.entity_type='contract' AND a.entity_id=@id AND a.action='updated'
                AND a.after_json->>'desktop_request'=@request AND " + ConfirmationOwnership("a", "srm_audit_logs"),
            db, tx, branch, actor.Id))
        {
            retry.Parameters.AddWithValue("id", original.Id);
            retry.Parameters.AddWithValue("hash", digest);
            retry.Parameters.AddWithValue("request", request.ToString());
            object? previous = await retry.ExecuteScalarAsync();
            if (previous is bool identical)
            {
                if (!identical)
                    throw new InvalidOperationException("This request already used different contract details.");
                tx.Commit();
                return;
            }
        }
        if (!StringComparer.Ordinal.Equals(revision, original.Revision))
            throw new InvalidOperationException("The contract changed. Reload before saving.");
        using var write = RegisterCommand(@"
            WITH changed AS (
                UPDATE public.srm_contracts SET title=@title,contract_type=@type,currency=@currency,
                    contract_value=@value,effective_date=@effective,expiry_date=@expiry,terms=@terms,updated_at=now()
                WHERE organization_id=@company AND id=@id AND sales_order_id=@order AND deleted_at IS NULL RETURNING id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,before_json,after_json)
                SELECT @company,'contract',id,'updated',@actor,@before,json_build_object(
                    'title',@title,'contract_type',@type,'currency',@currency,'contract_value',@value,
                    'effective_date',@effective,'expiry_date',@expiry,'terms',@terms,'desktop_request',@request,'desktop_sha256',@hash)
                FROM changed RETURNING id
            )
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit", db, tx, branch, actor.Id);
        write.Parameters.AddWithValue("id", original.Id);
        write.Parameters.AddWithValue("order", order);
        BindContractChanges(write, change);
        write.Parameters.AddWithValue("before", NpgsqlDbType.Json, before);
        write.Parameters.AddWithValue("request", request.ToString());
        write.Parameters.AddWithValue("hash", digest);
        if (await write.ExecuteNonQueryAsync() != 1)
            throw new InvalidOperationException("The contract and its audit could not both be saved.");
        tx.Commit();
    }

    private static SalesContractChanges NormalizeContractChanges(SalesContractChanges input)
    {
        var change = input with
        {
            Title = input.Title.Trim(), Kind = input.Kind.Trim(), Currency = input.Currency.Trim().ToUpperInvariant(),
            Effective = input.Effective?.Date, Expiry = input.Expiry?.Date
        };
        if (change.Title.Length is < 1 or > 220 || change.Kind.Length is < 1 or > 80 ||
            !ValidInvoiceCurrency(change.Currency) || change.Terms.Length > 10000)
            throw new ArgumentException("Enter a contract title, type, supported currency and up to 10,000 characters of terms.");
        if (change.Effective is DateTime effective && change.Expiry is DateTime expiry && expiry < effective)
            throw new ArgumentException("The expiry date must be on or after the effective date.");
        if (change.Value < 0 || change.Value > MaximumOrderMoney || decimal.Round(change.Value, 2) != change.Value)
            throw new ArgumentException("Enter a nonnegative contract value with up to two decimals.");
        return change;
    }

    private static void BindContractChanges(NpgsqlCommand command, SalesContractChanges change)
    {
        command.Parameters.AddWithValue("title", change.Title);
        command.Parameters.AddWithValue("type", change.Kind);
        command.Parameters.AddWithValue("currency", change.Currency);
        command.Parameters.AddWithValue("value", change.Value);
        command.Parameters.AddWithValue("effective", NpgsqlDbType.Date, (object?)change.Effective ?? DBNull.Value);
        command.Parameters.AddWithValue("expiry", NpgsqlDbType.Date, (object?)change.Expiry ?? DBNull.Value);
        command.Parameters.AddWithValue("terms", change.Terms);
    }
}
