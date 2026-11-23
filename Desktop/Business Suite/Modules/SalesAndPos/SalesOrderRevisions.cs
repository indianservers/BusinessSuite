using Npgsql;

namespace Business_Suite;

internal sealed record SalesOrderRevisionPreview(int Id, string Number, string Revision);

internal sealed partial class SalesOrderRepository
{
    internal async Task<SalesOrderRevisionPreview> LoadSalesOrderRevisionAsync(int order)
    {
        var rows = await ReadAsync("SELECT o.id,o.order_number," + SalesLineRevision +
            " FROM public.srm_sales_orders o" + ApprovalOrderScope,
            command => command.Parameters.AddWithValue("order", order),
            row => new SalesOrderRevisionPreview(row.GetInt32(0), row.GetString(1), row.GetString(2)), "create");
        return rows.SingleOrDefault() ?? throw new InvalidOperationException("The original Sales order is unavailable for revision.");
    }

    internal async Task<SalesOrderCreated> ReviseSalesOrderAsync(SalesOrderRevisionPreview original, string reason, Guid request)
    {
        reason = reason.Trim();
        if (reason.Length is < 5 or > 500 || reason.IndexOf('\0') >= 0 || request == Guid.Empty)
            throw new ArgumentException("Enter a meaningful revision reason of 5 to 500 characters.");
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose the source Sales order branch.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "Sales order revisions");
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "create");
        using (var source = ScopedCommand("SELECT o.id FROM public.srm_sales_orders o" + ApprovalOrderScope +
            " FOR UPDATE OF o", db, tx, branch, actor, scope))
        {
            source.Parameters.AddWithValue("order", original.Id);
            if (await source.ExecuteScalarAsync() is not int)
                throw new InvalidOperationException("The original Sales order is unavailable for revision.");
        }
        string hash = HashSalesPayload(new { original.Id, original.Revision, reason });
        using (var prior = RegisterCommand(@"SELECT copy.id,copy.order_number,coalesce(a.after_json->>'request_sha256'=@hash,false)
                AND " + ConfirmationOwnership("copy", "srm_sales_orders") + @"
            FROM public.srm_audit_logs a LEFT JOIN public.srm_sales_orders copy ON copy.id::text=a.after_json->'record'->>'id'
                AND copy.organization_id=@company AND copy.deleted_at IS NULL AND copy.created_by=@actor
            WHERE a.organization_id=@company AND a.actor_user_id=@actor AND a.entity_type='sales_order'
                AND a.entity_id=@order AND a.action='revision_created' AND a.after_json->>'request_id'=@request
                AND " + ConfirmationOwnership("a", "srm_audit_logs"),
            db, tx, branch, actor.Id))
        {
            prior.Parameters.AddWithValue("order", original.Id);
            prior.Parameters.AddWithValue("request", request.ToString());
            prior.Parameters.AddWithValue("hash", hash);
            SalesOrderCreated? previous = null;
            using (var rows = await prior.ExecuteReaderAsync())
            {
                if (await rows.ReadAsync())
                {
                    if (!rows.GetBoolean(2))
                        throw new InvalidOperationException("This revision request already used different details or its draft is unavailable.");
                    previous = new SalesOrderCreated(rows.GetInt32(0), rows.GetString(1));
                    if (await rows.ReadAsync())
                        throw new InvalidOperationException("More than one draft matches this revision request.");
                }
            }
            if (previous is not null)
            {
                tx.Commit();
                return previous;
            }
        }
        await ValidateConfirmationSourcesAsync(db, tx, branch, actor, original.Id);
        using (var revision = ScopedCommand("SELECT " + SalesLineRevision + " FROM public.srm_sales_orders o" + ApprovalOrderScope,
            db, tx, branch, actor, scope))
        {
            revision.Parameters.AddWithValue("order", original.Id);
            if (await revision.ExecuteScalarAsync() is not string version || version != original.Revision)
                throw new InvalidOperationException("The source order or one of its items changed. Reload before revising.");
        }
        string number = await ReserveCommercialNumberAsync(db, tx, CommercialNumberSeries.SalesOrder);
        using var write = RegisterCommand(@"
            WITH source AS (
                SELECT o.*,to_jsonb(o)||jsonb_build_object('lines',coalesce(
                    (SELECT jsonb_agg(to_jsonb(l) ORDER BY l.id) FROM public.srm_sales_order_lines l WHERE l.sales_order_id=o.id),'[]'::jsonb)) AS snapshot
                FROM public.srm_sales_orders o WHERE o.id=@order
            ), draft AS (
                INSERT INTO public.srm_sales_orders (organization_id,order_number,status,crm_deal_id,crm_quote_id,crm_company_id,
                    crm_contact_id,customer_id,assigned_user_id,created_by,title,currency,subtotal,discount_amount,tax_amount,
                    total_amount,expected_start_date,expected_end_date,terms,metadata_json)
                SELECT @company,@number,'draft',crm_deal_id,crm_quote_id,crm_company_id,crm_contact_id,customer_id,assigned_user_id,
                    @actor,title,currency,subtotal,discount_amount,tax_amount,total_amount,expected_start_date,expected_end_date,terms,
                    (coalesce(metadata_json::jsonb,'{}'::jsonb)-'desktop_create_request'-'desktop_create_sha256'
                        ||jsonb_build_object('desktop_revision_of',id))::json
                FROM source RETURNING id,order_number
            ), items AS (
                INSERT INTO public.srm_sales_order_lines (sales_order_id,source_quote_line_id,product_id,item_code,description,
                    service_type,quantity,unit_price,discount_amount,tax_amount,line_total,pms_template_key,metadata_json)
                SELECT d.id,l.source_quote_line_id,l.product_id,l.item_code,l.description,l.service_type,l.quantity,l.unit_price,
                    l.discount_amount,l.tax_amount,l.line_total,l.pms_template_key,
                    (l.metadata_json::jsonb-'desktop_add_request'-'desktop_add_sha256')::json
                FROM draft d JOIN public.srm_sales_order_lines l ON l.sales_order_id=@order ORDER BY l.id RETURNING id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,before_json,after_json)
                SELECT @company,'sales_order',s.id,'revision_created',@actor,s.snapshot::json,
                    json_build_object('record',json_build_object('id',d.id,'number',d.order_number),
                        'reason',@reason,'request_id',@request,'request_sha256',@hash)
                FROM source s CROSS JOIN draft d
                UNION ALL SELECT @company,'sales_order',d.id,'revised_from',@actor,NULL,
                    json_build_object('record',json_build_object('source_id',s.id,'source_number',s.order_number,'snapshot',s.snapshot),
                        'reason',@reason,'request_id',@request,'request_sha256',@hash)
                FROM source s CROSS JOIN draft d RETURNING id
            ), scoped AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'srm_sales_orders',id::text,@company,@branch,'validated-write' FROM draft
                UNION ALL SELECT 'srm_sales_order_lines',id::text,@company,@branch,'validated-write' FROM items
                UNION ALL SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit RETURNING resource_key
            )
            SELECT id FROM draft WHERE (SELECT count(*) FROM scoped)=3+(SELECT count(*) FROM items)", db, tx, branch, actor.Id);
        write.Parameters.AddWithValue("order", original.Id);
        write.Parameters.AddWithValue("number", number);
        write.Parameters.AddWithValue("hash", hash);
        write.Parameters.AddWithValue("reason", reason);
        write.Parameters.AddWithValue("request", request.ToString());
        if (await write.ExecuteScalarAsync() is not int id)
            throw new InvalidOperationException("The revision, copied lines and audit could not be saved together.");
        tx.Commit();
        return new SalesOrderCreated(id, number);
    }
}
