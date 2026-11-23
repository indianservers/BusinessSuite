using System.Globalization;
using System.Text.Json;
using System.Text.Json.Serialization;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record SalesRecurringScheduleInput(Guid Request, DateTime Start, DateTime? End, decimal Amount,
    int Occurrences, int Interval, string Rule, int PaymentTerms, string Template, string Subject,
    string CustomerNotes, string Terms, string OrderNumber)
{
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)]
    public bool Ongoing { get; init; }

    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public int? PaymentMode { get; init; }

    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public int? Salesperson { get; init; }

    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)]
    public bool AutomaticDrafts { get; init; }

    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)]
    public bool SuppressRecurringNotice { get; init; }
}
internal sealed record SalesRecurringScheduleResult(int Created, int Skipped);

internal sealed partial class SalesOrderRepository
{
    internal async Task<SalesRecurringScheduleResult> CreateSalesRecurringScheduleAsync(int order, int engagement, int plan,
        SalesRecurringScheduleInput input)
    {
        string chosenRule = input.Rule.Trim().ToLowerInvariant();
        if (input.Request == Guid.Empty || input.Amount <= 0 || input.Amount > MaximumOrderMoney ||
            decimal.Round(input.Amount, 2) != input.Amount || input.Occurrences is < 1 or > 120 ||
            input.Interval is < 1 or > 120 || input.PaymentTerms is < 0 or > 365 ||
            input.Template is not ("standard" or "compact" or "detailed") || input.End?.Date < input.Start.Date ||
            (input.Ongoing && input.End.HasValue) ||
            input.Subject.Length > 180 || input.CustomerNotes.Length > 4000 || input.Terms.Length > 4000 || input.OrderNumber.Length > 80)
            throw new ArgumentException("Review the recurring amount, date range, interval, occurrence count and invoice settings.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose the recurring billing branch.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "recurring billing setup");
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "create");
        if (input.AutomaticDrafts)
            await SalesInvoiceScopeAsync(db, tx, branch, actor);
        using var read = ScopedCommand("SELECT coalesce(b.recurrence_rule,''),coalesce(b.status,''),e.customer_id" +
            SalesBillingPlanChain + SalesBillingPlanScope + " AND b.id=@plan FOR UPDATE OF o,e,b", db, tx, branch, actor, scope);
        BindBillingMilestoneChain(read, order, engagement, plan);
        string rule;
        int? customer;
        using (var rows = await read.ExecuteReaderAsync())
        {
            if (!await rows.ReadAsync())
                throw new InvalidOperationException("The billing plan is unavailable for this engagement and branch.");
            if (rows.GetString(1) is "completed" or "cancelled")
                throw new InvalidOperationException("This billing plan is closed.");
            rule = rows.GetString(0).Trim().ToLowerInvariant();
            customer = rows.IsDBNull(2) ? null : rows.GetInt32(2);
        }
        if (input.AutomaticDrafts)
            await VerifyRecurringDraftCustomerAsync(db, tx, branch, actor.Id, customer);
        if (rule.Length == 0)
            rule = chosenRule;
        if (rule == "annually")
            rule = "yearly";
        if (chosenRule.Length > 0 && rule != chosenRule)
            throw new InvalidOperationException($"This plan already uses {rule} recurrence.");
        var dates = SalesOccurrenceDates(input, rule);
        string digest = HashSalesPayload(new { input, rule });
        var result = await SaveSalesRecurringScheduleAsync(db, tx, branch, actor.Id, plan, input, rule, dates, digest);
        tx.Commit();
        return result;
    }

    private async Task VerifyRecurringDraftCustomerAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor,
        int? customer)
    {
        if (!customer.HasValue)
            throw new InvalidOperationException("Link a customer to the engagement before enabling ready recurring drafts.");
        using var buyer = RegisterCommand("SELECT c.id FROM public.crm_companies c" + OrderCustomerScope +
            " AND c.id=@buyer FOR SHARE OF c", db, tx, branch, actor);
        buyer.Parameters.AddWithValue("buyer", customer.Value);
        if (await buyer.ExecuteScalarAsync() is not int)
            throw new InvalidOperationException("The engagement customer is unavailable in this branch.");
    }

    private static DateTime[] SalesOccurrenceDates(SalesRecurringScheduleInput input, string rule)
    {
        var dates = new List<DateTime>();
        try
        {
            for (int index = 0; index < input.Occurrences; index++)
            {
                var due = SalesOccurrenceDate(input.Start, rule, index, input.Interval);
                if (input.End.HasValue && due > input.End.Value.Date)
                    break;
                dates.Add(due);
            }
        }
        catch (ArgumentOutOfRangeException)
        {
            throw new ArgumentException("The recurrence extends beyond the supported calendar.");
        }
        return dates.ToArray();
    }

    private static DateTime SalesOccurrenceDate(DateTime start, string rule, int index, int interval)
    {
        int offset = index * interval;
        return rule switch
        {
            "daily" => start.Date.AddDays(offset),
            "weekly" => start.Date.AddDays(7 * offset),
            "monthly" => start.Date.AddMonths(offset),
            "quarterly" => start.Date.AddMonths(3 * offset),
            "yearly" or "annually" => start.Date.AddMonths(12 * offset),
            _ => throw new ArgumentException("Choose daily, weekly, monthly, quarterly or yearly recurrence.")
        };
    }

    private async Task<SalesRecurringScheduleResult> SaveSalesRecurringScheduleAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, int actor, int plan, SalesRecurringScheduleInput input, string rule, DateTime[] dates, string digest)
    {
        using (var previous = RegisterCommand(@"
            SELECT (after_json->>'created')::int,(after_json->>'skipped')::int,after_json->>'request_sha256'=@hash
            FROM public.srm_audit_logs a WHERE a.organization_id=@company AND a.actor_user_id=@actor
                AND a.entity_type='billing_plan' AND a.entity_id=@plan AND a.action='recurring_schedule_created'
                AND a.after_json->>'request_id'=@request AND " + ConfirmationOwnership("a", "srm_audit_logs"), db, tx, branch, actor))
        {
            previous.Parameters.AddWithValue("plan", plan);
            previous.Parameters.AddWithValue("request", input.Request.ToString());
            previous.Parameters.AddWithValue("hash", digest);
            using var rows = await previous.ExecuteReaderAsync();
            if (await rows.ReadAsync())
            {
                if (rows.IsDBNull(2) || !rows.GetBoolean(2))
                    throw new InvalidOperationException("The schedule request has already been used with different settings.");
                return new SalesRecurringScheduleResult(rows.GetInt32(0), rows.GetInt32(1));
            }
        }
        string presentation = JsonSerializer.Serialize(await BuildRecurringPresentationAsync(db, tx, branch, actor, input));
        string key = string.Format(CultureInfo.InvariantCulture, "recurring-profile:{0}:{1}", settings.OrganizationId, plan);
        if (input.Ongoing)
        {
            using var existing = RegisterCommand(@"
                SELECT CASE
                    WHEN values_json->>'ongoing' IS DISTINCT FROM 'false' THEN 'This plan already has an ongoing profile. Use its extension action.'
                    WHEN values_json->>'start_date' IS DISTINCT FROM @start
                        OR lower(trim(values_json->>'rule')) IS DISTINCT FROM @rule
                        OR coalesce(values_json->>'interval','1')<>@interval
                        THEN 'Keep the existing schedule start, rule and interval when enabling ongoing billing.'
                    ELSE '' END
                FROM public.suite_service_policies WHERE scope_key=@key AND organization_id=@company
                    AND kind='recurring_profile' AND module_key='srm' FOR UPDATE", db, tx, branch, actor);
            existing.Parameters.AddWithValue("key", key);
            existing.Parameters.AddWithValue("start", input.Start.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture));
            existing.Parameters.AddWithValue("rule", rule);
            existing.Parameters.AddWithValue("interval", input.Interval.ToString(CultureInfo.InvariantCulture));
            if (await existing.ExecuteScalarAsync() is string error && error.Length > 0)
                throw new InvalidOperationException(error);
        }
        using var write = RegisterCommand(@"
            WITH profile_before AS (
                SELECT values_json,version FROM public.suite_service_policies WHERE scope_key=@key AND organization_id=@company
                    AND module_key='srm' AND kind='recurring_profile'
            ), intended AS (
                SELECT occurrence.due FROM unnest(@dates::date[]) AS occurrence(due)
                WHERE NOT EXISTS (SELECT 1 FROM public.srm_billing_milestones m WHERE m.billing_plan_id=@plan AND m.due_date=occurrence.due)
            ), updated AS (
                UPDATE public.srm_billing_plans b SET total_amount=coalesce(b.total_amount,0)+@amount*(SELECT count(*) FROM intended),
                    recurrence_rule=coalesce(nullif(trim(b.recurrence_rule),''),@rule),updated_at=now()
                WHERE b.id=@plan AND b.organization_id=@company
                    AND abs(coalesce(b.total_amount,0)+@amount*(SELECT count(*) FROM intended))<=@maximum
                RETURNING b.id,b.name
            ), milestones AS (
                INSERT INTO public.srm_billing_milestones (billing_plan_id,name,due_date,amount,status,metadata_json)
                SELECT b.id,left(coalesce(nullif(@subject,''),b.name),167)||' · '||i.due,i.due,@amount,
                    CASE WHEN @automatic THEN 'ready' ELSE 'pending' END,@presentation
                FROM updated b CROSS JOIN intended i RETURNING id
            ), profile_saved AS (
                INSERT INTO public.suite_service_policies (scope_key,organization_id,module_key,kind,values_json,version,updated_by)
                SELECT @key,@company,'srm','recurring_profile',
                    json_build_object('ongoing',@ongoing,'interval',@interval,'start_date',@start,'next_index',@count,
                        'amount',@amount::text,'rule',@rule,'metadata',@presentation),1,@actor FROM updated
                ON CONFLICT (scope_key) DO UPDATE
                SET values_json=(excluded.values_json::jsonb || jsonb_build_object('next_index',
                        greatest((suite_service_policies.values_json->>'next_index')::int,@count)))::json,
                    version=suite_service_policies.version+1,updated_by=@actor,updated_at=now()
                WHERE @ongoing AND suite_service_policies.organization_id=@company
                    AND suite_service_policies.module_key='srm' AND suite_service_policies.kind='recurring_profile'
                    AND suite_service_policies.values_json->>'ongoing'='false'
                RETURNING values_json,version
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,before_json,after_json)
                SELECT @company,'billing_plan',b.id,'recurring_schedule_created',@actor,
                    json_build_object('profile',(SELECT values_json FROM profile_before)),
                    json_build_object('created',(SELECT count(*) FROM milestones),'skipped',cardinality(@dates)-(SELECT count(*) FROM milestones),
                        'start_date',@start,'profile',pr.values_json,'profile_version',pr.version,'request_id',@request,'request_sha256',@hash)
                FROM updated b CROSS JOIN (
                    SELECT values_json,version FROM profile_saved UNION ALL
                    SELECT values_json,version FROM profile_before WHERE NOT @ongoing AND NOT EXISTS (SELECT 1 FROM profile_saved)
                ) pr
                RETURNING id
            ), owned AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'srm_billing_milestones',id::text,@company,@branch,'validated-write' FROM milestones
                UNION ALL SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit
                RETURNING resource_key
            )
            SELECT (SELECT count(*) FROM milestones)::int,cardinality(@dates)-(SELECT count(*) FROM milestones)::int
            FROM audit WHERE (SELECT count(*) FROM owned)=1+(SELECT count(*) FROM milestones)", db, tx, branch, actor);
        write.Parameters.AddWithValue("key", key);
        write.Parameters.AddWithValue("plan", plan);
        write.Parameters.AddWithValue("dates", NpgsqlDbType.Array | NpgsqlDbType.Date, dates);
        write.Parameters.AddWithValue("start", NpgsqlDbType.Date, input.Start.Date);
        write.Parameters.AddWithValue("count", input.Occurrences);
        write.Parameters.AddWithValue("interval", input.Interval);
        write.Parameters.AddWithValue("rule", rule);
        write.Parameters.AddWithValue("ongoing", input.Ongoing);
        write.Parameters.AddWithValue("automatic", input.AutomaticDrafts);
        write.Parameters.AddWithValue("amount", input.Amount);
        write.Parameters.AddWithValue("maximum", MaximumOrderMoney);
        write.Parameters.AddWithValue("subject", input.Subject);
        write.Parameters.AddWithValue("presentation", NpgsqlDbType.Json, presentation);
        write.Parameters.AddWithValue("request", input.Request.ToString());
        write.Parameters.AddWithValue("hash", digest);
        using var result = await write.ExecuteReaderAsync();
        if (!await result.ReadAsync())
            throw new InvalidOperationException("The schedule, billing plan and audit could not be saved. Review the plan and its amount limit.");
        return new SalesRecurringScheduleResult(result.GetInt32(0), result.GetInt32(1));
    }
}
