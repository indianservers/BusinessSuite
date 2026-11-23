using System.Data;
using System.Globalization;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record AppointmentSlotChoice(DateTime Starts, string Status, bool Selectable,DateTime StartUtc,int[] Bookings);
internal sealed record AppointmentSlotPage(string Zone, List<AppointmentSlotChoice> Slots);

internal sealed partial class AppointmentRepository
{
    internal Task<AppointmentSlotPage> ProviderSlotsAsync(AppointmentSlot draft, CancellationToken cancellation) =>
        ProviderSlotsAsync(draft, null, cancellation);

    internal async Task<AppointmentSlotPage> ProviderSlotsAsync(AppointmentSlot draft, AppointmentKey? key,
        CancellationToken cancellation)
    {
        if (draft.Provider <= 0 || draft.Minutes is < 5 or > 720)
            throw new ArgumentException("Choose a provider and an appointment duration from 5 to 720 minutes.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeAsync(db, tx, "view", cancellation);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch does not permit booking.");
        await RequireAccessAsync(db, tx, actor, key is null ? "create" : "edit");
        if (key is not null)
        {
            var current = await CurrentAsync(db,tx,key,false,cancellation);
            if (current.Grouped)
            {
                await RequireAccessAsync(db,tx,actor,"create");
                await ReadGroupedScheduleAsync(db,tx,key,false,cancellation);
            }
            else
            {
                CheckReschedule(current);
                await CheckLinkedTaskAsync(db,tx,actor,current,draft.LocalTime.Date,cancellation);
            }
        }
        return await ReadProviderSlotsCoreAsync(db,tx,draft,key?.Id,cancellation);
    }

    private async Task<AppointmentSlotPage> ReadProviderSlotsCoreAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        AppointmentSlot draft,int? ignore,CancellationToken cancellation,bool physical=false)
    {
        var provider = (await ResourcesAsync(db, tx, [draft.Provider], true, cancellation)).Single();
        if ((physical ? !AssetKinds.Contains(provider.Kind) : !provider.IsProvider) || provider.Status!="active")
            throw new InvalidOperationException("The selected scheduling resource is unavailable in this branch.");
        DateTime day = Wall(draft.LocalTime.Date);
        var providerToday = (await LocalAsync(db, tx, DateTime.UtcNow, provider.Zone, cancellation)).Date;
        if (day < providerToday || day > providerToday.AddDays(90))
            throw new InvalidOperationException("Choose a provider date within the next 90 days.");
        int weekday = ((int)day.DayOfWeek + 6) % 7;
        var result = new List<AppointmentSlotChoice>();
        if (provider.Data["opens"] is not JsonValue opening || !opening.TryGetValue<string>(out var openText) ||
            !TimeSpan.TryParse(openText, CultureInfo.InvariantCulture, out var opens) ||
            provider.Data["closes"] is not JsonValue closing || !closing.TryGetValue<string>(out var closeText) ||
            !TimeSpan.TryParse(closeText, CultureInfo.InvariantCulture, out var closes) ||
            opens < TimeSpan.Zero || closes <= opens || closes > TimeSpan.FromDays(1) ||
            provider.Data["weekdays"] is not JsonArray weekdays ||
            !weekdays.Any(value => value is JsonValue dayValue && dayValue.TryGetValue<int>(out int index) && index == weekday))
            return new(provider.Zone, result);

        using var query = Query(db, tx, @"
            WITH potential AS (
                SELECT local,local AT TIME ZONE @zone AS guess
                FROM generate_series(@first,@last,interval '30 minutes') g(local)
            ), candidates AS (
                SELECT local,min(instant) AS instant,count(*) AS resolutions
                FROM potential
                LEFT JOIN LATERAL (
                    SELECT DISTINCT (value AT TIME ZONE @zone)-(value AT TIME ZONE 'UTC') AS offset_delta
                    FROM unnest(ARRAY[guess-interval '1 day',guess,guess+interval '1 day']) sample(value)
                ) offsets ON true
                LEFT JOIN LATERAL (
                    SELECT (local-offset_delta) AT TIME ZONE 'UTC' AS instant
                ) convert ON (convert.instant AT TIME ZONE @zone)=local
                WHERE instant IS NOT NULL GROUP BY local
            )
            SELECT local,instant,ARRAY(
                SELECT r.id FROM public.srm_industry_records r WHERE r.organization_id=@org AND r.branch_id=@branch
                    AND r.kind='appointment' AND r.id IS DISTINCT FROM @ignore AND " + Legacy + @"
                    AND r.status IN ('booked','checked_in','in_service')
                    AND r.starts_at < instant + make_interval(mins => @minutes) AND r.ends_at > instant
                    AND r.data::jsonb->'resource_ids' @> jsonb_build_array(@provider)
                ORDER BY r.starts_at,r.id
            ) AS overlap
            FROM candidates WHERE resolutions=1 AND instant>now()
                AND (instant + make_interval(mins => @minutes)) AT TIME ZONE @zone <= @closing
            ORDER BY local",
            ("zone", NpgsqlDbType.Text, provider.Zone), ("first", NpgsqlDbType.Timestamp, day.Add(opens)),
            ("last", NpgsqlDbType.Timestamp, day.Add(closes).AddTicks(-10)),
            ("closing", NpgsqlDbType.Timestamp, day.Add(closes)), ("provider", NpgsqlDbType.Integer, provider.Id),
            ("minutes", NpgsqlDbType.Integer, draft.Minutes), ("ignore", NpgsqlDbType.Integer, ignore));
        using var rows = await query.ExecuteReaderAsync(cancellation);
        while (await rows.ReadAsync(cancellation))
        {
            var bookings=rows.GetFieldValue<int[]>(2);
            result.Add(new(rows.GetDateTime(0),bookings.Length>0?"Booked":"Check availability",bookings.Length==0,
                rows.GetDateTime(1),bookings));
        }
        return new(provider.Zone, result);
    }
}
