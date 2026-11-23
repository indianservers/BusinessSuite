using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class QuoteDraftRepository
{
    internal async Task<int> SaveAsync(QuoteDraft draft,CancellationToken cancellation)
    {
        string number=draft.Number.Trim(),currency=draft.Currency.Trim().ToUpperInvariant();
        if (number.Length is <1 or >60 || draft.Customer<=0 || draft.Issue.Date>draft.Expiry.Date ||
            currency.Length!=3 || currency.Any(ch=>ch<'A'||ch>'Z') || draft.Terms.Length>10000 || draft.Notes.Length>10000 ||
            draft.Lines.Count>500 || draft.Lines.Where(line=>line.Id.HasValue).Select(line=>line.Id).Distinct().Count()!=
                draft.Lines.Count(line=>line.Id.HasValue))
            throw new ArgumentException("Complete the quotation number, customer, dates and three-letter currency. A quotation can contain up to 500 distinct lines.");
        var totals=draft.Lines.Select(Calculate).ToArray();
        decimal subtotal=totals.Sum(line=>line.Gross),grand=totals.Sum(line=>line.Total);
        if (subtotal>9999999999.99m || grand>9999999999.99m)
            throw new ArgumentException("The quotation total exceeds its supported limit.");
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        var actor=await EditorAsync(db,tx,draft.Id.HasValue,cancellation);
        using (var guard=Command(db,tx,"SELECT pg_advisory_xact_lock(720000000::bigint+@org)"))
            await guard.ExecuteNonQueryAsync(cancellation);
        actor=await EditorAsync(db,tx,draft.Id.HasValue,cancellation);
        var oldLines=new List<QuoteDraftLine>();
        int? retainedContact=null;
        if (draft.Id is int existingId)
        {
            var header=await HeaderAsync(db,tx,existingId,true,cancellation);
            var snapshot=await LinesAsync(db,tx,existingId,true,cancellation);
            oldLines=snapshot.Item1;
            if ((header["company_id"] as int? ?? header["account_id"] as int?)==draft.Customer &&
                (header["deal_id"] as int?)==draft.Deal)
                retainedContact=header["contact_id"] as int?;
            if ((string)header["revision"]!=draft.Revision || snapshot.Item2!=draft.LineRevision)
                throw new InvalidOperationException("The quotation or its lines changed. Reopen the draft before saving.");
        }
        if (draft.Lines.Any(line=>line.Id.HasValue&&!oldLines.Any(old=>old.Id==line.Id)))
            throw new InvalidOperationException("A quotation line does not belong to this draft.");
        int? contact=await ValidateLinksAsync(db,tx,actor,draft.Customer,draft.Deal,currency,retainedContact,cancellation);
        using (var duplicate=Command(db,tx,@"SELECT 1 FROM public.crm_quotations WHERE organization_id=@org
            AND lower(quote_number)=lower(@number) AND id IS DISTINCT FROM @id",
            ("number",NpgsqlDbType.Text,number),("id",NpgsqlDbType.Integer,draft.Id)))
            if (await duplicate.ExecuteScalarAsync(cancellation) is not null)
                throw new InvalidOperationException("This quotation number already exists in the company.");

        string sql=draft.Id.HasValue?@"UPDATE public.crm_quotations SET quote_number=@number,company_id=@customer,account_id=@customer,
            deal_id=@deal,contact_id=@contact,issue_date=@issue,quote_date=@issue,expiry_date=@expiry,valid_until=@expiry,currency=@currency,
            terms=@terms,terms_and_conditions=@terms,notes=@notes,updated_at=now(),updated_by_user_id=@actor
            WHERE id=@id AND organization_id=@org RETURNING id":
            @"INSERT INTO public.crm_quotations (organization_id,branch_id,quote_number,company_id,account_id,deal_id,contact_id,
                owner_user_id,owner_id,issue_date,quote_date,expiry_date,valid_until,currency,terms,terms_and_conditions,notes,
                created_by_user_id,updated_by_user_id,status,approval_status,version_number)
            VALUES (@org,@scope_branch,@number,@customer,@customer,@deal,@contact,@actor,@actor,@issue,@issue,@expiry,@expiry,@currency,
                @terms,@terms,@notes,@actor,@actor,'Draft','not_required',1) RETURNING id";
        using var headerWrite=Command(db,tx,sql,("id",NpgsqlDbType.Integer,draft.Id),("number",NpgsqlDbType.Text,number),
            ("customer",NpgsqlDbType.Integer,draft.Customer),("deal",NpgsqlDbType.Integer,draft.Deal),
            ("contact",NpgsqlDbType.Integer,contact),("issue",NpgsqlDbType.Date,draft.Issue.Date),("expiry",NpgsqlDbType.Date,draft.Expiry.Date),
            ("currency",NpgsqlDbType.Text,currency),("terms",NpgsqlDbType.Text,draft.Terms),("notes",NpgsqlDbType.Text,draft.Notes),
            ("actor",NpgsqlDbType.Integer,actor.Id));
        int id=(int)(await headerWrite.ExecuteScalarAsync(cancellation))!;
        if (!draft.Id.HasValue)
            await StampAsync(db,tx,"crm_quotations",id,cancellation);
        await CrmDirectoryWrites.CheckRequiredFieldsAsync(db,tx,"quotations",settings.OrganizationId,id,cancellation);
        foreach (var old in oldLines.Where(old=>!draft.Lines.Any(line=>line.Id==old.Id)))
        {
            using var delete=Command(db,tx,@"WITH removed AS (
                DELETE FROM public.crm_quotation_items WHERE id=@id AND quotation_id=@quote RETURNING id
                ) DELETE FROM public.suite_branch_ownership WHERE company_id=@org AND resource_table='crm_quotation_items'
                    AND resource_key IN (SELECT id::text FROM removed)",
                ("id",NpgsqlDbType.Integer,old.Id),("quote",NpgsqlDbType.Integer,id));
            await delete.ExecuteNonQueryAsync(cancellation);
            await CrmDirectoryWrites.Audit(db,tx,"quote-lines",settings.OrganizationId,old.Id!.Value,actor.Id,"DELETE",cancellation);
        }
        for(int index=0;index<draft.Lines.Count;index++)
            await WriteLineAsync(db,tx,id,actor.Id,draft.Lines[index],totals[index],index,cancellation);

        using var recalc=Command(db,tx,@"WITH costs AS (
            SELECT COALESCE(sum(estimated_cost),0) AS value FROM public.crm_quotation_items WHERE quotation_id=@id
            ) UPDATE public.crm_quotations q SET subtotal=@subtotal,discount_amount=@discount,discount_total=@discount,
                tax_amount=@tax,tax_total=@tax,total_amount=@total,grand_total=@total,estimated_cost=costs.value,
                expected_margin=@total-costs.value,margin_percentage=CASE WHEN @total=0 THEN 0
                    ELSE (@total-costs.value)/@total*100 END
            FROM costs WHERE q.id=@id AND q.organization_id=@org",
            ("id",NpgsqlDbType.Integer,id),("subtotal",NpgsqlDbType.Numeric,subtotal),("discount",NpgsqlDbType.Numeric,totals.Sum(v=>v.Discount)),
            ("tax",NpgsqlDbType.Numeric,totals.Sum(v=>v.Tax)),("total",NpgsqlDbType.Numeric,grand));
        await recalc.ExecuteNonQueryAsync(cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"quotations",settings.OrganizationId,id,actor.Id,draft.Id.HasValue?"UPDATE":"CREATE",cancellation);
        using var timeline=Command(db,tx,@"INSERT INTO public.crm_timeline_events
            (organization_id,record_type,record_id,event_type,title,description,actor_user_id)
            VALUES (@org,'quotation',@id,@type,@title,@description,@actor)",
            ("id",NpgsqlDbType.Integer,id),("type",NpgsqlDbType.Text,draft.Id.HasValue?"field_change":"quotation"),
            ("title",NpgsqlDbType.Text,draft.Id.HasValue?"Quotation updated":"Quotation created"),
            ("description",NpgsqlDbType.Text,number),("actor",NpgsqlDbType.Integer,actor.Id));
        await timeline.ExecuteNonQueryAsync(cancellation);
        tx.Commit();
        return id;
    }

    private async Task<int?> ValidateLinksAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,int customer,int? deal,
        string currency,int? retainedContact,CancellationToken cancellation)
    {
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"accounts","view");
        using (var candidate=Command(db,tx,@"SELECT c.id FROM public.crm_companies c WHERE c.organization_id=@org
            AND c.id=@id AND c.deleted_at IS NULL AND c.status='Active' AND "+
            CrmDirectoryWrites.BranchScope("crm_companies","c",includeShares:true)+@"
            AND NOT EXISTS (SELECT 1 FROM public.srm_anonymous_cash_accounts a WHERE a.organization_id=@org AND a.customer_id=c.id)
            FOR SHARE OF c",("id",NpgsqlDbType.Integer,customer)))
            if (await candidate.ExecuteScalarAsync(cancellation) is null)
                throw new InvalidOperationException("Choose an active customer available in this branch.");
        int? contact=retainedContact;
        if (deal.HasValue)
        {
            await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"deals","view");
            using var query=Command(db,tx,@"SELECT d.contact_id FROM public.crm_deals d WHERE d.organization_id=@org AND d.id=@id
                AND d.deleted_at IS NULL AND d.company_id=@customer AND d.currency=@currency AND "+
                CrmDirectoryWrites.BranchScope("crm_deals","d")+" FOR SHARE OF d",("id",NpgsqlDbType.Integer,deal),
                ("customer",NpgsqlDbType.Integer,customer),("currency",NpgsqlDbType.Text,currency));
            object? linked=await query.ExecuteScalarAsync(cancellation);
            if (linked is null)
                throw new InvalidOperationException("The linked deal must use the same customer and currency and be available in this branch.");
            contact??=linked as int?;
        }
        if (!contact.HasValue)
            return null;
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"contacts","view");
        using var contactQuery=Command(db,tx,@"SELECT p.id FROM public.crm_contacts p WHERE p.organization_id=@org AND p.id=@contact
            AND p.deleted_at IS NULL AND "+CrmDirectoryWrites.BranchScope("crm_contacts","p",includeShares:true)+" FOR SHARE OF p",
            ("contact",NpgsqlDbType.Integer,contact));
        if (await contactQuery.ExecuteScalarAsync(cancellation) is null)
            throw new InvalidOperationException("The deal contact is unavailable in this branch.");
        return contact;
    }

    private async Task WriteLineAsync(NpgsqlConnection db,NpgsqlTransaction tx,int quote,int actor,QuoteDraftLine line,
        QuoteLineTotals totals,int index,CancellationToken cancellation)
    {
        string command=line.Id.HasValue?@"UPDATE public.crm_quotation_items SET name=@name,quantity=@qty,unit_price=@price,
            discount_type=@kind,discount_value=@discount_value,discount_amount=@discount,tax_rate=@rate,line_total=@total,
            total_amount=@total,margin_amount=@total-COALESCE(estimated_cost,0),margin_percentage=CASE WHEN @total=0 THEN 0
                ELSE (@total-COALESCE(estimated_cost,0))/@total*100 END,sort_order=@position
            WHERE id=@id AND quotation_id=@quote RETURNING id":
            @"INSERT INTO public.crm_quotation_items (quotation_id,quote_id,name,item_type,billing_type,quantity,unit_price,discount_type,
                discount_value,discount_amount,tax_rate,line_total,total_amount,estimated_cost,margin_amount,margin_percentage,sort_order)
            VALUES (@quote,@quote,@name,'product','fixed',@qty,@price,@kind,@discount_value,@discount,@rate,@total,@total,0,@total,
                CASE WHEN @total=0 THEN 0 ELSE 100 END,@position) RETURNING id";
        using var write=Command(db,tx,command,("quote",NpgsqlDbType.Integer,quote),("id",NpgsqlDbType.Integer,line.Id),
            ("name",NpgsqlDbType.Text,line.Name.Trim()),("qty",NpgsqlDbType.Numeric,line.Quantity),("price",NpgsqlDbType.Numeric,line.UnitPrice),
            ("kind",NpgsqlDbType.Text,line.DiscountType.ToLowerInvariant()),("discount_value",NpgsqlDbType.Numeric,line.DiscountValue),
            ("discount",NpgsqlDbType.Numeric,totals.Discount),("rate",NpgsqlDbType.Numeric,line.TaxRate),
            ("total",NpgsqlDbType.Numeric,totals.Total),("position",NpgsqlDbType.Integer,index));
        int id=(int)(await write.ExecuteScalarAsync(cancellation))!;
        if (!line.Id.HasValue)
            await StampAsync(db,tx,"crm_quotation_items",id,cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"quote-lines",settings.OrganizationId,id,actor,line.Id.HasValue?"UPDATE":"CREATE",cancellation);
    }

    private async Task StampAsync(NpgsqlConnection db,NpgsqlTransaction tx,string table,int id,CancellationToken cancellation)
    {
        int branch=Branch;
        using var write=Command(db,tx,@"INSERT INTO public.suite_branch_ownership
            (resource_table,resource_key,company_id,branch_id,source) VALUES (@table,@id::text,@org,@scope_branch,'desktop-crm')",
            ("table",NpgsqlDbType.Text,table),("id",NpgsqlDbType.Integer,id));
        await write.ExecuteNonQueryAsync(cancellation);
    }
}
