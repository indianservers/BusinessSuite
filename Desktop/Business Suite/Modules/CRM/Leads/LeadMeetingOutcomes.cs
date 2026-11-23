using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal static partial class LeadStore
{
    private const string MeetingReadScope=@"(@scope_branch IS NULL OR NOT EXISTS (
        SELECT 1 FROM public.suite_branch_ownership ownership
        WHERE ownership.company_id=m.organization_id AND ownership.resource_table='crm_meetings'
            AND ownership.resource_key=m.id::text AND ownership.branch_id<>@scope_branch
        ) OR EXISTS (
        SELECT 1 FROM public.suite_branch_record_shares share
        WHERE share.company_id=m.organization_id AND share.resource_table='crm_meetings'
            AND share.resource_key=m.id::text AND share.branch_id=@scope_branch))";

    internal static async Task<DataTable> LeadMeetingsAsync(int lead,CancellationToken cancellation)
    {
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        await CrmDirectoryWrites.RequireCrmActorAsync(settings,db,tx,cancellation,"leads");
        using var query=Cmd(db,tx,@"SELECT m.id,m.xmin::text AS revision,m.title,m.status,m.outcome,
            m.start_time AT TIME ZONE 'UTC' AS starts,m.end_time AT TIME ZONE 'UTC' AS ends,
            (NULLIF(m.external_provider,'') IS NOT NULL OR NULLIF(m.external_event_id,'') IS NOT NULL) AS external_calendar
            FROM public.crm_meetings m
            JOIN public.crm_leads l ON l.organization_id=m.organization_id AND l.id=m.lead_id
            LEFT JOIN public.crm_lead_operating_states s ON s.organization_id=l.organization_id AND s.lead_id=l.id
            WHERE m.organization_id=@org AND l.id=@lead AND m.deleted_at IS NULL AND l.deleted_at IS NULL
                AND COALESCE(s.data_json->>'archived','false')<>'true'
                AND COALESCE(s.data_json->>'recordType','Lead')='Lead'
                AND "+CrmDirectoryWrites.BranchScope("crm_leads","l",includeShares:true)+" AND "+MeetingReadScope+
            " ORDER BY m.start_time DESC,m.id DESC",
            ("org",NpgsqlDbType.Integer,settings.OrganizationId),("scope_branch",NpgsqlDbType.Integer,settings.BranchId),
            ("lead",NpgsqlDbType.Integer,lead));
        using var rows=await query.ExecuteReaderAsync(cancellation);
        return await Table(rows,cancellation);
    }

    internal static async Task SaveLeadMeetingOutcomeAsync(LeadKey key,int meeting,string revision,string status,string outcome,
        CancellationToken cancellation,DateTime? replacementUtc=null)
    {
        outcome=outcome.Trim();
        if (status is not ("Confirmed" or "Attended" or "No-show" or "Cancelled" or "Rescheduled") || outcome.Length>4000)
            throw new ArgumentException("Choose an available meeting outcome and use up to 4,000 characters.");
        if ((status=="Rescheduled")!=replacementUtc.HasValue || replacementUtc is DateTime start &&
            (start.Kind!=DateTimeKind.Utc || start<=DateTime.UtcNow))
            throw new ArgumentException("Choose a future replacement meeting time in UTC.");
        if (key.Potential)
            throw new InvalidOperationException("Choose an active Lead.");
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"leads","edit");
        var lead=await LockLead(db,tx,settings,key,false,cancellation);
        using var current=Cmd(db,tx,@"SELECT m.xmin::text,m.status,m.start_time>now() AS upcoming,
                (NULLIF(m.external_provider,'') IS NOT NULL OR NULLIF(m.external_event_id,'') IS NOT NULL) AS external_calendar,
                m.owner_user_id,m.title,m.description
            FROM public.crm_meetings m WHERE m.organization_id=@org AND m.id=@id AND m.lead_id=@lead AND m.deleted_at IS NULL
                AND NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership ownership
                    WHERE ownership.company_id=m.organization_id AND ownership.resource_table='crm_meetings'
                      AND ownership.resource_key=m.id::text AND @scope_branch IS NOT NULL AND ownership.branch_id<>@scope_branch)
            FOR UPDATE",
            ("org",NpgsqlDbType.Integer,settings.OrganizationId),("scope_branch",NpgsqlDbType.Integer,settings.BranchId),
            ("id",NpgsqlDbType.Integer,meeting),("lead",NpgsqlDbType.Integer,key.Id));
        string previous;
        int? owner;
        bool demo;
        using(var item=await current.ExecuteReaderAsync(cancellation))
        {
            if (!await item.ReadAsync(cancellation) || item.GetString(0)!=revision)
                throw new InvalidOperationException("This meeting changed or is outside the writable branch. Refresh and try again.");
            previous=item.GetString(1);
            if (previous==status && status!="Rescheduled")
                return;
            if (previous is not ("Scheduled" or "Confirmed"))
                throw new InvalidOperationException("This meeting already has a final outcome.");
            if (status is ("Attended" or "No-show") && item.GetBoolean(2))
                throw new InvalidOperationException("Record attendance after the meeting starts.");
            if (item.GetBoolean(3))
                throw new InvalidOperationException("This meeting is linked to an external calendar. Update it through the connected calendar workflow.");
            owner=item.IsDBNull(4)?null:item.GetInt32(4);
            demo=item.GetString(5).IndexOf("demo",StringComparison.OrdinalIgnoreCase)>=0 ||
                (!item.IsDBNull(6) && item.GetString(6)=="Sales meeting: demo");
        }
        if (status=="Attended")
            await RecordLeadAttendanceAsync(db,tx,settings,key,lead,meeting,actor.Id,demo,cancellation);
        int? replacement=null;
        if (replacementUtc is DateTime replacementStart)
            replacement=await RescheduleLeadMeetingAsync(db,tx,settings,key.Id,meeting,
                owner??throw new InvalidOperationException("Assign a meeting owner before rescheduling."),
                lead["branch_id"] as int?,actor.Id,replacementStart,cancellation);
        using var update=Cmd(db,tx,@"UPDATE public.crm_meetings SET status=@status,outcome=@outcome,updated_by_user_id=@actor,
            updated_at=now() WHERE organization_id=@org AND lead_id=@lead AND id=@id",
            ("org",NpgsqlDbType.Integer,settings.OrganizationId),("lead",NpgsqlDbType.Integer,key.Id),
            ("id",NpgsqlDbType.Integer,meeting),("actor",NpgsqlDbType.Integer,actor.Id),("status",NpgsqlDbType.Text,status),
            ("outcome",NpgsqlDbType.Text,outcome));
        await update.ExecuteNonQueryAsync(cancellation);
        string title="Meeting "+status.ToLowerInvariant();
        string metadata=replacement.HasValue
            ?JsonSerializer.Serialize(new {meetingId=meeting,from=previous,to=status,replacementMeetingId=replacement.Value})
            :JsonSerializer.Serialize(new {meetingId=meeting,from=previous,to=status});
        await AddLeadHistoryAsync(db,tx,settings.OrganizationId,key.Id,lead["branch_id"] as int?,actor.Id,
            "meeting_outcome",title,outcome,metadata,cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"crm_meetings",settings.OrganizationId,meeting,actor.Id,"UPDATE",cancellation,title);
        tx.Commit();
    }

    private static async Task<int> RescheduleLeadMeetingAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        DesktopDatabaseSettings settings,int lead,int meeting,int owner,int? leadBranch,int actor,DateTime start,
        CancellationToken cancellation)
    {
        int org=settings.OrganizationId;
        await LockMeetingOwnerAsync(db,tx,owner,cancellation);
        using var insert=Cmd(db,tx,@"INSERT INTO public.crm_meetings (organization_id,owner_user_id,title,description,location,
                start_time,end_time,status,sync_status,lead_id,contact_id,company_id,deal_id,created_by_user_id,updated_by_user_id)
            SELECT m.organization_id,m.owner_user_id,m.title,m.description,m.location,@start,@start+(m.end_time-m.start_time),
                'Scheduled','not_synced',m.lead_id,m.contact_id,m.company_id,m.deal_id,@actor,@actor
            FROM public.crm_meetings m WHERE m.organization_id=@org AND m.id=@meeting
                AND m.end_time>m.start_time AND @start>clock_timestamp()
                AND NOT EXISTS (SELECT 1 FROM public.crm_meetings other
                    WHERE other.organization_id=m.organization_id AND other.owner_user_id=m.owner_user_id AND other.id<>m.id
                      AND other.deleted_at IS NULL AND other.status IN ('Scheduled','Confirmed')
                      AND other.start_time<@start+(m.end_time-m.start_time) AND other.end_time>@start)
            RETURNING id",
            ("org",NpgsqlDbType.Integer,org),("meeting",NpgsqlDbType.Integer,meeting),
            ("start",NpgsqlDbType.TimestampTz,start),("actor",NpgsqlDbType.Integer,actor));
        if (await insert.ExecuteScalarAsync(cancellation) is not int replacement)
            throw new InvalidOperationException("Choose a future time without an overlapping meeting for this owner and a valid duration.");
        using var branchLookup=Cmd(db,tx,@"SELECT branch_id FROM public.suite_branch_ownership
            WHERE company_id=@org AND resource_table='crm_meetings' AND resource_key=@meeting::text",
            ("org",NpgsqlDbType.Integer,org),("meeting",NpgsqlDbType.Integer,meeting));
        int? branch=await branchLookup.ExecuteScalarAsync(cancellation) as int? ?? settings.BranchId ?? leadBranch;
        if (branch.HasValue)
            await AddOwnership(db,tx,org,"crm_meetings",replacement,branch.Value,cancellation);
        using var followUp=Cmd(db,tx,@"UPDATE public.crm_leads SET next_follow_up_at=@start,updated_by_user_id=@actor,updated_at=now()
                WHERE organization_id=@org AND id=@lead",
            ("org",NpgsqlDbType.Integer,org),("lead",NpgsqlDbType.Integer,lead),
            ("start",NpgsqlDbType.TimestampTz,start),("actor",NpgsqlDbType.Integer,actor));
        await followUp.ExecuteNonQueryAsync(cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"crm_meetings",org,replacement,actor,"CREATE",cancellation,"Replacement Lead meeting");
        return replacement;
    }

    private static async Task LockMeetingOwnerAsync(NpgsqlConnection db,NpgsqlTransaction tx,int owner,CancellationToken cancellation)
    {
        using var ownerLock=Cmd(db,tx,"SELECT id FROM public.users WHERE id=@owner FOR UPDATE",
            ("owner",NpgsqlDbType.Integer,owner));
        if (await ownerLock.ExecuteScalarAsync(cancellation) is null)
            throw new InvalidOperationException("The meeting owner is unavailable.");
    }

    internal static async Task<int> BookLeadMeetingAsync(LeadKey key,string purpose,DateTime start,CancellationToken cancellation)
    {
        if (purpose is not ("consultation" or "demo"))
            throw new ArgumentException("Choose a consultation or product demo.");
        if (start.Kind!=DateTimeKind.Utc || start<=DateTime.UtcNow)
            throw new ArgumentException("Choose a future meeting time in UTC.");
        if (key.Potential)
            throw new InvalidOperationException("Choose an active Lead.");
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"leads","edit");
        var lead=await LockLead(db,tx,settings,key,false,cancellation);
        int owner=lead["owner_user_id"] as int? ?? actor.Id;
        await LockMeetingOwnerAsync(db,tx,owner,cancellation);
        string outcome=purpose=="demo"?"Product demonstration":"Requirements consultation";
        string title=(purpose=="demo"?"Product demo: ":"Consultation: ")+outcome;
        int org=settings.OrganizationId;
        using var insert=Cmd(db,tx,@"INSERT INTO public.crm_meetings (organization_id,owner_user_id,lead_id,title,description,
                  start_time,end_time,status,sync_status,created_by_user_id,updated_by_user_id)
              SELECT @org,@owner,@lead,@title,@description,@start,@end,'Scheduled','not_synced',@actor,@actor
              WHERE @start>clock_timestamp() AND NOT EXISTS (SELECT 1 FROM public.crm_meetings
                  WHERE organization_id=@org AND owner_user_id=@owner AND deleted_at IS NULL
                    AND status IN ('Scheduled','Confirmed') AND start_time<@end AND end_time>@start)
              RETURNING id",
            ("org",NpgsqlDbType.Integer,org),("owner",NpgsqlDbType.Integer,owner),("lead",NpgsqlDbType.Integer,key.Id),
            ("title",NpgsqlDbType.Text,title),("description",NpgsqlDbType.Text,"Sales meeting: "+purpose),
            ("start",NpgsqlDbType.TimestampTz,start),("end",NpgsqlDbType.TimestampTz,start.AddMinutes(30)),
            ("actor",NpgsqlDbType.Integer,actor.Id));
        if (await insert.ExecuteScalarAsync(cancellation) is not int meeting)
            throw new InvalidOperationException("Choose a future time without an overlapping meeting for this owner.");
        int? branch=settings.BranchId ?? lead["branch_id"] as int?;
        if (branch.HasValue)
            await AddOwnership(db,tx,org,"crm_meetings",meeting,branch.Value,cancellation);
        var now=DateTime.UtcNow;
        var details=ReadDetails(lead);
        details["lastActivityAt"]=now;
        await WriteState(db,tx,org,key.Id,details,key.StateRevision,cancellation);
        await AddLeadHistoryAsync(db,tx,org,key.Id,branch,actor.Id,"meeting_scheduled","Meeting scheduled",outcome,
            JsonSerializer.Serialize(new {startAt=start,meetingId=meeting}),cancellation);
        await RefreshLeadScoreAsync(db,tx,org,lead,actor.Id,now,cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"crm_meetings",org,meeting,actor.Id,"CREATE",cancellation,title);
        tx.Commit();
        return meeting;
    }
}
