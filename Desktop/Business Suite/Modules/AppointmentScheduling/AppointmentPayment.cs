using System.Globalization;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record AppointmentPaymentIntent(Guid Request,int Revision,decimal Amount,string Method,string Reference);
internal sealed class AppointmentPaymentRejectedException(string message) : InvalidOperationException(message);

internal sealed partial class AppointmentRepository
{
    internal ProtectedAppointmentJournal<AppointmentPaymentIntent> PaymentJournal(int appointment) =>
        new(settings,"Appointment payments",ValidateAppointmentPayment,maximumBytes:32768,
            readError:"The saved payment request could not be verified. Reconcile this appointment before continuing.",
            openError:"The saved payment request could not be opened for this Windows account.",
            resource:"\n"+appointment.ToString(CultureInfo.InvariantCulture));

    private static void ValidateAppointmentPayment(AppointmentPaymentIntent intent)
    {
        if (intent.Request==Guid.Empty || intent.Revision<=0 || intent.Amount is <=0 or >999999999999.99m ||
            RoundBilling(intent.Amount)!=intent.Amount || intent.Reference is null || intent.Reference.Length>120 ||
            intent.Method is not ("cash" or "upi" or "card" or "bank_transfer" or "cheque" or "other"))
            throw new ArgumentException("Enter a positive amount to two decimals, a payment method and a reference of up to 120 characters.");
    }

    internal async Task<int> RecordAppointmentPaymentAsync(int appointment,AppointmentPaymentIntent intent,CancellationToken cancellation)
    {
        ValidateAppointmentPayment(intent);
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await AuthorizeAsync(db,tx,"collect",cancellation);
        await RequireAccessAsync(db,tx,actor,"view");
        int customer;
        int revision;
        JsonObject metadata;
        using (var header=Query(db,tx,@"SELECT r.customer_id,r.revision,r.data::text,
                EXISTS(SELECT 1 FROM public.srm_pos_service_occurrences p WHERE p.appointment_id=r.id)
            FROM public.srm_industry_records r WHERE r.id=@id AND r.organization_id=@org AND r.branch_id=@branch
                AND r.kind='appointment' AND "+Legacy+" FOR UPDATE OF r",("id",NpgsqlDbType.Integer,appointment)))
        using (var row=await header.ExecuteReaderAsync(cancellation))
        {
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("The appointment is unavailable in this branch.");
            if (row.GetBoolean(3))
                throw new AppointmentPaymentRejectedException("Use the linked service checkout to record payments for this appointment.");
            if (row.IsDBNull(0))
                throw new AppointmentPaymentRejectedException("The visit has no customer for payment recording.");
            customer=row.GetInt32(0);
            revision=row.GetInt32(1);
            metadata=JsonNode.Parse(row.GetString(2))!.AsObject();
        }

        string request=intent.Request.ToString();
        string number=$"APPT-{appointment}-{intent.Request:N}";
        string amount=intent.Amount.ToString("0.00",CultureInfo.InvariantCulture);
        if (metadata["_payment_requests"] is not null && metadata["_payment_requests"] is not JsonObject)
            throw new InvalidOperationException("The appointment payment history is unavailable.");
        var requests = metadata["_payment_requests"] as JsonObject ?? new JsonObject();
        if (requests[request] is JsonObject existing)
        {
            if (existing["details"] is not JsonObject details || details["amount"]?.ToString()!=amount ||
                details["payment_method"]?.ToString()!=intent.Method || details["reference_number"]?.ToString()!=intent.Reference)
                throw new InvalidOperationException("This payment request has different recorded details.");
            if (!int.TryParse(existing["receipt_id"]?.ToString(),out int recovered))
                throw new InvalidOperationException("The stored appointment payment reference is incomplete.");
            using var receipt=Query(db,tx,@"SELECT r.id FROM public.srm_receipts r
                WHERE r.id=@receipt AND r.organization_id=@org AND r.customer_id=@customer AND r.receipt_number=@number
                  AND NOT EXISTS(SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='srm_receipts'
                    AND o.resource_key=r.id::text AND (o.company_id<>@org OR o.branch_id<>@branch))",
                ("receipt",NpgsqlDbType.Integer,recovered),("customer",NpgsqlDbType.Integer,customer),("number",NpgsqlDbType.Text,number));
            return await receipt.ExecuteScalarAsync(cancellation) is int found ? found
                : throw new InvalidOperationException("The recorded appointment receipt is unavailable.");
        }
        if (revision!=intent.Revision)
            throw new AppointmentPaymentRejectedException("The booking or its payments changed. Refresh before recording money received.");
        var state=await ReadBillingCoreAsync(db,tx,actor,appointment,cancellation);
        if (!state.CanCollect || intent.Amount>state.Balance)
            throw new AppointmentPaymentRejectedException("Enter a received payment within the current appointment balance.");

        DateTime date=await AppointmentPaymentDateAsync(db,tx,cancellation);
        int id;
        if (state.InvoiceId is int invoice && state.InvoiceStatus is not ("draft" or "pending_approval"))
        {
            using (var issued=AppointmentInvoiceQuery(db,tx,
                "SELECT i.approved_at IS NOT NULL AND c.issued_at IS NOT NULL AND i.balance_amount>=@amount" +
                " AND i.paid_amount+i.balance_amount=i.total_amount" +
                " AND i.status IN ('approved','issued','sent','overdue','partially_paid')",appointment,invoice,customer,state.Currency))
            {
                issued.Parameters.AddWithValue("amount",intent.Amount);
                if (await issued.ExecuteScalarAsync(cancellation) is not true)
                    throw new AppointmentPaymentRejectedException("The linked invoice must be issued with a consistent balance.");
            }
            var sales=new SalesOrderRepository(settings);
            var payment=new SalesPaymentIntent(intent.Request,intent.Amount,intent.Reference,intent.Method,date);
            id=(await sales.SaveAppointmentInvoicePaymentAsync(db,tx,Branch,actor.Id,invoice,number,payment)).ReceiptId;
        }
        else
        {
            id=await SaveAppointmentAdvanceAsync(db,tx,actor.Id,customer,state.Currency,number,date,intent,cancellation);
        }

        requests[request]=new JsonObject
        {
            ["receipt_id"]=id,
            ["details"]=new JsonObject { ["amount"]=amount,["payment_method"]=intent.Method,["reference_number"]=intent.Reference }
        };
        if (metadata["_payment_requests"] is null)
            metadata["_payment_requests"]=requests;
        using var update=Query(db,tx,@"UPDATE public.srm_industry_records SET data=@data,revision=revision+1,updated_at=now()
            WHERE id=@id AND organization_id=@org AND branch_id=@branch AND revision=@revision",
            ("id",NpgsqlDbType.Integer,appointment),("revision",NpgsqlDbType.Integer,revision),("data",NpgsqlDbType.Json,metadata.ToJsonString()));
        if (await update.ExecuteNonQueryAsync(cancellation)!=1)
            throw new InvalidOperationException("The booking changed before its receipt could be linked.");
        await AuditAsync(db,tx,actor.Id,appointment,"payment_recorded",state.Visit,revision+1,metadata,cancellation);
        await tx.CommitAsync(cancellation);
        return id;
    }

    private async Task<DateTime> AppointmentPaymentDateAsync(NpgsqlConnection db,NpgsqlTransaction tx,CancellationToken cancellation)
    {
        using var query=Query(db,tx,@"SELECT (now() AT TIME ZONE coalesce((
            SELECT p.values_json->>'timezone' FROM public.suite_service_policies p
            WHERE p.organization_id=@org AND p.kind='form_defaults' AND p.values_json->>'timezone' IS NOT NULL
              AND p.scope_key IN ('form-defaults:company:'||@org::text,
                'form-defaults:company:'||@org::text||':module:srm',
                'form-defaults:company:'||@org::text||':branch:'||@branch::text,
                'form-defaults:company:'||@org::text||':branch:'||@branch::text||':module:srm')
            ORDER BY (p.scope_key LIKE '%:branch:%') DESC,(p.scope_key LIKE '%:module:srm') DESC LIMIT 1),
            nullif(c.default_timezone,''),'Asia/Kolkata'))::date::timestamp
            FROM public.companies c WHERE c.id=@org");
        return ((DateTime)(await query.ExecuteScalarAsync(cancellation))!).Date;
    }

    private async Task<int> SaveAppointmentAdvanceAsync(NpgsqlConnection db,NpgsqlTransaction tx,int actor,int customer,
        string currency,string number,DateTime date,AppointmentPaymentIntent intent,CancellationToken cancellation)
    {
        using var query=Query(db,tx,@"WITH receipt AS (
            INSERT INTO public.srm_receipts(organization_id,receipt_number,customer_id,status,receipt_date,payment_method,
                reference_number,currency,amount,unallocated_amount,created_by)
            VALUES(@org,@number,@customer,'confirmed',@date,@method,nullif(@reference,''),@currency,@amount,@amount,@actor)
            RETURNING id
        ), ledger AS (
            INSERT INTO public.srm_audit_logs(organization_id,entity_type,entity_id,action,actor_user_id,before_json,after_json)
            SELECT @org,'receipt',id,'created',@actor,NULL,json_build_object('status','draft','receipt_number',@number) FROM receipt
            UNION ALL SELECT @org,'receipt',id,'confirmed',@actor,json_build_object('status','draft'),
                json_build_object('status','confirmed') FROM receipt RETURNING id
        ), owned AS (
            INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
            SELECT 'srm_receipts',id::text,@org,@branch,'validated-write' FROM receipt
            UNION ALL SELECT 'srm_audit_logs',id::text,@org,@branch,'validated-write' FROM ledger
        ) SELECT id FROM receipt",
            ("actor",NpgsqlDbType.Integer,actor),("customer",NpgsqlDbType.Integer,customer),("currency",NpgsqlDbType.Text,currency),
            ("number",NpgsqlDbType.Text,number),("date",NpgsqlDbType.Date,date),("method",NpgsqlDbType.Text,intent.Method),
            ("reference",NpgsqlDbType.Text,intent.Reference),("amount",NpgsqlDbType.Numeric,intent.Amount));
        return (int)(await query.ExecuteScalarAsync(cancellation))!;
    }
}
