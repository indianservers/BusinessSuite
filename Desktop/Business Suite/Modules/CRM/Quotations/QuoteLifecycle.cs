using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal enum QuoteLifecycleAction { Submit, Approve, Reject, Decline, Revise }
internal sealed record QuoteLifecycle(int Id,string Number,string Status,int Version,string Revision,string LineRevision,
    string Currency,decimal Total,List<QuoteLifecycleAction> Actions,string Terms,List<QuoteDraftLine> Lines,bool IsIssued,bool CanIssue);

internal sealed partial class QuoteDraftRepository
{
    internal async Task<QuoteLifecycle> ReadLifecycleAsync(int id,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await CrmDirectoryWrites.RequireCrmActorAsync(settings,db,tx,cancellation,"quotes");
        DataRow row=await LifecycleHeaderAsync(db,tx,id,false,cancellation);
        var lines=await LinesAsync(db,tx,id,false,cancellation);
        var actions=new List<QuoteLifecycleAction>();
        string status=(string)row["status"];
        if (actor.CanWriteBranch&&actor.IsSuperuser&&settings.BranchId.HasValue&&row["converted_srm_sales_order_id"] is DBNull)
        {
            if (await CanAsync(db,tx,actor,"quotes","edit"))
            {
                if (IsStatus(status,"Draft","Rejected")&&row["sent_at"] is DBNull)
                    actions.AddRange([QuoteLifecycleAction.Submit,QuoteLifecycleAction.Revise]);
                if (IsStatus(status,"Approved","Sent"))
                    actions.Add(QuoteLifecycleAction.Decline);
            }
            if (IsStatus(status,"Pending Approval")&&await CanApproveAsync(db,tx,actor))
                actions.AddRange([QuoteLifecycleAction.Approve,QuoteLifecycleAction.Reject]);
        }
        return new(id,(string)row["quote_number"],status,row["version_number"] as int? ?? 1,(string)row["revision"],
            lines.Item2,row["currency"] as string??"",row["total_amount"] as decimal? ?? 0,actions,
            row["terms"] as string??row["terms_and_conditions"] as string??"",lines.Item1,
            row["sent_at"] is not DBNull,await CanIssueAsync(db,tx,actor,row));
    }

    internal async Task ApplyLifecycleAsync(QuoteLifecycle original,QuoteLifecycleAction action,string comments,
        CancellationToken cancellation)
    {
        if (comments.Trim().Length>2000)
            throw new ArgumentException("Enter up to 2,000 characters.");
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        if (!actor.IsSuperuser || settings.BranchId is null)
            throw new UnauthorizedAccessException("This desktop quotation action requires a Suite superuser in a writable branch.");
        bool deciding=action is QuoteLifecycleAction.Approve or QuoteLifecycleAction.Reject;
        if (deciding)
            await RequireApproverAsync(db,tx,actor);
        else
            await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"quotes","edit");

        DataRow row=await LifecycleHeaderAsync(db,tx,original.Id,true,cancellation);
        var (lines,lineRevision)=await LinesAsync(db,tx,original.Id,true,cancellation);
        if ((string)row["revision"]!=original.Revision||lineRevision!=original.LineRevision)
            throw new InvalidOperationException("The quotation or its lines changed. Reopen it before continuing.");
        if (row["converted_srm_sales_order_id"] is not DBNull)
            throw new InvalidOperationException("This quotation already has a Sales handoff.");
        string previous=(string)row["status"];
        bool editable=IsStatus(previous,"Draft","Rejected")&&row["sent_at"] is DBNull;
        bool allowed=action switch
        {
            QuoteLifecycleAction.Submit or QuoteLifecycleAction.Revise=>editable,
            QuoteLifecycleAction.Approve or QuoteLifecycleAction.Reject=>IsStatus(previous,"Pending Approval"),
            QuoteLifecycleAction.Decline=>IsStatus(previous,"Approved","Sent"),
            _=>false
        };
        if (!allowed)
            throw new InvalidOperationException("This action is unavailable for the current quotation status.");

        using (var workflow=Command(db,tx,@"SELECT status FROM public.crm_approval_requests
            WHERE organization_id=@org AND entity_type='quotation' AND entity_id=@quote
            ORDER BY submitted_at DESC NULLS LAST,id DESC LIMIT 1 FOR SHARE",("quote",NpgsqlDbType.Integer,original.Id)))
            if (await workflow.ExecuteScalarAsync(cancellation) is string policy && policy is "pending" or "rejected")
                throw new InvalidOperationException("This quotation uses an approval workflow. Resolve the workflow request before changing its status.");
        if (action is QuoteLifecycleAction.Submit or QuoteLifecycleAction.Approve)
        {
            await CrmDirectoryWrites.CheckRequiredFieldsAsync(db,tx,"quotations",settings.OrganizationId,original.Id,cancellation);
            CheckTotals(row,lines);
        }
        string next=action switch
        {
            QuoteLifecycleAction.Submit=>"Pending Approval",
            QuoteLifecycleAction.Approve=>"Approved",
            QuoteLifecycleAction.Reject=>"Rejected",
            QuoteLifecycleAction.Decline=>"Declined",
            _=>"Draft"
        };
        string approval=action switch
        {
            QuoteLifecycleAction.Submit=>"pending",
            QuoteLifecycleAction.Approve=>"approved",
            QuoteLifecycleAction.Reject=>"rejected",
            QuoteLifecycleAction.Decline=>"declined",
            _=>"not_submitted"
        };
        bool revision=action==QuoteLifecycleAction.Revise;
        if (revision)
            await SnapshotAsync(db,tx,actor.Id,original.Id,cancellation);
        await RecordApprovalAsync(db,tx,actor.Id,original.Id,action,approval,comments.Trim(),cancellation);
        using var update=Command(db,tx,@"UPDATE public.crm_quotations SET status=@next,approval_status=@approval,
            approved_by=CASE WHEN @approval='approved' THEN @actor WHEN @clear THEN NULL ELSE approved_by END,
            approved_at=CASE WHEN @approval='approved' THEN now() WHEN @clear THEN NULL ELSE approved_at END,
            declined_at=CASE WHEN @approval IN ('rejected','declined') THEN now() WHEN @clear THEN NULL ELSE declined_at END,
            version_number=CASE WHEN @revision THEN COALESCE(version_number,1)+1 ELSE version_number END,
            pdf_url=CASE WHEN @revision THEN NULL ELSE pdf_url END,pdf_file_name=CASE WHEN @revision THEN NULL ELSE pdf_file_name END,
            pdf_status=CASE WHEN @revision THEN NULL ELSE pdf_status END,pdf_generated_at=CASE WHEN @revision THEN NULL ELSE pdf_generated_at END,
            pdf_generated_by_user_id=CASE WHEN @revision THEN NULL ELSE pdf_generated_by_user_id END,
            accepted_at=CASE WHEN @revision THEN NULL ELSE accepted_at END,
            updated_at=now(),updated_by_user_id=@actor WHERE organization_id=@org AND id=@quote",
            ("quote",NpgsqlDbType.Integer,original.Id),("next",NpgsqlDbType.Text,next),("approval",NpgsqlDbType.Text,approval),
            ("actor",NpgsqlDbType.Integer,actor.Id),("revision",NpgsqlDbType.Boolean,revision),
            ("clear",NpgsqlDbType.Boolean,action is QuoteLifecycleAction.Submit or QuoteLifecycleAction.Reject or QuoteLifecycleAction.Revise));
        await update.ExecuteNonQueryAsync(cancellation);
        await LifecycleEvidenceAsync(db,tx,actor.Id,original,row,revision,next,approval,comments.Trim(),cancellation);
        tx.Commit();
    }

    private async Task<DataRow> LifecycleHeaderAsync(NpgsqlConnection db,NpgsqlTransaction tx,int id,bool write,
        CancellationToken cancellation)
    {
        using var command=Command(db,tx,@"SELECT q.*,q.xmin::text AS revision FROM public.crm_quotations q
            WHERE q.organization_id=@org AND q.id=@id AND q.deleted_at IS NULL AND "+
            CrmDirectoryWrites.BranchScope("crm_quotations","q")+(write?" FOR UPDATE OF q":""),
            ("id",NpgsqlDbType.Integer,id));
        var rows=await TableAsync(command,cancellation);
        if (rows.Rows.Count==0)
            throw new InvalidOperationException("This quotation is unavailable in the current branch.");
        return rows.Rows[0];
    }

    private async Task RequireApproverAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor)
    {
        var grant=await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,Branch,actor,"crm","approve",
            "crm_quotes_approve","crm_admin","crm_manage");
        if (grant.Scope is not ("branch" or "organization"))
            throw new UnauthorizedAccessException("Desktop quotation approval requires branch-wide or organization-wide scope.");
    }

    private async Task<bool> CanApproveAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor)
    {
        try { await RequireApproverAsync(db,tx,actor);return true; }
        catch(UnauthorizedAccessException) { return false; }
    }

    private static bool IsStatus(string value,params string[] choices)=>choices.Contains(value,StringComparer.OrdinalIgnoreCase);
    private static void CheckTotals(DataRow row,List<QuoteDraftLine> lines)
    {
        var amounts=lines.Select(Calculate).ToArray();
        if (amounts.Sum(v=>v.Gross)!=(row["subtotal"] as decimal? ?? 0)||
            amounts.Sum(v=>v.Discount)!=(row["discount_amount"] as decimal? ?? 0)||
            amounts.Sum(v=>v.Tax)!=(row["tax_amount"] as decimal? ?? 0)||
            amounts.Sum(v=>v.Total)!=(row["total_amount"] as decimal? ?? 0))
            throw new InvalidOperationException("The stored quotation totals differ from its lines. Correct or recalculate the draft before approval.");
    }
}
