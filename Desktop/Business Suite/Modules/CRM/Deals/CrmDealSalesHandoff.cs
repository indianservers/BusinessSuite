using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class CrmDealRepository
{
    private async Task<int?> CreateWonHandoffAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,DataRow deal,
        decimal amount,DateTime today,CrmDealQuoteChoice? selection,CancellationToken cancellation)
    {
        if (settings.BranchId is not int branch || deal["owning_branch"] is not int ownerBranch || ownerBranch!=branch)
            throw new InvalidOperationException("Select the deal's owning branch before closing Won.");
        int id=(int)deal["id"];
        var grant=await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,branch,actor,"srm","create",
            "srm_manage","srm_admin","srm_sales_order_create");
        if (grant.Scope is not ("organization" or "branch"))
            throw new UnauthorizedAccessException("The Sales handoff requires branch-wide or organization-wide create access.");
        if (deal["company_id"] is not int customer)
            throw new InvalidOperationException("Link the customer before closing this deal Won.");
        string currency=Convert.ToString(deal["currency"])??"";
        if (currency.Length!=3 || currency.Any(value=>value<'A'||value>'Z'))
            throw new InvalidOperationException("Set a valid three-letter deal currency before closing Won.");

        using (var source=Query(db,tx,@"SELECT
            EXISTS(SELECT 1 FROM public.crm_quotations WHERE organization_id=@org AND deal_id=@id AND deleted_at IS NULL),
            EXISTS(SELECT 1 FROM public.srm_sales_orders WHERE organization_id=@org AND crm_deal_id=@id)
                OR EXISTS(SELECT 1 FROM public.srm_engagements WHERE organization_id=@org AND crm_deal_id=@id),
            EXISTS(SELECT 1 FROM public.crm_companies c WHERE c.organization_id=@org AND c.id=@customer
                AND c.deleted_at IS NULL AND c.status='Active' AND "+CrmDirectoryWrites.BranchScope("crm_companies","c",includeShares:true)+ @"),
            EXISTS(SELECT 1 FROM public.business_pack_contexts WHERE company_id=@org AND branch_id=@branch
                AND (state='active' OR ever_activated))",
            ("id",NpgsqlDbType.Integer,id),("customer",NpgsqlDbType.Integer,customer),("branch",NpgsqlDbType.Integer,branch)))
        using (var reader=await source.ExecuteReaderAsync(cancellation))
        {
            await reader.ReadAsync(cancellation);
            if (reader.GetBoolean(0) && selection is null)
                throw new InvalidOperationException("Select an approved quotation for this deal before closing Won.");
            if (reader.GetBoolean(1))
                throw new InvalidOperationException("A Sales handoff already exists for this deal. Review its existing Sales records before closing.");
            if (!reader.GetBoolean(2))
                throw new InvalidOperationException("Link an active customer available in the deal's branch before closing Won.");
            if (reader.GetBoolean(3))
                throw new InvalidOperationException("This branch uses an operational pack. Its Sales handoff requires pack authorization.");
        }
        var quote=selection is null?null:await ReadQuoteSourceAsync(db,tx,actor,deal,selection,cancellation);
        var fallbackName=Convert.ToString(deal["name"])??"";
        string lineData=System.Text.Json.JsonSerializer.Serialize(quote is null
            ? new[] {new CrmDealQuoteLine(0,null,fallbackName,1,amount,0,0,amount)}
            : quote.Lines.ToArray());
        string order=await ReserveHandoffNumberAsync(db,tx,"srm_sales_orders","order_number","SO",cancellation);
        string engagement=await ReserveHandoffNumberAsync(db,tx,"srm_engagements","engagement_number","ENG",cancellation);
        string contract=await ReserveHandoffNumberAsync(db,tx,"srm_contracts","contract_number","CTR",cancellation);
        int? contact=deal["contact_id"] as int?;
        if (contact.HasValue)
        {
            using var contactCheck=Query(db,tx,@"SELECT id FROM public.crm_contacts p WHERE p.organization_id=@org AND p.id=@contact
                AND p.deleted_at IS NULL AND "+CrmDirectoryWrites.BranchScope("crm_contacts","p",includeShares:true)+" FOR SHARE",
                ("contact",NpgsqlDbType.Integer,contact));
            if (await contactCheck.ExecuteScalarAsync(cancellation) is null)
                throw new InvalidOperationException("The linked contact is unavailable in this branch.");
        }
        using var handoff=Query(db,tx,@"WITH sales_order AS (
            INSERT INTO public.srm_sales_orders (organization_id,order_number,status,crm_deal_id,crm_quote_id,crm_company_id,crm_contact_id,
                customer_id,assigned_user_id,created_by,title,currency,subtotal,discount_amount,tax_amount,total_amount,terms,metadata_json)
            VALUES (@org,@order,'draft',@id,@quote,@customer,@contact,@customer,@owner,@actor,@name,@currency,@subtotal,@discount,@tax,@amount,@terms,
                json_build_object('source','crm_won_handoff','crm_status','Won','quote_version',@quote_version)) RETURNING id
        ), order_line AS (
            INSERT INTO public.srm_sales_order_lines (sales_order_id,source_quote_line_id,product_id,description,service_type,
                quantity,unit_price,discount_amount,tax_amount,line_total)
            SELECT o.id,NULLIF(i.""Id"",0),i.""ProductId"",i.""Description"",'service',i.""Quantity"",i.""UnitPrice"",i.""Discount"",i.""Tax"",i.""Total""
            FROM sales_order o CROSS JOIN jsonb_to_recordset(@lines::jsonb)
                AS i(""Id"" int,""ProductId"" int,""Description"" text,""Quantity"" numeric,""UnitPrice"" numeric,
                    ""Discount"" numeric,""Tax"" numeric,""Total"" numeric)
            RETURNING id,sales_order_id,source_quote_line_id,description,line_total
        ), contract_row AS (
            INSERT INTO public.srm_contracts (organization_id,contract_number,sales_order_id,customer_id,title,status,contract_type,
                contract_value,currency,terms,created_by)
            SELECT @org,@contract,id,@customer,'Contract for '||@name,'draft','services',@amount,@currency,@terms,@actor
                FROM sales_order RETURNING id,sales_order_id
        ), engagement_row AS (
            INSERT INTO public.srm_engagements (organization_id,engagement_number,sales_order_id,contract_id,customer_id,crm_deal_id,crm_quote_id,
                assigned_user_id,project_manager_user_id,name,status,billing_type,budget_amount,currency,created_by)
            SELECT @org,@engagement,sales_order_id,id,@customer,@id,@quote,@owner,@owner,@name,'created','fixed_fee',@amount,@currency,@actor
                FROM contract_row RETURNING id,sales_order_id,contract_id
        ), billing AS (
            INSERT INTO public.srm_billing_plans (organization_id,engagement_id,name,billing_type,status,currency,total_amount,created_by)
            SELECT @org,id,'Billing plan for '||@order,'milestone','draft',@currency,@amount,@actor
                FROM engagement_row RETURNING id,engagement_id
        ), milestones AS (
            INSERT INTO public.srm_billing_milestones (billing_plan_id,name,status,amount,metadata_json)
            SELECT billing.id,line.description,'pending',line.line_total,
                json_build_object('sales_order_line_id',line.id,'source_quote_line_id',line.source_quote_line_id,'pms_template_key',NULL::text)
                FROM billing CROSS JOIN order_line line
        ), relationships AS (
            INSERT INTO public.srm_engagement_links (engagement_id,linked_module,linked_entity_type,linked_entity_id,label)
            SELECT e.id,link.module,link.kind,link.identifier,link.module||':'||link.kind
            FROM engagement_row e CROSS JOIN LATERAL (VALUES ('crm','deal',@id),('crm','quote',@quote),('crm','company',@customer),
                ('crm','contact',@contact),('srm','sales_order',e.sales_order_id),('srm','contract',e.contract_id)) link(module,kind,identifier)
            WHERE link.identifier IS NOT NULL
        ), revenue AS (
            INSERT INTO public.srm_revenue_events (organization_id,engagement_id,event_type,amount,currency,recognized_on,metadata_json)
            SELECT @org,id,'crm_won_handoff',@amount,@currency,@today,json_build_object('crm_deal_id',@id) FROM engagement_row
        ), quote_link AS (
            UPDATE public.crm_quotations q SET converted_srm_sales_order_id=e.sales_order_id,converted_srm_contract_id=e.contract_id,
                converted_srm_engagement_id=e.id,updated_by_user_id=@actor,updated_at=now()
            FROM engagement_row e WHERE q.organization_id=@org AND q.id=@quote AND q.deal_id=@id
            RETURNING q.id
        ), quote_conversion AS (
            INSERT INTO public.crm_quote_srm_conversion_logs (organization_id,quote_id,deal_id,srm_sales_order_id,
                srm_contract_id,srm_engagement_id,srm_billing_plan_id,idempotency_key,status,message,payload_json,created_by_user_id)
            SELECT @org,q.id,@id,e.sales_order_id,e.contract_id,e.id,b.id,'desktop:quote:'||q.id,'converted',
                'Quote converted to SRM commercial records.',json_build_object('quote_version',@quote_version),@actor
            FROM quote_link q CROSS JOIN engagement_row e JOIN billing b ON b.engagement_id=e.id
        ), quote_activity AS (
            INSERT INTO public.crm_activities (organization_id,branch_id,owner_user_id,entity_type,entity_id,
                activity_type,title,subject,body,description,metadata_json,status,activity_date,created_by_user_id,updated_by_user_id)
            SELECT @org,@branch,@actor,'quotation',q.id,'srm_conversion','Quote converted to SRM','Quote converted to SRM',
                'Accepted CRM quote created or linked SRM commercial records.',
                'Accepted CRM quote created or linked SRM commercial records.',
                json_build_object('salesOrderId',e.sales_order_id,'engagementId',e.id),'Completed',now(),@actor,@actor
                FROM quote_link q CROSS JOIN engagement_row e RETURNING id
        ), quote_activity_scope AS (
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'crm_activities',id::text,@org,@branch,'desktop-crm' FROM quote_activity
        ), quote_timeline AS (
            INSERT INTO public.crm_timeline_events (organization_id,record_type,record_id,event_type,title,description,
                metadata_json,actor_user_id)
            SELECT @org,'quotation',q.id,'srm_conversion','Quote converted to SRM',
                'Accepted CRM quote created or linked SRM commercial records.',
                json_build_object('salesOrderId',e.sales_order_id,'engagementId',e.id),@actor
                FROM quote_link q CROSS JOIN engagement_row e
        ), ownership AS (
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT records.resource,records.id::text,@org,@branch,'desktop-crm-handoff' FROM (
                SELECT 'srm_sales_orders' AS resource,id FROM sales_order UNION ALL
                SELECT 'srm_sales_order_lines',id FROM order_line UNION ALL
                SELECT 'srm_contracts',id FROM contract_row UNION ALL
                SELECT 'srm_engagements',id FROM engagement_row UNION ALL
                SELECT 'srm_billing_plans',id FROM billing
            ) records
        ), audit AS (
            INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
            SELECT @org,'sales_order',e.sales_order_id,'crm_won_handoff',@actor,
                json_build_object('crm_deal_id',@id,'engagement_id',e.id,'contract_id',e.contract_id,'billing_plan_id',b.id)
                FROM engagement_row e JOIN billing b ON b.engagement_id=e.id
            UNION ALL
            SELECT @org,'engagement',id,'created_from_crm_won',@actor,
                json_build_object('crm_deal_id',@id,'sales_order_id',sales_order_id) FROM engagement_row
            UNION ALL
            SELECT @org,'billing_plan',b.id,'created_from_sales_order',@actor,
                json_build_object('sales_order_id',e.sales_order_id,'contract_id',e.contract_id)
                FROM billing b JOIN engagement_row e ON e.id=b.engagement_id
        ), notifications AS (
            INSERT INTO public.notifications (company_id,user_id,title,message,module,event_type,related_entity_type,related_entity_id,
                action_url,priority,channels,is_read)
            SELECT @org,u.id,n.title,n.message,'srm','srm.lifecycle',n.kind,n.id,n.url,'normal','[""in_app""]'::json,false
                FROM engagement_row e JOIN public.users u ON u.id=@owner AND u.is_active
                CROSS JOIN LATERAL (VALUES ('SRM sales order created',@order||' was created from CRM deal '||@name||'.',
                    'sales_order',e.sales_order_id,'/srm/sales-orders/'||e.sales_order_id),
                    ('SRM engagement ready',@engagement||' is ready for project creation.','engagement',e.id,'/srm/engagements/'||e.id))
                    n(title,message,kind,id,url)
                WHERE u.id=@actor OR EXISTS (SELECT 1 FROM public.common_people p WHERE p.user_id=u.id AND p.organization_id=@org)
        ), handoff_activity AS (
            INSERT INTO public.crm_activities (organization_id,branch_id,owner_user_id,entity_type,entity_id,deal_id,activity_type,
                title,subject,body,status,activity_date,created_by_user_id,updated_by_user_id)
            VALUES (@org,@branch,@actor,'deal',@id,@id,'srm_handoff','SRM commercial handoff created','SRM commercial handoff created',
                'Created Sales order, engagement, contract and billing plan.','Completed',now(),@actor,@actor) RETURNING id
        ), activity_scope AS (
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'crm_activities',id::text,@org,@branch,'desktop-crm' FROM handoff_activity
        ), timeline AS (
            INSERT INTO public.crm_timeline_events (organization_id,record_type,record_id,event_type,title,description,actor_user_id)
            VALUES (@org,'deal',@id,'srm_handoff','SRM commercial handoff created',
                'Created Sales order, engagement, contract and billing plan.',@actor)
        ) SELECT id FROM sales_order",
            ("id",NpgsqlDbType.Integer,id),("branch",NpgsqlDbType.Integer,branch),("actor",NpgsqlDbType.Integer,actor.Id),
            ("owner",NpgsqlDbType.Integer,deal["owner_user_id"] as int? ?? actor.Id),("customer",NpgsqlDbType.Integer,customer),
            ("contact",NpgsqlDbType.Integer,contact),("name",NpgsqlDbType.Text,deal["name"]),("currency",NpgsqlDbType.Text,currency),
            ("amount",NpgsqlDbType.Numeric,quote?.Choice.Total??amount),("subtotal",NpgsqlDbType.Numeric,quote?.Subtotal??amount),
            ("discount",NpgsqlDbType.Numeric,quote?.Discount??(deal["discount_amount"] as decimal? ?? 0)),
            ("tax",NpgsqlDbType.Numeric,quote?.Tax??0),("terms",NpgsqlDbType.Text,quote?.Terms),
            ("quote",NpgsqlDbType.Integer,quote?.Choice.Id),("quote_version",NpgsqlDbType.Integer,quote?.Choice.Version),
            ("lines",NpgsqlDbType.Json,lineData),("today",NpgsqlDbType.Date,today),("order",NpgsqlDbType.Text,order),
            ("engagement",NpgsqlDbType.Text,engagement),("contract",NpgsqlDbType.Text,contract));
        return (int)(await handoff.ExecuteScalarAsync(cancellation))!;
    }

    // All series identifiers are selected by the fixed handoff call sites.
    private async Task<string> ReserveHandoffNumberAsync(NpgsqlConnection db,NpgsqlTransaction tx,string table,string column,
        string prefix,CancellationToken cancellation)
    {
        using var command=Query(db,tx,$@"WITH candidate AS (
            SELECT GREATEST(COALESCE((SELECT last_number::numeric FROM public.business_number_sequences WHERE series=@series),0),
                COALESCE((SELECT max(substring({column} FROM '[0-9]+$')::numeric) FROM public.{table}
                    WHERE COALESCE(organization_id,1)=@org AND {column} LIKE @prefix||'-%'
                     AND {column} ~ '-[0-9]+$'),0))+1 AS next_value
        ) INSERT INTO public.business_number_sequences (series,last_number)
            SELECT @series,next_value::bigint FROM candidate
            ON CONFLICT (series) DO UPDATE SET last_number=excluded.last_number RETURNING last_number",
            ("series",NpgsqlDbType.Text,$"srm_company:{settings.OrganizationId}:{table}:{prefix}"),("prefix",NpgsqlDbType.Text,prefix));
        long value=(long)(await command.ExecuteScalarAsync(cancellation))!;
        return $"{prefix}-{value:D6}";
    }
}
