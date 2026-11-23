using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record CrmDealPage(DataTable Rows, long Total, bool CanArchive, bool CanCapture);
internal sealed record CrmDealDetails(DataRow Overview, DataTable Stakeholders, DataTable History, DataTable Notes,
    bool CanEdit,bool CanEditStakeholders,bool CanReadNotes,bool CanAddNotes,bool CanReadTasks,bool CanWriteTasks,CrmDealHealth Health);

internal sealed partial class CrmDealRepository(DesktopDatabaseSettings settings)
{
    internal const int PageSize = 50;
    private const string DealPermission = "crm_deals_view";
    private const string ManageDeals = "crm_deals_manage";
    private const string AccountsPermission = "crm_accounts_view";
    private const string ManageAccounts = "crm_accounts_manage";
    private const string ContactsPermission = "crm_contacts_view";
    private const string ManageContacts = "crm_contacts_manage";

    internal async Task<CrmDealPage> ListAsync(string search, string status, bool archived, int page,
        CancellationToken cancellation, CrmDealFilters? filter = null) =>
        await QueryDealsAsync(search,status,archived,page,cancellation,filter ?? new(),null);

    private async Task<CrmDealPage> QueryDealsAsync(string search,string status,bool archived,int page,
        CancellationToken cancellation,CrmDealFilters filter,int[]? exportIds)
    {
        if (page < 0)
            throw new ArgumentException("Select a valid deal page.");
        filter.Validate();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, cancellation);
        await RequireDealsAsync(db, tx, actor, archived);
        if (exportIds is not null)
            await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"deals","export");
        var (from,criteria)=await FilteredDealDataAsync(db,tx,actor,search,status,archived,filter,exportIds ?? []);
        var filters=criteria.Concat(new (string,NpgsqlDbType,object?)[] {
            ("limit",NpgsqlDbType.Integer,exportIds is null?PageSize:ExportLimit),
            ("offset",NpgsqlDbType.Bigint,(long)page*PageSize)
        }).ToArray();
        using var count = Query(db,tx,"SELECT count(*)"+from,filters);
        long total = (long)(await count.ExecuteScalarAsync(cancellation))!;
        if (exportIds is not null)
        {
            if (total>ExportLimit)
                throw new InvalidOperationException($"Narrow the filters to export at most {ExportLimit:N0} deals.");
            if (exportIds.Distinct().Count()>total)
                throw new InvalidOperationException("Some selected deals are unavailable. Refresh and select again.");
        }
        using var query = Query(db,tx,@"SELECT d.id,d.xmin::text AS revision,d.name,c.name AS company,pi.name AS pipeline,st.name AS stage,
            d.amount,d.currency,d.probability,d.expected_close_date,d.status,d.priority,d.next_follow_up_at,
            d.owner_user_id,d.expected_revenue"+(exportIds is null?",d.created_at,"+DealHealthColumns:"") + from +
            " ORDER BY COALESCE(d.updated_at,d.created_at) DESC NULLS LAST,d.id DESC LIMIT @limit OFFSET @offset",filters);
        DataTable rows=await ReadAsync(query,cancellation);
        if (exportIds is null)
        {
            CrmDealHealth.AddColumns(rows,DateTime.UtcNow);
            return new(rows,total,await CanArchiveAsync(db,tx,actor),!archived && await CanCaptureAsync(db,tx,actor));
        }
        if (total>0)
        {
            var writer=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
            await AuditExportAsync(db,tx,writer.Id,total,archived,exportIds.Length>0,cancellation);
            tx.Commit();
        }
        return new(rows,total,false,false);
    }

    private async Task<(string From,(string Name,NpgsqlDbType Type,object? Value)[] Filters)> FilteredDealDataAsync(
        NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,string search,string status,bool archived,
        CrmDealFilters filter,int[] ids)
    {
        bool accountAccess = await CanViewAsync(db, tx, actor, AccountsPermission, ManageAccounts);
        bool contactAccess = await CanViewAsync(db, tx, actor, ContactsPermission, ManageContacts);
        string from = From(accountAccess, contactAccess) + @"
            WHERE d.organization_id=@org AND (d.deleted_at IS NOT NULL)=@archived AND " +
            CrmDirectoryWrites.BranchScope("crm_deals", "d") + @"
            AND (@status='' OR d.status=@status)
            AND (cardinality(@ids)=0 OR d.id=ANY(@ids))
            AND (@pipeline IS NULL OR d.pipeline_id=@pipeline)
            AND (@stage IS NULL OR d.stage_id=@stage)
            AND (@owner IS NULL OR d.owner_user_id=@owner)
            AND (@team IS NULL OR d.assigned_team_id=@team)
            AND (@currency IS NULL OR d.currency=@currency)
            AND (@priority IS NULL OR d.priority=@priority)
            AND (@type IS NULL OR d.deal_type=@type)
            AND (@industry IS NULL OR d.industry=@industry)
            AND (@source IS NULL OR d.source=@source OR d.lead_source=@source)
            AND (@loss IS NULL OR COALESCE(NULLIF(d.lost_reason,''),NULLIF(d.loss_reason,''),'No reason recorded')=@loss)
            AND (@from IS NULL OR d.expected_close_date>=@from)
            AND (@until IS NULL OR d.expected_close_date<=@until)
            AND (NOT @next OR (d.status='Open' AND d.next_follow_up_at IS NULL))
            AND (@entered IS NULL OR EXISTS (
                SELECT 1 FROM public.crm_timeline_events e WHERE e.organization_id=d.organization_id
                AND e.record_type='deal' AND e.record_id=d.id AND e.event_type='stage_change'
                AND e.metadata_json->>'new'=@entered::text))
            AND (@search='' OR strpos(lower(d.name),lower(@search))>0
                OR strpos(lower(d.description),lower(@search))>0
                OR strpos(lower(c.name),lower(@search))>0 OR strpos(lower(p.full_name),lower(@search))>0
                OR strpos(lower(p.email),lower(@search))>0)";
        (string, NpgsqlDbType, object?)[] filters = [
            ("search", NpgsqlDbType.Text, search), ("status", NpgsqlDbType.Text, status),
            ("archived",NpgsqlDbType.Boolean,archived),
            ("ids",NpgsqlDbType.Array|NpgsqlDbType.Integer,ids),
            ("pipeline",NpgsqlDbType.Integer,filter.Pipeline),("stage",NpgsqlDbType.Integer,filter.Stage),
            ("owner",NpgsqlDbType.Integer,filter.Owner),("team",NpgsqlDbType.Integer,filter.Team),
            ("currency",NpgsqlDbType.Text,filter.Currency),("priority",NpgsqlDbType.Text,filter.Priority),
            ("type",NpgsqlDbType.Text,filter.Type),("industry",NpgsqlDbType.Text,filter.Industry),
            ("source",NpgsqlDbType.Text,filter.Source),("loss",NpgsqlDbType.Text,filter.LostReason),
            ("entered",NpgsqlDbType.Integer,filter.EnteredStage),("from",NpgsqlDbType.Date,filter.From),
            ("until",NpgsqlDbType.Date,filter.Until),("next",NpgsqlDbType.Boolean,filter.NoNextAction)
        ];
        return (from,filters);
    }

    internal async Task<CrmDealDetails> DetailAsync(int id, bool archived, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, cancellation);
        await RequireDealsAsync(db, tx, actor, archived);
        bool accountAccess = await CanViewAsync(db, tx, actor, AccountsPermission, ManageAccounts);
        bool contactAccess = await CanViewAsync(db, tx, actor, ContactsPermission, ManageContacts);
        using var overview = Query(db,tx,@"SELECT d.id,d.name,c.name AS company,pi.name AS pipeline,st.name AS stage,
            d.amount,d.currency,d.expected_revenue,d.probability,d.expected_close_date,d.status,d.priority,
            d.next_follow_up_at,d.description,d.deal_type,d.source,d.created_at,d.updated_at,d.tags_text,
            p.full_name AS primary_contact,"+DealHealthColumns + From(accountAccess, contactAccess) + @"
            WHERE d.id=@id AND d.organization_id=@org AND (d.deleted_at IS NOT NULL)=@archived AND " +
            CrmDirectoryWrites.BranchScope("crm_deals", "d"),("id",NpgsqlDbType.Integer,id),
            ("archived",NpgsqlDbType.Boolean,archived));
        DataTable row = await ReadAsync(overview,cancellation);
        if (row.Rows.Count == 0)
            throw new InvalidOperationException("This deal changed or is outside the current branch. Refresh the deal list.");

        using var people = Query(db,tx,@"SELECT * FROM (
            SELECT p.full_name AS contact,link.role,link.influence_level,link.is_primary
            FROM public.crm_deal_contacts link JOIN public.crm_contacts p ON p.id=link.contact_id
                AND p.organization_id=@org AND p.deleted_at IS NULL AND " +
                CrmDirectoryWrites.BranchScope("crm_contacts","p",includeShares:true) + @"
            WHERE @allow AND link.organization_id=@org AND link.deal_id=@id
            UNION ALL
            SELECT p.full_name,'Primary',NULL::text,true
            FROM public.crm_deals d JOIN public.crm_contacts p ON p.id=d.contact_id
                AND p.organization_id=@org AND p.deleted_at IS NULL AND "+
                CrmDirectoryWrites.BranchScope("crm_contacts","p",includeShares:true)+@"
            WHERE @allow AND d.organization_id=@org AND d.id=@id
                AND NOT EXISTS (SELECT 1 FROM public.crm_deal_contacts l WHERE l.deal_id=d.id)
            ) contacts ORDER BY is_primary DESC NULLS LAST,contact",
            ("id",NpgsqlDbType.Integer,id),("allow",NpgsqlDbType.Boolean,contactAccess));
        bool readNotes=await CanReadNotesAsync(db,tx,actor);
        bool readTasks=await CanReadTasksAsync(db,tx,actor);
        string callTitle=readTasks?@"CASE WHEN c.id IS NOT NULL THEN c.direction||' call logged'
            WHEN m.id IS NOT NULL AND e.event_type='meeting' THEN m.title ELSE e.title END":"e.title";
        string callBody=readTasks?@"CASE WHEN c.id IS NOT NULL THEN COALESCE(NULLIF(c.notes,''),c.outcome,'')
            WHEN m.id IS NOT NULL AND e.event_type='meeting' THEN COALESCE(NULLIF(m.description,''),m.outcome,'')
            ELSE COALESCE(n.body,e.description) END"
            :"COALESCE(n.body,e.description)";
        string callJoin=readTasks?@"LEFT JOIN public.crm_call_logs c ON c.organization_id=@org AND c.deal_id=@id
            AND c.id::text=e.metadata_json->>'sourceId' AND c.deleted_at IS NULL AND "+CallBranchScope+@"
            AND lower(e.metadata_json->>'sourceEntity')='calls'
            LEFT JOIN public.crm_meetings m ON m.organization_id=@org AND m.deal_id=@id
                AND m.id::text=e.metadata_json->>'sourceId' AND m.deleted_at IS NULL AND "+MeetingBranchScope+@"
                AND lower(e.metadata_json->>'sourceEntity')='meetings'":"";
        string callVisibility=readTasks?@"AND (COALESCE(lower(e.metadata_json->>'sourceEntity'),'')<>'calls' OR c.id IS NOT NULL)
            AND (COALESCE(lower(e.metadata_json->>'sourceEntity'),'')<>'meetings' OR m.id IS NOT NULL)":"";
        using var history = Query(db,tx,@"SELECT * FROM (
            SELECT e.occurred_at AS occurred,"+callTitle+" AS title,"+callBody+@" AS description
            FROM public.crm_timeline_events e
            LEFT JOIN public.crm_notes n ON @read_notes AND n.organization_id=@org AND n.deal_id=@id
                AND n.id::text=e.metadata_json->>'sourceId' AND n.deleted_at IS NULL AND "+NoteBranchScope+@"
                AND (lower(e.event_type) IN ('note','notes') OR lower(e.metadata_json->>'sourceEntity') IN ('note','notes'))
            "+callJoin+@"
                WHERE e.organization_id=@org AND e.record_type='deal' AND e.record_id=@id
                AND ((lower(e.event_type) NOT IN ('note','notes')
                    AND COALESCE(lower(e.metadata_json->>'sourceEntity'),'') NOT IN ('note','notes'))
                    OR n.id IS NOT NULL)
                AND (@read_tasks OR (lower(e.event_type) NOT IN ('task','call','meeting') AND
                    COALESCE(lower(e.metadata_json->>'sourceEntity'),'') NOT IN ('tasks','calls','meetings')))
                "+callVisibility+@"
            UNION ALL
            SELECT cl.converted_at,'Lead converted',cl.notes FROM public.crm_lead_conversion_logs cl
                WHERE cl.organization_id=@org AND cl.converted_deal_id=@id
            ) events ORDER BY occurred DESC NULLS LAST LIMIT 100",("id",NpgsqlDbType.Integer,id),
            ("read_notes",NpgsqlDbType.Boolean,readNotes),("read_tasks",NpgsqlDbType.Boolean,readTasks));
        bool writable=!archived && actor.CanWriteBranch && actor.IsSuperuser;
        return new(row.Rows[0],await ReadAsync(people,cancellation),await ReadAsync(history,cancellation),
            await ReadDealNotesAsync(db,tx,id,readNotes,cancellation),writable && row.Rows[0]["status"] is "Open",
            writable && contactAccess,readNotes,writable && readNotes && settings.BranchId.HasValue,
            !archived && readTasks,writable && readTasks && settings.BranchId.HasValue,
            CrmDealHealth.Evaluate(row.Rows[0],DateTime.UtcNow));
    }

    private static string From(bool accountAccess, bool contactAccess) => @" FROM public.crm_deals d
        LEFT JOIN public.crm_pipelines pi ON pi.id=d.pipeline_id AND pi.organization_id=@org
        LEFT JOIN public.crm_pipeline_stages st ON st.id=d.stage_id AND st.pipeline_id=pi.id
            AND (st.organization_id IS NULL OR st.organization_id=@org)
        LEFT JOIN public.crm_companies c ON " + (accountAccess ? "TRUE" : "FALSE") + @" AND c.id=d.company_id
            AND c.organization_id=@org AND c.deleted_at IS NULL AND " +
            CrmDirectoryWrites.BranchScope("crm_companies","c",includeShares:true) + @"
        LEFT JOIN public.crm_contacts p ON " + (contactAccess ? "TRUE" : "FALSE") + @" AND p.id=d.contact_id
            AND p.organization_id=@org AND p.deleted_at IS NULL AND " +
            CrmDirectoryWrites.BranchScope("crm_contacts","p",includeShares:true);

    private const string DealHealthColumns=@"d.last_activity_at,st.policy_json->>'stagnation_days' AS stagnation_days,
        (SELECT max(entry.occurred_at) FROM public.crm_timeline_events entry WHERE entry.organization_id=@org
            AND entry.record_type='deal' AND entry.record_id=d.id AND entry.event_type='stage_change') AS stage_entered_at";

    private async Task RequireDealsAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,bool archived)
    {
        string[] permissions = archived ? ["crm_manage","crm_admin",ManageDeals]
            : ["crm_view","crm_manage","crm_admin",DealPermission,ManageDeals];
        await RequireVisibilityAsync(db,tx,actor,permissions);
    }

    private async Task<bool> CanViewAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,string view,string manage)
    {
        try
        {
            await RequireVisibilityAsync(db,tx,actor,["crm_view","crm_manage","crm_admin",view,manage]);
            return true;
        }
        catch (UnauthorizedAccessException) { return false; }
    }

    private async Task RequireVisibilityAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,string[] permissions)
    {
        var grant = await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,settings.BranchId ?? 0,
            actor,"crm","view",permissions);
        if (grant.Scope is not ("organization" or "branch") || (grant.Scope=="branch" && !settings.BranchId.HasValue)
            || (grant.IsLegacy && !actor.IsSuperuser && !actor.IsCompanyAdmin))
            throw new UnauthorizedAccessException("The desktop Deal directory requires branch-wide or organization-wide CRM access.");
    }

    private NpgsqlCommand Query(NpgsqlConnection db,NpgsqlTransaction tx,string sql,
        params (string Name,NpgsqlDbType Type,object? Value)[] values)
    {
        var query = new NpgsqlCommand(sql,db,tx);
        query.Parameters.AddWithValue("org",NpgsqlDbType.Integer,settings.OrganizationId);
        query.Parameters.Add("scope_branch",NpgsqlDbType.Integer).Value=(object?)settings.BranchId??DBNull.Value;
        foreach (var value in values)
            query.Parameters.Add(value.Name,value.Type).Value=value.Value??DBNull.Value;
        return query;
    }

    private static async Task<DataTable> ReadAsync(NpgsqlCommand query,CancellationToken cancellation)
    {
        using var reader=await query.ExecuteReaderAsync(cancellation);
        var rows=new DataTable();
        rows.Load(reader);
        return rows;
    }
}

