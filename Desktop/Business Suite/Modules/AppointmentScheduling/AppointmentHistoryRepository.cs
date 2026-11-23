using System.Data;
using System.Globalization;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record AppointmentHistoryRow(DateTime? Recorded, string Action, string Status, int? Revision,
    int? Actor, DateTime? Starts, string Reason);
internal sealed record AppointmentHistory(string Title, List<AppointmentHistoryRow> Events);

internal sealed partial class AppointmentRepository
{
    internal async Task<AppointmentHistory> HistoryAsync(int appointmentId, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await AuthorizeAsync(db, tx, "view", cancellation);

        using var record = Query(db, tx, @"SELECT r.title FROM public.srm_industry_records r
            WHERE r.organization_id=@org AND r.branch_id=@branch AND r.kind='appointment'
                AND r.id=@id AND " + Legacy, ("id", NpgsqlDbType.Integer, appointmentId));
        if (await record.ExecuteScalarAsync(cancellation) is not string title)
            throw new InvalidOperationException("The appointment is unavailable in this branch.");

        using var command = Query(db, tx, @"
            SELECT a.created_at,initcap(replace(a.action,'_',' ')),
                initcap(replace(coalesce(a.after_json->>'status',''),'_',' ')),
                a.after_json->>'revision',a.actor_user_id,a.after_json->'data'->>'starts_at',
                coalesce(a.after_json->'data'->>'transition_reason','')
            FROM public.srm_audit_logs a
            WHERE a.organization_id=@org AND a.entity_type='industry_appointment' AND a.entity_id=@id
                AND NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership b
                    WHERE b.resource_table='srm_audit_logs' AND b.resource_key=a.id::text
                    AND (b.company_id<>@org OR b.branch_id<>@branch))
            ORDER BY a.created_at DESC NULLS LAST,a.id DESC LIMIT 250",
            ("id", NpgsqlDbType.Integer, appointmentId));
        using var reader = await command.ExecuteReaderAsync(cancellation);
        var rows = new List<AppointmentHistoryRow>();
        while (await reader.ReadAsync(cancellation))
        {
            int? revision = !reader.IsDBNull(3) && int.TryParse(reader.GetString(3),
                NumberStyles.Integer, CultureInfo.InvariantCulture, out int version) ? version : null;
            DateTime? starts = !reader.IsDBNull(5) && DateTimeOffset.TryParse(reader.GetString(5),
                CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out var appointmentTime)
                ? appointmentTime.LocalDateTime : null;
            rows.Add(new(reader.IsDBNull(0) ? null : reader.GetDateTime(0).ToLocalTime(),
                reader.GetString(1), reader.GetString(2), revision,
                reader.IsDBNull(4) ? null : reader.GetInt32(4), starts, reader.GetString(6)));
        }
        return new(title, rows);
    }
}
