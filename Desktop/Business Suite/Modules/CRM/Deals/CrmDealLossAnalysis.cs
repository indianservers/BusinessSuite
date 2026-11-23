using System.Data;
using Npgsql;

namespace Business_Suite;

internal sealed record CrmDealLossAnalysis(DataTable Reasons,DataTable Competitors);

internal sealed partial class CrmDealRepository
{
    internal async Task<CrmDealLossAnalysis> LossAnalysisAsync(string search,CrmDealFilters filters,CancellationToken cancellation)
    {
        filters.Validate();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        await RequireDealsAsync(db,tx,actor,false);
        var (from,parameters)=await FilteredDealDataAsync(db,tx,actor,search,"Lost",false,filters,[]);
        string data=@"WITH scoped AS (
            SELECT COALESCE(NULLIF(d.lost_reason,''),NULLIF(d.loss_reason,''),'No reason recorded') AS reason,
                COALESCE(NULLIF(d.planning #>> '{closure,competitor}',''),
                    NULLIF(d.planning #>> '{qualification,competitor}',''),'No competitor recorded') AS competitor,
                NULLIF(d.currency,'') AS currency_key,d.amount"+from+@"
        ) ";
        using var reasons=Query(db,tx,data+@"SELECT reason AS name,currency_key,
            COALESCE(currency_key,'Unknown') AS currency,count(*) AS deals,COALESCE(sum(amount),0) AS amount
            FROM scoped GROUP BY reason,currency_key ORDER BY reason,currency",parameters);
        using var competitors=Query(db,tx,data+@"SELECT competitor AS name,
            COALESCE(currency_key,'Unknown') AS currency,count(*) AS deals,COALESCE(sum(amount),0) AS amount
            FROM scoped GROUP BY competitor,currency_key ORDER BY competitor,currency",parameters);
        return new(await ReadAsync(reasons,cancellation),await ReadAsync(competitors,cancellation));
    }
}
