using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record CrmDealQuoteChoice(int Id, int Version, string Revision, string Number, string Currency, decimal Total)
{
    public string Display => $"{Number} · v{Version} · {Currency} {Total:N2}";
}

internal sealed record CrmDealQuoteLine(int Id, int? ProductId, string Description, decimal Quantity, decimal UnitPrice,
    decimal Discount, decimal Tax, decimal Total);

internal sealed record CrmDealQuoteSource(CrmDealQuoteChoice Choice, decimal Subtotal, decimal Discount, decimal Tax,
    string? Terms, List<CrmDealQuoteLine> Lines);

internal sealed partial class CrmDealRepository
{
    private async Task<List<CrmDealQuoteChoice>> ReadQuoteChoicesAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        DesktopActor actor,DataRow deal,CancellationToken cancellation)
    {
        if (!await CanViewAsync(db,tx,actor,"crm_quotes_view","crm_quotes_manage"))
            return [];
        using var query=Query(db,tx,@"SELECT q.id,q.version_number,q.xmin::text,q.quote_number,q.currency,q.total_amount
            FROM public.crm_quotations q WHERE q.organization_id=@org AND q.deal_id=@deal AND q.deleted_at IS NULL
                AND "+QuoteEligibility("q")+@" AND "+CrmDirectoryWrites.BranchScope("crm_quotations","q")+@"
                AND q.currency=@currency AND (q.company_id IS NULL OR q.company_id=@customer)
                AND (q.account_id IS NULL OR q.account_id=@customer) AND q.total_amount IS NOT NULL
            ORDER BY q.id DESC",("deal",NpgsqlDbType.Integer,deal["id"]),
            ("currency",NpgsqlDbType.Text,deal["currency"] as string),("customer",NpgsqlDbType.Integer,deal["company_id"] as int?));
        using var reader=await query.ExecuteReaderAsync(cancellation);
        var quotes=new List<CrmDealQuoteChoice>();
        while (await reader.ReadAsync(cancellation))
            quotes.Add(new(reader.GetInt32(0),reader.GetInt32(1),reader.GetString(2),reader.GetString(3),
                reader.GetString(4),reader.GetDecimal(5)));
        return quotes;
    }

    private async Task<CrmDealQuoteSource> ReadQuoteSourceAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,
        DataRow deal,CrmDealQuoteChoice selection,CancellationToken cancellation)
    {
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"quotes","view");
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"quotes","edit");
        using var query=Query(db,tx,@"SELECT q.id,q.version_number,q.xmin::text,q.quote_number,q.currency,q.total_amount,
                q.subtotal,COALESCE(q.discount_amount,0),COALESCE(q.tax_amount,0),COALESCE(q.terms,q.terms_and_conditions)
            FROM public.crm_quotations q WHERE q.organization_id=@org AND q.deal_id=@deal AND q.id=@quote
                AND q.deleted_at IS NULL AND "+QuoteEligibility("q")+@" AND "+CrmDirectoryWrites.BranchScope("crm_quotations","q")+@"
                AND q.currency=@currency AND (q.company_id IS NULL OR q.company_id=@customer)
                AND (q.account_id IS NULL OR q.account_id=@customer)
                AND NOT EXISTS(SELECT 1 FROM public.crm_quote_srm_conversion_logs l
                    WHERE l.quote_id=q.id AND l.status='converted')
                AND NOT EXISTS(SELECT 1 FROM public.srm_sales_orders o WHERE o.organization_id=@org AND o.crm_quote_id=q.id)
            FOR UPDATE OF q",("deal",NpgsqlDbType.Integer,deal["id"]),("quote",NpgsqlDbType.Integer,selection.Id),
            ("currency",NpgsqlDbType.Text,deal["currency"] as string),("customer",NpgsqlDbType.Integer,deal["company_id"] as int?));
        CrmDealQuoteChoice current;
        decimal subtotal,discount,tax;
        string? terms;
        using (var reader=await query.ExecuteReaderAsync(cancellation))
        {
            if (!await reader.ReadAsync(cancellation) || reader.IsDBNull(5) || reader.IsDBNull(6))
                throw new InvalidOperationException("The selected quotation is unavailable, converted or outside the deal's owning branch.");
            current=new(reader.GetInt32(0),reader.GetInt32(1),reader.GetString(2),reader.GetString(3),
                reader.GetString(4),reader.GetDecimal(5));
            if (current!=selection)
                throw new InvalidOperationException("The quotation changed. Reopen the deal and review its latest version.");
            subtotal=reader.GetDecimal(6);
            discount=reader.GetDecimal(7);
            tax=reader.GetDecimal(8);
            terms=reader.IsDBNull(9)?null:reader.GetString(9);
        }

        using var lineQuery=Query(db,tx,@"SELECT i.id,COALESCE(i.service_id,i.product_id),i.name,i.quantity,i.unit_price,
              COALESCE(i.discount_amount,0),COALESCE(i.tax_rate,0),i.total_amount,
              (i.product_id IS NULL OR i.service_id IS NULL OR i.product_id=i.service_id)
                AND (i.quotation_id=@quote AND (i.quote_id IS NULL OR i.quote_id=@quote)) AS consistent,
              (i.product_id IS NULL AND i.service_id IS NULL) OR p.id IS NOT NULL AS product_visible
            FROM public.crm_quotation_items i LEFT JOIN public.srm_products p ON p.id=COALESCE(i.service_id,i.product_id)
                AND p.organization_id=@org AND NOT EXISTS(SELECT 1 FROM public.suite_branch_ownership o
                 WHERE o.company_id=@org AND o.resource_table='srm_products' AND o.resource_key=p.id::text
                   AND o.branch_id<>@scope_branch AND NOT EXISTS(SELECT 1 FROM public.suite_branch_record_shares s
                     WHERE s.company_id=@org AND s.resource_table='srm_products' AND s.resource_key=p.id::text
                       AND s.branch_id=@scope_branch))
            WHERE i.quotation_id=@quote OR i.quote_id=@quote ORDER BY i.sort_order,i.id FOR SHARE OF i",
            ("quote",NpgsqlDbType.Integer,selection.Id));
        var lines=new List<CrmDealQuoteLine>();
        decimal lineSubtotal=0,lineDiscount=0,lineTax=0,lineTotal=0;
        using (var reader=await lineQuery.ExecuteReaderAsync(cancellation))
        {
            while (await reader.ReadAsync(cancellation))
            {
                if (reader.IsDBNull(3)||reader.IsDBNull(4)||reader.IsDBNull(7)||!reader.GetBoolean(8)||!reader.GetBoolean(9))
                    throw new InvalidOperationException("A quotation line is incomplete or outside this company and branch.");
                decimal quantity=reader.GetDecimal(3), price=reader.GetDecimal(4), reduction=reader.GetDecimal(5),
                    rate=reader.GetDecimal(6), total=reader.GetDecimal(7);
                decimal gross=Math.Round(quantity*price,2,MidpointRounding.AwayFromZero);
                decimal taxAmount=Math.Round((gross-reduction)*rate/100m,2,MidpointRounding.AwayFromZero);
                if (quantity<=0||price<0||reduction<0||reduction>gross||rate<0||rate>100||
                    total!=gross-reduction+taxAmount)
                    throw new InvalidOperationException("A quotation line does not reconcile with its approved discount, tax and total.");
                lines.Add(new(reader.GetInt32(0),reader.IsDBNull(1)?null:reader.GetInt32(1),reader.GetString(2),
                    quantity,price,reduction,taxAmount,total));
                lineSubtotal+=gross;
                lineDiscount+=reduction;
                lineTax+=taxAmount;
                lineTotal+=total;
            }
        }

        if (lines.Count==0||lineSubtotal!=subtotal||lineDiscount!=discount||lineTax!=tax||lineTotal!=selection.Total)
            throw new InvalidOperationException("The quotation lines do not reconcile with its approved totals.");
        return new(current,subtotal,discount,tax,terms,lines);
    }

    private static string QuoteEligibility(string alias) => $@"lower({alias}.status) IN ('accepted','approved')
        AND lower(COALESCE({alias}.approval_status,'not_required')) IN ('approved','not_required')
        AND {alias}.converted_srm_sales_order_id IS NULL
        AND {alias}.converted_srm_engagement_id IS NULL AND {alias}.converted_srm_contract_id IS NULL";
}
