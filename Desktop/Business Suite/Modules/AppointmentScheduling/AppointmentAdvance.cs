using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class AppointmentRepository
{
    internal async Task<int> ApplyAppointmentAdvancesAsync(AppointmentKey key,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await AuthorizeAsync(db,tx,"collect",cancellation);
        await RequireAccessAsync(db,tx,actor,"view");

        int customer,invoice;
        JsonObject metadata;
        string visit;
        using (var header=Query(db,tx,@"SELECT r.status,r.customer_id,r.invoice_id,r.revision,r.data::text,
                EXISTS (SELECT 1 FROM public.srm_pos_service_occurrences p WHERE p.appointment_id=r.id)
            FROM public.srm_industry_records r WHERE r.id=@id AND r.organization_id=@org AND r.branch_id=@branch
                AND r.kind='appointment' AND "+Legacy+" FOR UPDATE OF r",("id",NpgsqlDbType.Integer,key.Id)))
        using (var row=await header.ExecuteReaderAsync(cancellation))
        {
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("The appointment is unavailable in this branch.");
            if (row.GetBoolean(5))
                throw new InvalidOperationException("Use the linked service checkout to apply payments for this appointment.");
            if (row.GetInt32(3)!=key.Revision)
                throw new InvalidOperationException("The booking or its payments changed. Refresh before applying advances.");
            if (row.IsDBNull(1) || row.IsDBNull(2))
                throw new InvalidOperationException("Create and approve the invoice before applying advances.");
            visit=row.GetString(0);
            customer=row.GetInt32(1);
            invoice=row.GetInt32(2);
            metadata=JsonNode.Parse(row.GetString(4))!.AsObject();
        }

        string currency=metadata["currency"]?.ToString() ?? "";
        decimal balance;
        using (var issued=AppointmentInvoiceQuery(db,tx,@"SELECT i.balance_amount,i.status,i.approved_at IS NOT NULL
            AND c.issued_at IS NOT NULL AND i.balance_amount>=0 AND i.paid_amount>=0
            AND i.total_amount=i.balance_amount+i.paid_amount AND i.engagement_id IS NULL
            AND (SELECT count(*)=1 AND bool_and(l.source_type='industry_appointment' AND l.source_id=@appointment)
                FROM public.srm_invoice_lines l WHERE l.invoice_id=i.id)",key.Id,invoice,customer,currency))
        {
            issued.CommandText+=" FOR UPDATE OF i,c";
            using var row=await issued.ExecuteReaderAsync(cancellation);
            if (!await row.ReadAsync(cancellation) || row.IsDBNull(2) || !row.GetBoolean(2) ||
                row.GetString(1) is not ("approved" or "issued" or "sent" or "overdue" or "partially_paid" or "paid"))
                throw new InvalidOperationException("Approve the matching appointment invoice before applying advances.");
            balance=row.GetDecimal(0);
        }

        var receipts = new List<(int Id,decimal Unallocated)>();
        using (var query=Query(db,tx,@"SELECT r.id,r.unallocated_amount FROM public.srm_receipts r
            LEFT JOIN public.business_receipt_contexts c ON c.receipt_id=r.id WHERE "+LinkedAppointmentReceiptScope+@"
                AND r.currency=@currency AND r.status IN ('confirmed','partially_allocated','allocated')
                AND r.unallocated_amount>0
                AND (c.receipt_id IS NULL OR (c.seller_id=@org AND c.reversed_at IS NULL))
            ORDER BY r.id FOR UPDATE OF r",("appointment",NpgsqlDbType.Integer,key.Id),("customer",NpgsqlDbType.Integer,customer),
            ("currency",NpgsqlDbType.Text,currency),("ids",NpgsqlDbType.Array|NpgsqlDbType.Integer,ReadAppointmentReceiptIds(metadata))))
        using (var rows=await query.ExecuteReaderAsync(cancellation))
        {
            while (await rows.ReadAsync(cancellation))
                receipts.Add((rows.GetInt32(0),rows.GetDecimal(1)));
        }

        int count=0;
        foreach (var receipt in receipts)
        {
            decimal amount=Math.Min(receipt.Unallocated,balance);
            if (amount<=0)
                break;
            if (await ApplyAppointmentReceiptAsync(db,tx,actor.Id,key.Id,invoice,receipt.Id,amount,currency,cancellation))
            {
                balance-=amount;
                count++;
            }
        }
        if (count>0)
        {
            using var changed=Query(db,tx,@"UPDATE public.srm_industry_records SET revision=revision+1,updated_at=now()
                WHERE id=@id AND organization_id=@org AND branch_id=@branch AND revision=@revision",
                ("id",NpgsqlDbType.Integer,key.Id),("revision",NpgsqlDbType.Integer,key.Revision));
            if (await changed.ExecuteNonQueryAsync(cancellation)!=1)
                throw new InvalidOperationException("The booking changed before its applied advances could be recorded.");
            await AuditAsync(db,tx,actor.Id,key.Id,"advances_applied",visit,key.Revision+1,metadata,cancellation);
        }
        await tx.CommitAsync(cancellation);
        return count;
    }

    private async Task<bool> ApplyAppointmentReceiptAsync(NpgsqlConnection db,NpgsqlTransaction tx,int actor,int appointment,
        int invoice,int receipt,decimal amount,string currency,CancellationToken cancellation)
    {
        string request=AppointmentAllocationKey(appointment,receipt,invoice);
        using (var lookup=Query(db,tx,@"SELECT invoice_id=@invoice AND amount=@amount FROM public.srm_receipt_allocations
            WHERE receipt_id=@receipt AND request_id=@request",("receipt",NpgsqlDbType.Integer,receipt),("invoice",NpgsqlDbType.Integer,invoice),
            ("amount",NpgsqlDbType.Numeric,amount),("request",NpgsqlDbType.Text,request)))
        {
            object? existing=await lookup.ExecuteScalarAsync(cancellation);
            if (existing is true)
                return false;
            if (existing is not null)
                throw new InvalidOperationException("This advance has a different recorded allocation. Reconcile it before retrying.");
        }

        using var apply=Query(db,tx,@"WITH changed_receipt AS (
            UPDATE public.srm_receipts SET unallocated_amount=unallocated_amount-@amount,
                status=CASE WHEN unallocated_amount=@amount THEN 'allocated' ELSE 'partially_allocated' END,updated_at=now()
            WHERE id=@receipt AND organization_id=@org AND unallocated_amount>=@amount RETURNING id
        ), changed_invoice AS (
            UPDATE public.srm_invoices i SET paid_amount=i.paid_amount+@amount,balance_amount=i.balance_amount-@amount,
                status=CASE WHEN i.balance_amount=@amount THEN 'paid' ELSE 'partially_paid' END,updated_at=now()
            FROM changed_receipt r WHERE i.id=@invoice AND i.organization_id=@org AND i.balance_amount>=@amount RETURNING i.id
        ), allocation AS (
            INSERT INTO public.srm_receipt_allocations(receipt_id,invoice_id,amount,allocated_by,request_id)
            SELECT r.id,i.id,@amount,@actor,@request FROM changed_receipt r CROSS JOIN changed_invoice i RETURNING id
        ), revenue AS (
            INSERT INTO public.srm_revenue_events(organization_id,invoice_id,event_type,amount,currency,recognized_on)
            SELECT @org,id,'cash_collected',@amount,@currency,current_date FROM changed_invoice RETURNING id
        ), audit AS (
            INSERT INTO public.srm_audit_logs(organization_id,entity_type,entity_id,action,actor_user_id,after_json)
            SELECT @org,'receipt',id,'allocated',@actor,json_build_object('invoice_id',@invoice,'amount',@amount)
            FROM changed_receipt RETURNING id
        ), owned AS (
            INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
            SELECT 'srm_receipt_allocations',id::text,@org,@branch,'validated-write' FROM allocation
            UNION ALL SELECT 'srm_revenue_events',id::text,@org,@branch,'validated-write' FROM revenue
            UNION ALL SELECT 'srm_audit_logs',id::text,@org,@branch,'validated-write' FROM audit
        ) SELECT id FROM allocation",
            ("receipt",NpgsqlDbType.Integer,receipt),("invoice",NpgsqlDbType.Integer,invoice),("amount",NpgsqlDbType.Numeric,amount),
            ("request",NpgsqlDbType.Text,request),("actor",NpgsqlDbType.Integer,actor),("currency",NpgsqlDbType.Text,currency));
        if (await apply.ExecuteScalarAsync(cancellation) is not int)
            throw new InvalidOperationException("The invoice or advance amount changed before allocation.");
        return true;
    }

    private static string AppointmentAllocationKey(int appointment,int receipt,int invoice)
    {
        // Match Python uuid5(NAMESPACE_URL,...) across web and desktop.
        byte[] urlNamespace={0x6b,0xa7,0xb8,0x11,0x9d,0xad,0x11,0xd1,0x80,0xb4,0x00,0xc0,0x4f,0xd4,0x30,0xc8};
        byte[] label=Encoding.UTF8.GetBytes(FormattableString.Invariant($"appointment:{appointment}:receipt:{receipt}:invoice:{invoice}"));
        using var sha=SHA1.Create();
        byte[] hash=sha.ComputeHash(urlNamespace.Concat(label).ToArray());
        hash[6]=(byte)((hash[6]&0x0f)|0x50);
        hash[8]=(byte)((hash[8]&0x3f)|0x80);
        string hex=string.Concat(hash.Take(16).Select(value=>value.ToString("x2",CultureInfo.InvariantCulture)));
        return Guid.ParseExact(hex,"N").ToString();
    }
}
