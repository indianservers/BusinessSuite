using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record QuoteChoice(int Id,string Name,int? Company=null,int? Contact=null,string Currency="");
internal sealed record QuotePickers(List<QuoteChoice> Customers,List<QuoteChoice> Deals,string Currency);
internal sealed record QuoteWorkspace(DataTable Rows,bool CanCreate,bool CanEdit);
internal sealed record QuoteDraft(int? Id,string Revision,string LineRevision,string Number,int Customer,int? Deal,
    DateTime Issue,DateTime Expiry,string Currency,string Terms,string Notes,List<QuoteDraftLine> Lines);
internal sealed class QuoteDraftLine
{
    internal int? Id { get; set; }
    public string Name { get; set; }="";
    public decimal Quantity { get; set; }=1;
    public decimal UnitPrice { get; set; }
    public string DiscountType { get; set; }="amount";
    public decimal DiscountValue { get; set; }
    public decimal TaxRate { get; set; }
}
internal sealed record QuoteLineTotals(decimal Gross,decimal Discount,decimal Tax,decimal Total);

internal sealed partial class QuoteDraftRepository(DesktopDatabaseSettings settings)
{
    private int Branch=>settings.BranchId??throw new InvalidOperationException("Select the quotation's owning branch first.");

    internal async Task<QuoteWorkspace> ListAsync(string search,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await CrmDirectoryWrites.RequireCrmActorAsync(settings,db,tx,cancellation,"quotes");
        bool accounts=await CanAsync(db,tx,actor,"accounts","view");
        bool deals=await CanAsync(db,tx,actor,"deals","view");
        bool create=actor.CanWriteBranch&&actor.IsSuperuser&&await CanAsync(db,tx,actor,"quotes","create");
        bool edit=actor.CanWriteBranch&&actor.IsSuperuser&&await CanAsync(db,tx,actor,"quotes","edit");
        using var query=Command(db,tx,@"SELECT q.id,q.quote_number,q.version_number,q.issue_date,q.expiry_date,
                q.status,q.currency,q.total_amount,c.name AS customer,d.name AS deal
            FROM public.crm_quotations q LEFT JOIN public.crm_companies c ON @accounts AND c.organization_id=@org
                AND c.id=COALESCE(q.company_id,q.account_id) AND c.deleted_at IS NULL AND "+
                CrmDirectoryWrites.BranchScope("crm_companies","c",includeShares:true)+@"
            LEFT JOIN public.crm_deals d ON @deals AND d.organization_id=@org AND d.id=q.deal_id AND d.deleted_at IS NULL AND "+
                CrmDirectoryWrites.BranchScope("crm_deals","d")+@"
            WHERE q.organization_id=@org AND q.deleted_at IS NULL AND "+CrmDirectoryWrites.BranchScope("crm_quotations","q")+@"
              AND (@search='' OR strpos(lower(q.quote_number),lower(@search))>0 OR strpos(lower(c.name),lower(@search))>0
                OR strpos(lower(d.name),lower(@search))>0 OR strpos(lower(q.status),lower(@search))>0)
            ORDER BY COALESCE(q.updated_at,q.created_at) DESC NULLS LAST,q.id DESC LIMIT 200",
            ("accounts",NpgsqlDbType.Boolean,accounts),("deals",NpgsqlDbType.Boolean,deals),("search",NpgsqlDbType.Text,search));
        return new(await TableAsync(query,cancellation),create,edit);
    }

    internal async Task<QuotePickers> OptionsAsync(bool creating,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await EditorAsync(db,tx,!creating,cancellation);
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"accounts","view");
        var customers=new List<QuoteChoice>();
        using (var query=Command(db,tx,@"SELECT c.id,c.name FROM public.crm_companies c WHERE c.organization_id=@org
            AND c.deleted_at IS NULL AND c.status='Active' AND "+CrmDirectoryWrites.BranchScope("crm_companies","c",includeShares:true)+@"
            AND NOT EXISTS (SELECT 1 FROM public.srm_anonymous_cash_accounts a WHERE a.organization_id=@org AND a.customer_id=c.id)
            ORDER BY c.name,c.id"))
        using (var reader=await query.ExecuteReaderAsync(cancellation))
            while (await reader.ReadAsync(cancellation))
                customers.Add(new(reader.GetInt32(0),reader.GetString(1)));
        var deals=new List<QuoteChoice> {new(0,"No linked deal")};
        if (await CanAsync(db,tx,actor,"deals","view"))
        {
            using var query=Command(db,tx,@"SELECT d.id,d.name,d.company_id,d.contact_id,d.currency
                FROM public.crm_deals d WHERE d.organization_id=@org AND d.deleted_at IS NULL AND "+
                CrmDirectoryWrites.BranchScope("crm_deals","d")+" ORDER BY d.name,d.id");
            using var reader=await query.ExecuteReaderAsync(cancellation);
            while (await reader.ReadAsync(cancellation))
                deals.Add(new(reader.GetInt32(0),reader.GetString(1),reader.IsDBNull(2)?null:reader.GetInt32(2),
                    reader.IsDBNull(3)?null:reader.GetInt32(3),reader.IsDBNull(4)?"":reader.GetString(4)));
        }
        using var currency=Command(db,tx,"SELECT COALESCE(default_currency,'INR') FROM public.companies WHERE id=@org");
        return new(customers,deals,(string)(await currency.ExecuteScalarAsync(cancellation))!);
    }

    internal async Task<QuoteDraft> ReadAsync(int id,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        await EditorAsync(db,tx,true,cancellation);
        DataRow row=await HeaderAsync(db,tx,id,false,cancellation);
        var (lines,revision)=await LinesAsync(db,tx,id,false,cancellation);
        return new(id,(string)row["revision"],revision,(string)row["quote_number"],
            row["company_id"] as int? ?? row["account_id"] as int? ?? 0,row["deal_id"] as int?,
            (DateTime)row["issue_date"],(DateTime)row["expiry_date"],row["currency"] as string??"",
            row["terms"] as string??row["terms_and_conditions"] as string??"",row["notes"] as string??"",lines);
    }

    internal static QuoteLineTotals Calculate(QuoteDraftLine line)
    {
        if (line.Name.Trim().Length is <1 or >180 || line.Quantity<=0 || line.Quantity>9999999999m ||
            line.UnitPrice<0 || line.UnitPrice>9999999999m || line.DiscountValue<0 ||
            line.TaxRate<0 || line.TaxRate>100 || new[] {line.Quantity,line.UnitPrice,line.TaxRate,line.DiscountValue}.Any(value=>Round(value)!=value))
            throw new ArgumentException("Quote lines require a name, positive quantity, nonnegative price and discount, and a tax rate of 0–100%, with at most two decimals.");
        decimal gross=Round(line.Quantity*line.UnitPrice);
        decimal discount=line.DiscountType.ToLowerInvariant() switch
        {
            "percent" or "percentage" when line.DiscountValue<=100=>Round(gross*line.DiscountValue/100m),
            "amount"=>line.DiscountValue,
            _=>throw new ArgumentException("Choose amount or percentage discount and enter its value.")
        };
        if (discount>gross || gross>9999999999.99m)
            throw new ArgumentException("The quote line exceeds its allowed amount or discount.");
        decimal tax=Round((gross-discount)*line.TaxRate/100m);
        decimal total=gross-discount+tax;
        if (total>9999999999.99m)
            throw new ArgumentException("The quote line total exceeds the allowed amount.");
        return new(gross,discount,tax,total);

        static decimal Round(decimal value)=>Math.Round(value,2,MidpointRounding.AwayFromZero);
    }

    private async Task<DesktopActor> EditorAsync(NpgsqlConnection db,NpgsqlTransaction tx,bool exists,CancellationToken cancellation)
    {
        var actor=await CrmDirectoryWrites.RequireCrmActorAsync(settings,db,tx,cancellation,"quotes",exists?"edit":"create");
        if (!actor.IsSuperuser || !actor.CanWriteBranch || settings.BranchId is null)
            throw new UnauthorizedAccessException("Desktop quote drafting requires a Suite superuser in a writable branch.");
        return actor;
    }

    private async Task<bool> CanAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,string entity,string action)
    {
        try { await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,entity,action);return true; }
        catch(UnauthorizedAccessException) { return false; }
    }

    private async Task<DataRow> HeaderAsync(NpgsqlConnection db,NpgsqlTransaction tx,int id,bool write,CancellationToken cancellation)
    {
        using var query=Command(db,tx,@"SELECT q.*,q.xmin::text AS revision FROM public.crm_quotations q
            WHERE q.organization_id=@org AND q.id=@id AND q.deleted_at IS NULL AND lower(q.status) IN ('draft','rejected')
                AND q.sent_at IS NULL AND q.converted_srm_sales_order_id IS NULL AND "+
                CrmDirectoryWrites.BranchScope("crm_quotations","q")+(write?" FOR UPDATE OF q":""),
            ("id",NpgsqlDbType.Integer,id));
        var rows=await TableAsync(query,cancellation);
        if (rows.Rows.Count==0)
            throw new InvalidOperationException("Only available draft or rejected quotations can be edited.");
        return rows.Rows[0];
    }

    private async Task<(List<QuoteDraftLine>,string)> LinesAsync(NpgsqlConnection db,NpgsqlTransaction tx,int id,bool write,
        CancellationToken cancellation)
    {
        using var query=Command(db,tx,@"SELECT i.id,i.xmin::text,i.name,COALESCE(i.quantity,1),COALESCE(i.unit_price,0),
            COALESCE(i.discount_type,'amount'),COALESCE(i.discount_value,i.discount_amount,0),COALESCE(i.tax_rate,0),
            i.quotation_id=@id AND (i.quote_id IS NULL OR i.quote_id=@id)
            FROM public.crm_quotation_items i WHERE i.quotation_id=@id OR i.quote_id=@id
            ORDER BY i.sort_order,i.id"+(write?" FOR UPDATE OF i":""),
            ("id",NpgsqlDbType.Integer,id));
        using var reader=await query.ExecuteReaderAsync(cancellation);
        var lines=new List<QuoteDraftLine>();
        var revisions=new List<string>();
        while (await reader.ReadAsync(cancellation))
        {
            if (!reader.GetBoolean(8))
                throw new InvalidOperationException("This quotation has conflicting line relationships.");
            int line=reader.GetInt32(0);
            revisions.Add($"{line}:{reader.GetString(1)}");
            lines.Add(new() {Id=line,Name=reader.GetString(2),Quantity=reader.GetDecimal(3),UnitPrice=reader.GetDecimal(4),
                DiscountType=reader.GetString(5),DiscountValue=reader.GetDecimal(6),TaxRate=reader.GetDecimal(7)});
        }
        return (lines,string.Join(",",revisions));
    }

    private NpgsqlCommand Command(NpgsqlConnection db,NpgsqlTransaction tx,string sql,
        params (string Name,NpgsqlDbType Type,object? Value)[] parameters)
    {
        var command=new NpgsqlCommand(sql,db,tx);
        command.Parameters.AddWithValue("org",NpgsqlDbType.Integer,settings.OrganizationId);
        command.Parameters.Add("scope_branch",NpgsqlDbType.Integer).Value=(object?)settings.BranchId??DBNull.Value;
        foreach (var parameter in parameters)
            command.Parameters.Add(parameter.Name,parameter.Type).Value=parameter.Value??DBNull.Value;
        return command;
    }

    private static async Task<DataTable> TableAsync(NpgsqlCommand command,CancellationToken cancellation)
    {
        using var reader=await command.ExecuteReaderAsync(cancellation);
        var result=new DataTable();
        result.Load(reader);
        return result;
    }
}
