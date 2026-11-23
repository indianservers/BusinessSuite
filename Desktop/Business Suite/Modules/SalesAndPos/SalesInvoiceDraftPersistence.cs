using System.Globalization;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    internal async Task<int> SaveAppointmentInvoiceDraftAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        int branch,int actor,int appointment,int customer,string currency,string title,decimal subtotal,decimal tax)
    {
        decimal total = subtotal+tax;
        if (!ValidInvoiceCurrency(currency) || subtotal<0 || tax<0 || total>999999999999.99m)
            throw new InvalidOperationException("The appointment charge is outside the supported invoice amounts or currencies.");
        string number = await ReserveCommercialNumberAsync(db,tx,CommercialNumberSeries.Invoice);
        var line = new SalesInvoiceDraftLine(null,title,1m,subtotal,0m,tax,subtotal,total);
        var saved = await SaveSalesInvoiceDraftAsync(db,tx,branch,actor,null,currency,number,[line],appointment:(appointment,customer));
        return saved.Id;
    }

    private async Task<SalesInvoiceDraftResult> SaveSalesInvoiceDraftAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, int actor, int? order, string currency, string number, List<SalesInvoiceDraftLine> lines,
        MilestoneInvoiceSource? milestone = null, (int Id,int Customer)? appointment = null)
    {
        string companyKey = settings.OrganizationId.ToString(CultureInfo.InvariantCulture);
        string branchKey = branch.ToString(CultureInfo.InvariantCulture);
        string defaultsKey = "form-defaults:company:" + companyKey;
        using var write = RegisterCommand(@"
            WITH base AS (
                SELECT jsonb_build_object('date_format','DD/MM/YYYY','time_format','12h','number_format','en-IN','language','en',
                    'timezone',coalesce(nullif(default_timezone,''),'Asia/Kolkata'),'invoice_template','standard','quote_template','standard',
                    'bank_account_id',NULL,'payment_mode_id',NULL,'payment_terms_days',30) AS snapshot
                FROM public.companies WHERE id=@company
            ), overrides AS (
                SELECT DISTINCT ON (item.key) item.key,item.value
                FROM unnest(@default_keys::text[]) WITH ORDINALITY wanted(scope_key,priority)
                JOIN public.suite_service_policies configured ON configured.scope_key=wanted.scope_key
                    AND configured.organization_id=@company AND configured.kind='form_defaults'
                CROSS JOIN LATERAL jsonb_each(configured.values_json::jsonb) item
                WHERE item.key IN ('date_format','time_format','number_format','language','timezone','invoice_template',
                    'quote_template','bank_account_id','payment_mode_id','payment_terms_days')
                ORDER BY item.key,wanted.priority DESC
            ), settings AS (
                SELECT base.snapshot || coalesce((SELECT jsonb_object_agg(key,value) FROM overrides),'{}'::jsonb) AS snapshot
                FROM base
            ), defaults AS (
                SELECT s.snapshot || jsonb_build_object('bank_account_id',bank.id,'payment_mode_id',mode.id)
                    || CASE WHEN bank.id IS NULL THEN '{}'::jsonb ELSE jsonb_build_object('bank_details',
                        jsonb_build_object('bank_name',bank.bank_name,'branch_name',bank.branch_name,
                        'account_number_masked',bank.account_number_masked,'ifsc',bank.ifsc)) END
                    || CASE WHEN mode.id IS NULL THEN '{}'::jsonb ELSE jsonb_build_object('payment_method',mode.name) END AS snapshot,
                    (s.snapshot->>'payment_terms_days')::int AS terms
                FROM settings s
                LEFT JOIN public.fam_bank_accounts bank ON bank.id::text=s.snapshot->>'bank_account_id'
                    AND bank.company_id=@company AND bank.active
                LEFT JOIN public.fam_payment_modes mode ON mode.id::text=s.snapshot->>'payment_mode_id'
                    AND mode.company_id=@company AND mode.active
            ), draft AS (
                INSERT INTO public.srm_invoice_drafts (organization_id,sales_order_id,engagement_id,billing_plan_id,customer_id,status,source_type,
                    currency,subtotal,discount_amount,tax_amount,total_amount,created_by)
                SELECT @company,id,@engagement,@plan,coalesce(@buyer,customer_id),'draft',@source_type,@currency,@subtotal,@discount,@tax,@total,@actor
                FROM public.srm_sales_orders WHERE id=@order
                UNION ALL SELECT @company,NULL,NULL,NULL,@buyer,'draft',@source_type,@currency,@subtotal,@discount,@tax,@total,@actor
                WHERE @appointment IS NOT NULL
                RETURNING id,sales_order_id,engagement_id,customer_id
            ), invoice AS (
                INSERT INTO public.srm_invoices (organization_id,invoice_number,invoice_draft_id,sales_order_id,engagement_id,customer_id,status,
                    issue_date,due_date,currency,subtotal,discount_amount,tax_amount,total_amount,paid_amount,balance_amount,created_by)
                SELECT @company,@number,d.id,d.sales_order_id,d.engagement_id,d.customer_id,'draft',@issue,@issue+coalesce(@recurring_terms,defaults.terms),
                    @currency,@subtotal,@discount,@tax,@total,0,@total,@actor FROM draft d CROSS JOIN defaults
                WHERE @recurring_terms IS NOT NULL OR defaults.terms IN (0,7,15,30,45,60,90)
                RETURNING id,invoice_number,invoice_draft_id,currency,total_amount,due_date
            ), saved_lines AS (
                INSERT INTO public.srm_invoice_lines (invoice_id,source_type,source_id,description,quantity,unit_price,
                    discount_amount,tax_amount,line_total)
                SELECT invoice.id,CASE WHEN @appointment IS NOT NULL OR @milestone IS NOT NULL THEN @source_type
                    WHEN line.""SourceLineId"" IS NULL THEN 'sales_order' ELSE 'sales_order_line' END,
                    coalesce(@appointment,@milestone,line.""SourceLineId"",@order),line.""Description"",line.""Quantity"",line.""Price"",line.""Discount"",line.""Tax"",line.""Total""
                FROM invoice CROSS JOIN jsonb_to_recordset(@lines::jsonb) AS line(""SourceLineId"" int,""Description"" text,
                    ""Quantity"" numeric,""Price"" numeric,""Discount"" numeric,""Tax"" numeric,""Total"" numeric)
                RETURNING id
            ), history AS (
                INSERT INTO public.srm_invoice_history (invoice_id,to_status,actor_user_id,notes)
                SELECT id,'draft',@actor,'Invoice draft created' FROM invoice RETURNING id
            ), snapshot AS (
                INSERT INTO public.suite_service_policies (scope_key,organization_id,module_key,kind,values_json,version,updated_by)
                SELECT 'form-snapshot:'||@company||':srm:invoice:'||invoice.id,@company,'srm','form_snapshot',
                    (defaults.snapshot || @recurring_snapshot)::json,1,@actor FROM invoice CROSS JOIN defaults
                ON CONFLICT (scope_key) DO UPDATE SET values_json=excluded.values_json,updated_by=excluded.updated_by,
                    version=suite_service_policies.version+1,updated_at=now()
                WHERE suite_service_policies.organization_id=@company AND suite_service_policies.kind='form_snapshot'
                RETURNING id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'invoice',id,'draft_created',@actor,
                    json_build_object('source_type',@source_type,'source_id',coalesce(@appointment,@milestone,@order)) FROM invoice RETURNING id
            ), billed AS (
                UPDATE public.srm_billing_milestones m SET invoice_draft_id=i.invoice_draft_id,status='invoiced'
                FROM invoice i WHERE m.id=@milestone AND m.billing_plan_id=@plan AND m.invoice_draft_id IS NULL
                RETURNING m.id,i.id AS invoice_id,i.invoice_draft_id
            ), billed_audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'billing_milestone',id,CASE WHEN @batch THEN 'recurring_invoice_created' ELSE 'invoiced' END,@actor,
                    json_build_object('invoice_id',invoice_id,'invoice_draft_id',invoice_draft_id) FROM billed RETURNING id
            ), notice AS (
                INSERT INTO public.notifications (company_id,user_id,title,message,module,event_type,related_entity_type,
                    related_entity_id,action_url,priority,channels,is_read)
                SELECT @company,@actor,'Invoice draft created',invoice_number||' is ready for review.','srm','srm.lifecycle',
                    'invoice',id,'/srm/invoices/'||id,'normal',json_build_array('in_app'),false FROM invoice
                UNION ALL SELECT @company,@actor,'Recurring invoice draft created','Review '||invoice_number||' before approval and sending.',
                    'srm','srm.lifecycle','invoice',id,'/srm/invoices/'||id,'normal',json_build_array('in_app'),false
                    FROM invoice WHERE @notify_recurring RETURNING id
            ), ownership AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT records.resource,records.id::text,@company,@branch,'validated-write' FROM (
                    SELECT 'srm_invoice_drafts' AS resource,id FROM draft UNION ALL
                    SELECT 'srm_invoices',id FROM invoice UNION ALL SELECT 'srm_invoice_lines',id FROM saved_lines UNION ALL
                    SELECT 'srm_invoice_history',id FROM history UNION ALL SELECT 'srm_audit_logs',id FROM audit UNION ALL
                    SELECT 'notifications',id FROM notice UNION ALL SELECT 'srm_audit_logs',id FROM billed_audit
                ) records
            )
            SELECT id,invoice_number,currency,total_amount,due_date FROM invoice WHERE (SELECT count(*) FROM snapshot)=1
                AND (@milestone IS NULL OR (SELECT count(*) FROM billed_audit)=1)", db, tx, branch, actor);
        write.Parameters.AddWithValue("default_keys", NpgsqlDbType.Array | NpgsqlDbType.Text,
            new[] { defaultsKey, defaultsKey + ":module:srm", defaultsKey + ":branch:" + branchKey, defaultsKey + ":branch:" + branchKey + ":module:srm" });
        write.Parameters.AddWithValue("order",NpgsqlDbType.Integer,(object?)order ?? DBNull.Value);
        write.Parameters.AddWithValue("appointment",NpgsqlDbType.Integer,(object?)appointment?.Id ?? DBNull.Value);
        write.Parameters.AddWithValue("source_type",appointment.HasValue ? "industry_appointment" : milestone is null ? "sales_order" : "billing_milestone");
        write.Parameters.AddWithValue("milestone", NpgsqlDbType.Integer, (object?)milestone?.Id ?? DBNull.Value);
        write.Parameters.AddWithValue("engagement", NpgsqlDbType.Integer, (object?)milestone?.Engagement ?? DBNull.Value);
        write.Parameters.AddWithValue("plan", NpgsqlDbType.Integer, (object?)milestone?.Plan ?? DBNull.Value);
        write.Parameters.AddWithValue("buyer", NpgsqlDbType.Integer, (object?)(appointment?.Customer ?? milestone?.Buyer) ?? DBNull.Value);
        write.Parameters.AddWithValue("currency", currency);
        write.Parameters.AddWithValue("number", number);
        write.Parameters.AddWithValue("issue", NpgsqlDbType.Date, milestone?.Recurring?.IssueDate ?? DateTime.Today);
        write.Parameters.AddWithValue("recurring_terms", NpgsqlDbType.Integer, (object?)milestone?.Recurring?.PaymentTerms ?? DBNull.Value);
        write.Parameters.AddWithValue("recurring_snapshot", NpgsqlDbType.Jsonb, milestone?.Recurring?.Snapshot ?? "{}");
        write.Parameters.AddWithValue("batch", milestone?.Batch == true);
        write.Parameters.AddWithValue("notify_recurring", milestone?.NotifyRecurring == true);
        write.Parameters.AddWithValue("subtotal", lines.Sum(row => row.Subtotal));
        write.Parameters.AddWithValue("discount", lines.Sum(row => row.Discount));
        write.Parameters.AddWithValue("tax", lines.Sum(row => row.Tax));
        write.Parameters.AddWithValue("total", lines.Sum(row => row.Total));
        write.Parameters.AddWithValue("lines", NpgsqlDbType.Jsonb, JsonSerializer.Serialize(lines));
        using var reader = await write.ExecuteReaderAsync();
        if (!await reader.ReadAsync())
            throw new InvalidOperationException("Review the company's invoice presentation and payment terms settings before drafting.");
        return new SalesInvoiceDraftResult(reader.GetInt32(0), reader.GetString(1), reader.GetString(2), reader.GetDecimal(3),
            reader.GetDateTime(4));
    }
}
