using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record AppointmentVisitContextRow(string Group, int Id, string Service, string Status, DateTime Starts);
internal sealed record AppointmentCustomerContext(string Customer, string Zone, AppointmentOption? Preferred,
    List<AppointmentVisitContextRow> Visits);

internal sealed partial class AppointmentRepository
{
    internal async Task<AppointmentCustomerContext> CustomerContextAsync(int customer, int? service,
        int? provider, DateTime localStart, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await AuthorizeAsync(db, tx, "view", cancellation);
        using var client = Query(db, tx, Customers + " AND c.id=@id", ("id", NpgsqlDbType.Integer, customer));
        string name;
        using (var row = await client.ExecuteReaderAsync(cancellation))
        {
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("The customer is unavailable in this branch.");
            name = row.GetString(1);
        }
        using var zoneQuery = Query(db, tx, @"SELECT COALESCE(
                (SELECT r.data->>'timezone' FROM public.srm_industry_records r WHERE r.organization_id=@org
                    AND r.branch_id=@branch AND r.kind='resource' AND r.id=@provider AND " + Legacy + @"), 'UTC')",
            ("provider", NpgsqlDbType.Integer, provider));
        string zone = (string)(await zoneQuery.ExecuteScalarAsync(cancellation))!;
        DateTime? start = provider.HasValue && service.HasValue
            ? await UtcAsync(db, tx, Wall(localStart), zone, cancellation) : null;
        const string active = "status IN ('booked','checked_in','in_service')";
        string grouped = @"
            WITH visits AS (
                SELECT r.id,r.status,r.starts_at,r.data FROM public.srm_industry_records r
                WHERE r.organization_id=@org AND r.branch_id=@branch AND r.kind='appointment'
                    AND r.customer_id=@customer AND r.starts_at IS NOT NULL AND " + Legacy + @"
            ), recent AS (
                SELECT * FROM visits WHERE starts_at<now() ORDER BY starts_at DESC,id DESC LIMIT 3
            ), upcoming AS (
                SELECT * FROM visits WHERE starts_at>=now() AND " + active + @" ORDER BY starts_at,id LIMIT 5
            ), duplicates AS (
                SELECT * FROM visits WHERE @service IS NOT NULL AND data->>'service_id'=@service::text AND " + active + @"
                    AND ((@start IS NULL AND starts_at>=now()) OR
                        starts_at BETWEEN @start - interval '2 hour' AND @start + interval '2 hour')
                ORDER BY starts_at,id LIMIT 5
            ), results AS (
                SELECT 0 AS group_rank,'Possible duplicate' AS listing,id,status,starts_at,data FROM duplicates
                UNION ALL SELECT 1,'Upcoming',id,status,starts_at,data FROM upcoming
                UNION ALL SELECT 2,'Recent',id,status,starts_at,data FROM recent
            )
            SELECT listing,id,coalesce(data->>'service_name','Appointment'),
                initcap(replace(status,'_',' ')),starts_at AT TIME ZONE @zone FROM results
            ORDER BY group_rank,CASE WHEN group_rank=2 THEN starts_at END DESC,starts_at,id";
        using var query = Query(db, tx, grouped, ("customer", NpgsqlDbType.Integer, customer),
            ("service", NpgsqlDbType.Integer, service), ("start", NpgsqlDbType.TimestampTz, start),
            ("zone", NpgsqlDbType.Text, zone));
        var visits = new List<AppointmentVisitContextRow>();
        using (var rows = await query.ExecuteReaderAsync(cancellation))
            while (await rows.ReadAsync(cancellation))
                visits.Add(new(rows.GetString(0), rows.GetInt32(1), rows.GetString(2), rows.GetString(3), rows.GetDateTime(4)));

        using var suggested = Query(db, tx, @"
            WITH recent AS (
                SELECT r.id,r.data FROM public.srm_industry_records r WHERE r.organization_id=@org
                    AND r.branch_id=@branch AND r.kind='appointment' AND r.customer_id=@customer
                    AND r.starts_at<now() AND " + Legacy + @" ORDER BY r.starts_at DESC,r.id DESC LIMIT 3
            )
            SELECT r.id,r.title,r.data->>'timezone' FROM recent
            CROSS JOIN LATERAL jsonb_array_elements(CASE WHEN jsonb_typeof(recent.data::jsonb->'resource_ids')='array'
                THEN recent.data::jsonb->'resource_ids' ELSE '[]'::jsonb END) item(value)
            JOIN public.srm_industry_records r ON r.id::text=item.value::text AND r.organization_id=@org
                AND r.branch_id=@branch AND r.kind='resource' AND r.status='active' AND " + Legacy + @"
            WHERE nullif(r.data->>'employee_id','') IS NOT NULL AND r.data->>'timezone' IS NOT NULL
                AND r.data->>'resource_type' IN (" + ProviderTypes + @")
            GROUP BY r.id,r.title,r.data->>'timezone' ORDER BY count(*) DESC,max(recent.id) DESC,r.id LIMIT 1",
            ("customer", NpgsqlDbType.Integer, customer));
        using var preferredRow = await suggested.ExecuteReaderAsync(cancellation);
        AppointmentOption? preferred = await preferredRow.ReadAsync(cancellation)
            ? new(preferredRow.GetInt32(0), preferredRow.GetString(1), preferredRow.GetString(2)) : null;
        return new(name, zone, preferred, visits);
    }
}
