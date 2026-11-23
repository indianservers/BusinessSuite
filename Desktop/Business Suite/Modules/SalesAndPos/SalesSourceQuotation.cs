using Npgsql;

namespace Business_Suite;

internal sealed record SalesSourceQuotation(int Id, QuoteDraftRepository Repository);

internal sealed partial class SalesOrderRepository
{
    internal async Task<SalesSourceQuotation?> FindSourceQuotationAsync(int order)
    {
        var ids = await ReadAsync(@"SELECT o.crm_quote_id FROM public.srm_sales_orders o" + OrderDetailScope +
            " AND o.id=@order AND o.crm_quote_id IS NOT NULL AND o.metadata_json->>'source' IS DISTINCT FROM 'pos'",
            query => query.Parameters.AddWithValue("order", order), row => row.GetInt32(0));
        if (ids.Count == 0)
            return null;

        var quotes = new QuoteDraftRepository(settings);
        try
        {
            var source = await quotes.ReadLifecycleAsync(ids.Single(), CancellationToken.None);
            return new SalesSourceQuotation(source.Id, quotes);
        }
        catch (Exception error) when (error is UnauthorizedAccessException or InvalidOperationException or
            KeyNotFoundException)
        {
            return null;
        }
    }
}
