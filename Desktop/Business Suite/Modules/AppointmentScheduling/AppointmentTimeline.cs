using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record AppointmentTimelineSlot(DateTime Starts,string Provider,string Zone,string Status,bool Selectable,int ProviderId,
    DateTime StartUtc,bool Physical,int[] Bookings);
internal sealed record AppointmentTimelinePage(List<AppointmentOption> Providers,List<AppointmentTimelineSlot> Slots,bool CanBook,
    Dictionary<int,AppointmentOption> Bookings);

internal sealed partial class AppointmentRepository
{
    internal Task<AppointmentTimelinePage> ReadProviderTimelineAsync(DateTime date,bool week,int provider,CancellationToken cancellation) =>
        ReadTimelineAsync(date,week,provider,false,cancellation);

    internal async Task<AppointmentTimelinePage> ReadTimelineAsync(DateTime date,bool week,int provider,bool physical,
        CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await AuthorizeAsync(db,tx,"view",cancellation);
        bool canBook=actor.CanWriteBranch && await CanWriteAsync(db,tx,actor,"create");
        string resourceSource=physical ? @"FROM public.srm_industry_records r WHERE r.organization_id=@org AND r.branch_id=@branch
            AND r.kind='resource' AND r.status='active' AND r.data->>'resource_type' IN ("+AssetTypes+") AND "+Legacy
            : EligibilityProviderSource;
        using var sources=Query(db,tx,"SELECT r.id,r.title,r.data->>'timezone' "+resourceSource+@"
            AND EXISTS (SELECT 1 FROM pg_catalog.pg_timezone_names z WHERE z.name=r.data->>'timezone') ORDER BY r.title,r.id");
        var providers=new List<AppointmentOption>();
        using (var rows=await sources.ExecuteReaderAsync(cancellation))
            while (await rows.ReadAsync(cancellation))
                providers.Add(new AppointmentOption(rows.GetInt32(0),rows.GetString(1),rows.GetString(2)));
        if (provider>0 && !providers.Any(item=>item.Id==provider))
            throw new InvalidOperationException(physical ? "The selected resource is unavailable in this branch." :
                "The selected provider is unavailable in this branch.");
        var candidates=provider!=0 ? providers.Where(item=>item.Id==provider) : providers;
        var slots=new List<AppointmentTimelineSlot>();
        foreach (var item in candidates)
        {
            var current=(await LocalAsync(db,tx,DateTime.UtcNow,item.Zone,cancellation)).Date;
            for (int index=0;index<(week?7:1);index++)
            {
                DateTime day=date.Date.AddDays(index);
                if (day<current || day>current.AddDays(90))
                    continue;
                var schedule=await ReadProviderSlotsCoreAsync(db,tx,new AppointmentSlot(day,30,item.Id,[]),null,cancellation,physical);
                slots.AddRange(schedule.Slots.Select(slot=>new AppointmentTimelineSlot(slot.Starts,item.Name,item.Zone,slot.Status,
                    canBook && slot.Selectable,item.Id,slot.StartUtc,physical,slot.Bookings)));
            }
        }
        var bookings=new Dictionary<int,AppointmentOption>();
        int[] bookingIds=slots.SelectMany(slot=>slot.Bookings).Distinct().ToArray();
        if(bookingIds.Length>0)
        {
            using var query=Query(db,tx,@"SELECT r.id,
                COALESCE(NULLIF(r.data->>'customer_name',''),'Customer'),
                COALESCE(NULLIF(r.data->>'service_name',''),'Appointment')
                FROM public.srm_industry_records r WHERE r.organization_id=@org AND r.branch_id=@branch
                AND r.kind='appointment' AND r.id=ANY(@ids) AND "+Legacy,
                ("ids",NpgsqlDbType.Array|NpgsqlDbType.Integer,bookingIds));
            using var rows=await query.ExecuteReaderAsync(cancellation);
            while(await rows.ReadAsync(cancellation))
            {
                int id=rows.GetInt32(0);
                bookings.Add(id,new(id,$"{rows.GetString(1)} · {rows.GetString(2)} (#{id})"));
            }
        }
        return new(providers,slots.OrderBy(slot=>slot.Starts).ThenBy(slot=>slot.Provider,StringComparer.CurrentCultureIgnoreCase).ToList(),canBook,bookings);
    }

    internal async Task<DateTime> TimelineProviderLocalAsync(DateTime startUtc,int provider,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        await AuthorizeAsync(db,tx,"view",cancellation);
        var resource=(await ResourcesAsync(db,tx,[provider],true,cancellation)).Single();
        if (!resource.IsProvider || resource.Status!="active")
            throw new InvalidOperationException("Choose an available provider for the selected time.");
        return await LocalAsync(db,tx,startUtc,resource.Zone,cancellation);
    }
}
