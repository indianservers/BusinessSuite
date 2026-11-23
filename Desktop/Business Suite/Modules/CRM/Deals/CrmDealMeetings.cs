using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record DealMeetingDraft(string Title,string Description,string Location,DateTime Start,DateTime End,
    string Status="Scheduled",string Outcome="");

internal sealed partial class CrmDealRepository
{
    private const string MeetingBranchScope=@"(@scope_branch IS NULL OR NOT EXISTS (
        SELECT 1 FROM public.suite_branch_ownership o WHERE o.company_id=@org AND o.resource_table='crm_meetings'
          AND o.resource_key=m.id::text AND o.branch_id<>@scope_branch))";

    internal async Task<DataTable> DealMeetingsAsync(int deal,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        await RequireDealActivityAccessAsync(db,tx,actor,"view");
        await LockableDealAsync(db,tx,deal,false,cancellation,requireOpen:false);
        using var query=Query(db,tx,@"SELECT m.id,m.xmin::text AS revision,m.title,m.location,m.status,m.sync_status,m.description,m.outcome,
            (NULLIF(m.external_provider,'') IS NOT NULL OR NULLIF(m.external_event_id,'') IS NOT NULL) AS external_calendar,
            m.start_time AT TIME ZONE 'UTC' AS starts,m.end_time AT TIME ZONE 'UTC' AS ends
            FROM public.crm_meetings m WHERE m.organization_id=@org AND m.deal_id=@deal AND m.deleted_at IS NULL
            AND "+MeetingBranchScope+@"
            ORDER BY m.start_time DESC,m.id DESC LIMIT 200",("deal",NpgsqlDbType.Integer,deal));
        return await ReadAsync(query,cancellation);
    }

    internal async Task<int> AddDealMeetingAsync(int deal,DealMeetingDraft draft,CancellationToken cancellation)
    {
        draft=ValidateMeetingDraft(draft);
        if (draft.Status!="Scheduled" || draft.Outcome.Length>0)
            throw new ArgumentException("Create the scheduled meeting before recording an outcome.");
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireDealActivityAccessAsync(db,tx,actor,"create");
        var parent=await LockableDealAsync(db,tx,deal,true,cancellation,requireOpen:false);
        int branch=parent["owning_branch"] as int? ?? throw new InvalidOperationException("The deal must belong to the writable branch.");
        using var command=Query(db,tx,@"INSERT INTO public.crm_meetings (organization_id,owner_user_id,title,description,location,
            start_time,end_time,status,sync_status,deal_id,created_by_user_id,updated_by_user_id)
            VALUES (@org,@actor,@title,NULLIF(@description,''),NULLIF(@location,''),@start,@end,'Scheduled','not_synced',
                @deal,@actor,@actor) RETURNING id",
            ("deal",NpgsqlDbType.Integer,deal),("actor",NpgsqlDbType.Integer,actor.Id),("title",NpgsqlDbType.Text,draft.Title),
            ("description",NpgsqlDbType.Text,draft.Description),("location",NpgsqlDbType.Text,draft.Location),
            ("start",NpgsqlDbType.TimestampTz,draft.Start),("end",NpgsqlDbType.TimestampTz,draft.End));
        int id=(int)(await command.ExecuteScalarAsync(cancellation))!;
        await WriteRecordedEngagementAsync(db,tx,actor,branch,deal,id,"meetings","meeting","crm_meetings",draft.Title,
            draft.Description,cancellation);
        tx.Commit();
        return id;
    }

    private static DealMeetingDraft ValidateMeetingDraft(DealMeetingDraft draft)
    {
        draft=draft with {Title=draft.Title.Trim(),Description=draft.Description.Trim(),Location=draft.Location.Trim(),Outcome=draft.Outcome.Trim()};
        if (draft.Title.Length is <1 or >180 || draft.Location.Length>240 || draft.Description.Length>10000 || draft.Outcome.Length>10000
            || draft.Status is not ("Scheduled" or "Completed" or "Cancelled"))
            throw new ArgumentException("Enter a title up to 180 characters, a valid status and values within the field limits.");
        if (draft.Start.Kind!=DateTimeKind.Utc || draft.End.Kind!=DateTimeKind.Utc || draft.End<=draft.Start)
            throw new ArgumentException("The meeting end must be after its start.");
        return draft;
    }
}
