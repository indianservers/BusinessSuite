using System.Data;
using System.Text.Json;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record CrmDealClosing(CrmDealEdit Original, decimal Amount, string Currency, DateTime BusinessToday, List<CrmDealQuoteChoice> Quotes, bool CanCreateTask);
internal sealed record CrmDealClosure(string Outcome, DateTime Date, decimal Amount, string Reason,
    string ContractReference, string HandoverNotes, string Competitor, CrmDealQuoteChoice? Quote = null, bool Onboarding = false, DateTime? Reengagement = null);

internal sealed partial class CrmDealRepository
{
    internal async Task<CrmDealClosing> ReadClosingAsync(int id,CancellationToken cancellation)
    {
        var original=await EditAsync(id,cancellation);
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await RequireEditorAsync(db,tx,cancellation);
        var deal=await LockableDealAsync(db,tx,id,false,cancellation);
        AssertCurrent(original,deal);
        return new(original,deal["amount"] as decimal? ?? 0,Convert.ToString(deal["currency"])??"",
            await BusinessTodayAsync(db,tx,cancellation),await ReadQuoteChoicesAsync(db,tx,actor,deal,cancellation),
            await CanCreateClosureTaskAsync(db,tx,actor,cancellation));
    }

    internal async Task<int?> CloseAsync(CrmDealEdit original,CrmDealClosure closure,CancellationToken cancellation)
    {
        if (closure.Outcome is not ("Won" or "Lost") || closure.Reason.Trim().Length is <5 or >2000 ||
            closure.Amount<0 || closure.Amount>9999999999m || Math.Round(closure.Amount,2)!=closure.Amount ||
            closure.ContractReference.Length>180 || closure.HandoverNotes.Length>4000 || closure.Competitor.Length>180)
            throw new ArgumentException("Choose Won or Lost, provide a reason of 5–2,000 characters and enter a valid final amount.");
        bool won=closure.Outcome=="Won";
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        var actor=await RequireEditorAsync(db,tx,cancellation);
        if (won)
        {
            using (var companyLock=Query(db,tx,"SELECT pg_advisory_xact_lock(720000000::bigint+@org)"))
                await companyLock.ExecuteNonQueryAsync(cancellation);
            using (var company=Query(db,tx,"SELECT id FROM public.companies WHERE id=@org AND is_active FOR UPDATE"))
                if (await company.ExecuteScalarAsync(cancellation) is null)
                    throw new InvalidOperationException("The selected company is unavailable.");
            await settings.VerifyWriteTargetAsync(db,tx,cancellation);
            actor=await RequireEditorAsync(db,tx,cancellation);
        }
        var deal=await LockableDealAsync(db,tx,original.Id,true,cancellation);
        AssertCurrent(original,deal);
        DateTime today=await BusinessTodayAsync(db,tx,cancellation);
        if (closure.Date.Date>today)
            throw new InvalidOperationException("Actual closing date cannot be in the future.");
        if (won && closure.Reengagement.HasValue || !won && closure.Onboarding)
            throw new ArgumentException("Choose the follow-up task that matches the outcome.");
        if (closure.Reengagement is DateTime reviewDate && reviewDate.Date<today)
            throw new InvalidOperationException("Re-engagement date must be today or later.");
        bool createTask=closure.Onboarding || closure.Reengagement.HasValue;
        if (createTask)
            await RequireDealActivityAccessAsync(db,tx,actor,"create");
        if (deal["catalog_items"] is string catalog && catalog is not ("[]" or "null") &&
            (deal["amount"] as decimal? ?? 0)!=closure.Amount)
            throw new InvalidOperationException("Update the catalog lines to match the final value before closing.");

        await CrmDirectoryWrites.CheckRequiredFieldsAsync(db,tx,"deals",settings.OrganizationId,original.Id,cancellation);
        await GuardLocalEffectsAsync(db,tx,true,cancellation,closure.Outcome);
        int destination=await ClosingStageAsync(db,tx,(int)deal["pipeline_id"],won,cancellation);
        if (won)
            await CheckFinalApprovalAsync(db,tx,original.Id,cancellation);
        decimal? previousAmount=deal["amount"] as decimal?;
        DataRow stage=await CheckStageAsync(db,tx,deal,destination,cancellation,closure.Outcome,closure.Amount);
        int probability=stage["probability"] as int? ?? 0;
        if (probability<0 || probability>100)
            throw new InvalidOperationException("Closing stage probability is invalid.");

        var planning=deal["planning"] is string data ? JsonNode.Parse(data)?.AsObject()??new JsonObject() : new JsonObject();
        planning["closure"]=JsonSerializer.SerializeToNode(new
        {
            reason=closure.Reason.Trim(),actual_close_date=closure.Date.ToString("yyyy-MM-dd"),
            currency=Convert.ToString(deal["currency"]),contract_reference=closure.ContractReference,
            handover_notes=closure.HandoverNotes,competitor=closure.Competitor,onboarding=closure.Onboarding,
            reengagement_date=closure.Reengagement?.ToString("yyyy-MM-dd"),
            quotation_id=won?closure.Quote?.Id:null
        });
        string reasonField=won?"win_reason":"lost_reason";
        using var update=Query(db,tx,$@"UPDATE public.crm_deals SET status=@status,stage_id=@stage,amount=@amount,
            probability=@probability,expected_revenue=@expected,actual_close_date=@date,closed_at=now(),
            won_at=CASE WHEN @won THEN now() ELSE NULL END,lost_at=CASE WHEN NOT @won THEN now() ELSE NULL END,
            {reasonField}=@reason,loss_reason=CASE WHEN NOT @won AND COALESCE(loss_reason,'')='' THEN @reason ELSE loss_reason END,
            planning=@planning,version=version+1,updated_at=now(),updated_by_user_id=@actor
            WHERE organization_id=@org AND id=@id",
            ("status",NpgsqlDbType.Text,closure.Outcome),("stage",NpgsqlDbType.Integer,destination),
            ("amount",NpgsqlDbType.Numeric,closure.Amount),("probability",NpgsqlDbType.Integer,probability),
            ("expected",NpgsqlDbType.Numeric,Math.Round(closure.Amount*probability/100m,2,MidpointRounding.ToEven)),
            ("date",NpgsqlDbType.Date,closure.Date.Date),("won",NpgsqlDbType.Boolean,won),
            ("reason",NpgsqlDbType.Text,closure.Reason.Trim()),("planning",NpgsqlDbType.Json,planning.ToJsonString()),
            ("actor",NpgsqlDbType.Integer,actor.Id),("id",NpgsqlDbType.Integer,original.Id));
        await update.ExecuteNonQueryAsync(cancellation);

        var changes=new List<(string Field,object? Old,object? New)>
        {
            ("stage_id",original.Stage,destination),("status","Open",closure.Outcome),
            ("actual_close_date",deal["actual_close_date"] as DateTime?,closure.Date.Date),
            (reasonField,deal[reasonField] as string,closure.Reason.Trim())
        };
        if (previousAmount!=closure.Amount) changes.Add(("amount",previousAmount,closure.Amount));
        if (deal["probability"] as int? != probability) changes.Add(("probability",deal["probability"] as int?,probability));
        foreach (var change in changes)
            await AddHistoryAsync(db,tx,actor.Id,deal,change,cancellation);
        await WriteAuditAsync(db,tx,actor.Id,original.Id,true,changes,cancellation);
        await QueueStageEventAsync(db,tx,actor.Id,deal,original,stage,cancellation);
        await LeadStore.ApplyDealStageAsync(db,tx,settings,original.Id,(int)deal["pipeline_id"],(string)stage["name"],
            actor.Id,cancellation,stage["is_won"] is true,deal["company_id"] as int?,deal["contact_id"] as int?);
        int? order=won ? await CreateWonHandoffAsync(db,tx,actor,deal,closure.Amount,today,closure.Quote,cancellation) : null;
        if (createTask)
        {
            DateTime due=DateTime.SpecifyKind((closure.Reengagement ?? closure.Date).Date,DateTimeKind.Utc);
            await InsertDealTaskAsync(db,tx,actor,deal,new DealTaskDraft(
                closure.Onboarding?"Customer onboarding":"Review lost opportunity",
                string.IsNullOrWhiteSpace(closure.HandoverNotes)?closure.Reason.Trim():closure.HandoverNotes.Trim(),
                "Medium",due,null),null,cancellation,deal["owner_user_id"] as int?);
        }
        await NotifyDealWatchersAsync(db,tx,actor.Id,deal,(string)deal["name"],cancellation);
        tx.Commit();
        return order;
    }

    private async Task<bool> CanCreateClosureTaskAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,
        CancellationToken cancellation)
    {
        try
        {
            await RequireDealActivityAccessAsync(db,tx,actor,"create");
            return true;
        }
        catch (UnauthorizedAccessException) { return false; }
    }

    private static void AssertCurrent(CrmDealEdit original,DataRow deal)
    {
        if ((int)deal["version"]!=original.Version || (string)deal["revision"]!=original.Revision)
            throw new InvalidOperationException("This deal changed. Close the dialog and refresh.");
    }

    private async Task<int> ClosingStageAsync(NpgsqlConnection db,NpgsqlTransaction tx,int pipeline,bool won,
        CancellationToken cancellation)
    {
        using var query=Query(db,tx,@"SELECT id FROM public.crm_pipeline_stages WHERE organization_id=@org
            AND pipeline_id=@pipeline AND active AND deleted_at IS NULL AND
            ((@won AND (is_won OR lower(stage_type)='won')) OR (NOT @won AND (is_lost OR lower(stage_type)='lost')))
            ORDER BY position NULLS LAST,id LIMIT 1",("pipeline",NpgsqlDbType.Integer,pipeline),("won",NpgsqlDbType.Boolean,won));
        return await query.ExecuteScalarAsync(cancellation) is int id ? id :
            throw new InvalidOperationException($"Configure an active Closed {(won?"Won":"Lost")} stage in this pipeline first.");
    }

    private async Task CheckFinalApprovalAsync(NpgsqlConnection db,NpgsqlTransaction tx,int id,CancellationToken cancellation)
    {
        using var query=Query(db,tx,@"SELECT status FROM public.crm_approval_requests WHERE organization_id=@org
            AND entity_type='deal' AND entity_id=@id ORDER BY submitted_at DESC NULLS LAST,id DESC LIMIT 1 FOR SHARE",
            ("id",NpgsqlDbType.Integer,id));
        if (await query.ExecuteScalarAsync(cancellation) is string status && status is "pending" or "rejected")
            throw new InvalidOperationException($"Deal approval is {status}. Approve it before closing Won.");
    }

    private async Task<DateTime> BusinessTodayAsync(NpgsqlConnection db,NpgsqlTransaction tx,CancellationToken cancellation)
    {
        string key=$"form-defaults:company:{settings.OrganizationId}";
        string branch=$"{key}:branch:{settings.BranchId}";
        using var query=Query(db,tx,@"SELECT (now() AT TIME ZONE COALESCE((
            SELECT p.values_json->>'timezone' FROM public.suite_service_policies p
            WHERE p.organization_id=@org AND p.kind='form_defaults' AND p.scope_key=ANY(@keys)
                AND NULLIF(p.values_json->>'timezone','') IS NOT NULL
            ORDER BY array_position(@keys,p.scope_key) LIMIT 1
        ),c.default_timezone,'Asia/Kolkata'))::date FROM public.companies c WHERE c.id=@org",
        ("keys",NpgsqlDbType.Array|NpgsqlDbType.Text,settings.BranchId.HasValue
            ? new[] {branch+":module:crm",branch,key+":module:crm",key}
            : new[] {key+":module:crm",key}));
        return (DateTime)(await query.ExecuteScalarAsync(cancellation))!;
    }
}
