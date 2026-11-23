using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class CrmDealRepository
{
    internal Task<DealTaskSave> AddDealCallFollowUpAsync(int deal,int call,string title,DateTime due,CancellationToken cancellation)=>
        AddDealEngagementFollowUpAsync(deal,call,title,due,cancellation,false);

    internal Task<DealTaskSave> AddDealMeetingFollowUpAsync(int deal,int meeting,string title,DateTime due,CancellationToken cancellation)=>
        AddDealEngagementFollowUpAsync(deal,meeting,title,due,cancellation,true);

    private async Task<DealTaskSave> AddDealEngagementFollowUpAsync(int deal,int engagement,string title,DateTime due,
        CancellationToken cancellation,bool meeting)
    {
        var draft=ValidateTaskDraft(new(title,"","Medium",due,null));
        using var db=new Npgsql.NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireDealActivityAccessAsync(db,tx,actor,"view");
        await RequireDealActivityAccessAsync(db,tx,actor,"create");
        var parent=await LockableDealAsync(db,tx,deal,true,cancellation,requireOpen:false);
        string singular=meeting?"meeting":"call";
        string entity=singular+"s";
        string sql=meeting?@"SELECT m.lead_id,m.contact_id,m.company_id,COALESCE(NULLIF(m.title,''),m.outcome) AS context
            FROM public.crm_meetings m WHERE m.organization_id=@org AND m.deal_id=@deal AND m.id=@source AND m.deleted_at IS NULL
            AND "+MeetingBranchScope+" FOR SHARE OF m":@"SELECT c.lead_id,c.contact_id,c.company_id,c.outcome AS context
            FROM public.crm_call_logs c WHERE c.organization_id=@org AND c.deal_id=@deal AND c.id=@source AND c.deleted_at IS NULL
            AND "+CallBranchScope+" FOR SHARE OF c";
        using var lookup=Query(db,tx,sql,("deal",NpgsqlDbType.Integer,deal),("source",NpgsqlDbType.Integer,engagement));
        var rows=await ReadAsync(lookup,cancellation);
        if (rows.Rows.Count!=1)
            throw new InvalidOperationException($"The {singular} is unavailable for this deal in the current branch.");
        var row=rows.Rows[0];
        int? lead=row["lead_id"] as int?,contact=row["contact_id"] as int?,company=row["company_id"] as int?;
        await CheckLinkedAsync(lead,"crm_leads","leads");
        await CheckLinkedAsync(contact,"crm_contacts","contacts");
        await CheckLinkedAsync(company,"crm_companies","accounts");
        // PostgreSQL and the existing web idempotency key both use microsecond precision.
        due=new DateTime(due.Ticks-due.Ticks%10,DateTimeKind.Utc);
        string timestamp=due.ToString(due.Ticks%TimeSpan.TicksPerSecond==0?"yyyy-MM-dd'T'HH:mm:ss":"yyyy-MM-dd'T'HH:mm:ss.ffffff",
            CultureInfo.InvariantCulture)+"+00:00";
        string source=engagement.ToString(CultureInfo.InvariantCulture);
        using var hash=SHA256.Create();
        string idempotency="engagement:"+BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes($"{entity}:{source}:{draft.Title}:{timestamp}")))
            .Replace("-","").ToLowerInvariant();
        string details=JsonSerializer.Serialize(new {workType="Follow-up",relatedRecord=$"{entity} #{source}",sourceEntity=entity,sourceId=engagement});
        string context=row["context"] is string value&&value.Length>0?value:"Customer conversation";
        var result=await InsertDealTaskAsync(db,tx,actor,parent,draft with {Due=due,Description=$"Follow-up from {singular} #{source}: {context}"},
            new(idempotency,details,lead,contact,company),cancellation);
        tx.Commit();
        return result;

        async Task CheckLinkedAsync(int? id,string table,string entity)
        {
            if (!id.HasValue)
                return;
            await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,entity,"view");
            using var command=Query(db,tx,$@"SELECT r.id FROM public.{table} r WHERE r.organization_id=@org AND r.id=@id
                AND r.deleted_at IS NULL AND "+CrmDirectoryWrites.BranchScope(table,"r",includeShares:true)+" FOR SHARE OF r",
                ("id",NpgsqlDbType.Integer,id));
            if (await command.ExecuteScalarAsync(cancellation) is null)
                throw new InvalidOperationException($"A record linked to the {singular} is archived or outside the current scope.");
        }
    }
}
