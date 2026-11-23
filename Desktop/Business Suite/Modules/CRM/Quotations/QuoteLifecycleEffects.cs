using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class QuoteDraftRepository
{
    private async Task RecordApprovalAsync(NpgsqlConnection db,NpgsqlTransaction tx,int actor,int quote,
        QuoteLifecycleAction action,string approval,string comments,CancellationToken cancellation)
    {
        switch(action)
        {
            case QuoteLifecycleAction.Submit:
                using(var pending=Command(db,tx,@"SELECT 1 FROM public.crm_quote_approvals
                    WHERE organization_id=@org AND quote_id=@quote AND status='pending' LIMIT 1 FOR UPDATE",
                    ("quote",NpgsqlDbType.Integer,quote)))
                    if (await pending.ExecuteScalarAsync(cancellation) is not null)
                        throw new InvalidOperationException("This quotation already has a pending approval.");
                using(var create=Command(db,tx,@"INSERT INTO public.crm_quote_approvals
                    (organization_id,quote_id,status,reason,submitted_by) VALUES (@org,@quote,'pending',@comments,@actor)
                    RETURNING id",("quote",NpgsqlDbType.Integer,quote),("comments",NpgsqlDbType.Text,comments),
                    ("actor",NpgsqlDbType.Integer,actor)))
                {
                    int id=(int)(await create.ExecuteScalarAsync(cancellation))!;
                    await StampAsync(db,tx,"crm_quote_approvals",id,cancellation);
                }
                break;
            case QuoteLifecycleAction.Approve:
            case QuoteLifecycleAction.Reject:
                using(var decide=Command(db,tx,@"UPDATE public.crm_quote_approvals SET status=@approval,approved_by=@actor,
                    approver_user_id=@actor,comments=@comments,decided_at=now()
                    WHERE organization_id=@org AND quote_id=@quote AND status='pending'",
                    ("quote",NpgsqlDbType.Integer,quote),("approval",NpgsqlDbType.Text,approval),
                    ("comments",NpgsqlDbType.Text,comments),("actor",NpgsqlDbType.Integer,actor)))
                    if (await decide.ExecuteNonQueryAsync(cancellation)!=1)
                        throw new InvalidOperationException("Exactly one pending approval is required to record a decision.");
                break;
            case QuoteLifecycleAction.Revise:
                using(var supersede=Command(db,tx,@"UPDATE public.crm_quote_approvals SET status='superseded',decided_at=now()
                    WHERE organization_id=@org AND quote_id=@quote AND status='pending'",("quote",NpgsqlDbType.Integer,quote)))
                    await supersede.ExecuteNonQueryAsync(cancellation);
                break;
        }
    }

    private async Task SnapshotAsync(NpgsqlConnection db,NpgsqlTransaction tx,int actor,int quote,CancellationToken cancellation)
    {
        using var check=Command(db,tx,@"SELECT 1 FROM public.crm_quote_versions v JOIN public.crm_quotations q ON q.id=v.quote_id
            WHERE q.organization_id=@org AND v.organization_id=@org AND q.id=@quote AND v.version_number=q.version_number",
            ("quote",NpgsqlDbType.Integer,quote));
        if (await check.ExecuteScalarAsync(cancellation) is not null)
            throw new InvalidOperationException("A snapshot already exists for this revision. Refresh the quotation.");
        using var snapshot=Command(db,tx,@"INSERT INTO public.crm_quote_versions
            (organization_id,quote_id,version_number,snapshot_json,created_by_user_id)
            SELECT @org,q.id,COALESCE(q.version_number,1),to_jsonb(q)||jsonb_build_object(
                'lines',COALESCE((SELECT jsonb_agg(to_jsonb(i) ORDER BY i.sort_order,i.id)
                    FROM public.crm_quotation_items i WHERE i.quotation_id=q.id),'[]'::jsonb),
                'approvals',COALESCE((SELECT jsonb_agg(to_jsonb(a) ORDER BY a.id DESC)
                    FROM public.crm_quote_approvals a WHERE a.organization_id=@org AND a.quote_id=q.id),'[]'::jsonb)),
                @actor FROM public.crm_quotations q WHERE q.organization_id=@org AND q.id=@quote RETURNING id",
            ("quote",NpgsqlDbType.Integer,quote),("actor",NpgsqlDbType.Integer,actor));
        int versionId=(int)(await snapshot.ExecuteScalarAsync(cancellation))!;
        await StampAsync(db,tx,"crm_quote_versions",versionId,cancellation);
    }

    private async Task LifecycleEvidenceAsync(NpgsqlConnection db,NpgsqlTransaction tx,int actor,QuoteLifecycle original,
        DataRow before,bool revision,string next,string approval,string comments,CancellationToken cancellation)
    {
        string title=revision?$"Quotation revision {original.Version+1}":$"Quote {next}";
        string body=revision?"Previous revision retained in version history.":$"Quote {original.Number} changed to {next}.";
        if (comments.Length!=0)
            body+=" "+comments;
        string action=revision?"QUOTATION_REVISED":"QUOTATION_STATUS_CHANGE";
        string type=revision?"quotation_revised":"quotation_status";
        string oldValues=JsonSerializer.Serialize(new {status=original.Status,approval_status=before["approval_status"] as string,
            version_number=original.Version});
        string newValues=JsonSerializer.Serialize(new {status=next,approval_status=approval,
            version_number=original.Version+(revision?1:0)});
        using var evidence=Command(db,tx,@"WITH activity AS (
            INSERT INTO public.crm_activities (organization_id,branch_id,owner_user_id,entity_type,entity_id,activity_type,
                title,subject,body,description,status,activity_date,created_by_user_id,updated_by_user_id)
            VALUES (@org,@scope_branch,@actor,'quotation',@quote,@type,@title,@title,@body,@body,'Completed',now(),@actor,@actor)
            RETURNING id
        ), owner AS (
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'crm_activities',id::text,@org,@scope_branch,'desktop-crm' FROM activity
        ), timeline AS (
            INSERT INTO public.crm_timeline_events (organization_id,record_type,record_id,event_type,title,description,actor_user_id)
            VALUES (@org,'quotation',@quote,@type,@title,@body,@actor)
        ) INSERT INTO public.audit_logs (organization_id,user_id,actor_authenticated,method,entity_type,entity_id,action,
            description,module,old_values,new_values)
          VALUES (@org,@actor,true,'CRM','quotations',@quote,@action,@title,'crm',@old,@new)",
            ("actor",NpgsqlDbType.Integer,actor),("quote",NpgsqlDbType.Integer,original.Id),("type",NpgsqlDbType.Text,type),
            ("title",NpgsqlDbType.Text,title),("body",NpgsqlDbType.Text,body),("action",NpgsqlDbType.Text,action),
            ("old",NpgsqlDbType.Text,oldValues),("new",NpgsqlDbType.Text,newValues));
        await evidence.ExecuteNonQueryAsync(cancellation);
    }
}
