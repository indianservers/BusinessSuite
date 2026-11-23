using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal static partial class LeadStore
{
    internal static async Task<DataTable> LeadTasksAsync(int lead,CancellationToken cancellation)
    {
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        await CrmDirectoryWrites.RequireCrmActorAsync(settings,db,tx,cancellation,"leads");
        using var query=Cmd(db,tx,@"SELECT a.id,a.xmin::text AS revision,a.subject,a.activity_type,a.status,a.owner_user_id,
            COALESCE(NULLIF(person.display_name,''),'User '||a.owner_user_id::text,'Unassigned') AS owner_name,
            a.due_date AT TIME ZONE 'UTC' AS due,a.completed_at AT TIME ZONE 'UTC' AS completed
            FROM public.crm_activities a
            JOIN public.crm_leads l ON l.organization_id=a.organization_id AND l.id=a.lead_id
            LEFT JOIN public.crm_lead_operating_states s ON s.organization_id=l.organization_id AND s.lead_id=l.id
            LEFT JOIN public.common_people person ON person.organization_id=l.organization_id AND person.user_id=a.owner_user_id
            WHERE a.organization_id=@org AND l.id=@lead AND l.deleted_at IS NULL AND a.deleted_at IS NULL
              AND COALESCE(s.data_json->>'archived','false')<>'true'
              AND COALESCE(s.data_json->>'recordType','Lead')='Lead'
              AND (a.status='Pending' OR a.activity_type='task'
                  OR (a.activity_type IN ('call','email','meeting') AND a.completed_at IS NOT NULL))
              AND "+CrmDirectoryWrites.BranchScope("crm_leads","l",includeShares:true)+@"
              AND "+LeadActivityScope(true)+@"
            ORDER BY (a.status='Pending') DESC,a.due_date NULLS LAST,a.id",
            ("org",NpgsqlDbType.Integer,settings.OrganizationId),("lead",NpgsqlDbType.Integer,lead),
            ("scope_branch",NpgsqlDbType.Integer,settings.BranchId));
        using var rows=await query.ExecuteReaderAsync(cancellation);
        return await Table(rows,cancellation);
    }

    internal static async Task CompleteLeadTaskAsync(LeadKey key,int activity,string revision,CancellationToken cancellation)
    {
        if (key.Potential)
            throw new InvalidOperationException("Choose an active Lead.");
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"leads","edit");
        var lead=await LockLead(db,tx,settings,key,false,cancellation);
        int org=settings.OrganizationId;
        DateTime now=DateTime.UtcNow;
        using var update=Cmd(db,tx,@"UPDATE public.crm_activities a SET status='Completed',completed_at=@now,
            updated_at=@now,updated_by_user_id=@actor
            WHERE a.organization_id=@org AND a.lead_id=@lead AND a.id=@id AND a.deleted_at IS NULL
              AND a.status='Pending' AND a.xmin::text=@revision AND "+LeadActivityScope(false)+@"
            RETURNING a.subject,a.activity_type",
            ("org",NpgsqlDbType.Integer,org),("lead",NpgsqlDbType.Integer,key.Id),
            ("scope_branch",NpgsqlDbType.Integer,settings.BranchId),("id",NpgsqlDbType.Integer,activity),
            ("actor",NpgsqlDbType.Integer,actor.Id),("revision",NpgsqlDbType.Text,revision),("now",NpgsqlDbType.TimestampTz,now));
        string subject;
        bool contacted;
        using (var row=await update.ExecuteReaderAsync(cancellation))
        {
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("This task changed, is outside your writable branch, or is already complete.");
            subject=row.IsDBNull(0)?"Task completed":row.GetString(0);
            contacted=!row.IsDBNull(1)&&row.GetString(1) is ("call" or "email" or "meeting");
        }

        var details=ReadDetails(lead);
        details["lastActivityAt"]=now;
        if (contacted)
        {
            details["enquiryPending"]=false;
            if (!details.ContainsKey("firstContactAt"))
                details["firstContactAt"]=now;
        }
        details.TryGetValue("sequence",out var sequence);
        DateTime? next=null;
        bool sequencePending=false;
        object? sequenceId=Nested(sequence,"id");
        using(var pending=Cmd(db,tx,@"SELECT due_date,metadata_json->'sequenceId' AS sequence_id,"+LeadActivityScope(true)+@"
            FROM public.crm_activities a WHERE organization_id=@org AND lead_id=@lead AND status='Pending' AND deleted_at IS NULL
            ORDER BY due_date NULLS LAST,id",
            ("org",NpgsqlDbType.Integer,org),("lead",NpgsqlDbType.Integer,key.Id),("scope_branch",NpgsqlDbType.Integer,settings.BranchId)))
        using (var rows=await pending.ExecuteReaderAsync(cancellation))
        {
            bool first=true;
            while (await rows.ReadAsync(cancellation))
            {
                if (first&&rows.GetBoolean(2))
                {
                    next=rows.IsDBNull(0)?null:rows.GetDateTime(0);
                    first=false;
                }
                if (sequenceId is JsonElement identity && !rows.IsDBNull(1) && identity.GetRawText()==rows.GetString(1))
                    sequencePending=true;
            }
        }
        if (!sequencePending && sequence is JsonElement activeSequence &&
            Nested(sequence,"active") is JsonElement active && active.ValueKind==JsonValueKind.True)
        {
            var copy=activeSequence.EnumerateObject().ToDictionary(item=>item.Name,item=>(object?)item.Value.Clone());
            copy["active"]=false;
            copy["stopReason"]="All steps completed";
            copy["stoppedAt"]=now;
            details["sequence"]=copy;
        }
        await WriteState(db,tx,org,key.Id,details,key.StateRevision,cancellation);
        using var stamp=Cmd(db,tx,@"UPDATE public.crm_leads SET next_follow_up_at=@due,updated_at=@now,updated_by_user_id=@actor,
            last_contacted_at=CASE WHEN @contacted THEN @now ELSE last_contacted_at END
            WHERE organization_id=@org AND id=@lead",
            ("org",NpgsqlDbType.Integer,org),("lead",NpgsqlDbType.Integer,key.Id),("now",NpgsqlDbType.TimestampTz,now),
            ("due",NpgsqlDbType.TimestampTz,next),("contacted",NpgsqlDbType.Boolean,contacted),("actor",NpgsqlDbType.Integer,actor.Id));
        await stamp.ExecuteNonQueryAsync(cancellation);
        await AddLeadHistoryAsync(db,tx,org,key.Id,settings.BranchId??lead["branch_id"] as int?,actor.Id,
            "task_completed",subject,null,JsonSerializer.Serialize(new {activityId=activity}),cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"crm_activities",org,activity,actor.Id,"UPDATE",cancellation,"Lead task completed");
        tx.Commit();
    }

    private static string LeadActivityScope(bool shared)
    {
        string shares=shared?@" OR EXISTS (SELECT 1 FROM public.suite_branch_record_shares share
            WHERE share.company_id=a.organization_id AND share.resource_table='crm_activities'
              AND share.resource_key=a.id::text AND share.branch_id=@scope_branch)":"";
        return @"(@scope_branch IS NULL OR COALESCE((SELECT ownership.branch_id FROM public.suite_branch_ownership ownership
            WHERE ownership.company_id=a.organization_id AND ownership.resource_table='crm_activities'
              AND ownership.resource_key=a.id::text),a.branch_id,@scope_branch)=@scope_branch"+shares+")";
    }
}
