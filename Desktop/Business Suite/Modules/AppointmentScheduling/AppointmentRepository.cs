using System.Data;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.Json.Serialization;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record AppointmentOption(int Id, string Name, string Zone = "", int DefaultMinutes = 30);
internal sealed record AppointmentOptions(List<AppointmentOption> Customers, List<AppointmentOption> Services,
    List<AppointmentOption> Providers, List<AppointmentOption> Resources, Dictionary<int, HashSet<int>> Eligibility);
internal sealed record AppointmentSlot(DateTime LocalTime, int Minutes, int Provider, int[] Extras);
internal sealed record AppointmentDraft(int Customer, int Service, AppointmentSlot Slot, string Notes, Guid Request,
    string CustomerNotes = "", bool WalkIn = false,
    [property:JsonIgnore(Condition=JsonIgnoreCondition.WhenWritingNull)] int? Project = null,
    [property:JsonIgnore(Condition=JsonIgnoreCondition.WhenWritingNull)] int? Deal = null);
internal sealed record AppointmentQuote(decimal Price, decimal Tax, string Currency,GroupedSchedulePreview? Grouped = null);
internal sealed record AppointmentKey(int Id, int Revision);
internal sealed record AppointmentPage(DataTable Rows, bool CanCreate, bool CanEdit,
    List<AppointmentOption> Providers, List<AppointmentOption> Assets, bool CanViewBilling);
internal sealed record AppointmentEditorData(AppointmentKey Key, int Customer, int Service, AppointmentSlot Slot,
    GroupedScheduleVersion? Grouped = null);

internal sealed partial class AppointmentRepository(DesktopDatabaseSettings settings)
{
    private const string AssetTypes = "'room','chair','equipment','location'";
    private const string ProviderTypes = "'provider','doctor','stylist','consultant','technician','employee'";
    private const string Legacy = @"NOT EXISTS (
        SELECT 1 FROM public.business_pack_record_ownership own
        WHERE own.resource_table='srm_industry_records' AND own.resource_key=r.id::text)";
    private const string AgendaZone = @"SELECT COALESCE((SELECT r.data->>'timezone' FROM public.srm_industry_records r
        WHERE r.organization_id=@org AND r.branch_id=@branch AND r.kind='resource' AND r.status='active'
        AND r.data->>'resource_type' IN (" + ProviderTypes + ") AND " + Legacy + @" ORDER BY r.id LIMIT 1),'Asia/Kolkata')";
    private const string CustomerScope = @" FROM public.crm_companies c
        WHERE c.organization_id=@org AND c.deleted_at IS NULL AND c.status='Active'
        AND NOT EXISTS (SELECT 1 FROM public.srm_anonymous_cash_accounts a WHERE a.organization_id=@org AND a.customer_id=c.id)
        AND (c.account_type='Customer' OR EXISTS (SELECT 1 FROM public.suite_business_relationships b
            WHERE b.organization_id=@org AND b.account_id=c.id AND b.role='Customer' AND b.status='Active'))
        AND (COALESCE((SELECT o.branch_id FROM public.suite_branch_ownership o
              WHERE o.company_id=@org AND o.resource_table='crm_companies' AND o.resource_key=c.id::text), c.branch_id, @branch)=@branch
          OR EXISTS (SELECT 1 FROM public.suite_branch_record_shares sh WHERE sh.company_id=@org
              AND sh.resource_table='crm_companies' AND sh.resource_key=c.id::text AND sh.branch_id=@branch))";
    private const string Customers = "SELECT c.id,c.name" + CustomerScope;
    private const string Services = @"SELECT s.id,s.item_name,s.sales_rate,s.gst_rate,
            COALESCE(s.metadata_json->>'currency','INR'),COALESCE(s.metadata_json::text,'{}')
        FROM public.srm_products s WHERE s.organization_id=@org AND s.deleted_at IS NULL
        AND s.active AND lower(s.product_type) IN ('services','service')
        AND (NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership o WHERE o.company_id=@org
                AND o.resource_table='srm_products' AND o.resource_key=s.id::text AND o.branch_id<>@branch)
            OR EXISTS (SELECT 1 FROM public.suite_branch_record_shares sh WHERE sh.company_id=@org
                AND sh.resource_table='srm_products' AND sh.resource_key=s.id::text AND sh.branch_id=@branch))";
    private int Branch => settings.BranchId ??
        throw new InvalidOperationException("Select one active branch to open Appointments.");

    internal async Task<DateTime> AgendaTodayAsync(CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await AuthorizeAsync(db, tx, "view", cancellation);
        using var command = Query(db, tx, "SELECT (CURRENT_TIMESTAMP AT TIME ZONE (" + AgendaZone + "))::timestamp");
        return ((DateTime)(await command.ExecuteScalarAsync(cancellation))!).Date;
    }

    internal Task<AppointmentPage> ListAsync(DateTime day, bool week, string status, CancellationToken cancellation) =>
        FilterAgendaAsync(day, week, status, "", 0, 0, cancellation);

    internal async Task<AppointmentPage> FilterAgendaAsync(DateTime day, bool week, string status, string search,
        int provider, int asset, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeAsync(db, tx, "view", cancellation);
        bool canCreate = actor.CanWriteBranch && await CanWriteAsync(db, tx, actor, "create");
        bool canEdit = actor.CanWriteBranch && await CanWriteAsync(db, tx, actor, "edit");
        var providers = await AgendaResourcesAsync(db, tx, ProviderTypes, cancellation);
        var assets = await AgendaResourcesAsync(db, tx, AssetTypes, cancellation);
        bool filtersAvailable = (provider == 0 || providers.Any(option => option.Id == provider)) &&
            (asset == 0 || assets.Any(option => option.Id == asset));
        using var command = Query(db, tx, "WITH zone(name) AS (" + AgendaZone + @")
            SELECT r.id,r.revision,r.status,initcap(replace(r.status,'_',' ')) AS status_label,r.data->>'customer_name' AS customer,r.data->>'service_name' AS service,
                r.starts_at AT TIME ZONE zone.name AS starts_local, r.ends_at AT TIME ZONE zone.name AS ends_local,
                r.starts_at,zone.name AS timezone,r.data->>'notes' AS notes,
                (NOT EXISTS (SELECT 1 FROM public.srm_pos_service_occurrences p WHERE p.appointment_id=r.id)
                    OR r.starts_at>now()) AS can_reschedule
            FROM public.srm_industry_records r CROSS JOIN zone WHERE r.organization_id=@org AND r.branch_id=@branch
                AND r.kind='appointment' AND " + Legacy + @"
                AND r.starts_at < (@finish AT TIME ZONE zone.name) AND r.ends_at > (@start AT TIME ZONE zone.name)
                AND (@status='' OR r.status=@status)
                AND (@search='' OR strpos(lower(coalesce(r.data->>'customer_name','Customer') || ' ' || coalesce(r.data->>'service_name','')),lower(@search))>0)
                AND @filtersAvailable
                AND (@provider=0 OR (r.data->'resource_ids')::jsonb @> jsonb_build_array(@provider))
                AND (@asset=0 OR (r.data->'resource_ids')::jsonb @> jsonb_build_array(@asset))
            ORDER BY r.starts_at,r.id",
            ("start",NpgsqlDbType.Timestamp,Wall(day.Date)),
            ("finish",NpgsqlDbType.Timestamp,Wall(day.Date.AddDays(week?7:1))),("status",NpgsqlDbType.Text,status),
            ("search",NpgsqlDbType.Text,search.Trim()),
            ("provider",NpgsqlDbType.Integer,provider),("asset",NpgsqlDbType.Integer,asset),
            ("filtersAvailable",NpgsqlDbType.Boolean,filtersAvailable));
        using var reader = await command.ExecuteReaderAsync(cancellation);
        var rows = new DataTable();
        rows.Load(reader);
        return new(rows,canCreate,canEdit,providers,assets,await CanViewBillingAsync(db,tx,actor));
    }

    private async Task<List<AppointmentOption>> AgendaResourcesAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        string types, CancellationToken cancellation)
    {
        using var command = Query(db, tx, ResourceList(types));
        using var reader = await command.ExecuteReaderAsync(cancellation);
        var options = new List<AppointmentOption>();
        while (await reader.ReadAsync(cancellation))
            options.Add(new(reader.GetInt32(0), reader.GetString(1), reader.GetString(2)));
        return options;
    }

    internal async Task<AppointmentOptions> OptionsAsync(CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await AuthorizeAsync(db, tx, "view", cancellation);
        var eligibility = new Dictionary<int, HashSet<int>>();
        using (var query = Query(db,tx,@"WITH provider AS (
            SELECT r.id,coalesce(e.work_categories::text,'[]') AS categories "+EligibilityProviderSource+@"
        ) SELECT l.service_product_id,l.provider_resource_id,r.categories,coalesce(p.employee_categories::text,'[]')
        FROM public.srm_service_specialist_eligibility l JOIN provider r ON r.id=l.provider_resource_id
        JOIN public.srm_service_booking_policies p ON p.id=l.booking_policy_id AND p.service_product_id=l.service_product_id
            AND p.organization_id=@org AND p.branch_id=@branch AND p.pack_context_id IS NULL AND p.active
        WHERE l.organization_id=@org AND l.branch_id=@branch AND l.pack_context_id IS NULL AND l.active
            AND NOT EXISTS (SELECT 1 FROM public.business_pack_record_ownership o WHERE
                (o.resource_table='srm_service_specialist_eligibility' AND o.resource_key=l.id::text)
                OR (o.resource_table='srm_service_booking_policies' AND o.resource_key=p.id::text))"))
        using (var reader = await query.ExecuteReaderAsync(cancellation))
        {
            while (await reader.ReadAsync(cancellation))
            {
                var required=JsonSerializer.Deserialize<string[]>(reader.GetString(3)) ?? [];
                if (required.Length>0 && !MatchesProviderCategories(
                    JsonSerializer.Deserialize<string[]>(reader.GetString(2)) ?? [],required))
                    continue;
                int service = reader.GetInt32(0);
                if (!eligibility.TryGetValue(service, out var providers))
                    eligibility.Add(service, providers = new HashSet<int>());
                providers.Add(reader.GetInt32(1));
            }
        }
        string serviceChoices = "SELECT s.id,s.item_name,p.default_duration_minutes FROM (" + Services + @") s
            JOIN public.srm_service_booking_policies p ON p.service_product_id=s.id
                AND p.organization_id=@org AND p.branch_id=@branch AND p.pack_context_id IS NULL AND p.active
            ORDER BY s.item_name,s.id";
        return new(await Read(Customers + " ORDER BY c.name,c.id"), await Read(serviceChoices, service: true),
            await Read(ResourceList(ProviderTypes), resource: true),
            await Read(ResourceList(AssetTypes), resource: true), eligibility);

        async Task<List<AppointmentOption>> Read(string sql, bool resource=false, bool service=false)
        {
            using var command=Query(db,tx,sql);
            using var reader=await command.ExecuteReaderAsync(cancellation);
            var choices=new List<AppointmentOption>();
            while (await reader.ReadAsync(cancellation))
                choices.Add(new(reader.GetInt32(0),reader.GetString(1),resource?reader.GetString(2):"",service?reader.GetInt32(2):30));
            return choices;
        }
    }

    internal async Task<AppointmentEditorData> EditDataAsync(AppointmentKey key, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeAsync(db,tx,"view",cancellation);
        var row=await CurrentAsync(db,tx,key,false,cancellation);
        GroupedScheduleVersion? grouped=null;
        if (row.Grouped)
        {
            await RequireAccessAsync(db,tx,actor,"create");
            grouped=await ReadGroupedScheduleAsync(db,tx,key,false,cancellation);
        }
        else
        {
            CheckReschedule(row);
            await CheckLinkedTaskAsync(db,tx,actor,row,null,cancellation);
        }
        var resources=await ResourcesAsync(db,tx,ReadIds(row.Data),true,cancellation);
        var providers=resources.Where(resource=>resource.IsProvider).ToArray();
        if (providers.Length!=1)
            throw new InvalidOperationException("This booking needs exactly one provider to be rescheduled.");
        var provider=providers[0];
        DateTime local=await LocalAsync(db,tx,row.Start,provider.Zone,cancellation);
        return new(key,row.Customer ?? throw new InvalidOperationException("This appointment has no active customer."),
            row.Data["service_id"]!.GetValue<int>(),
            new(local,row.Data["duration_minutes"]!.GetValue<int>(),provider.Id,
                resources.Where(resource=>resource.Id!=provider.Id).Select(resource=>resource.Id).ToArray()),grouped);
    }

    internal Task<AppointmentQuote> CheckAsync(int serviceId, AppointmentSlot slot, CancellationToken cancellation) =>
        CheckSlotAsync(serviceId, slot, null, cancellation);

    internal async Task<List<AppointmentOption>> ProjectOptionsAsync(CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeAsync(db,tx,"view",cancellation);
        if (!actor.CanWriteBranch || !await CanWriteAsync(db,tx,actor,"create"))
            return [];
        try
        {
            var rows = await PmsProjectRepository.ReadAppointmentProjectOptionsAsync(settings,db,tx,actor,cancellation);
            return rows.Select(row => new AppointmentOption(row.Id,row.Name)).ToList();
        }
        catch (PostgresException ex) when (ex.SqlState == PostgresErrorCodes.InsufficientPrivilege)
        {
            return [];
        }
        catch (UnauthorizedAccessException)
        {
            return [];
        }
    }

    internal async Task<List<AppointmentOption>> DealOptionsAsync(int customer,CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeAsync(db,tx,"view",cancellation);
        if (!actor.CanWriteBranch || !await CanWriteAsync(db,tx,actor,"create"))
            return [];
        try
        {
            await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"deals","view");
            using var query = DealQuery(db,tx,customer,null);
            using var reader = await query.ExecuteReaderAsync(cancellation);
            var options = new List<AppointmentOption>();
            while (await reader.ReadAsync(cancellation))
                options.Add(new AppointmentOption(reader.GetInt32(0),reader.GetString(1)));
            return options;
        }
        catch (UnauthorizedAccessException) { return []; }
        catch (PostgresException ex) when (ex.SqlState == PostgresErrorCodes.InsufficientPrivilege) { return []; }
    }

    private NpgsqlCommand DealQuery(NpgsqlConnection db,NpgsqlTransaction tx,int customer,int? deal)
    {
        var sql = @"SELECT d.id,d.name FROM public.crm_deals d WHERE d.organization_id=@org AND d.company_id=@customer
            AND d.deleted_at IS NULL AND " + CrmDirectoryWrites.BranchScope("crm_deals","d") +
            " AND EXISTS (SELECT 1" + CustomerScope +
            " AND c.id=@customer)" + (deal.HasValue ? " AND d.id=@deal FOR SHARE OF d" : " ORDER BY d.name,d.id");
        return Query(db,tx,sql,("customer",NpgsqlDbType.Integer,customer),("deal",NpgsqlDbType.Integer,deal),
            ("scope_branch",NpgsqlDbType.Integer,Branch));
    }

    internal Task<AppointmentQuote> CheckRescheduleAsync(AppointmentKey key, AppointmentSlot slot, CancellationToken cancellation) =>
        CheckSlotAsync(0, slot, key, cancellation);

    private async Task<AppointmentQuote> CheckSlotAsync(int serviceId, AppointmentSlot slot, AppointmentKey? key,
        CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeAsync(db, tx, "view", cancellation);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch does not permit booking.");
        await RequireAccessAsync(db, tx, actor, key is null ? "create" : "edit");
        GroupedScheduleVersion? grouped=null;
        if (key is not null)
        {
            var current = await CurrentAsync(db, tx, key, false, cancellation);
            if (current.Grouped)
            {
                await RequireAccessAsync(db,tx,actor,"create");
                grouped=await ReadGroupedScheduleAsync(db,tx,key,false,cancellation);
            }
            else
            {
                CheckReschedule(current);
                await CheckLinkedTaskAsync(db,tx,actor,current,slot.LocalTime.Date,cancellation);
            }
            serviceId = current.Data["service_id"]!.GetValue<int>();
        }
        var service = await ReadServiceAsync(db, tx, serviceId, cancellation);
        if (grouped is null)
        {
            await ValidateAsync(db,tx,service,slot,key?.Id,cancellation);
            return new(service.Price,service.Tax,service.Currency);
        }
        var booking=await ValidateGroupedBookingAsync(db,tx,service,slot,key!.Id,cancellation);
        var policy=booking.Policy;
        return new(0,0,"",new(grouped,slot,policy.Id,policy.Revision,policy.Eligibility,policy.EligibilityRevision));
    }

    internal async Task<int> CreateAsync(AppointmentDraft draft,CancellationToken cancellation)
    {
        ValidateDraft(draft);
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await AuthorizeAsync(db,tx,"create",cancellation);
        int id=await CreateInTransactionAsync(db,tx,actor,draft,cancellation);
        tx.Commit();
        return id;
    }

    private async Task<int> CreateInTransactionAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,
        AppointmentDraft draft,CancellationToken cancellation)
    {
        string request=draft.Request.ToString();
        string digest=Digest(draft);
        using (var command=Query(db,tx,@"SELECT r.id,r.kind,r.data->>'_request_digest',r.created_by= @actor,
                " + Legacy + @" FROM public.srm_industry_records r
            WHERE r.organization_id=@org AND r.branch_id=@branch AND r.request_id=@request",
            ("request",NpgsqlDbType.Text,request),("actor",NpgsqlDbType.Integer,actor.Id)))
        using (var reader=await command.ExecuteReaderAsync(cancellation))
        {
            if (await reader.ReadAsync(cancellation))
            {
                if (reader.GetString(1)!="appointment"||reader.IsDBNull(2)||reader.GetString(2)!=digest ||
                    reader.IsDBNull(3)||!reader.GetBoolean(3)||!reader.GetBoolean(4))
                    throw new InvalidOperationException("The existing booking request has different details.");
                return reader.GetInt32(0);
            }
        }
        string customer;
        using(var command=Query(db,tx,Customers+" AND c.id=@customer FOR SHARE",("customer",NpgsqlDbType.Integer,draft.Customer)))
        using(var reader=await command.ExecuteReaderAsync(cancellation))
            customer=await reader.ReadAsync(cancellation)?reader.GetString(1):throw new InvalidOperationException("Choose an active customer.");
        var service=await ReadServiceAsync(db,tx,draft.Service,cancellation);
        var booking=await ValidateAsync(db,tx,service,draft.Slot,null,cancellation);
        if (draft.Deal is int opportunity)
        {
            await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"deals","view");
            using var linked = DealQuery(db,tx,draft.Customer,opportunity);
            if (await linked.ExecuteScalarAsync(cancellation) is null)
                throw new InvalidOperationException("Choose a CRM opportunity for the same customer in this branch.");
        }
        var data=new JsonObject
        {
            ["customer_id"]=draft.Customer,["customer_name"]=customer,["service_id"]=draft.Service,["service_name"]=service.Name,
            ["unit_price"]=service.Price,["tax_rate"]=service.Tax,["currency"]=service.Currency,["notes"]=draft.Notes,
            ["customer_notes"]=draft.CustomerNotes,["walk_in"]=draft.WalkIn,["create_pms_task"]=draft.Project.HasValue,["_request_digest"]=digest
        };
        if (draft.Project is int selectedProject)
            data["project_id"] = selectedProject;
        if (draft.Deal is int selectedDeal)
            data["deal_id"] = selectedDeal;
        Apply(data,booking,draft.Slot);
        string title=service.Name+" · "+customer;
        title=title.Substring(0,Math.Min(220,title.Length));
        using var insert=Query(db,tx,@"INSERT INTO public.srm_industry_records
            (organization_id,branch_id,kind,title,status,revision,request_id,customer_id,project_id,starts_at,ends_at,data,created_by)
            VALUES (@org,@branch,'appointment',@title,'booked',1,@request,@customer,@project,@start,@finish,@data,@actor) RETURNING id",
            ("title",NpgsqlDbType.Text,title),("request",NpgsqlDbType.Text,request),
            ("project",NpgsqlDbType.Integer,draft.Project),
            ("customer",NpgsqlDbType.Integer,draft.Customer),("start",NpgsqlDbType.TimestampTz,booking.Start),
            ("finish",NpgsqlDbType.TimestampTz,booking.End),("data",NpgsqlDbType.Json,data.ToJsonString()),("actor",NpgsqlDbType.Integer,actor.Id));
        int id=(int)(await insert.ExecuteScalarAsync(cancellation))!;
        if (draft.Project is int project)
        {
            string prefix = booking.ProviderKind == "stylist" ? "SALON" : "APPT";
            string body = $"Appointment #{id}. Service: {service.Name}. Manage the booking from Appointments.";
            DateTime local = draft.Slot.LocalTime.Date;
            var task = new PmsTaskDraft(title,body,"To Do","Medium",local,local,draft.Slot.Minutes/60m);
            data["pms_task_id"] = await PmsProjectRepository.CreateAppointmentTaskAsync(settings,db,tx,actor,project,
                prefix+"-"+id,task,cancellation);
            using var bind=Query(db,tx,"UPDATE public.srm_industry_records SET data=@data WHERE id=@id AND organization_id=@org AND branch_id=@branch",
                ("data",NpgsqlDbType.Json,data.ToJsonString()),("id",NpgsqlDbType.Integer,id));
            if (await bind.ExecuteNonQueryAsync(cancellation) != 1)
                throw new InvalidOperationException("The new appointment could not be linked to its delivery task.");
        }
        await AuditAsync(db,tx,actor.Id,id,"created","booked",1,data,cancellation);
        return id;
    }

    internal async Task RescheduleAsync(AppointmentKey key,AppointmentSlot slot,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await AuthorizeAsync(db,tx,"edit",cancellation);
        var row=await CurrentAsync(db,tx,key,true,cancellation);
        CheckReschedule(row);
        var service=await ReadServiceAsync(db,tx,row.Data["service_id"]!.GetValue<int>(),cancellation);
        var booking=await ValidateAsync(db,tx,service,slot,key.Id,cancellation);
        if (LinkedTask(row) is int task)
            await PmsProjectRepository.SaveAppointmentTaskAsync(settings,db,tx,actor,row.Project!.Value,task,
                slot.LocalTime.Date,slot.Minutes/60m,cancellation);
        Apply(row.Data,booking,slot);
        using var update=Query(db,tx,@"UPDATE public.srm_industry_records SET starts_at=@start,ends_at=@finish,
            data=@data,revision=revision+1,updated_at=now() WHERE id=@id AND organization_id=@org AND branch_id=@branch",
            ("id",NpgsqlDbType.Integer,key.Id),("start",NpgsqlDbType.TimestampTz,booking.Start),
            ("finish",NpgsqlDbType.TimestampTz,booking.End),("data",NpgsqlDbType.Json,row.Data.ToJsonString()));
        await update.ExecuteNonQueryAsync(cancellation);
        await AuditAsync(db,tx,actor.Id,key.Id,"rescheduled",row.Status,key.Revision+1,row.Data,cancellation);
        tx.Commit();
    }

    internal async Task TransitionAsync(AppointmentKey key,string status,string reason,CancellationToken cancellation)
    {
        if (reason.Length>1000||((status=="cancelled"||status=="no_show")&&string.IsNullOrWhiteSpace(reason)))
            throw new ArgumentException("Enter a reason of up to 1,000 characters.");
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await AuthorizeAsync(db,tx,"edit",cancellation);
        var row=await CurrentAsync(db,tx,key,true,cancellation);
        bool allowed=row.Status switch
        {
            "booked"=>status is "checked_in" or "cancelled" or "no_show",
            "checked_in"=>status is "in_service" or "cancelled",
            "in_service"=>status=="completed",
            _=>false
        };
        if (!allowed||(status=="no_show"&&row.Start>DateTime.UtcNow))
            throw new InvalidOperationException("This status change is unavailable.");
        row.Data["transition_reason"]=reason;
        using var update=Query(db,tx,@"UPDATE public.srm_industry_records SET status=@status,data=@data,revision=revision+1,
            updated_at=now() WHERE id=@id AND organization_id=@org AND branch_id=@branch",
            ("id",NpgsqlDbType.Integer,key.Id),("status",NpgsqlDbType.Text,status),("data",NpgsqlDbType.Json,row.Data.ToJsonString()));
        await update.ExecuteNonQueryAsync(cancellation);
        await AuditAsync(db,tx,actor.Id,key.Id,status,status,key.Revision+1,row.Data,cancellation);
        tx.Commit();
    }
    private async Task<DesktopActor> AuthorizeAsync(NpgsqlConnection db,NpgsqlTransaction tx,string action,CancellationToken cancellation)
    {
        bool writing=action!="view";
        var actor=writing?await settings.VerifyWriteTargetAsync(db,tx,cancellation):await settings.RequireActorAsync(db,tx,cancellation);
        await RequireAccessAsync(db,tx,actor,action);
        if (writing)
        {
            using (var lockCompany=Query(db,tx,"SELECT pg_advisory_xact_lock(720000000::bigint+@org)"))
                await lockCompany.ExecuteNonQueryAsync(cancellation);
            using (var company=Query(db,tx,"SELECT id FROM public.companies WHERE id=@org AND is_active FOR UPDATE"))
                if (await company.ExecuteScalarAsync(cancellation) is null)
                    throw new InvalidOperationException("The company is inactive.");
            actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
            await RequireAccessAsync(db,tx,actor,action);
        }
        using var scope=Query(db,tx,@"SELECT EXISTS (SELECT 1 FROM public.business_pack_contexts
            WHERE company_id=@org AND branch_id=@branch AND (state='active' OR ever_activated))");
        if ((bool)(await scope.ExecuteScalarAsync(cancellation))!)
            throw new InvalidOperationException("This branch uses an operational pack. Desktop pack appointments are unavailable.");
        return actor;
    }

    private async Task RequireAccessAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,string action)
    {
        string[] permissions=action=="view"
            ? ["srm_view","srm_manage","srm_admin","srm_invoice_view","srm_invoice_create"]
            : action=="invoice" ? ["srm_invoice_create","srm_admin"]
            : action=="approve_invoice" ? ["srm_invoice_approve","srm_admin"]
            : action=="collect" ? ["srm_collection_create","srm_admin"] : ["srm_manage","srm_admin"];
        var grant=await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,Branch,actor,"srm",
            action is "invoice" or "collect" ? "create" : action=="approve_invoice" ? "approve" : action,permissions);
        if (grant.Scope is not ("organization" or "branch"))
            throw new UnauthorizedAccessException("The desktop agenda requires branch-wide or company-wide Sales record access.");
    }

    private async Task<bool> CanWriteAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,string action)
    {
        try
        {
            await RequireAccessAsync(db,tx,actor,action);
            return true;
        }
        catch (UnauthorizedAccessException) { return false; }
    }

    private static string ResourceList(string types) => @"SELECT r.id,r.title,r.data->>'timezone'
        FROM public.srm_industry_records r WHERE r.organization_id=@org AND r.branch_id=@branch
          AND r.kind='resource' AND r.status='active' AND r.data->>'resource_type' IN ("+types+") AND "+Legacy+
        " AND r.data->>'timezone' IS NOT NULL ORDER BY r.title,r.id";

    private async Task<Current> CurrentAsync(NpgsqlConnection db,NpgsqlTransaction tx,AppointmentKey key,bool locked,
        CancellationToken cancellation)
    {
        using var query=Query(db,tx,@"SELECT r.status,r.customer_id,r.starts_at,r.data::text,r.revision,
            EXISTS (SELECT 1 FROM public.srm_pos_service_occurrences p WHERE p.appointment_id=r.id),r.project_id
            FROM public.srm_industry_records r WHERE r.organization_id=@org AND r.branch_id=@branch
                AND r.id=@id AND r.kind='appointment' AND "+Legacy+(locked?" FOR UPDATE":""),
            ("id",NpgsqlDbType.Integer,key.Id));
        using var reader=await query.ExecuteReaderAsync(cancellation);
        if (!await reader.ReadAsync(cancellation)||reader.GetInt32(4)!=key.Revision)
            throw new InvalidOperationException("The appointment changed or is outside the current branch. Refresh the agenda.");
        return new(reader.GetString(0),reader.IsDBNull(1)?null:reader.GetInt32(1),reader.GetDateTime(2),JsonNode.Parse(reader.GetString(3))!.AsObject(),
            reader.GetBoolean(5),reader.IsDBNull(6) ? null : reader.GetInt32(6));
    }

    private static void CheckReschedule(Current row)
    {
        if (row.Status!="booked")
            throw new InvalidOperationException("Only booked appointments can be rescheduled.");
        if (row.Grouped)
            throw new InvalidOperationException("Use the linked service schedule to reschedule this grouped appointment.");
    }

    private static int? LinkedTask(Current row)
    {
        var value = row.Data["pms_task_id"];
        if (value is null)
            return null;
        if (!row.Project.HasValue || !int.TryParse(value.ToString(),out int task) || task <= 0)
            throw new InvalidOperationException("The appointment's project task link is unavailable.");
        return task;
    }

    private async Task CheckLinkedTaskAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,Current row,
        DateTime? date,CancellationToken cancellation)
    {
        if (LinkedTask(row) is int task)
            await PmsProjectRepository.CheckAppointmentTaskAsync(settings,db,tx,actor,row.Project!.Value,task,date,cancellation);
    }

    private async Task<Service> ReadServiceAsync(NpgsqlConnection db,NpgsqlTransaction tx,int id,CancellationToken cancellation)
    {
        using var command=Query(db,tx,Services+" AND s.id=@id FOR SHARE",("id",NpgsqlDbType.Integer,id));
        using var reader=await command.ExecuteReaderAsync(cancellation);
        if (!await reader.ReadAsync(cancellation)||reader.IsDBNull(2)||reader.IsDBNull(3))
            throw new InvalidOperationException("The selected service or its price is unavailable.");
        return new(id,reader.GetString(1),reader.GetDecimal(2),reader.GetDecimal(3),reader.GetString(4),
            JsonNode.Parse(reader.GetString(5))?.AsObject()??new JsonObject());
    }

    private async Task AuditAsync(NpgsqlConnection db,NpgsqlTransaction tx,int actor,int id,string action,string status,
        int revision,JsonObject data,CancellationToken cancellation,string kind="appointment")
    {
        using var insert=Query(db,tx,@"INSERT INTO public.srm_audit_logs
            (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
            VALUES (@org,@entity,@id,@action,@actor,@data)",
            ("id",NpgsqlDbType.Integer,id),("action",NpgsqlDbType.Text,action),("actor",NpgsqlDbType.Integer,actor),
            ("entity",NpgsqlDbType.Text,"industry_"+kind),
            ("data",NpgsqlDbType.Json,JsonSerializer.Serialize(new {revision,status,data})));
        await insert.ExecuteNonQueryAsync(cancellation);
    }

    private NpgsqlCommand Query(NpgsqlConnection db,NpgsqlTransaction tx,string sql,
        params (string Name,NpgsqlDbType Type,object? Value)[] args)
    {
        var command=new NpgsqlCommand(sql,db,tx);
        command.Parameters.AddWithValue("org",NpgsqlDbType.Integer,settings.OrganizationId);
        command.Parameters.AddWithValue("branch",NpgsqlDbType.Integer,Branch);
        foreach (var argument in args)
            command.Parameters.Add(argument.Name,argument.Type).Value=argument.Value??DBNull.Value;
        return command;
    }

    private static int[] ReadIds(JsonObject data)=>data["resource_ids"]?.Deserialize<int[]>()??[];
    private static DateTime Wall(DateTime value)=>DateTime.SpecifyKind(value,DateTimeKind.Unspecified);
    private static string Digest(AppointmentDraft draft)
    {
        using var hash=SHA256.Create();
        string serialized=JsonSerializer.Serialize(draft with { Slot=draft.Slot with { Extras=draft.Slot.Extras.OrderBy(id=>id).ToArray() } });
        return BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(serialized))).Replace("-","").ToLowerInvariant();
    }

    private sealed record Current(string Status,int? Customer,DateTime Start,JsonObject Data,bool Grouped,int? Project);
    private sealed record Service(int Id,string Name,decimal Price,decimal Tax,string Currency,JsonObject Metadata);
}
