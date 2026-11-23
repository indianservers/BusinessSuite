using System.Data;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record AppointmentRebookSeed(int? Customer,int? Service=null,AppointmentSlot? Slot=null,DateTime? ResourceStartUtc=null);

internal sealed record AppointmentConfirmation(int Id, int Revision, string Status, int? CustomerId,
    string Customer, string Service, string Provider, string Zone, string[] Resources, DateTime Start,
    DateTime End, DateTime LocalStart, DateTime LocalEnd, string CustomerNotes, string CalendarScope,
    int? ServiceId, int? ProviderId, int[] AdditionalResourceIds, DateTime NextDay)
{
    internal string Reference => Id.ToString(CultureInfo.InvariantCulture);
    internal string StatusText => CultureInfo.CurrentCulture.TextInfo.ToTitleCase(Status.Replace('_', ' '));
    internal AppointmentRebookSeed Rebook(bool repeat) => !repeat
        ? new(CustomerId)
        : new(CustomerId, ServiceId, ProviderId is int provider
            ? new AppointmentSlot(NextDay.Add(LocalStart.TimeOfDay), (int)(End - Start).TotalMinutes,
                provider, AdditionalResourceIds)
            : null);
    internal string Summary => string.Join(Environment.NewLine, new[]
    {
        $"Booking #{Reference} · {StatusText}",
        $"Customer: {Customer}" + (CustomerId is int id ? $" · #{id}" : ""),
        $"Service: {Service}",
        $"Provider: {Provider}",
        $"Starts: {LocalStart:g}",
        $"Ends: {LocalEnd:g}",
        $"Timezone: {Zone}",
        $"Resources: {(Resources.Length == 0 ? "None" : string.Join(", ", Resources))}",
        $"Duration: {(End - Start).TotalMinutes:0} minutes"
    }) + (string.IsNullOrWhiteSpace(CustomerNotes) ? "" : Environment.NewLine + Environment.NewLine + CustomerNotes);

    internal string CalendarText(DateTime timestamp)
    {
        using var hash = SHA256.Create();
        string suffix = BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(CalendarScope)), 0, 12).Replace("-", "");
        var lines = new[]
        {
            "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Business Suite//Prebooking//EN", "CALSCALE:GREGORIAN",
            "BEGIN:VEVENT", $"UID:prebooking-{Reference}-{suffix}@business-suite.invalid",
            $"DTSTAMP:{Stamp(timestamp)}", $"DTSTART:{Stamp(Start)}", $"DTEND:{Stamp(End)}",
            $"SUMMARY:{Escape(Service)}",
            $"DESCRIPTION:{Escape($"Booking #{Reference}\n{Customer}\n{Provider}\nBooking timezone: {Zone}")}",
            $"LOCATION:{Escape(string.Join(", ", Resources))}",
            $"SEQUENCE:{Math.Max(0, Revision - 1).ToString(CultureInfo.InvariantCulture)}",
            $"STATUS:{(Status is "cancelled" or "no_show" ? "CANCELLED" : "CONFIRMED")}",
            "END:VEVENT", "END:VCALENDAR"
        };
        return string.Concat(lines.Select(FoldLine));
    }

    internal void SaveCalendar(string path)
    {
        string temporary = Path.Combine(Path.GetDirectoryName(path)!, $".booking-{Guid.NewGuid():N}.tmp");
        try
        {
            File.WriteAllText(temporary, CalendarText(DateTime.UtcNow), new UTF8Encoding(false));
            WindowsCompatibility.ReplaceFile(temporary, path);
        }
        finally
        {
            if (File.Exists(temporary))
                File.Delete(temporary);
        }
    }

    private static string Stamp(DateTime instant) => instant.ToUniversalTime().ToString("yyyyMMdd'T'HHmmss'Z'", CultureInfo.InvariantCulture);

    private static string Escape(string value) => value.Replace("\\", "\\\\").Replace("\r\n", "\n")
        .Replace("\r", "\n").Replace("\n", "\\n").Replace(";", "\\;").Replace(",", "\\,");

    private static string FoldLine(string line)
    {
        var result = new StringBuilder();
        int octets = 0;
        for (int i = 0; i < line.Length;)
        {
            int length = char.IsSurrogatePair(line, i) ? 2 : 1;
            string character = line.Substring(i, length);
            int width = Encoding.UTF8.GetByteCount(character);
            if (octets + width > 75)
            {
                result.Append("\r\n ");
                octets = 1;
            }
            result.Append(character);
            octets += width;
            i += length;
        }
        return result.Append("\r\n").ToString();
    }
}

internal sealed partial class AppointmentRepository
{
    internal async Task<(string Email, string Phone)> ConfirmationRecipientAsync(int customer, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await AuthorizeAsync(db, tx, "view", cancellation);
        using var command = Query(db, tx, "SELECT coalesce(c.email,''),coalesce(c.phone,''),coalesce(c.phone_country_code,'')"
            + CustomerScope + " AND c.id=@customer", ("customer", NpgsqlDbType.Integer, customer));
        using var row = await command.ExecuteReaderAsync(cancellation);
        return await row.ReadAsync(cancellation)
            ? (row.GetString(0), AppointmentMessageDraft.InternationalPhone(row.GetString(1), row.GetString(2)))
            : ("", "");
    }

    internal async Task<AppointmentConfirmation> ConfirmationAsync(int id, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await AuthorizeAsync(db, tx, "view", cancellation);
        int revision;
        int? customer;
        string status;
        DateTime start, end;
        JsonObject data;
        using (var command = Query(db, tx, @"SELECT r.revision,r.status,r.customer_id,r.starts_at,r.ends_at,r.data::text
                FROM public.srm_industry_records r WHERE r.organization_id=@org AND r.branch_id=@branch
                AND r.kind='appointment' AND r.id=@id AND " + Legacy, ("id", NpgsqlDbType.Integer, id)))
        using (var row = await command.ExecuteReaderAsync(cancellation))
        {
            if (!await row.ReadAsync(cancellation) || row.IsDBNull(3) || row.IsDBNull(4))
                throw new InvalidOperationException("The appointment schedule is unavailable in this branch.");
            revision = row.GetInt32(0);
            status = row.GetString(1);
            customer = row.IsDBNull(2) ? null : row.GetInt32(2);
            start = row.GetDateTime(3);
            end = row.GetDateTime(4);
            data = JsonNode.Parse(row.GetString(5))!.AsObject();
        }
        int[] ids = ReadIds(data);
        var resources = (await ResourcesAsync(db, tx, ids, true, cancellation))
            .OrderBy(resource => Array.IndexOf(ids, resource.Id)).ToArray();
        var provider = resources.FirstOrDefault(resource => resource.IsProvider);
        string zone = provider?.Zone ?? "UTC";
        var localStart = await LocalAsync(db, tx, start, zone, cancellation);
        var localEnd = await LocalAsync(db, tx, end, zone, cancellation);
        var nextDay = (await LocalAsync(db, tx, DateTime.UtcNow, zone, cancellation)).Date.AddDays(1);
        var additional = resources.Where(resource => resource != provider).ToArray();
        var endpoint = new NpgsqlConnectionStringBuilder(settings.ConnectionString);
        string scope = string.Join(":", settings.ExpectedAddress, endpoint.Port, endpoint.Database,
            settings.OrganizationId, settings.BranchId);
        return new(id, revision, status, customer, data["customer_name"]?.GetValue<string>() ?? "",
            data["service_name"]?.GetValue<string>() ?? "Appointment", provider?.Name ?? "Provider unavailable",
            zone, additional.Select(resource => resource.Name).ToArray(),
            start, end, localStart, localEnd, data["customer_notes"]?.GetValue<string>() ?? "", scope,
            data["service_id"]?.GetValue<int>(), provider?.Id, additional.Select(resource => resource.Id).ToArray(), nextDay);
    }
}
