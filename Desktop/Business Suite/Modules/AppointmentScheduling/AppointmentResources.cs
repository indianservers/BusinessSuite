using System.Data;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record AppointmentResourceDraft(string Name,string Type,string Status,int Capacity,string Zone,int[] Weekdays,
    TimeSpan Opens,TimeSpan Closes,string Location,string Accessibility,string Facilities,string Color,int? Employee,Guid Request);
internal sealed record AppointmentResourcePage(DataTable Rows,List<AppointmentOption> Employees,List<string> Zones,bool CanCreate,bool CanEdit);

internal sealed partial class AppointmentRepository
{
    private static readonly string[] ProviderKinds=["provider","doctor","stylist","consultant","technician","employee"];
    private static readonly string[] AssetKinds=["chair","room","equipment","location"];
    private static readonly string[] ResourceColors=["Lavender","Blue","Mint","Peach","Rose","Slate"];

    internal async Task<AppointmentResourcePage> ReadAppointmentResourcesAsync(CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await AuthorizeAsync(db,tx,"view",cancellation);
        bool canCreate=actor.CanWriteBranch && await CanWriteAsync(db,tx,actor,"create");
        bool canEdit=actor.CanWriteBranch && await CanWriteAsync(db,tx,actor,"edit");
        using var query=Query(db,tx,@"SELECT r.id,r.revision,r.title,r.status,r.data->>'resource_type' AS resource_type,
            r.data->>'timezone' AS timezone,r.data->>'opens' AS opens,r.data->>'closes' AS closes,r.data::text AS metadata
            FROM public.srm_industry_records r WHERE r.organization_id=@org AND r.branch_id=@branch
                AND r.kind='resource' AND "+Legacy+" ORDER BY r.status='archived',r.title,r.id");
        var table=new DataTable();
        using (var rows=await query.ExecuteReaderAsync(cancellation))
        {
            for(int i=0;i<rows.FieldCount;i++) table.Columns.Add(rows.GetName(i),rows.GetFieldType(i));
            while(await rows.ReadAsync(cancellation))
            {
                var values=new object[rows.FieldCount];
                rows.GetValues(values);
                table.Rows.Add(values);
            }
        }
        var people=new List<AppointmentOption>();
        if (canCreate)
        {
            using var employees=Query(db,tx,@"SELECT e.id,concat(e.employee_id,' · ',e.first_name,' ',e.last_name)
                FROM public.employees e JOIN public.branches b ON b.id=e.branch_id AND b.company_id=@org
                WHERE e.branch_id=@branch AND e.deleted_at IS NULL AND e.status IN ('Active','Probation','On Leave')
                ORDER BY e.first_name,e.last_name,e.id");
            using var rows=await employees.ExecuteReaderAsync(cancellation);
            while(await rows.ReadAsync(cancellation)) people.Add(new(rows.GetInt32(0),rows.GetString(1)));
        }
        using var timezones=Query(db,tx,"SELECT name FROM pg_catalog.pg_timezone_names WHERE name NOT LIKE 'posix/%' ORDER BY name");
        var zones=new List<string>();
        using (var rows=await timezones.ExecuteReaderAsync(cancellation))
            while(await rows.ReadAsync(cancellation)) zones.Add(rows.GetString(0));
        return new(table,people,zones,canCreate,canEdit);
    }

    internal async Task<int> SaveAppointmentResourceAsync(AppointmentKey? key,AppointmentResourceDraft draft,CancellationToken cancellation)
    {
        draft=draft with {Name=draft.Name.Trim(),Weekdays=draft.Weekdays.OrderBy(day=>day).ToArray()};
        bool provider=ProviderKinds.Contains(draft.Type);
        if (draft.Name.Length is <1 or >220 || (!provider && !AssetKinds.Contains(draft.Type)) ||
            draft.Status is not ("active" or "inactive" or "maintenance" or "archived") ||
            (key is null && (draft.Status=="archived" || draft.Request==Guid.Empty)) ||
            (draft.Employee.HasValue && !provider) || (key is null && provider && !draft.Employee.HasValue) ||
            draft.Capacity is <1 or >1000 || (provider && draft.Capacity!=1) ||
            draft.Weekdays.Length is <1 or >7 || draft.Weekdays.Distinct().Count()!=draft.Weekdays.Length ||
            draft.Weekdays.Any(day=>day is <0 or >6) || draft.Opens<TimeSpan.Zero ||
            draft.Closes>=TimeSpan.FromDays(1) || draft.Closes<=draft.Opens ||
            draft.Location.Length>300 || draft.Accessibility.Length>500 || draft.Facilities.Length>1000 || !ResourceColors.Contains(draft.Color))
            throw new InvalidOperationException("Enter a valid resource, capacity, opening days and hours, and provider employee.");

        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await AuthorizeAsync(db,tx,key is null ? "create" : "edit",cancellation);
        using (var zone=Query(db,tx,"SELECT 1 FROM pg_catalog.pg_timezone_names WHERE name=@zone",("zone",NpgsqlDbType.Text,draft.Zone)))
            if (await zone.ExecuteScalarAsync(cancellation) is null)
                throw new InvalidOperationException("Choose a valid scheduling timezone.");

        string hash;
        using (var sha=SHA256.Create())
            hash=BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(JsonSerializer.Serialize(draft)))).Replace("-","").ToLowerInvariant();

        if (key is null)
        {
            using var prior=Query(db,tx,@"SELECT r.id,r.kind,r.data->>'_request_digest',r.created_by FROM public.srm_industry_records r
                WHERE r.organization_id=@org AND r.branch_id=@branch AND r.request_id=@request AND "+Legacy,
                ("request",NpgsqlDbType.Text,draft.Request.ToString()));
            using var found=await prior.ExecuteReaderAsync(cancellation);
            if (await found.ReadAsync(cancellation))
            {
                if (found.GetString(1)!="resource" || found.IsDBNull(2) || found.GetString(2)!=hash ||
                    found.IsDBNull(3) || found.GetInt32(3)!=actor.Id)
                    throw new InvalidOperationException("This resource request already has different recorded details.");
                return found.GetInt32(0);
            }
        }

        using (var duplicates=Query(db,tx,@"SELECT EXISTS(SELECT 1 FROM public.srm_industry_records r
            WHERE r.organization_id=@org AND r.branch_id=@branch AND r.kind='resource' AND r.title=@title
                AND r.status<>'archived' AND r.id IS DISTINCT FROM @id AND "+Legacy+")",
            ("title",NpgsqlDbType.Text,draft.Name),("id",NpgsqlDbType.Integer,key?.Id)))
            if (await duplicates.ExecuteScalarAsync(cancellation) is true)
                throw new InvalidOperationException("A resource with this name already exists in this branch.");

        JsonObject data;
        if (key is null)
        {
            data=new JsonObject { ["_request_digest"]=hash,["initial_status"]=draft.Status,["employee_id"]=draft.Employee };
            if (draft.Employee is int employee)
            {
                using var staff=Query(db,tx,@"SELECT e.user_id FROM public.employees e JOIN public.branches b ON b.id=e.branch_id
                    WHERE e.id=@employee AND e.branch_id=@branch AND b.company_id=@org AND b.is_active
                    AND e.deleted_at IS NULL AND e.status IN ('Active','Probation','On Leave') FOR SHARE OF e",
                    ("employee",NpgsqlDbType.Integer,employee));
                object? login=await staff.ExecuteScalarAsync(cancellation);
                if (login is null)
                    throw new InvalidOperationException("Choose an active HRMS employee in this branch.");
                data["user_id"]=login is int user ? user : (int?)null;
            }
        }
        else
        {
            using var current=Query(db,tx,@"SELECT r.data::text FROM public.srm_industry_records r
                WHERE r.organization_id=@org AND r.branch_id=@branch AND r.kind='resource' AND r.id=@id
                    AND r.revision=@revision AND "+Legacy+" FOR UPDATE",
                ("id",NpgsqlDbType.Integer,key.Id),("revision",NpgsqlDbType.Integer,key.Revision));
            if (await current.ExecuteScalarAsync(cancellation) is not string json)
                throw new InvalidOperationException("The resource changed or is outside this branch. Refresh first.");
            data=JsonNode.Parse(json)!.AsObject();
            string priorType=data["resource_type"]?.GetValue<string>() ?? "";
            if (data["employee_id"]?.GetValue<int>()!=draft.Employee || ((provider || ProviderKinds.Contains(priorType)) && priorType!=draft.Type))
                throw new InvalidOperationException("Manage provider identity changes through HRMS and service eligibility.");
            bool changed=priorType!=draft.Type || (data["capacity"]?.GetValue<int>() ?? 1)!=draft.Capacity ||
                data["timezone"]?.GetValue<string>()!=draft.Zone || !ExistingTime("opens").Equals(draft.Opens) ||
                !ExistingTime("closes").Equals(draft.Closes) ||
                !(data["weekdays"]?.Deserialize<int[]>() ?? []).OrderBy(day=>day).SequenceEqual(draft.Weekdays);
            if (changed || draft.Status=="archived")
            {
                using var occupied=Query(db,tx,@"SELECT EXISTS(SELECT 1 FROM public.srm_industry_records ap
                    WHERE ap.organization_id=@org AND ap.branch_id=@branch AND ap.kind='appointment'
                        AND ap.status IN ('booked','checked_in','in_service') AND ap.ends_at>now()
                        AND (ap.data->'resource_ids')::jsonb @> jsonb_build_array(@id))",("id",NpgsqlDbType.Integer,key.Id));
                if (await occupied.ExecuteScalarAsync(cancellation) is true)
                    throw new InvalidOperationException("This resource has upcoming bookings. Reschedule them before changing scheduling rules or archiving it.");
            }

            TimeSpan ExistingTime(string name) =>
                TimeSpan.TryParse(data[name]?.ToString(),CultureInfo.InvariantCulture,out TimeSpan value)
                    ? TimeSpan.FromMinutes((int)value.TotalMinutes) : TimeSpan.MinValue;
        }

        data["resource_type"]=draft.Type;
        data["capacity"]=draft.Capacity;
        data["timezone"]=draft.Zone;
        data["weekdays"]=JsonSerializer.SerializeToNode(draft.Weekdays);
        data["opens"]=draft.Opens.ToString(@"hh\:mm\:ss",CultureInfo.InvariantCulture);
        data["closes"]=draft.Closes.ToString(@"hh\:mm\:ss",CultureInfo.InvariantCulture);
        data["location"]=draft.Location;
        data["accessibility"]=draft.Accessibility;
        data["facilities"]=draft.Facilities;
        data["assigned_color"]=draft.Color;

        string sql=key is null ? @"INSERT INTO public.srm_industry_records
            (organization_id,branch_id,kind,title,status,revision,request_id,data,created_by)
            VALUES(@org,@branch,'resource',@title,@status,1,@request,@data,@actor) RETURNING id"
            : @"UPDATE public.srm_industry_records SET title=@title,status=@status,data=@data,
                revision=revision+1,updated_at=now() WHERE id=@id AND organization_id=@org AND branch_id=@branch
                AND revision=@revision RETURNING id";
        using var write=Query(db,tx,sql,("id",NpgsqlDbType.Integer,key?.Id),("revision",NpgsqlDbType.Integer,key?.Revision),
            ("title",NpgsqlDbType.Text,draft.Name),("status",NpgsqlDbType.Text,draft.Status),
            ("request",NpgsqlDbType.Text,draft.Request.ToString()),("actor",NpgsqlDbType.Integer,actor.Id),("data",NpgsqlDbType.Json,data.ToJsonString()));
        if (await write.ExecuteScalarAsync(cancellation) is not int id)
            throw new InvalidOperationException("The resource changed. Refresh before saving.");
        await AuditAsync(db,tx,actor.Id,id,key is null ? "created" : draft.Status=="archived" ? "resource_archived" : "resource_updated",
            draft.Status,(key?.Revision ?? 0)+1,data,cancellation,kind:"resource");
        await tx.CommitAsync(cancellation);
        return id;
    }
}
