using System.Data;
using System.Globalization;
using System.Net.Mail;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadStage(string Name, string[] AllowedNext, string[] Required);
internal sealed record LeadPolicy(LeadStage[] Stages,bool PreventDuplicates,bool SalesProcess,int? PipelineId,int SlaHours,int StaleDays);
internal sealed record LeadPage(DataTable Records, long Total);
internal sealed record LeadKey(int Id, string Revision, string StateRevision, bool Potential = false);

internal static partial class LeadStore
{
    internal const int PageSize = 50;
    internal static readonly string[] Ratings = ["Cold", "Warm", "Hot"];

    private static readonly string[] TextFields =
    [
        "first_name", "last_name", "full_name", "company_name", "job_title", "email", "phone",
        "phone_country_code", "alternate_phone", "alternate_phone_country_code", "website",
        "company_website", "linkedin_url", "source", "status", "rating", "industry",
        "city", "state", "country", "address", "tags_text", "notes"
    ];

    internal static async Task<LeadPolicy> PolicyAsync(CancellationToken cancellation)
    {
        var settings = DesktopDatabaseSettings.Load();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await CrmDirectoryWrites.RequireCrmActorAsync(settings, db, tx, cancellation, "leads");
        return await ReadPolicy(db, tx, settings.OrganizationId, cancellation);
    }

    private static async Task<LeadPolicy> ReadPolicy(NpgsqlConnection db, NpgsqlTransaction? tx,
        int org, CancellationToken cancellation)
    {
        using var command = Cmd(db, tx, "SELECT settings_json::text FROM public.crm_lead_management_config WHERE organization_id=@org",
            ("org", NpgsqlDbType.Integer, org));
        string json = await command.ExecuteScalarAsync(cancellation) as string ?? "{}";
        using var parsed = JsonDocument.Parse(json);
        var value = parsed.RootElement;
        LeadStage[] stages =
        [
            new("New", ["Contacted", "Qualified", "Lost"], []),
            new("Contacted", ["Qualified", "Lost"], []),
            new("Qualified", ["Lost"], []),
            new("Converted", [], []),
            new("Lost", ["New"], ["lossReason"])
        ];
        if (value.TryGetProperty("stages", out var configured) && configured.ValueKind == JsonValueKind.Array &&
            configured.GetArrayLength() > 0)
            stages = JsonSerializer.Deserialize<LeadStage[]>(configured.GetRawText(), CrmExtrasStore.Json)!;
        bool prevent = !value.TryGetProperty("preventDuplicates", out var guard) || guard.ValueKind != JsonValueKind.False;
        bool sales = value.TryGetProperty("salesProcess", out var process) && process.ValueKind == JsonValueKind.Object
            && process.TryGetProperty("enabled", out var enabled) && enabled.ValueKind == JsonValueKind.True;
        int? pipeline = sales && process.TryGetProperty("pipelineId", out var id) && id.TryGetInt32(out var number) ? number : null;
        int sla=WorkflowInteger(value,"slaHours") is int hours && hours is >=1 and <=8760?hours:24;
        int inactive=WorkflowInteger(value,"staleDays") is int days && days is >=1 and <=365?days:7;
        return new(stages,prevent,sales,pipeline,sla,inactive);
    }

    internal static Task<LeadPage> ListAsync(string search, string stage, string source, string rating,
        bool archived, int page, CancellationToken cancellation, int? owner = null, bool potential = false) =>
        QueryLeadsAsync(search,stage,source,rating,archived,page,cancellation,owner,potential,false,[]);

    internal const int ExportLimit=5000;

    internal static async Task<DataTable> ExportRowsAsync(string search,string stage,string source,string rating,
        int? owner,bool potential,int[] selected,CancellationToken cancellation)
    {
        if (selected.Length>200 || selected.Any(id=>id<=0))
            throw new ArgumentException("Choose up to 200 valid lead records.");
        var result=await QueryLeadsAsync(search,stage,source,rating,null,0,cancellation,owner,potential,true,selected);
        if (selected.Distinct().Count()>result.Records.Rows.Count)
            throw new InvalidOperationException("Some selected records are outside your current access. Refresh the list and select again.");
        return result.Records;
    }

    private static async Task<LeadPage> QueryLeadsAsync(string search,string stage,string source,string rating,
        bool? archived,int page,CancellationToken cancellation,int? owner,bool potential,bool exporting,int[] selected)
    {
        var settings = DesktopDatabaseSettings.Load();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using(var readOnly=Cmd(db,tx,"SET TRANSACTION READ ONLY"))
            await readOnly.ExecuteNonQueryAsync(cancellation);
        var actor=await CrmDirectoryWrites.RequireCrmActorAsync(settings, db, tx, cancellation, "leads");
        if (exporting)
            await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"leads","export");
        string from = @" FROM public.crm_leads l
            LEFT JOIN public.crm_lead_operating_states s ON s.organization_id=l.organization_id AND s.lead_id=l.id
            WHERE l.organization_id=@org AND " + CrmDirectoryWrites.BranchScope("crm_leads", "l", includeShares: true) + @" AND
              (@archived IS NULL OR (l.deleted_at IS NOT NULL OR COALESCE(s.data_json->>'archived','false')='true')=@archived)
              AND (COALESCE(s.data_json->>'recordType','Lead') = 'Potential') = @potential
              AND (cardinality(@selected)=0 OR l.id=ANY(@selected))
              AND (@stage='' OR l.status=@stage) AND (@source='' OR lower(l.source)=lower(@source))
              AND (@rating='' OR l.rating=@rating)
              AND (@owner IS NULL OR l.owner_user_id=@owner OR (@owner=-1 AND l.owner_user_id IS NULL))
              AND (@search='' OR strpos(lower(l.full_name),lower(@search))>0
                OR strpos(lower(COALESCE(l.company_name,'')),lower(@search))>0
                OR strpos(lower(COALESCE(l.email,'')),lower(@search))>0
                OR strpos(COALESCE(l.phone_country_code,'') || COALESCE(l.phone,''), @search)>0)";
        var values = new (string, NpgsqlDbType, object?)[]
        {
            ("org",NpgsqlDbType.Integer,settings.OrganizationId), ("scope_branch",NpgsqlDbType.Integer,settings.BranchId), ("archived",NpgsqlDbType.Boolean,archived),
            ("potential",NpgsqlDbType.Boolean,potential), ("search",NpgsqlDbType.Text,search), ("stage",NpgsqlDbType.Text,stage),
            ("source",NpgsqlDbType.Text,source), ("rating",NpgsqlDbType.Text,rating), ("owner",NpgsqlDbType.Integer,owner),
            ("selected",NpgsqlDbType.Array|NpgsqlDbType.Integer,selected)
        };
        using var count = Cmd(db, tx, "SELECT count(*)" + from, values);
        long total = (long)(await count.ExecuteScalarAsync(cancellation))!;
        if (exporting && total>ExportLimit)
            throw new InvalidOperationException($"Narrow the filters to export at most {ExportLimit:N0} records.");
        string order=exporting?" ORDER BY l.id":" ORDER BY l.created_at DESC NULLS LAST,l.id DESC";
        using var query = Cmd(db, tx, @"SELECT l.*, l.xmin::text AS revision, COALESCE(s.xmin::text,'') AS state_revision,
            COALESCE(s.data_json::text,'{}') AS operating_state,
            CASE WHEN trim(l.phone) LIKE '+%' OR l.phone_country_code IS NULL THEN l.phone
                 ELSE l.phone_country_code || ' ' || l.phone END AS phone_display" + from +
            order+" LIMIT @limit OFFSET @offset",
            values.Concat(new (string,NpgsqlDbType,object?)[] {("limit",NpgsqlDbType.Integer,exporting?ExportLimit:PageSize),
                ("offset",NpgsqlDbType.Bigint,(long)page*PageSize)}).ToArray());
        using var reader = await query.ExecuteReaderAsync(cancellation);
        return new(await Table(reader,cancellation),total);
    }

    internal static async Task<List<CrmLookup>> OwnersAsync(CancellationToken cancellation)
    {
        var settings = DesktopDatabaseSettings.Load();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await CrmDirectoryWrites.RequireCrmActorAsync(settings, db, tx, cancellation, "leads");
        using var query = Cmd(db, tx, @"SELECT DISTINCT u.id, u.email FROM public.users u
            JOIN public.crm_leads l ON l.owner_user_id=u.id WHERE l.organization_id=@org AND " +
            CrmDirectoryWrites.BranchScope("crm_leads", "l", includeShares: true) + " ORDER BY u.email,u.id",
            ("org", NpgsqlDbType.Integer, settings.OrganizationId), ("scope_branch", NpgsqlDbType.Integer, settings.BranchId));
        using var reader = await query.ExecuteReaderAsync(cancellation);
        var options = new List<CrmLookup> { new(null,"All owners"), new(-1,"Unassigned") };
        while (await reader.ReadAsync(cancellation))
            options.Add(new(reader.GetInt32(0), reader.GetString(1)));
        return options;
    }

    internal static async Task SaveAsync(LeadKey? key, Dictionary<string,string> draft, int? branch,
        CancellationToken cancellation, bool potential = false, int? captureOwner = null)
    {
        if (captureOwner.HasValue && (key is not null || potential || captureOwner.Value<=0))
            throw new ArgumentException("Choose an eligible owner when capturing a new Lead.");
        var values = TextFields.ToDictionary(name => name, name => Read(draft,name));
        if (values["first_name"].Length == 0)
            throw new ArgumentException("Enter the lead's first name.");
        values["full_name"] = (values["first_name"] + " " + values["last_name"]).Trim();
        if (!Ratings.Contains(values["rating"]))
            throw new ArgumentException("Choose Cold, Warm or Hot.");
        if (values["email"].Length > 0)
        {
            try
            {
                if (!new MailAddress(values["email"]).Address.Equals(values["email"], StringComparison.OrdinalIgnoreCase))
                    throw new FormatException();
            }
            catch (FormatException) { throw new ArgumentException("Enter a valid email address."); }
        }

        foreach (string field in new[] { "phone", "alternate_phone" })
        {
            string code = field + "_country_code";
            if (values[field].Length == 0)
            {
                values[code] = "";
                continue;
            }
            values[field] = CrmPhone.Normalize(values[field],values[code]).National;
        }
        foreach (string field in new[] { "website", "company_website", "linkedin_url" })
        {
            string website = values[field];
            if (website.Length == 0)
                continue;
            if (!website.Contains("://"))
                website = "https://" + website;
            if (!Uri.TryCreate(website, UriKind.Absolute, out Uri? uri) || uri.Scheme is not ("http" or "https")
                || uri.UserInfo.Length != 0 || !uri.Host.Contains(".") || website.Any(char.IsWhiteSpace)
                || website.Length > (field == "linkedin_url" ? 300 : 200))
                throw new ArgumentException("Enter a valid HTTP or HTTPS URL in " + field.Replace('_', ' ') + ".");
            values[field] = website;
        }

        decimal? amount = null;
        string amountText = Read(draft,"estimated_value");
        if (amountText.Length != 0)
        {
            if (!decimal.TryParse(amountText,NumberStyles.Number,CultureInfo.InvariantCulture,out decimal parsedAmount)
                || parsedAmount < 0 || parsedAmount >= 10000000000m)
                throw new ArgumentException("Enter a nonnegative estimated value with up to ten whole digits.");
            amount = parsedAmount;
        }
        DateTime? close = DateValue(Read(draft,"expected_close_date"), "Expected close date");
        string followUpText = Read(draft, "next_follow_up_at");
        DateTime? followup = null;
        if (followUpText.Length > 0)
        {
            if (!DateTime.TryParseExact(followUpText, new[] { "yyyy-MM-dd HH:mm", "yyyy-MM-dd" },
                    CultureInfo.InvariantCulture, DateTimeStyles.AssumeLocal, out DateTime parsedFollowUp))
                throw new ArgumentException("Next follow-up must use YYYY-MM-DD HH:mm.");
            followup = parsedFollowUp.ToUniversalTime();
        }

        var settings = DesktopDatabaseSettings.Load();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.Serializable);
        var actor = await settings.VerifyWriteTargetAsync(db, tx, cancellation);
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings, db, tx, actor, "leads", key is null ? "create" : "edit");
        DataRow? current = key is null ? null : await LockLead(db,tx,settings,key,false,cancellation);
        var policy = await ReadPolicy(db,tx,settings.OrganizationId,cancellation);
        var details = ReadDetails(current);
        if (current is null && potential)
            details["recordType"] = "Potential";
        details["qualification"] = new Dictionary<string,string> {
            ["need"]=Read(draft,"need"), ["budget"]=Read(draft,"budget"),
            ["decisionMaker"]=Read(draft,"decisionMaker"), ["timeline"]=Read(draft,"timeline")
        };
        details["lossReason"] = Read(draft,"lossReason");
        if (draft.ContainsKey("competitor"))
        {
            string competitor=Read(draft,"competitor");
            if (competitor.Length>200)
                throw new ArgumentException("Enter a competitor of up to 200 characters.");
            details["competitor"]=competitor;
        }
        string status=values["status"];
        var requiredValues=new Dictionary<string,string>(values) {
            ["next_follow_up_at"]=followUpText,["estimated_value"]=amountText
        };
        ValidateTransition(policy,current,status,requiredValues,details,false);
        string? previousStage=current is null?null:Text(current,"status");
        string? trigger=current is null?"created":previousStage!=status?"stage_changed":null;

        if (policy.PreventDuplicates && (current is null || !string.Equals(Text(current,"email"), values["email"],StringComparison.OrdinalIgnoreCase)
                || Text(current,"phone") != values["phone"] || Text(current,"phone_country_code") != values["phone_country_code"]))
        {
            using var duplicate = Cmd(db,tx,@"SELECT id FROM public.crm_leads WHERE organization_id=@org
                AND deleted_at IS NULL AND id IS DISTINCT FROM @id AND (
                  (@email <> '' AND lower(trim(email))=lower(@email)) OR
                  (@phone <> '' AND (
                    (phone_country_code=@code OR phone_country_code IS NULL)
                       AND regexp_replace(phone,'[ ().-]','','g')=@phone
                    OR regexp_replace(phone,'[ ().-]','','g')=@code || @phone)))
                ORDER BY id LIMIT 1",
                ("org",NpgsqlDbType.Integer,settings.OrganizationId),("id",NpgsqlDbType.Integer,key?.Id),
                ("email",NpgsqlDbType.Text,values["email"]),("phone",NpgsqlDbType.Text,values["phone"]),
                ("code",NpgsqlDbType.Text,values["phone_country_code"]));
            if (await duplicate.ExecuteScalarAsync(cancellation) is int)
                throw new InvalidOperationException("A lead with the same email or phone already exists.");
        }

        int? newBranch = key is null ? await CrmDirectoryWrites.CreationBranch(db,tx,settings,branch,cancellation) : null;
        string? assignedOwnerName=captureOwner.HasValue && newBranch is int chosenBranch
            ?await ValidateLeadCaptureOwnerAsync(db,tx,settings,actor,chosenBranch,captureOwner.Value,cancellation):null;
        var salesAssignment=captureOwner is null && key is null && !potential && newBranch is int routeBranch
            ?await AssignNewLeadAsync(db,tx,settings,routeBranch,values,cancellation):(Owner:(int?)null,Deferred:false);
        string[] writeFields = TextFields.Concat(new[] { "estimated_value","expected_close_date","next_follow_up_at" }).ToArray();
        string sql = key is null
            ? "INSERT INTO public.crm_leads (organization_id,branch_id,owner_user_id,is_converted,lead_score,lead_score_label,lead_score_mode,updated_at,created_by_user_id,updated_by_user_id," +
              string.Join(",",writeFields) + ") VALUES (@org,@branch,@sales_owner,false,0,'Cold','automatic',now(),@actor,@actor," +
              string.Join(",",writeFields.Select(name=>"@"+name)) + ") RETURNING *"
            : "UPDATE public.crm_leads SET updated_at=now(),updated_by_user_id=@actor," + string.Join(",",writeFields.Select(name=>$"{name}=@{name}"))+
              " WHERE organization_id=@org AND id=@id RETURNING *";
        using var write = Cmd(db,tx,sql,("org",NpgsqlDbType.Integer,settings.OrganizationId),("id",NpgsqlDbType.Integer,key?.Id),
            ("actor",NpgsqlDbType.Integer,actor.Id),
            ("branch",NpgsqlDbType.Integer,newBranch),("sales_owner",NpgsqlDbType.Integer,captureOwner ?? salesAssignment.Owner),("estimated_value",NpgsqlDbType.Numeric,amount),
            ("expected_close_date",NpgsqlDbType.Date,close),("next_follow_up_at",NpgsqlDbType.TimestampTz,followup));
        foreach (var field in values)
            CrmExtrasStore.Param(write,field.Key,NpgsqlDbType.Text,field.Value.Length==0 ? null : field.Value);
        DataRow saved;
        using(var reader=await write.ExecuteReaderAsync(cancellation))
            saved=(await Table(reader,cancellation)).Rows[0];
        int id=(int)saved["id"];
        if (newBranch is int branchId)
            await AddOwnership(db,tx,settings.OrganizationId,"crm_leads",id,branchId,cancellation);
        if (trigger is not null)
        {
            int org=settings.OrganizationId;
            int? owningBranch=newBranch??settings.BranchId??saved["branch_id"] as int?;
            var workflowScope=settings.ForScope(org,owningBranch);
            DateTime now=DateTime.UtcNow;
            if (current is null)
            {
                bool enquiry=values["source"] is "Website" or "Email" or "WhatsApp" or "Webform";
                details["enquiryInbox"]=details["enquiryPending"]=enquiry;
                await AddLeadHistoryAsync(db,tx,org,id,owningBranch,actor.Id,"created","Lead captured",null,
                    JsonSerializer.Serialize(new {status}),cancellation);
                if (salesAssignment.Deferred)
                    await AddLeadHistoryAsync(db,tx,org,id,owningBranch,actor.Id,"assignment_deferred",
                        "Awaiting an available salesperson",null,"{}",cancellation);
            }
            else
            {
                details.TryGetValue("stageEnteredAt",out var stamp);
                DateTime entered=DateTimeOffset.TryParse(Convert.ToString(stamp,CultureInfo.InvariantCulture),
                    CultureInfo.InvariantCulture,DateTimeStyles.AssumeUniversal,out var previousTime)
                    ?previousTime.UtcDateTime:current["created_at"] as DateTime? ?? now;
                double durationHours=Math.Round((now-entered).TotalHours,2);
                await AddLeadHistoryAsync(db,tx,org,id,owningBranch,actor.Id,"stage_changed",$"{previousStage} → {status}",null,
                    JsonSerializer.Serialize(new {from=previousStage,to=status,durationHours}),cancellation);
                if (status=="Lost")
                    await CancelActiveSequenceAsync(db,tx,workflowScope,id,details,actor.Id,now,"Lost",cancellation);
            }
            details["stageEnteredAt"]=now;
            await ApplyLeadWorkflowsAsync(db,tx,workflowScope,id,saved,actor,trigger,now,cancellation);
            if (captureOwner is int requested && (saved["owner_user_id"] as int?)==requested)
            {
                await AddLeadHistoryAsync(db,tx,org,id,owningBranch,actor.Id,"assignment",$"Assigned to {assignedOwnerName}",null,
                    JsonSerializer.Serialize(new {ownerId=requested,reason="Manual assignment"}),cancellation);
                if (owningBranch is int alertBranch && requested!=actor.Id)
                    await NotifyLeadOwnerAsync(db,tx,org,alertBranch,id,saved,actor.Id,"lead_assignment","Lead assigned to you",
                        $"{Text(saved,"full_name")} has been assigned to you.",cancellation,requested);
            }
        }
        await WriteState(db,tx,settings.OrganizationId,id,details,key?.StateRevision,cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"crm_leads",settings.OrganizationId,id,actor.Id,key is null?"CREATE":"UPDATE",cancellation);
        tx.Commit();
    }

    internal static async Task PromotePotentialAsync(LeadKey key, CancellationToken cancellation)
    {
        if (!key.Potential)
            throw new InvalidOperationException("Choose a potential client.");

        var settings = DesktopDatabaseSettings.Load();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await settings.VerifyWriteTargetAsync(db, tx, cancellation);
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings, db, tx, actor, "leads", "edit");
        int org = settings.OrganizationId;
        DataRow current = await LockLead(db, tx, settings, key, false, cancellation);
        if (current["is_converted"] is true)
            throw new InvalidOperationException("Converted customer records cannot change prospect type.");

        var details = ReadDetails(current);
        details["recordType"] = "Lead";
        await WriteState(db, tx, org, key.Id, details, key.StateRevision, cancellation);
        using var activity = Cmd(db, tx, @"INSERT INTO public.crm_activities
            (organization_id, branch_id, entity_type, entity_id, lead_id, activity_type,
             title, subject, status, activity_date, metadata_json)
            VALUES (@org, @branch, 'lead', @id, @id, 'type_changed',
                    'Client type changed', 'Client type changed', 'Completed', now(), @metadata)
            RETURNING id",
            ("org", NpgsqlDbType.Integer, org), ("id", NpgsqlDbType.Integer, key.Id),
            ("branch", NpgsqlDbType.Integer, current["branch_id"]),
            ("metadata", NpgsqlDbType.Json, JsonSerializer.Serialize(new { from = "Potential", to = "Lead" })));
        int activityId = (int)(await activity.ExecuteScalarAsync(cancellation))!;
        if (current["branch_id"] is int branch)
            await AddOwnership(db, tx, org, "crm_activities", activityId, branch, cancellation);
        await CrmDirectoryWrites.Audit(db, tx, "crm_leads", org, key.Id, actor.Id, "UPDATE", cancellation);
        tx.Commit();
    }

    internal static async Task SetArchivedAsync(LeadKey key,bool archive,CancellationToken cancellation,string? reason=null)
    {
        if (archive && (string.IsNullOrWhiteSpace(reason) || reason!.Length > 1000))
            throw new ArgumentException("Enter an archive reason of up to 1,000 characters.");
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor = await settings.VerifyWriteTargetAsync(db, tx, cancellation);
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings, db, tx, actor, "leads", "delete");
        DataRow row=await LockLead(db,tx,settings,key,!archive,cancellation);
        if (!archive)
        {
            using var merged=Cmd(db,tx,@"SELECT EXISTS(SELECT 1 FROM public.crm_activities WHERE organization_id=@org
                AND entity_type='lead' AND entity_id=@id AND activity_type='duplicate_merge' AND metadata_json->>'loserId'=@id::text)",
                ("org",NpgsqlDbType.Integer,settings.OrganizationId),("id",NpgsqlDbType.Integer,key.Id));
            if ((bool)(await merged.ExecuteScalarAsync(cancellation))!)
                throw new InvalidOperationException("This lead was merged. Open the surviving lead.");
            foreach (var (table,field) in new[] {("crm_companies","converted_company_id"),("crm_contacts","converted_contact_id"),
                     ("crm_deals","converted_deal_id")})
                if (row[field] is int id)
                    await RequireRelated(db,tx,settings,table,id,cancellation, includeShares: true);
        }
        var details = ReadDetails(row);
        details["archived"] = archive;
        details["archiveReason"] = archive ? reason : null;
        if (archive)
            await StopSequence(db,tx,settings.OrganizationId,key.Id,details,"Archived",cancellation);
        await WriteState(db,tx,settings.OrganizationId,key.Id,details,key.StateRevision,cancellation);
        using var write=Cmd(db,tx,@"UPDATE public.crm_leads SET deleted_at=CASE WHEN @archive THEN deleted_at ELSE NULL END,
            updated_at=now() WHERE organization_id=@org AND id=@id",
            ("org",NpgsqlDbType.Integer,settings.OrganizationId),("id",NpgsqlDbType.Integer,key.Id),("archive",NpgsqlDbType.Boolean,archive));
        await write.ExecuteNonQueryAsync(cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"crm_leads",settings.OrganizationId,key.Id,actor.Id,archive?"DELETE":"RESTORE",cancellation);
        tx.Commit();
    }

    private static async Task<DataRow> LockLead(NpgsqlConnection db,NpgsqlTransaction tx,DesktopDatabaseSettings settings,LeadKey key,
        bool archived,CancellationToken cancellation,bool lockRecord=true)
    {
        using var query=Cmd(db,tx,@"SELECT l.*, l.xmin::text AS revision,COALESCE(s.xmin::text,'') AS state_revision,
            COALESCE(s.data_json::text,'{}') AS operating_state FROM public.crm_leads l
            LEFT JOIN public.crm_lead_operating_states s ON s.organization_id=l.organization_id AND s.lead_id=l.id
            WHERE l.organization_id=@org AND l.id=@id AND " + CrmDirectoryWrites.BranchScope("crm_leads", "l") + @" AND
                (l.deleted_at IS NOT NULL OR COALESCE(s.data_json->>'archived','false')='true')=@archived
                AND (COALESCE(s.data_json->>'recordType','Lead') = 'Potential') = @potential"+
            (lockRecord?" FOR UPDATE OF l":""),
            ("org",NpgsqlDbType.Integer,settings.OrganizationId),("scope_branch",NpgsqlDbType.Integer,settings.BranchId),
            ("id",NpgsqlDbType.Integer,key.Id),("archived",NpgsqlDbType.Boolean,archived),
            ("potential",NpgsqlDbType.Boolean,key.Potential));
        using var reader=await query.ExecuteReaderAsync(cancellation);
        var table=await Table(reader,cancellation);
        if (table.Rows.Count==0 || Text(table.Rows[0],"revision")!=key.Revision || Text(table.Rows[0],"state_revision")!=key.StateRevision)
            throw new InvalidOperationException("This lead changed. Refresh the directory before trying again.");
        return table.Rows[0];
    }

    private static async Task<DataTable> Table(NpgsqlDataReader reader,CancellationToken cancellation)
    {
        var table=new DataTable();
        for(int i=0;i<reader.FieldCount;i++)
            table.Columns.Add(reader.GetName(i),reader.GetFieldType(i));
        while(await reader.ReadAsync(cancellation))
        {
            var row=new object[reader.FieldCount];
            reader.GetValues(row);
            table.Rows.Add(row);
        }
        return table;
    }

    private static void ValidateTransition(LeadPolicy policy,DataRow? current,string status,Dictionary<string,string> draft,
        Dictionary<string,object?> details,bool converting)
    {
        LeadStage stage=policy.Stages.FirstOrDefault(item=>item.Name==status)
            ?? throw new ArgumentException("Choose a configured lead stage.");
        if (status=="Converted" && !converting && current?["is_converted"] is not true)
            throw new ArgumentException("Use Convert Lead to convert this record.");
        if (current?["is_converted"] is true && status!="Converted")
            throw new InvalidOperationException("A converted lead cannot return to the prospect pipeline.");
        if (current is not null && !converting && status!=Text(current,"status") &&
            policy.Stages.FirstOrDefault(item=>item.Name==Text(current,"status")) is LeadStage previous &&
            !previous.AllowedNext.Contains(status))
            throw new ArgumentException($"Transition from {previous.Name} to {status} is not allowed.");
        var missing=new List<string>();
        foreach(string required in stage.Required.Concat(status=="Lost"?new[]{"lossReason"}:Array.Empty<string>()).Distinct())
        {
            object? value = required is "need" or "budget" or "decisionMaker" or "timeline"
                ? (details.TryGetValue("qualification",out var qualification) ? Nested(qualification,required) : null)
                : details.TryGetValue(required,out var extra) ? extra :
                    draft.TryGetValue(required,out string editable) ? editable :
                    current?.Table.Columns.Contains(required)==true ? current[required] : null;
            if (value is null or DBNull || value is false || value is JsonElement element &&
                element.ValueKind is JsonValueKind.Null or JsonValueKind.False or JsonValueKind.Undefined ||
                string.IsNullOrWhiteSpace(Convert.ToString(value)))
                missing.Add(required);
        }
        if (missing.Count>0)
            throw new ArgumentException("Complete the required fields: "+string.Join(", ",missing)+".");
    }

    private static object? Nested(object? data,string name) =>
        data is Dictionary<string,string> fields && fields.TryGetValue(name,out string text) ? text :
        data is JsonElement json && json.ValueKind==JsonValueKind.Object && json.TryGetProperty(name,out var value) ? value : null;

    internal static Dictionary<string,object?> ReadDetails(DataRow? row)
    {
        using var doc=JsonDocument.Parse(row is null?"{}":Text(row,"operating_state"));
        return doc.RootElement.EnumerateObject().ToDictionary(item=>item.Name,item=>(object?)item.Value.Clone());
    }

    private static async Task WriteState(NpgsqlConnection db,NpgsqlTransaction tx,int org,int lead,
        Dictionary<string,object?> details,string? revision,CancellationToken cancellation)
    {
        using var command=Cmd(db,tx,@"INSERT INTO public.crm_lead_operating_states (organization_id,lead_id,data_json,version)
            VALUES (@org,@id,@data,1) ON CONFLICT (organization_id,lead_id) DO UPDATE
            SET data_json=excluded.data_json,version=crm_lead_operating_states.version+1,updated_at=now()
            WHERE crm_lead_operating_states.xmin::text=@revision",
            ("org",NpgsqlDbType.Integer,org),("id",NpgsqlDbType.Integer,lead),
            ("data",NpgsqlDbType.Json,JsonSerializer.Serialize(details)),("revision",NpgsqlDbType.Text,revision));
        if(await command.ExecuteNonQueryAsync(cancellation)!=1)
            throw new InvalidOperationException("Lead qualification changed. Reopen the editor.");
    }

    private static async Task AddOwnership(NpgsqlConnection db,NpgsqlTransaction tx,int org,string table,int id,int branch,
        CancellationToken cancellation)
    {
        using var cmd=Cmd(db,tx,@"INSERT INTO public.suite_branch_ownership
            (resource_table,resource_key,company_id,branch_id,source) VALUES(@table,@id::text,@org,@branch,'desktop-crm')",
            ("org",NpgsqlDbType.Integer,org),("table",NpgsqlDbType.Text,table),("id",NpgsqlDbType.Integer,id),("branch",NpgsqlDbType.Integer,branch));
        await cmd.ExecuteNonQueryAsync(cancellation);
    }

    private static async Task RequireRelated(NpgsqlConnection db,NpgsqlTransaction tx,DesktopDatabaseSettings settings,string table,int id,
        CancellationToken cancellation, bool includeShares = false)
    {
        using var command=Cmd(db,tx,$"SELECT id FROM public.{table} r WHERE organization_id=@org AND id=@id AND deleted_at IS NULL AND " +
            CrmDirectoryWrites.BranchScope(table, "r", includeShares) + " FOR SHARE",
            ("org",NpgsqlDbType.Integer,settings.OrganizationId),("id",NpgsqlDbType.Integer,id),
            ("scope_branch",NpgsqlDbType.Integer,settings.BranchId));
        if(await command.ExecuteScalarAsync(cancellation) is null)
            throw new InvalidOperationException("A related CRM record is archived or unavailable.");
    }

    internal static LeadKey Key(DataRow row, bool potential = false) =>
        new((int)row["id"], Text(row,"revision"), Text(row,"state_revision"), potential);
    internal static string Text(DataRow row,string field)=>Convert.ToString(row[field],CultureInfo.InvariantCulture)??"";
    internal static string Detail(Dictionary<string,object?> state,string key)=>
        state.TryGetValue(key,out object? value)?Convert.ToString(value)??"":"";
    internal static string Qualification(Dictionary<string,object?> state,string key)=>
        state.TryGetValue("qualification",out object? value)?Convert.ToString(Nested(value,key))??"":"";
    private static string Read(Dictionary<string,string> draft,string key)=>draft.TryGetValue(key,out string value)?value.Trim():"";
    private static DateTime? DateValue(string value,string label)=>value.Length==0?null:
        DateTime.TryParseExact(value,"yyyy-MM-dd",CultureInfo.InvariantCulture,DateTimeStyles.None,out var date)?date:
        throw new ArgumentException($"{label} must use YYYY-MM-DD.");

    private static NpgsqlCommand Cmd(NpgsqlConnection db,NpgsqlTransaction? tx,string sql,
        params (string Name,NpgsqlDbType Type,object? Value)[] values)
    {
        var command=new NpgsqlCommand(sql,db,tx);
        foreach(var parameter in values)
            CrmExtrasStore.Param(command,parameter.Name,parameter.Type,parameter.Value);
        return command;
    }
}
