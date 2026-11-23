using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class AppointmentRepository
{
    private async Task<Booking> ValidateAsync(NpgsqlConnection db,NpgsqlTransaction tx,Service service,
        AppointmentSlot slot,int? ignore,CancellationToken cancellation)
    {
        int[] ids=[slot.Provider,..slot.Extras];
        if (ids.Length>10||ids.Any(id=>id<=0)||ids.Distinct().Count()!=ids.Length||slot.Minutes<5||slot.Minutes>720)
            throw new ArgumentException("Choose one provider, distinct resources, and a duration from 5 to 720 minutes.");
        var resources=await ResourcesAsync(db,tx,ids,true,cancellation);
        var provider=resources.Single(resource=>resource.Id==slot.Provider);
        if (!provider.IsProvider||!provider.Employee.HasValue||resources.Count(resource=>resource.IsProvider)!=1||
            resources.Any(resource=>!resource.IsProvider&&resource.Kind is not ("room" or "chair" or "equipment" or "location")))
            throw new InvalidOperationException("Choose an HRMS-linked provider and eligible additional resources.");
        DateTime start=await UtcAsync(db,tx,Wall(slot.LocalTime),provider.Zone,cancellation);
        DateTime end=start.AddMinutes(slot.Minutes);
        var today=(await LocalAsync(db,tx,DateTime.UtcNow,provider.Zone,cancellation)).Date;
        if (start<=DateTime.UtcNow||slot.LocalTime.Date>today.AddDays(90))
            throw new InvalidOperationException("Choose a future appointment time within 90 days.");
        var policy=await RulesAsync(db,tx,service,provider,resources,slot.Minutes,start,end,cancellation);
        foreach (var resource in resources)
        {
            var begins=await LocalAsync(db,tx,start,resource.Zone,cancellation);
            var ends=await LocalAsync(db,tx,end,resource.Zone,cancellation);
            var opens=TimeSpan.Parse(resource.Data["opens"]!.GetValue<string>(),CultureInfo.InvariantCulture);
            var closes=TimeSpan.Parse(resource.Data["closes"]!.GetValue<string>(),CultureInfo.InvariantCulture);
            int day=((int)begins.DayOfWeek+6)%7;
            if (resource.Status!="active"||begins.Date!=ends.Date||begins.TimeOfDay<opens||ends.TimeOfDay>closes||
                closes<=opens||!resource.Data["weekdays"]!.AsArray().Any(value=>value?.GetValue<int>()==day))
                throw new InvalidOperationException($"{resource.Name} is outside opening hours.");
            if (resource.Employee is int employee)
                await EmployeeAsync(db,tx,resource,employee,begins.Date,ends.Date,policy.Categories,cancellation);
        }
        await OverlapAsync(db,tx,resources,start,end,ignore,cancellation);
        return new(start,end,policy,provider.Kind);
    }

    private async Task<List<Resource>> ResourcesAsync(NpgsqlConnection db,NpgsqlTransaction tx,int[] ids,bool currentBranch,
        CancellationToken cancellation)
    {
        using var query=Query(db,tx,@"SELECT r.id,r.title,r.status,r.branch_id,r.data::text
            FROM public.srm_industry_records r JOIN public.branches b ON b.id=r.branch_id AND b.company_id=@org
            WHERE r.organization_id=@org AND r.kind='resource' AND r.id=ANY(@ids)"+
            (currentBranch?" AND r.branch_id=@branch AND "+Legacy:""),
            ("ids",NpgsqlDbType.Array|NpgsqlDbType.Integer,ids));
        using var reader=await query.ExecuteReaderAsync(cancellation);
        var resources=new List<Resource>();
        while (await reader.ReadAsync(cancellation))
        {
            var data=JsonNode.Parse(reader.GetString(4))!.AsObject();
            int capacity=data["capacity"]?.GetValue<int>()??1;
            if (capacity<1||capacity>1000)
                throw new InvalidOperationException("A scheduling resource has invalid capacity.");
            resources.Add(new(reader.GetInt32(0),reader.GetString(1),reader.GetString(2),reader.GetInt32(3),
                data["resource_type"]!.GetValue<string>(),data["timezone"]!.GetValue<string>(),capacity,
                data["employee_id"]?.GetValue<int>(),data["user_id"]?.GetValue<int>(),data));
        }
        if (resources.Count!=ids.Length)
            throw new InvalidOperationException("A scheduling resource is unavailable.");
        return resources;
    }

    private async Task<Policy> RulesAsync(NpgsqlConnection db,NpgsqlTransaction tx,Service service,Resource provider,
        List<Resource> resources,int minutes,DateTime start,DateTime end,CancellationToken cancellation)
    {
        using var command=Query(db,tx,@"SELECT p.id,p.revision,p.default_duration_minutes,p.min_duration_minutes,
            p.max_duration_minutes,p.allow_duration_override,p.employee_categories::text,e.id,e.revision
            FROM public.srm_service_booking_policies p
            JOIN public.srm_service_specialist_eligibility e ON e.booking_policy_id=p.id AND e.organization_id=@org
                AND e.branch_id=@branch AND e.pack_context_id IS NULL AND e.active AND e.service_product_id=p.service_product_id
            WHERE p.organization_id=@org AND p.branch_id=@branch AND p.pack_context_id IS NULL AND p.service_product_id=@service
                AND p.active AND e.provider_resource_id=@provider AND (e.effective_from IS NULL OR e.effective_from<=@start)
                AND (e.effective_until IS NULL OR e.effective_until>=@end) FOR SHARE OF p,e",
            ("service",NpgsqlDbType.Integer,service.Id),("provider",NpgsqlDbType.Integer,provider.Id),
            ("start",NpgsqlDbType.TimestampTz,start),("end",NpgsqlDbType.TimestampTz,end));
        using var reader=await command.ExecuteReaderAsync(cancellation);
        if (!await reader.ReadAsync(cancellation))
            throw new InvalidOperationException("This provider is ineligible for the service or time. Check scheduling settings.");
        if (minutes<reader.GetInt32(3)||minutes>reader.GetInt32(4)||(!reader.GetBoolean(5)&&minutes!=reader.GetInt32(2)))
            throw new InvalidOperationException($"Choose a duration allowed by the service policy. Default: {reader.GetInt32(2)} minutes.");
        int policyId=reader.GetInt32(0);
        var required=service.Metadata["service_resource_requirements"]?[policyId.ToString(CultureInfo.InvariantCulture)]?.AsArray();
        string[] missing=required?.Select(value=>value!.GetValue<string>())
            .Except(resources.Select(resource=>resource.Kind)).ToArray()??[];
        if (missing.Length>0)
            throw new InvalidOperationException("Missing required service resources: "+string.Join(", ",missing)+".");
        return new(policyId,reader.GetInt32(1),reader.GetInt32(7),reader.GetInt32(8),provider.Employee!.Value,
            JsonSerializer.Deserialize<string[]>(reader.GetString(6))??[]);
    }

    private async Task EmployeeAsync(NpgsqlConnection db,NpgsqlTransaction tx,Resource resource,int employee,
        DateTime start,DateTime end,string[] categories,CancellationToken cancellation)
    {
        using var command=Query(db,tx,@"SELECT e.date_of_exit,e.work_categories::text,e.user_id, EXISTS (
            SELECT 1 FROM public.leave_requests l WHERE l.company_id=@org AND l.employee_id=e.id
                AND l.status='Approved' AND l.deleted_at IS NULL AND (l.from_date IS NULL OR l.to_date IS NULL
                    OR l.from_date>l.to_date OR (l.from_date<=@end AND l.to_date>=@start)))
            FROM public.employees e WHERE e.id=@employee AND e.branch_id=@branch AND e.deleted_at IS NULL
                AND e.status IN ('Active','Probation','On Leave')",
            ("employee",NpgsqlDbType.Integer,employee),("start",NpgsqlDbType.Date,start),("end",NpgsqlDbType.Date,end));
        using var reader=await command.ExecuteReaderAsync(cancellation);
        if (!await reader.ReadAsync(cancellation)||(!reader.IsDBNull(0)&&reader.GetDateTime(0)<=start)||reader.GetBoolean(3)||
            (resource.User.HasValue&&(reader.IsDBNull(2)||reader.GetInt32(2)!=resource.User)))
            throw new InvalidOperationException($"{resource.Name} is unavailable for this appointment.");
        if (resource.IsProvider&&categories.Length>0)
        {
            string[] values=reader.IsDBNull(1)?[]:JsonSerializer.Deserialize<string[]>(reader.GetString(1))??[];
            if (!MatchesProviderCategories(values,categories))
                throw new InvalidOperationException("The provider no longer belongs to an eligible service category.");
        }
    }
    private async Task OverlapAsync(NpgsqlConnection db,NpgsqlTransaction tx,List<Resource> resources,
        DateTime start,DateTime end,int? ignore,CancellationToken cancellation)
    {
        using var query=Query(db,tx,@"SELECT r.branch_id,r.starts_at,r.ends_at,(r.data->'resource_ids')::text
            FROM public.srm_industry_records r WHERE r.organization_id=@org AND r.kind='appointment'
                AND r.status IN ('booked','checked_in','in_service') AND r.id IS DISTINCT FROM @ignore
                AND (r.starts_at IS NULL OR r.ends_at IS NULL OR r.starts_at>=r.ends_at OR (r.starts_at<@end AND r.ends_at>@start))",
            ("ignore",NpgsqlDbType.Integer,ignore),("start",NpgsqlDbType.TimestampTz,start),("end",NpgsqlDbType.TimestampTz,end));
        var bookings=new List<(int Branch,DateTime Start,DateTime End,int[] Ids)>();
        using (var reader=await query.ExecuteReaderAsync(cancellation))
        {
            while (await reader.ReadAsync(cancellation))
            {
                if (reader.IsDBNull(1)||reader.IsDBNull(2)||reader.IsDBNull(3)||reader.GetDateTime(1)>=reader.GetDateTime(2))
                    throw new InvalidOperationException("Existing scheduling data needs review before booking.");
                var ids=JsonSerializer.Deserialize<int[]>(reader.GetString(3))??[];
                if (ids.Length==0||ids.Any(id=>id<=0)||ids.Distinct().Count()!=ids.Length)
                    throw new InvalidOperationException("Existing scheduling data needs review before booking.");
                bookings.Add((reader.GetInt32(0),reader.GetDateTime(1),reader.GetDateTime(2),ids));
            }
        }
        if (bookings.Count==0)
            return;

        var historical=(await ResourcesAsync(db,tx,bookings.SelectMany(booking=>booking.Ids).Distinct().ToArray(),
            false,cancellation)).ToDictionary(resource=>resource.Id);
        var employees=new HashSet<int>(resources.Where(resource=>resource.Employee.HasValue).Select(resource=>resource.Employee!.Value));
        var users=new HashSet<int>(resources.Where(resource=>resource.User.HasValue).Select(resource=>resource.User!.Value));
        foreach (var booking in bookings)
        {
            foreach (int id in booking.Ids)
            {
                var prior=historical[id];
                if (prior.Branch!=booking.Branch)
                    throw new InvalidOperationException("An existing resource belongs to a different branch.");
                if ((prior.Employee is int employee&&employees.Contains(employee))||(prior.User is int user&&users.Contains(user)))
                    throw new InvalidOperationException("A selected provider is already booked at this time.");
            }
        }
        foreach (var resource in resources)
        {
            var events=bookings.Where(booking=>booking.Ids.Contains(resource.Id))
                .SelectMany(booking=>new[] { (At:booking.Start<start?start:booking.Start,Delta:1),
                    (At:booking.End>end?end:booking.End,Delta:-1) }).OrderBy(point=>point.At).ThenBy(point=>point.Delta);
            int occupied=0;
            foreach (var point in events)
            {
                occupied+=point.Delta;
                if (occupied>=resource.Capacity)
                    throw new InvalidOperationException($"{resource.Name} is already booked at this time.");
            }
        }
    }

    private static void Apply(JsonObject data,Booking booking,AppointmentSlot slot)
    {
        data["starts_at"]=booking.Start.ToString("o",CultureInfo.InvariantCulture);
        data["duration_minutes"]=slot.Minutes;
        data["resource_ids"]=JsonSerializer.SerializeToNode(new[] {slot.Provider}.Concat(slot.Extras));
        data["booking"]=JsonSerializer.SerializeToNode(new {
            policy_id=booking.Policy.Id,expected_policy_revision=booking.Policy.Revision,eligibility_id=booking.Policy.Eligibility,
            expected_eligibility_revision=booking.Policy.EligibilityRevision,employee_id=booking.Policy.Employee,
            provider_resource_id=slot.Provider,additional_resource_ids=slot.Extras,
            starts_at=booking.Start.ToString("o",CultureInfo.InvariantCulture),duration_minutes=slot.Minutes
        });
    }

    private async Task<DateTime> UtcAsync(NpgsqlConnection db,NpgsqlTransaction tx,DateTime local,string zone,
        CancellationToken cancellation)
    {
        using var command=Query(db,tx,@"WITH local_input AS (
            SELECT @local AS wall,(@local AT TIME ZONE @zone) AS guess
        ), offsets AS (
            SELECT DISTINCT (value AT TIME ZONE @zone)-(value AT TIME ZONE 'UTC') AS utc_offset
            FROM local_input, LATERAL unnest(ARRAY[guess-interval '1 day',guess,guess+interval '1 day']) AS sample(value)
        ), candidates AS (SELECT (wall-utc_offset) AT TIME ZONE 'UTC' AS instant,wall FROM local_input,offsets)
        SELECT instant FROM candidates WHERE instant AT TIME ZONE @zone=wall",
            ("local",NpgsqlDbType.Timestamp,local),("zone",NpgsqlDbType.Text,zone));
        using var reader=await command.ExecuteReaderAsync(cancellation);
        if (!await reader.ReadAsync(cancellation))
            throw new InvalidOperationException("This local time does not exist in the provider's timezone.");
        DateTime instant=reader.GetDateTime(0);
        if (await reader.ReadAsync(cancellation))
            throw new InvalidOperationException("This local time occurs twice in the provider's timezone. Choose another time.");
        return instant;
    }

    private async Task<DateTime> LocalAsync(NpgsqlConnection db,NpgsqlTransaction tx,DateTime instant,string zone,
        CancellationToken cancellation)
    {
        using var command=Query(db,tx,"SELECT @instant AT TIME ZONE @zone",
            ("instant",NpgsqlDbType.TimestampTz,instant),("zone",NpgsqlDbType.Text,zone));
        return (DateTime)(await command.ExecuteScalarAsync(cancellation))!;
    }

    private sealed record Booking(DateTime Start,DateTime End,Policy Policy,string ProviderKind);
    private sealed record Policy(int Id,int Revision,int Eligibility,int EligibilityRevision,int Employee,string[] Categories);
    private sealed record Resource(int Id,string Name,string Status,int Branch,string Kind,string Zone,
        int Capacity,int? Employee,int? User,JsonObject Data)
    {
        internal bool IsProvider=>Kind is "provider" or "doctor" or "stylist" or "consultant" or "technician" or "employee";
    }
}
