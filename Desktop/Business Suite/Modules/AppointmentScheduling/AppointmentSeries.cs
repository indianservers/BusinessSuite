using System.Data;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record AppointmentSeriesRequest(Guid Request, AppointmentDraft Base, int Count, int Interval, int[] Included);
internal sealed record AppointmentSeriesOccurrence(int Index, DateTime LocalTime, DateTime? StartUtc, string Status)
{
    public bool Available => StartUtc.HasValue;
}
internal sealed record AppointmentSeriesSaved(int Id, int[] Bookings);

internal sealed partial class AppointmentRepository
{
    internal ProtectedAppointmentJournal<AppointmentSeriesRequest> SeriesJournal() =>
        new(settings, "Appointment series recovery", request => ValidateSeries(request, requireSelected: true));

    internal async Task<List<AppointmentSeriesOccurrence>> PreviewSeriesAsync(AppointmentSeriesRequest request,
        CancellationToken cancellation)
    {
        ValidateSeries(request, requireSelected: false);
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await AuthorizeAsync(db, tx, "create", cancellation);
        using (var customer = Query(db, tx, Customers + " AND c.id=@customer",
            ("customer", NpgsqlDbType.Integer, request.Base.Customer)))
            if (await customer.ExecuteScalarAsync(cancellation) is null)
                throw new InvalidOperationException("Choose an active customer.");
        var service = await ReadServiceAsync(db, tx, request.Base.Service, cancellation);
        var result = new List<AppointmentSeriesOccurrence>();
        for (int index = 0; index < request.Count; index++)
        {
            var occurrence = SeriesOccurrence(request, index);
            try
            {
                var booking = await ValidateAsync(db, tx, service, occurrence.Slot, null, cancellation);
                result.Add(new(index, occurrence.Slot.LocalTime, booking.Start, "Available"));
            }
            catch (Exception error) when (error is ArgumentException or InvalidOperationException)
            {
                result.Add(new(index, occurrence.Slot.LocalTime, null, error.Message));
            }
        }
        return result;
    }

    internal async Task<AppointmentSeriesSaved?> CheckSeriesAsync(AppointmentSeriesRequest request, CancellationToken cancellation)
    {
        ValidateSeries(request, requireSelected: true);
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeAsync(db, tx, "view", cancellation);
        return await FindSeriesAsync(db, tx, actor, request, cancellation);
    }

    internal async Task<AppointmentSeriesSaved> SaveSeriesAsync(AppointmentSeriesRequest request, CancellationToken cancellation)
    {
        ValidateSeries(request, requireSelected: true);
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeAsync(db, tx, "create", cancellation);
        if (await FindSeriesAsync(db, tx, actor, request, cancellation) is { } existing)
            return existing;
        var appointments = new List<int>();
        foreach (int index in request.Included.OrderBy(index => index))
            appointments.Add(await CreateInTransactionAsync(db, tx, actor, SeriesOccurrence(request, index), cancellation));
        var data = new JsonObject
        {
            ["appointment_ids"] = JsonSerializer.SerializeToNode(appointments),
            ["_request_digest"] = SeriesDigest(request)
        };
        using var insert = Query(db, tx, @"INSERT INTO public.srm_industry_records
            (organization_id,branch_id,kind,title,status,revision,request_id,created_by,customer_id,data)
            VALUES (@org,@branch,'prebooking_series','Recurring prebooking series','confirmed',1,@request,@actor,@customer,@data)
            RETURNING id", ("request", NpgsqlDbType.Text, request.Request.ToString()), ("actor", NpgsqlDbType.Integer, actor.Id),
            ("customer", NpgsqlDbType.Integer, request.Base.Customer), ("data", NpgsqlDbType.Json, data.ToJsonString()));
        int parent = (int)(await insert.ExecuteScalarAsync(cancellation))!;
        using var audit = Query(db, tx, @"INSERT INTO public.srm_audit_logs
            (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
            VALUES (@org,'industry_prebooking_series',@id,'created',@actor,@after)",
            ("id", NpgsqlDbType.Integer, parent), ("actor", NpgsqlDbType.Integer, actor.Id),
            ("after", NpgsqlDbType.Json, JsonSerializer.Serialize(new { revision = 1, status = "draft", data })));
        await audit.ExecuteNonQueryAsync(cancellation);
        tx.Commit();
        return new(parent, appointments.ToArray());
    }

    private async Task<AppointmentSeriesSaved?> FindSeriesAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        DesktopActor actor, AppointmentSeriesRequest request, CancellationToken cancellation)
    {
        using var command = Query(db, tx, @"SELECT r.id,r.data->>'_request_digest',r.data->'appointment_ids'
            FROM public.srm_industry_records r WHERE r.organization_id=@org AND r.branch_id=@branch
              AND r.kind='prebooking_series' AND r.status='confirmed' AND r.created_by=@actor AND r.request_id=@request
              AND " + Legacy, ("actor", NpgsqlDbType.Integer, actor.Id), ("request", NpgsqlDbType.Text, request.Request.ToString()));
        using var row = await command.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            return null;
        if (row.IsDBNull(1) || row.GetString(1) != SeriesDigest(request) || row.IsDBNull(2))
            throw new InvalidOperationException("This request was saved with different series details.");
        var bookings = JsonSerializer.Deserialize<int[]>(row.GetString(2));
        if (bookings is null || bookings.Length != request.Included.Length)
            throw new InvalidOperationException("The saved series has inconsistent booking references.");
        return new(row.GetInt32(0), bookings);
    }

    private static AppointmentDraft SeriesOccurrence(AppointmentSeriesRequest request, int index)
    {
        using var hash = SHA256.Create();
        var bytes = hash.ComputeHash(Encoding.UTF8.GetBytes(request.Request.ToString("D") + ":" + index));
        byte[] identity = new byte[16];
        Array.Copy(bytes, identity, 16);
        return request.Base with
        {
            Request = new Guid(identity),
            Slot = request.Base.Slot with { LocalTime = request.Base.Slot.LocalTime.AddDays(index * request.Interval) }
        };
    }

    private static string SeriesDigest(AppointmentSeriesRequest request)
    {
        using var hash = SHA256.Create();
        var payload = new { request.Request, Base = Digest(request.Base), request.Count, request.Interval,
            Included = request.Included.OrderBy(index => index).ToArray() };
        return BitConverter.ToString(hash.ComputeHash(JsonSerializer.SerializeToUtf8Bytes(payload))).Replace("-", "").ToLowerInvariant();
    }

    internal static void ValidateSeries(AppointmentSeriesRequest request, bool requireSelected)
    {
        if (request.Request == Guid.Empty || request.Base is null || request.Count is < 2 or > 12 ||
            request.Interval is not (1 or 7 or 14) || request.Included is null ||
            (requireSelected && request.Included.Length == 0) ||
            request.Included.Any(index => index < 0 || index >= request.Count) ||
            request.Included.Distinct().Count() != request.Included.Length)
            throw new ArgumentException("Choose 2 to 12 occurrences and valid dates to reserve.");
        ValidateDraft(request.Base);
        if (request.Base.Project.HasValue || request.Base.Deal.HasValue)
            throw new InvalidOperationException("Confirm appointments with a project or CRM opportunity individually.");
    }
}
