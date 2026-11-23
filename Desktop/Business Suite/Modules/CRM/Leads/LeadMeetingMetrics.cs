using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadMeetingMetrics(bool SalesProcessEnabled,IReadOnlyList<LeadMeetingCount> Counts);
internal sealed record LeadMeetingCount(string Status,long Occurrences);

internal static partial class LeadStore
{
    internal static async Task<LeadMeetingMetrics> MeetingMetricsAsync(string search,string stage,int? owner,
        CancellationToken cancellation)
    {
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        await CrmDirectoryWrites.RequireCrmActorAsync(settings,db,tx,cancellation,"leads");
        using var process=Cmd(db,tx,@"SELECT EXISTS (SELECT 1 FROM public.crm_lead_management_config
            WHERE organization_id=@org AND settings_json->'salesProcess'->>'enabled'='true')",
            ("org",NpgsqlDbType.Integer,settings.OrganizationId));
        bool enabled=await process.ExecuteScalarAsync(cancellation) is true;
        using var query=Cmd(db,tx,@"WITH cohorts(status,position) AS (
                VALUES ('Scheduled',0),('Confirmed',1),('Attended',2),('No-show',3),('Rescheduled',4)
            ), counts AS (
                SELECT CASE WHEN m.status='Completed' THEN 'Attended' ELSE m.status END AS status,count(*) AS occurrences
                FROM public.crm_meetings m
                JOIN public.crm_leads l ON l.organization_id=m.organization_id AND l.id=m.lead_id
                LEFT JOIN public.crm_lead_operating_states s ON s.organization_id=l.organization_id AND s.lead_id=l.id
                WHERE m.organization_id=@org AND m.deleted_at IS NULL AND l.deleted_at IS NULL
                    AND COALESCE(s.data_json->>'archived','false')<>'true'
                    AND COALESCE(s.data_json->>'recordType','Lead')='Lead'
                    AND "+CrmDirectoryWrites.BranchScope("crm_leads","l",includeShares:true)+@"
                    AND "+MeetingReadScope+@"
                    AND (@stage='' OR l.status=@stage)
                    AND (@owner IS NULL OR l.owner_user_id=@owner OR (@owner=-1 AND l.owner_user_id IS NULL))
                    AND (@search='' OR strpos(lower(l.full_name),lower(@search))>0
                        OR strpos(lower(l.company_name),lower(@search))>0 OR strpos(lower(l.email),lower(@search))>0)
                GROUP BY 1
            ) SELECT cohorts.status,COALESCE(counts.occurrences,0) AS occurrences
            FROM cohorts LEFT JOIN counts USING (status) ORDER BY cohorts.position",
            ("org",NpgsqlDbType.Integer,settings.OrganizationId),("scope_branch",NpgsqlDbType.Integer,settings.BranchId),
            ("search",NpgsqlDbType.Text,search),("stage",NpgsqlDbType.Text,stage),("owner",NpgsqlDbType.Integer,owner));
        using var rows=await query.ExecuteReaderAsync(cancellation);
        var counts=new List<LeadMeetingCount>();
        while(await rows.ReadAsync(cancellation))
            counts.Add(new(rows.GetString(0),rows.GetInt64(1)));
        return new(enabled,counts);
    }
}
