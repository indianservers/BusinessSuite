using System.Globalization;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    private sealed record RecurrenceExtensionProfile(int Id, int Version, DateTime Start, int Cursor, int Interval,
        string Rule, decimal Amount, string Metadata, string Subject, bool AutomaticDrafts);

    internal async Task<SalesRecurringScheduleResult> ExtendSalesRecurringScheduleAsync(
        int order, int engagement, int plan, DateTime through)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose the recurring billing branch.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "recurring billing extension");
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "create");
        using var read = ScopedCommand(@"SELECT p.id,p.version,p.values_json::text,b.recurrence_rule,e.customer_id
            " + SalesBillingPlanChain + @" JOIN public.suite_service_policies p ON p.organization_id=@company
                AND p.scope_key='recurring-profile:'||@company||':'||b.id AND p.kind='recurring_profile' AND p.module_key='srm'
            " + SalesBillingPlanScope + @" AND b.id=@plan AND b.status='active'
                AND e.status NOT IN ('closed','cancelled') FOR UPDATE OF o,e,b,p", db, tx, branch, actor, scope);
        BindBillingMilestoneChain(read, order, engagement, plan);
        RecurrenceExtensionProfile profile;
        int? customer;
        using (var rows = await read.ExecuteReaderAsync())
        {
            if (!await rows.ReadAsync())
                throw new InvalidOperationException("An active billing plan with a saved recurring profile is required.");
            profile = ReadRecurrenceExtension(rows.GetInt32(0), rows.GetInt32(1), rows.GetString(2),
                rows.IsDBNull(3) ? "" : rows.GetString(3));
            customer = rows.IsDBNull(4) ? null : rows.GetInt32(4);
        }
        if (profile.AutomaticDrafts)
        {
            await SalesInvoiceScopeAsync(db, tx, branch, actor);
            await VerifyRecurringDraftCustomerAsync(db, tx, branch, actor.Id, customer);
        }

        var dates = new List<DateTime>();
        try
        {
            for (int index = profile.Cursor; index < profile.Cursor + 120; index++)
            {
                DateTime due = SalesOccurrenceDate(profile.Start, profile.Rule, index, profile.Interval);
                if (due > through.Date)
                    break;
                dates.Add(due);
            }
        }
        catch (ArgumentOutOfRangeException)
        {
            throw new ArgumentException("The recurrence reaches beyond the supported calendar.");
        }
        if (dates.Count == 0)
        {
            tx.Commit();
            return new SalesRecurringScheduleResult(0, 0);
        }

        using var write = RegisterCommand(@"
            WITH intended AS (
                SELECT occurrence.due FROM unnest(@dates::date[]) AS occurrence(due)
                WHERE NOT EXISTS(SELECT 1 FROM public.srm_billing_milestones m WHERE m.billing_plan_id=@plan AND m.due_date=occurrence.due)
            ), plan AS (
                UPDATE public.srm_billing_plans SET total_amount=coalesce(total_amount,0)+@amount*(SELECT count(*) FROM intended),
                    updated_at=now()
                WHERE id=@plan AND organization_id=@company AND status='active'
                    AND abs(coalesce(total_amount,0)+@amount*(SELECT count(*) FROM intended))<=@maximum
                RETURNING id,name
            ), milestones AS (
                INSERT INTO public.srm_billing_milestones (billing_plan_id,name,due_date,amount,status,metadata_json)
                SELECT p.id,left(coalesce(nullif(@subject,''),p.name),167)||' · '||i.due,i.due,@amount,
                    CASE WHEN @automatic THEN 'ready' ELSE 'pending' END,@metadata
                FROM plan p CROSS JOIN intended i RETURNING id
            ), profile AS (
                UPDATE public.suite_service_policies p SET values_json=jsonb_set(p.values_json::jsonb,'{next_index}',to_jsonb(@next::int))::json,
                    version=version+1,updated_at=now()
                WHERE p.id=@profile AND p.organization_id=@company AND p.version=@version AND EXISTS(SELECT 1 FROM plan)
                RETURNING p.id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,before_json,after_json)
                SELECT @company,'billing_plan',p.id,'recurring_schedule_extended',@actor,json_build_object('next_index',@cursor),
                    json_build_object('next_index',@next,'through',@through,'created',(SELECT count(*) FROM milestones),
                        'skipped',cardinality(@dates)-(SELECT count(*) FROM milestones))
                FROM plan p WHERE EXISTS (SELECT 1 FROM profile) RETURNING id
            ), scoped AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'srm_billing_milestones',id::text,@company,@branch,'validated-write' FROM milestones
                UNION ALL SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit RETURNING resource_key
            )
            SELECT (SELECT count(*) FROM milestones)::int FROM audit
            WHERE (SELECT count(*) FROM scoped)=1+(SELECT count(*) FROM milestones)", db, tx, branch, actor.Id);
        write.Parameters.AddWithValue("plan", plan);
        write.Parameters.AddWithValue("profile", profile.Id);
        write.Parameters.AddWithValue("version", profile.Version);
        write.Parameters.AddWithValue("cursor", profile.Cursor);
        write.Parameters.AddWithValue("next", profile.Cursor + dates.Count);
        write.Parameters.AddWithValue("through", NpgsqlDbType.Date, through.Date);
        write.Parameters.AddWithValue("dates", NpgsqlDbType.Array | NpgsqlDbType.Date, dates.ToArray());
        write.Parameters.AddWithValue("amount", profile.Amount);
        write.Parameters.AddWithValue("subject", profile.Subject);
        write.Parameters.AddWithValue("automatic", profile.AutomaticDrafts);
        write.Parameters.AddWithValue("maximum", MaximumOrderMoney);
        write.Parameters.AddWithValue("metadata", NpgsqlDbType.Json, profile.Metadata);
        if (await write.ExecuteScalarAsync() is not int created)
            throw new InvalidOperationException("The schedule cursor, milestones and audit could not be saved together.");
        tx.Commit();
        return new SalesRecurringScheduleResult(created, dates.Count - created);
    }

    private static RecurrenceExtensionProfile ReadRecurrenceExtension(int id, int version, string json, string planRule)
    {
        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;
        const string invalid = "The saved recurring profile is invalid.";
        if (root.ValueKind != JsonValueKind.Object)
            throw new InvalidOperationException(invalid);
        if (root.TryGetProperty("ongoing", out var ongoing) && ongoing.ValueKind != JsonValueKind.True)
            throw new InvalidOperationException("This recurring profile is finite. Create another finite schedule to add dates.");
        if (!root.TryGetProperty("next_index", out var cursorNode) || cursorNode.ValueKind != JsonValueKind.Number ||
            !cursorNode.TryGetInt32(out int cursor) || cursor is < 0 or > 100000 ||
            !root.TryGetProperty("start_date", out var startNode) || !DateTime.TryParseExact(startNode.ToString(), "yyyy-MM-dd",
                CultureInfo.InvariantCulture, DateTimeStyles.None, out var start) ||
            !root.TryGetProperty("rule", out var ruleNode) || !root.TryGetProperty("amount", out var amountNode) ||
            !decimal.TryParse(amountNode.ToString(), NumberStyles.Number, CultureInfo.InvariantCulture, out decimal amount) ||
            amount <= 0 || amount > MaximumOrderMoney || decimal.Round(amount, 2) != amount ||
            !root.TryGetProperty("metadata", out var metadata) || metadata.ValueKind != JsonValueKind.Object ||
            !metadata.TryGetProperty("recurring", out var recurring) || recurring.ValueKind != JsonValueKind.True)
            throw new InvalidOperationException(invalid);
        int interval = 1;
        if (root.TryGetProperty("interval", out var intervalNode) && (intervalNode.ValueKind != JsonValueKind.Number ||
            !intervalNode.TryGetInt32(out interval) || interval is < 1 or > 120))
            throw new InvalidOperationException(invalid);
        bool automaticDrafts = false;
        if (metadata.TryGetProperty("automatic_drafts", out var automatic))
        {
            if (automatic.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                throw new InvalidOperationException(invalid);
            automaticDrafts = automatic.GetBoolean();
        }
        string rule = ruleNode.ToString().Trim().ToLowerInvariant();
        if (rule != planRule.Trim().ToLowerInvariant())
            throw new InvalidOperationException("The plan and recurring profile have different billing rules.");
        string subject = metadata.TryGetProperty("subject", out var label) && label.ValueKind == JsonValueKind.String
            ? label.GetString()! : "";
        return new RecurrenceExtensionProfile(id, version, start, cursor, interval, rule, amount,
            metadata.GetRawText(), subject, automaticDrafts);
    }
}
