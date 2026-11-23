using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal enum DealForecastGroup { Month,Quarter,Owner,Stage,Pipeline }
internal sealed record DealForecast(DataRow Counts,DataTable Currencies,DataTable Groups);

internal sealed partial class CrmDealRepository
{
    internal async Task<DealForecast> ForecastAsync(string search,string status,bool archived,CrmDealFilters filters,
        DealForecastGroup grouping,CancellationToken cancellation)
    {
        filters.Validate();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        await RequireDealsAsync(db,tx,actor,archived);
        var (from,parameters)=await FilteredDealDataAsync(db,tx,actor,search,status,archived,filters,[]);
        string data=@"WITH scoped AS (
            SELECT d.organization_id,d.status,d.currency,d.amount,d.probability,d.expected_close_date,
                d.owner_user_id,d.pipeline_id,d.stage_id,pi.name AS pipeline,st.name AS stage,
                COALESCE(d.actual_close_date,(d.closed_at AT TIME ZONE 'UTC')::date) AS closed_day,
                (d.created_at AT TIME ZONE 'UTC')::date AS created_day,d.next_follow_up_at,d.last_activity_at"+from+@"
        ) ";
        using var count=Query(db,tx,data+@"SELECT
            count(*) FILTER (WHERE status='Open') AS opened,
            count(*) FILTER (WHERE status='Open' AND date_trunc('month',expected_close_date)=date_trunc('month',now() AT TIME ZONE 'UTC')) AS closing_month,
            count(*) FILTER (WHERE status='Won' AND date_trunc('month',closed_day)=date_trunc('month',now() AT TIME ZONE 'UTC')) AS won_month,
            count(*) FILTER (WHERE status='Lost' AND date_trunc('month',closed_day)=date_trunc('month',now() AT TIME ZONE 'UTC')) AS lost_month,
            count(*) FILTER (WHERE status='Open' AND next_follow_up_at<now()) AS overdue,
            count(*) FILTER (WHERE status='Open' AND next_follow_up_at IS NULL) AS missing_action,
            count(*) FILTER (WHERE status='Open' AND last_activity_at IS NULL) AS missing_activity,
            round(100.0*count(*) FILTER (WHERE status='Won')/NULLIF(count(*) FILTER (WHERE status IN ('Won','Lost')),0),2) AS win_rate
            FROM scoped",parameters);
        var counts=await ReadAsync(count,cancellation);
        using var money=Query(db,tx,data+@"SELECT COALESCE(NULLIF(currency,''),'Unknown') AS currency,
            count(*) FILTER (WHERE status='Open') AS opened,
            COALESCE(sum(amount) FILTER (WHERE status='Open'),0) AS open_value,
            COALESCE(sum(amount*probability/100.0) FILTER (WHERE status='Open'),0) AS weighted,
            COALESCE(sum(amount) FILTER (WHERE status='Won'),0) AS won,
            COALESCE(sum(amount) FILTER (WHERE status='Lost'),0) AS lost,
            round(COALESCE(avg(amount),0),2) AS average_size,
            round(avg(closed_day-created_day) FILTER (WHERE status IN ('Won','Lost') AND closed_day>=created_day),2) AS cycle_days
            FROM scoped GROUP BY COALESCE(NULLIF(currency,''),'Unknown') ORDER BY currency",parameters);
        var currencies=await ReadAsync(money,cancellation);
        (string Label,string Number,string Period,string Join)=grouping switch
        {
            DealForecastGroup.Month=>("COALESCE(to_char(expected_close_date,'YYYY-MM'),'Unscheduled')","NULL::int",
                "date_trunc('month',expected_close_date)::date",""),
            DealForecastGroup.Quarter=>(@"COALESCE(to_char(expected_close_date,'YYYY-""Q""Q'),'Unscheduled')","NULL::int",
                "date_trunc('quarter',expected_close_date)::date",""),
            DealForecastGroup.Owner=>("COALESCE(NULLIF(person.display_name,''),'Owner #'||scoped.owner_user_id::text,'Unassigned')",
                "scoped.owner_user_id","NULL::date","LEFT JOIN public.common_people person ON person.user_id=scoped.owner_user_id AND person.organization_id=@org"),
            DealForecastGroup.Stage=>("COALESCE(stage,'Stage #'||stage_id::text)","stage_id","NULL::date",""),
            DealForecastGroup.Pipeline=>("COALESCE(pipeline,'Pipeline #'||pipeline_id::text)","pipeline_id","NULL::date",""),
            _=>throw new ArgumentException("Choose a forecast grouping.")
        };
        using var breakdown=Query(db,tx,data+$@"SELECT {Label} AS group_name,{Number} AS group_id,{Period} AS period_start,
            NULLIF(currency,'') AS currency_key,COALESCE(NULLIF(currency,''),'Unknown') AS currency,
            count(*) AS deals,COALESCE(sum(amount),0) AS amount,COALESCE(sum(amount*probability/100.0),0) AS weighted
            FROM scoped {Join} WHERE scoped.status='Open'
            GROUP BY 1,2,3,4,5 ORDER BY period_start NULLS LAST,group_name,currency",parameters);
        return new(counts.Rows[0],currencies,await ReadAsync(breakdown,cancellation));
    }
}
