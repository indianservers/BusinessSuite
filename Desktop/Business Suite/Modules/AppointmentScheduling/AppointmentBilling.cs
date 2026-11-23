using System.Data;
using System.Globalization;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record AppointmentBillingView(string Visit,string Currency,decimal Total,decimal Paid,decimal Advance,
    decimal Balance,string? Invoice,string? InvoiceStatus,DataTable Receipts,bool Grouped,int Revision,bool CanDraft,
    int? InvoiceId,bool CanApprove,bool CanCollect,bool CanApplyAdvance);

internal sealed partial class AppointmentRepository
{
    private async Task RequireBillingAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor)
    {
        var grant = await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,Branch,actor,"srm","view",
            "srm_collection_view","srm_collection_create","srm_invoice_view","srm_invoice_create","srm_admin");
        if (grant.Scope is not ("organization" or "branch"))
            throw new UnauthorizedAccessException("Appointment charges require branch-wide or company-wide billing access.");
    }

    private async Task<bool> CanViewBillingAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor)
    {
        try
        {
            await RequireBillingAsync(db,tx,actor);
            return true;
        }
        catch (UnauthorizedAccessException) { return false; }
    }

    private const string AppointmentInvoiceBillingScope = @" FROM public.srm_invoices i
        JOIN public.business_invoice_contexts c ON c.invoice_id=i.id
        WHERE i.id=@invoice AND i.organization_id=@org AND i.customer_id=@customer AND i.currency=@currency
            AND i.deleted_at IS NULL AND c.seller_id=@org AND c.request_id='industry:'||@appointment::text
            AND NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership owner WHERE owner.resource_table='srm_invoices'
                AND owner.resource_key=i.id::text AND (owner.company_id<>@org OR owner.branch_id<>@branch))";

    internal async Task<int> DraftAppointmentInvoiceAsync(AppointmentKey key,CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeAsync(db,tx,"invoice",cancellation);
        int customer;
        int? project;
        string title;
        JsonObject metadata;
        string visit;
        int revision;
        int? existing;
        using (var header = Query(db,tx,@"SELECT r.customer_id,r.project_id,r.title,r.data::text,r.status,r.revision,r.invoice_id,
                EXISTS(SELECT 1 FROM public.srm_pos_service_occurrences p WHERE p.appointment_id=r.id)
            FROM public.srm_industry_records r WHERE r.id=@id AND r.organization_id=@org AND r.branch_id=@branch
                AND r.kind='appointment' AND " + Legacy + " FOR UPDATE OF r",("id",NpgsqlDbType.Integer,key.Id)))
        using (var row = await header.ExecuteReaderAsync(cancellation))
        {
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("The appointment is unavailable in this branch.");
            if (row.GetBoolean(7))
                throw new InvalidOperationException("Use the linked service checkout for this appointment's invoice.");
            if (row.IsDBNull(0))
                throw new InvalidOperationException("The appointment has no customer for billing.");
            customer=row.GetInt32(0);
            project=row.IsDBNull(1) ? null : row.GetInt32(1);
            title=row.GetString(2);
            metadata=JsonNode.Parse(row.GetString(3))!.AsObject();
            visit=row.GetString(4);
            revision=row.GetInt32(5);
            existing=row.IsDBNull(6) ? null : row.GetInt32(6);
        }
        string currency = metadata["currency"]?.ToString() ?? "";
        if (existing is int current)
        {
            using var linked = AppointmentInvoiceQuery(db,tx,"SELECT i.id",key.Id,current,customer,currency);
            if (await linked.ExecuteScalarAsync(cancellation) is int id)
                return id;
            throw new InvalidOperationException("The linked invoice no longer matches this appointment.");
        }
        if (visit!="completed" || key.Revision!=revision)
            throw new InvalidOperationException("Complete and refresh the appointment before creating an invoice draft.");
        using (var buyer = Query(db,tx,Customers+" AND c.id=@customer FOR SHARE OF c",("customer",NpgsqlDbType.Integer,customer)))
            if (await buyer.ExecuteScalarAsync(cancellation) is null)
                throw new InvalidOperationException("Choose an active customer available in this branch.");
        using (var source = Query(db,tx,@"SELECT EXISTS (SELECT 1 FROM public.srm_invoice_lines
            WHERE source_type='industry_appointment' AND source_id=@id)",("id",NpgsqlDbType.Integer,key.Id)))
            if (await source.ExecuteScalarAsync(cancellation) is true)
                throw new InvalidOperationException("The appointment is already reserved by an invoice.");

        decimal subtotal=RoundBilling(ReadBillingAmount(metadata["unit_price"]));
        decimal tax=RoundBilling(subtotal*ReadBillingAmount(metadata["tax_rate"])/100m);
        var sales = new SalesOrderRepository(settings);
        int invoice = await sales.SaveAppointmentInvoiceDraftAsync(db,tx,Branch,actor.Id,key.Id,customer,currency,title,subtotal,tax);
        metadata["retention_percent"]="0";
        metadata["retention_amount"]="0.00";
        using var save = Query(db,tx,@"INSERT INTO public.business_invoice_contexts(invoice_id,project_id,seller_id,request_id,origin)
            VALUES(@invoice,@project,@org,'industry:'||@id::text,'srm');
            UPDATE public.srm_industry_records SET invoice_id=@invoice,revision=revision+1,updated_at=now(),data=@data
            WHERE id=@id AND organization_id=@org AND branch_id=@branch AND revision=@revision",
            ("invoice",NpgsqlDbType.Integer,invoice),("project",NpgsqlDbType.Integer,project),
            ("id",NpgsqlDbType.Integer,key.Id),("revision",NpgsqlDbType.Integer,revision),
            ("data",NpgsqlDbType.Json,metadata.ToJsonString()));
        if (await save.ExecuteNonQueryAsync(cancellation)!=2)
            throw new InvalidOperationException("The appointment changed before its invoice could be linked.");
        await AuditAsync(db,tx,actor.Id,key.Id,"invoice_drafted",visit,revision+1,metadata,cancellation);
        await tx.CommitAsync(cancellation);
        return invoice;
    }

    internal async Task ApproveAppointmentInvoiceAsync(int appointment,int invoice,CancellationToken cancellation)
    {
        if (appointment <= 0 || invoice <= 0)
            throw new ArgumentException("Select a linked appointment invoice.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor=await AuthorizeAsync(db,tx,"approve_invoice",cancellation);
        var sales=new SalesOrderRepository(settings);
        await sales.ApproveAppointmentInvoiceInTransactionAsync(db,tx,Branch,actor.Id,appointment,invoice,cancellation);
        await tx.CommitAsync(cancellation);
    }

    private NpgsqlCommand AppointmentInvoiceQuery(NpgsqlConnection db,NpgsqlTransaction tx,string select,int appointment,
        int invoice,int customer,string currency) => Query(db,tx,select+AppointmentInvoiceBillingScope,
        ("appointment",NpgsqlDbType.Integer,appointment),("invoice",NpgsqlDbType.Integer,invoice),
        ("customer",NpgsqlDbType.Integer,customer),("currency",NpgsqlDbType.Text,currency));

    private const string LinkedAppointmentReceiptScope = @" r.organization_id=@org AND r.customer_id=@customer AND r.id=ANY(@ids)
        AND strpos(r.receipt_number,'APPT-'||@appointment::text||'-')=1
        AND NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership owner WHERE owner.resource_table='srm_receipts'
            AND owner.resource_key=r.id::text AND (owner.company_id<>@org OR owner.branch_id<>@branch))";

    private static int[] ReadAppointmentReceiptIds(JsonObject metadata)
    {
        var ids = new HashSet<int>();
        if (metadata["_payment_requests"] is JsonObject requests)
            foreach (var request in requests)
                if (request.Value is JsonObject entry && int.TryParse(entry["receipt_id"]?.ToString(),out int id) && id>0)
                    ids.Add(id);
        return ids.ToArray();
    }

    internal async Task<AppointmentBillingView> ReadBillingAsync(int appointment,CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeAsync(db,tx,"view",cancellation);
        await RequireBillingAsync(db,tx,actor);
        return await ReadBillingCoreAsync(db,tx,actor,appointment,cancellation);
    }

    private async Task<AppointmentBillingView> ReadBillingCoreAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,
        int appointment,CancellationToken cancellation)
    {
        JsonObject metadata;
        int customer;
        int? invoice;
        string visit;
        int revision;
        using (var header = Query(db,tx,@"SELECT r.status,r.customer_id,r.invoice_id,r.data::text,
                EXISTS (SELECT 1 FROM public.srm_pos_service_occurrences p WHERE p.appointment_id=r.id),r.revision
            FROM public.srm_industry_records r WHERE r.id=@id AND r.organization_id=@org AND r.branch_id=@branch
                AND r.kind='appointment' AND " + Legacy,("id",NpgsqlDbType.Integer,appointment)))
        using (var row = await header.ExecuteReaderAsync(cancellation))
        {
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("The appointment is unavailable in this branch.");
            visit=row.GetString(0);
            revision=row.GetInt32(5);
            if (row.GetBoolean(4))
                return new(visit,"",0,0,0,0,null,null,new DataTable(),true,revision,false,null,false,false,false);
            if (row.IsDBNull(1))
                throw new InvalidOperationException("The appointment has no customer for billing.");
            customer=row.GetInt32(1);
            invoice=row.IsDBNull(2) ? null : row.GetInt32(2);
            metadata=JsonNode.Parse(row.GetString(3))!.AsObject();
        }

        string currency = metadata["currency"]?.ToString().Trim() ?? "";
        if (currency.Length == 0)
            throw new InvalidOperationException("The appointment currency is unavailable.");
        decimal quoted = ReadBillingAmount(metadata["unit_price"]);
        decimal tax = ReadBillingAmount(metadata["tax_rate"]);
        decimal total = RoundBilling(quoted + RoundBilling(quoted*tax/100m));
        decimal paid = 0;
        string? number = null;
        string? invoiceStatus = null;
        if (invoice is int invoiceId)
        {
            using var invoiceQuery = AppointmentInvoiceQuery(db,tx,
                "SELECT i.invoice_number,i.status,coalesce(i.total_amount,0),coalesce(i.paid_amount,0)",
                appointment,invoiceId,customer,currency);
            using var row = await invoiceQuery.ExecuteReaderAsync(cancellation);
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("The linked invoice no longer matches this appointment. Reconcile billing before continuing.");
            number=row.GetString(0);
            invoiceStatus=row.GetString(1);
            total=RoundBilling(row.GetDecimal(2));
            paid=RoundBilling(row.GetDecimal(3));
        }

        using var receipts = Query(db,tx,@"SELECT r.receipt_number,r.status,r.currency,coalesce(r.amount,0) AS amount,
                coalesce(r.unallocated_amount,0) AS unallocated,r.payment_method,r.reference_number
            FROM public.srm_receipts r WHERE "+LinkedAppointmentReceiptScope+
            " ORDER BY r.id",("customer",NpgsqlDbType.Integer,customer),("appointment",NpgsqlDbType.Integer,appointment),
            ("ids",NpgsqlDbType.Array|NpgsqlDbType.Integer,ReadAppointmentReceiptIds(metadata)));
        var table = new DataTable();
        decimal advance = 0;
        using (var rows = await receipts.ExecuteReaderAsync(cancellation))
        {
            for (int index=0; index<rows.FieldCount; index++)
                table.Columns.Add(rows.GetName(index),rows.GetFieldType(index));
            while (await rows.ReadAsync(cancellation))
            {
                var values = new object[rows.FieldCount];
                rows.GetValues(values);
                table.Rows.Add(values);
                if (values[2] as string == currency && values[1] as string is "confirmed" or "partially_allocated" or "allocated")
                    advance += (decimal)values[4];
            }
        }
        advance=RoundBilling(advance);
        bool canDraft = visit=="completed" && !invoice.HasValue && actor.CanWriteBranch && await CanWriteAsync(db,tx,actor,"invoice");
        bool canApprove = visit=="completed" && invoiceStatus is "draft" or "pending_approval" &&
            actor.CanWriteBranch && await CanWriteAsync(db,tx,actor,"approve_invoice");
        decimal balance = Math.Max(0,total-paid-advance);
        bool canReceive = visit is not ("cancelled" or "no_show") && invoiceStatus!="cancelled" && balance>0;
        bool canApply = invoiceStatus is "approved" or "issued" or "sent" or "overdue" or "partially_paid" &&
            advance>0 && total>paid;
        bool collectionPermission = (canReceive || canApply) && actor.CanWriteBranch && await CanWriteAsync(db,tx,actor,"collect");
        return new(visit,currency,total,paid,advance,balance,number,invoiceStatus,table,false,revision,canDraft,invoice,canApprove,
            canReceive && collectionPermission,canApply && collectionPermission);
    }

    private static decimal ReadBillingAmount(JsonNode? value)
    {
        if (!decimal.TryParse(value?.ToString(),NumberStyles.Float,CultureInfo.InvariantCulture,out decimal result) ||
            result is < 0 or > 999999999999.99m)
            throw new InvalidOperationException("The appointment's recorded price or tax is unavailable.");
        return result;
    }

    private static decimal RoundBilling(decimal amount) => Math.Round(amount,2,MidpointRounding.AwayFromZero);
}
