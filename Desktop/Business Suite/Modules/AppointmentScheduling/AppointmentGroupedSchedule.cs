using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record GroupedScheduleVersion(int Occurrence,int Revision);
internal sealed record GroupedSchedulePreview(GroupedScheduleVersion Version,AppointmentSlot Slot,
    int Policy,int PolicyRevision,int Eligibility,int EligibilityRevision);

internal sealed partial class AppointmentRepository
{
    private async Task<GroupedScheduleVersion> ReadGroupedScheduleAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        AppointmentKey key,bool locked,CancellationToken cancellation)
    {
        // Prove the committed checkout graph without exposing charge fields through scheduling.
        using var query=Query(db,tx,@"SELECT occurrence.id,occurrence.revision,a.starts_at,occurrence.starts_at,occurrence.ends_at,
                occurrence.duration_minutes,occurrence.provider_resource_id,a.data::text
            FROM public.srm_industry_records a
            JOIN public.srm_pos_service_occurrences occurrence ON occurrence.appointment_id=a.id
            JOIN public.srm_pos_service_checkouts root ON root.id=occurrence.checkout_id
            JOIN public.srm_pos_checkout_lines charge ON charge.id=occurrence.checkout_line_id AND charge.checkout_id=root.id
            JOIN public.srm_sales_orders sales ON sales.id=root.sales_order_id
            JOIN public.srm_sales_order_lines sold ON sold.id=charge.sales_order_line_id AND sold.sales_order_id=sales.id
            JOIN public.srm_invoices invoice ON invoice.id=root.invoice_id AND invoice.sales_order_id=sales.id
            JOIN public.srm_invoice_lines billed ON billed.id=charge.invoice_line_id AND billed.invoice_id=invoice.id
            JOIN public.srm_industry_records provider ON provider.id=occurrence.provider_resource_id
            WHERE a.id=@id AND a.organization_id=@org AND a.branch_id=@branch AND a.kind='appointment' AND a.status='booked'
                AND a.invoice_id IS NULL AND a.project_id IS NULL AND NOT (a.data::jsonb ? 'pms_task_id')
                AND a.revision=@revision AND a.starts_at>clock_timestamp() AND a.starts_at=occurrence.starts_at AND a.ends_at=occurrence.ends_at
                AND a.customer_id=root.customer_id AND a.data->>'service_id'=occurrence.service_product_id::text
                AND occurrence.organization_id=@org AND occurrence.branch_id=@branch AND occurrence.scope_context_key=0
                AND root.organization_id=@org AND root.branch_id=@branch AND root.scope_context_key=0 AND root.pack_context_id IS NULL
                AND root.state='committed' AND root.committed_at IS NOT NULL
                AND charge.organization_id=@org AND charge.branch_id=@branch AND charge.scope_context_key=0
                AND charge.line_kind='booked_service' AND charge.product_id=occurrence.service_product_id
                AND sales.organization_id=@org AND sales.customer_id=root.customer_id AND sales.currency=root.currency
                AND invoice.organization_id=@org AND invoice.customer_id=root.customer_id AND invoice.currency=root.currency
                AND invoice.deleted_at IS NULL AND sold.product_id=charge.product_id
                AND billed.source_type='sales_order_line' AND billed.source_id=sold.id
                AND ROW(charge.quantity,charge.unit_price,charge.discount_amount,charge.tax_amount,charge.line_total)
                    =ROW(sold.quantity,sold.unit_price,sold.discount_amount,sold.tax_amount,sold.line_total)
                AND ROW(charge.quantity,charge.unit_price,charge.discount_amount,charge.tax_amount,charge.line_total)
                    =ROW(billed.quantity,billed.unit_price,billed.discount_amount,billed.tax_amount,billed.line_total)
                AND provider.organization_id=@org AND provider.branch_id=@branch AND provider.kind='resource'
                AND provider.data->>'employee_id'=occurrence.employee_id::text
                AND NOT EXISTS(SELECT 1 FROM (VALUES
                    ('srm_sales_orders',sales.id),('srm_sales_order_lines',sold.id),
                    ('srm_invoices',invoice.id),('srm_invoice_lines',billed.id)) native(resource,id)
                    WHERE NOT EXISTS(SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table=native.resource
                        AND o.resource_key=native.id::text AND o.company_id=@org AND o.branch_id=@branch))
                AND NOT EXISTS(SELECT 1 FROM (VALUES
                    ('srm_sales_orders',sales.id),('srm_sales_order_lines',sold.id),('srm_invoices',invoice.id),
                    ('srm_invoice_lines',billed.id),('srm_industry_records',a.id),('srm_industry_records',provider.id),
                    ('srm_pos_service_occurrences',occurrence.id),('srm_pos_service_checkouts',root.id),
                    ('srm_pos_checkout_lines',charge.id)) source(resource,id)
                    JOIN public.business_pack_record_ownership o ON o.resource_table=source.resource AND o.resource_key=source.id::text)"
            +(locked?" FOR UPDATE OF a,occurrence,root":""),
            ("id",NpgsqlDbType.Integer,key.Id),("revision",NpgsqlDbType.Integer,key.Revision));
        using var row=await query.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            throw new InvalidOperationException("The grouped service schedule changed or needs checkout reconciliation.");
        var data=JsonNode.Parse(row.GetString(7))!.AsObject();
        if (!DateTimeOffset.TryParse(data["starts_at"]?.ToString(),CultureInfo.InvariantCulture,DateTimeStyles.AssumeUniversal,out var start) ||
            start.UtcDateTime!=row.GetDateTime(3) || row.GetDateTime(2)!=row.GetDateTime(3) ||
            data["duration_minutes"]?.GetValue<int>()!=row.GetInt32(5) || !ReadIds(data).Contains(row.GetInt32(6)) ||
            row.GetDateTime(4)!=row.GetDateTime(3).AddMinutes(row.GetInt32(5)))
            throw new InvalidOperationException("The grouped appointment no longer matches its stored occurrence schedule.");
        return new(row.GetInt32(0),row.GetInt32(1));
    }

    private async Task<Booking> ValidateGroupedBookingAsync(NpgsqlConnection db,NpgsqlTransaction tx,Service service,
        AppointmentSlot slot,int appointment,CancellationToken cancellation)
    {
        var booking=await ValidateAsync(db,tx,service,slot,appointment,cancellation);
        using var scope=Query(db,tx,@"SELECT EXISTS (SELECT 1 FROM public.business_pack_record_ownership o WHERE
            (o.resource_table='srm_service_booking_policies' AND o.resource_key=@policy::text) OR
            (o.resource_table='srm_service_specialist_eligibility' AND o.resource_key=@eligibility::text))",
            ("policy",NpgsqlDbType.Integer,booking.Policy.Id),("eligibility",NpgsqlDbType.Integer,booking.Policy.Eligibility));
        if (await scope.ExecuteScalarAsync(cancellation) is true)
            throw new InvalidOperationException("The service scheduling policy belongs to an operational pack.");
        return booking;
    }

    internal async Task RescheduleGroupedAsync(AppointmentKey key,GroupedSchedulePreview preview,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await AuthorizeAsync(db,tx,"create",cancellation);
        var version=await ReadGroupedScheduleAsync(db,tx,key,true,cancellation);
        if (version!=preview.Version)
            throw new InvalidOperationException("The service occurrence changed. Reopen the schedule.");
        var current=await CurrentAsync(db,tx,key,true,cancellation);
        var slot=preview.Slot;
        var service=await ReadServiceAsync(db,tx,current.Data["service_id"]!.GetValue<int>(),cancellation);
        var booking=await ValidateGroupedBookingAsync(db,tx,service,slot,key.Id,cancellation);
        var policy=booking.Policy;
        if (policy.Id!=preview.Policy || policy.Revision!=preview.PolicyRevision ||
            policy.Eligibility!=preview.Eligibility || policy.EligibilityRevision!=preview.EligibilityRevision)
            throw new InvalidOperationException("Service policy or specialist eligibility changed. Check availability again.");

        current.Data["starts_at"]=booking.Start.ToString("o",CultureInfo.InvariantCulture);
        current.Data["duration_minutes"]=slot.Minutes;
        current.Data["resource_ids"]=JsonSerializer.SerializeToNode(new[]{slot.Provider}.Concat(slot.Extras));
        using var update=Query(db,tx,@"UPDATE public.srm_industry_records SET starts_at=@start,ends_at=@finish,
            data=@data,revision=revision+1,updated_at=now() WHERE id=@appointment AND organization_id=@org AND branch_id=@branch
                AND revision=@appointment_revision;
            UPDATE public.srm_pos_service_occurrences SET provider_resource_id=@provider,employee_id=@employee,
                starts_at=@start,ends_at=@finish,duration_minutes=@duration,booking_policy_id=@policy,policy_revision=@policy_revision,
                eligibility_id=@eligibility,eligibility_revision=@eligibility_revision,revision=revision+1,updated_at=now()
            WHERE id=@occurrence AND appointment_id=@appointment AND revision=@revision AND organization_id=@org AND branch_id=@branch",
            ("appointment",NpgsqlDbType.Integer,key.Id),("appointment_revision",NpgsqlDbType.Integer,key.Revision),
            ("occurrence",NpgsqlDbType.Integer,version.Occurrence),("revision",NpgsqlDbType.Integer,version.Revision),
            ("start",NpgsqlDbType.TimestampTz,booking.Start),("finish",NpgsqlDbType.TimestampTz,booking.End),
            ("duration",NpgsqlDbType.Integer,slot.Minutes),("provider",NpgsqlDbType.Integer,slot.Provider),
            ("employee",NpgsqlDbType.Integer,policy.Employee),("policy",NpgsqlDbType.Integer,policy.Id),
            ("policy_revision",NpgsqlDbType.Integer,policy.Revision),("eligibility",NpgsqlDbType.Integer,policy.Eligibility),
            ("eligibility_revision",NpgsqlDbType.Integer,policy.EligibilityRevision),("data",NpgsqlDbType.Json,current.Data.ToJsonString()));
        if (await update.ExecuteNonQueryAsync(cancellation)!=2)
            throw new InvalidOperationException("The appointment or service occurrence changed. Reopen the schedule.");
        await AuditAsync(db,tx,actor.Id,key.Id,"group_rescheduled",current.Status,key.Revision+1,current.Data,cancellation);
        await tx.CommitAsync(cancellation);
    }
}
